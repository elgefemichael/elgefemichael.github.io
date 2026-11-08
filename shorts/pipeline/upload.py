"""Step 5 — upload to YouTube (Data API v3, OAuth refresh token).

Default: uploaded as private with publishAt = 07:00 KST, so there is a ~2h window to watch it on the
phone and delete it if anything is wrong. Set YT_PUBLISH_AT_KST="" to publish immediately (YT_PRIVACY=public).

Required env (GitHub secrets): YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
Get the refresh token once with:  python -m pipeline.upload auth  client_secret.json
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import YT_CATEGORY_ID, YT_PRIVACY, YT_PUBLISH_AT_KST
from .schema import Episode

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
KST = timezone(timedelta(hours=9))


def _creds():
    from google.oauth2.credentials import Credentials

    return Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
                       client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"], scopes=SCOPES)


def upload(video: Path, ep: Episode, now: datetime | None = None) -> str:
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    now = now or datetime.now(KST)
    status = {"privacyStatus": YT_PRIVACY, "selfDeclaredMadeForKids": False,
              "containsSyntheticMedia": True}     # AI anchors + AI voice -> disclose
    if YT_PUBLISH_AT_KST:
        hh, mm = map(int, YT_PUBLISH_AT_KST.split(":"))
        at = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        if at > now + timedelta(minutes=15):
            status.update(privacyStatus="private", publishAt=at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"))
    title = ep.youtube.title if "#shorts" in ep.youtube.title.lower() else ep.youtube.title + " #Shorts"
    body = {
        "snippet": {"title": title[:100], "description": ep.youtube.description[:4900],
                    "tags": ep.youtube.tags[:15], "categoryId": YT_CATEGORY_ID,
                    "defaultLanguage": "ko", "defaultAudioLanguage": "ko"},
        "status": status,
    }
    yt = build("youtube", "v3", credentials=_creds(), cache_discovery=False)
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(str(video), mimetype="video/mp4", resumable=True, chunksize=8 << 20))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    vid = resp["id"]
    print(f"[upload] https://youtube.com/shorts/{vid}  status={status}")
    return vid


def auth(client_secret_json: str):
    """One-time, on your own computer: opens a browser, prints the refresh token to store as a secret."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_json, SCOPES)
    cred = flow.run_local_server(port=0, access_type="offline", prompt="consent")
    print("YT_REFRESH_TOKEN =", cred.refresh_token)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "auth":
        auth(sys.argv[2])
    else:
        print(__doc__)
