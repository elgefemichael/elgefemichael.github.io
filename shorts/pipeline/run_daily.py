"""Daily orchestrator:  collect -> script -> TTS/timeline -> render -> (upload)

  python -m pipeline.run_daily                       # full run (needs ANTHROPIC_API_KEY, YT_* secrets)
  python -m pipeline.run_daily --no-upload           # make the video only
  python -m pipeline.run_daily --episode samples/demo_episode.json --no-upload   # render a given script
  python -m pipeline.run_daily --episode ... --no-tts --no-upload               # offline preview (silent voice)
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import collect, timeline, write_script
from .config import RENDERER, RUNS
from .schema import Episode

KST = timezone(timedelta(hours=9))


def render(workdir: Path) -> Path:
    silent = workdir / "video_silent.mp4"
    subprocess.run(["node", str(RENDERER / "render.mjs"), str(workdir / "timeline.json"), str(silent)], check=True)
    final = workdir / "short.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(silent), "-i", str(workdir / "mix.wav"),
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(final)], check=True)
    return final


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", help="skip collect+script and use this episode JSON")
    ap.add_argument("--no-tts", action="store_true")
    ap.add_argument("--no-upload", action="store_true")
    ap.add_argument("--out", help="working directory")
    a = ap.parse_args()

    now = datetime.now(KST)
    workdir = Path(a.out) if a.out else RUNS / now.strftime("%Y-%m-%d")
    workdir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    if a.episode:
        ep = Episode.model_validate_json(Path(a.episode).read_text())
    else:
        news = collect.run(workdir)
        ep = write_script.write(news, workdir, now)
    print(f"[script] {[i.headline for i in ep.items]}")

    tl = timeline.build(ep, workdir, use_tts=not a.no_tts)
    print(f"[timeline] {tl['duration']:.1f}s, {len(tl['scenes'])} scenes")
    video = render(workdir)
    print(f"[render] {video}  ({time.time() - t0:.0f}s total)")

    if not a.no_upload:
        from .upload import upload
        vid = upload(video, ep, now)
        (workdir / "youtube.json").write_text(json.dumps({"id": vid}))


if __name__ == "__main__":
    main()
