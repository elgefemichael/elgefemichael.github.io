"""Realistic (live-action-looking) anchors.

For every spoken segment we need a short clip of the anchor saying exactly that audio, on a
solid green background. The clip is chroma-keyed here into a VP9 webm with alpha, and the renderer
composites it into the virtual studio (big "studio shot" first, then a hard cut to the graphics
with the anchor in the corner — the way real news cuts, which also hides avatar artifacts).

AVATAR_PROVIDER
  none    cartoon anchors (default, no extra cost)
  heygen  HeyGen API: our TTS audio -> lip-synced avatar video (needs HEYGEN_API_KEY,
          HEYGEN_AVATAR_F / HEYGEN_AVATAR_M = avatar ids, e.g. your own custom/photo avatars)
  dir     pre-made clips: AVATAR_DIR/segNN.mp4 (green background). Use this to plug in any other
          service (Hedra, Captions, Synthesia, ...) or real recorded footage.

Why our own audio instead of the provider's voice: the timeline (captions, cuts, graphics) is
built from our audio, so the avatar must follow it frame-for-frame.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

PROVIDER = os.getenv("AVATAR_PROVIDER", "none")
KEY_COLOR = os.getenv("AVATAR_KEY_COLOR", "0x00FF00")
# crop of the provider frame to keep (fractions x,y,w,h). Portrait avatar videos usually have
# head+torso in the upper ~75%.
CROP = [float(x) for x in os.getenv("AVATAR_CROP", "0,0.04,1,0.78").split(",")]


def enabled() -> bool:
    return PROVIDER != "none"


def make_clip(seg_index: int, audio_path: Path, speaker: str, workdir: Path) -> Path:
    """Returns path of keyed webm (alpha) for this segment."""
    raw = workdir / "avatar" / f"seg{seg_index:02d}.mp4"
    raw.parent.mkdir(parents=True, exist_ok=True)
    if PROVIDER == "heygen":
        if not raw.exists():
            _heygen(audio_path, speaker, raw)
    elif PROVIDER == "dir":
        src = Path(os.environ["AVATAR_DIR"]) / f"seg{seg_index:02d}.mp4"
        raw = src
    else:
        raise ValueError(PROVIDER)
    out = workdir / "clips" / f"seg{seg_index:02d}.webm"
    out.parent.mkdir(parents=True, exist_ok=True)
    key(raw, out)
    return out


def key(src: Path, dst: Path, width: int = 720):
    x, y, w, h = CROP
    vf = (f"crop=iw*{w}:ih*{h}:iw*{x}:ih*{y},"
          f"chromakey={KEY_COLOR}:0.16:0.08,despill=type=green:mix=0.6:expand=0.1,"
          f"scale={width}:-2,format=yuva420p")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", vf, "-an", "-r", "30",
                    "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "3M", "-auto-alt-ref", "0",
                    "-deadline", "good", "-cpu-used", "4", str(dst)], check=True)


# ---------------- HeyGen ----------------
# NOTE: written against HeyGen's v2 API as publicly documented; the docs could not be fetched from
# the build environment, so verify endpoints/field names on the first run (errors are printed raw).
API = "https://api.heygen.com"
UPLOAD = "https://upload.heygen.com/v1/asset"


def _req(method, url, body=None, headers=None, raw=None):
    h = {"X-Api-Key": os.environ["HEYGEN_API_KEY"], "Accept": "application/json"}
    h.update(headers or {})
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    if body is not None:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HeyGen {method} {url} -> {e.code}: {e.read()[:800]!r}") from None


def _heygen(audio: Path, speaker: str, out: Path):
    avatar_id = os.environ[f"HEYGEN_AVATAR_{speaker}"]
    asset = _req("POST", UPLOAD, raw=audio.read_bytes(), headers={"Content-Type": "audio/mpeg"})
    asset_id = asset["data"]["id"]
    style = os.getenv("HEYGEN_AVATAR_STYLE", "normal")
    gen = _req("POST", f"{API}/v2/video/generate", body={
        "video_inputs": [{
            "character": {"type": os.getenv("HEYGEN_CHARACTER_TYPE", "avatar"), "avatar_id": avatar_id, "avatar_style": style},
            "voice": {"type": "audio", "audio_asset_id": asset_id},
            "background": {"type": "color", "value": "#00FF00"},
        }],
        "dimension": {"width": 720, "height": 1280},
    })
    vid = gen["data"]["video_id"]
    print(f"[avatar] heygen video {vid} for {audio.name}")
    deadline = time.time() + 20 * 60
    while time.time() < deadline:
        st = _req("GET", f"{API}/v1/video_status.get?video_id={vid}")["data"]
        if st.get("status") == "completed":
            urllib.request.urlretrieve(st["video_url"], out)
            return
        if st.get("status") == "failed":
            raise RuntimeError(f"HeyGen render failed: {st.get('error')}")
        time.sleep(10)
    raise TimeoutError("HeyGen render timed out")
