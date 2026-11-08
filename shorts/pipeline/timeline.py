"""Episode script -> voice audio + frame-exact timeline.json for the renderer."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np

from . import audio, avatar, tts
from .config import ANCHORS, BRAND, FPS, MAX_SECONDS, SR
from .schema import Episode

GAP = 0.18          # silence between speakers
INTRO_MIN = 2.8     # the intro graphics need a moment to land
TAIL = 0.15


def _segments(ep: Episode):
    order = list(ANCHORS)           # ["F", "M"]
    segs = [("intro", ep.intro.line, order[0], None)]
    for i, it in enumerate(ep.items):
        segs.append(("news", it.narration, order[(i + 1) % 2], i))
    segs.append(("outro", ep.outro.line, order[(len(ep.items) + 1) % 2], None))
    return segs


def _chunks(words, speaker, max_chars=15):
    """Group words into caption chunks (<= max_chars, broken at punctuation)."""
    out, cur, n = [], [], 0
    for w in words:
        L = len(w["w"])
        if cur and n + L > max_chars:
            out.append(cur); cur, n = [], 0
        cur.append(w); n += L
        if re.search(r"[.!?…]$", w["w"]) or (re.search(r",$", w["w"]) and n > 8):
            out.append(cur); cur, n = [], 0
    if cur:
        out.append(cur)
    return [{"start": c[0]["s"], "end": c[-1]["e"], "speaker": speaker, "words": c} for c in out]


def _synthetic_mouth(words, n_frames, offset):
    m = np.zeros(n_frames)
    for w in words:
        syl = max(1, len(re.sub(r"[^가-힣A-Za-z0-9]", "", w["w"])))
        f0, f1 = int((w["s"] + offset) * FPS), int((w["e"] + offset) * FPS)
        for f in range(f0, min(f1, n_frames)):
            ph = (f - f0) / max(1, f1 - f0) * syl
            m[f] = max(m[f], 0.25 + 0.75 * abs(np.sin(np.pi * ph)))
    return m


def build(ep: Episode, workdir: Path, use_tts: bool = True) -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    segs = _segments(ep)
    clips = []
    for k, (kind, text, spk, idx) in enumerate(segs):
        if use_tts:
            p = workdir / f"seg{k:02d}.mp3"
            words = tts.synth(text, ANCHORS[spk]["voice"], p)
            wav = audio.load_audio(p)
            # TTS clips carry ~0.5-1s of trailing silence: cut right after the last word
            end = min(len(wav) / SR, words[-1]["e"] + 0.12) if words else len(wav) / SR
            wav = wav[: int(end * SR)]
            fade = min(len(wav), int(0.03 * SR))
            wav[-fade:] *= np.linspace(1, 0, fade)
            dur = end
        else:
            words, wav = tts.estimate(text), None
            dur = words[-1]["e"] + 0.1
        clips.append({"kind": kind, "spk": spk, "idx": idx, "words": words, "wav": wav, "dur": dur})

    # fit into MAX_SECONDS by time-compressing speech if needed (max 1.2x)
    def lead(c):
        return 0.35 if c["kind"] == "news" else 0.25

    def fixed(cl):   # time that does not shrink with speech speed
        return sum(lead(c) + TAIL + GAP * 0.5 for c in cl) + 0.6

    def total(cl, sp=1.0):
        t = 0.0
        for c in cl:
            seg = c["dur"] / sp + lead(c)
            if c["kind"] == "intro":
                seg = max(seg, INTRO_MIN)
            if c["kind"] == "outro":
                seg = max(seg + TAIL, 2.6) - TAIL
            t += seg + TAIL + GAP * 0.5
        return t + 0.6

    target = MAX_SECONDS - 0.3
    speed = 1.0
    while total(clips, speed) > target and speed < 1.25:
        speed += 0.01
    if total(clips, speed) > target:
        raise RuntimeError(f"script too long: {total(clips, speed):.1f}s even at {speed:.2f}x — shorten narration")
    if speed > 1.0:
        for c in clips:
            c["dur"] /= speed
            for w in c["words"]:
                w["s"] /= speed; w["e"] /= speed
            if c["wav"] is not None:
                c["wav"] = _atempo(c["wav"], speed, workdir)

    # lay out on the timeline
    t, scenes, captions, voice_parts = 0.0, [], [], []
    for c in clips:
        start = t
        speak_at = start + (0.35 if c["kind"] == "news" else 0.25)   # let the transition land first
        for w in c["words"]:
            w["s"] += speak_at; w["e"] += speak_at
        seg_len = max(c["dur"] + (speak_at - start), INTRO_MIN if c["kind"] == "intro" else 0) + TAIL
        if c["kind"] == "outro":
            seg_len = max(seg_len, 2.6)
        c["speak_at"] = speak_at
        sc = {"type": c["kind"], "start": round(start, 3), "end": round(start + seg_len, 3), "speaker": c["spk"]}
        if c["kind"] == "intro":
            sc.update(title_lines=ep.intro.title_lines, sub=ep.intro.sub, teasers=ep.intro.teasers)
        elif c["kind"] == "news":
            it = ep.items[c["idx"]]
            sc.update(no=c["idx"] + 1, category=it.category, headline=it.headline, highlight=it.highlight,
                      viz=it.viz.model_dump(exclude_none=True), meme=it.meme.model_dump(exclude_none=True) if it.meme else None)
        else:
            sc.update(cta=ep.outro.cta)
        if avatar.enabled():
            k = len(scenes)
            seg_audio = workdir / f"seg{k:02d}_final.mp3"
            if c["wav"] is not None:
                audio.write_wav(workdir / "_seg.wav", c["wav"])
                subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(workdir / "_seg.wav"), "-b:a", "192k", str(seg_audio)], check=True)
            clip = avatar.make_clip(k, seg_audio, c["spk"], workdir)
            sc["clip"] = {"src": str(clip.relative_to(workdir)), "at": round(speak_at, 3), "dur": round(c["dur"], 3)}
        scenes.append(sc)
        captions += _chunks(c["words"], c["spk"])
        voice_parts.append((speak_at, c["wav"]))
        t = start + seg_len + GAP * 0.5
    duration = round(t + 0.6, 3)
    for i in range(len(scenes) - 1):
        scenes[i]["end"] = scenes[i + 1]["start"]
    scenes[-1]["end"] = duration

    n_frames = int(np.ceil(duration * FPS))
    # voice track + mouth envelopes
    mouth = {k: np.zeros(n_frames) for k in ANCHORS}
    voice = None
    if use_tts:
        voice = np.zeros(int(duration * SR) + SR)
        for (at, wav), c in zip(voice_parts, clips):
            p = int(at * SR)
            voice[p:p + len(wav)] += wav[: len(voice) - p]
            seg = np.zeros_like(voice); seg[p:p + len(wav)] = wav[: len(voice) - p]
            mouth[c["spk"]] = np.maximum(mouth[c["spk"]], audio.envelope(seg, FPS, n_frames))
    else:
        for c in clips:
            mouth[c["spk"]] = np.maximum(mouth[c["spk"]], _synthetic_mouth(c["words"], n_frames, 0))

    # sound design cues
    ev = [(0.0, "hit")]
    for sc in scenes:
        s = sc["start"]
        if sc["type"] != "intro":
            ev.append((s - 0.25, "whoosh"))
        if sc["type"] == "intro":
            ev += [(0.6 + i * 0.16, "pop") for i in range(len(sc.get("teasers", [])))]
        if sc["type"] == "news":
            ev.append((s + 0.12, "hit"))
            k = sc["viz"]["kind"]
            if k == "counter":
                ev.append((s + 0.75, "ticks"))
            if k == "stamp":
                ev.append((s + 0.95, "hit")); ev.append((s + 0.97, "ding"))
            if k == "versus":
                ev.append((s + 1.1, "hit"))
            if sc.get("meme"):
                d = sc["end"] - s
                ev.append((s + min(d * 0.55, d - 1.2), "pop"))
        if sc["type"] == "outro":
            ev.append((s + 1.2, "pop")); ev.append((s + 1.25, "ding"))
    mixed = audio.mix(duration, voice, ev)
    audio.write_wav(workdir / "mix.wav", mixed)

    a = {k: {"name": v["name"], "role": v["role"]} for k, v in ANCHORS.items()}
    tl = {"brand": BRAND, "date_label": ep.date_label, "fps": FPS, "duration": duration, "anchors": a,
          "scenes": scenes, "captions": captions,
          "mouth": {k: [round(float(x), 3) for x in v] for k, v in mouth.items()},
          "tts": use_tts, "live": avatar.enabled()}
    (workdir / "timeline.json").write_text(json.dumps(tl, ensure_ascii=False))
    return tl


def _atempo(wav, speed, workdir):
    src, dst = workdir / "_t_in.wav", workdir / "_t_out.wav"
    audio.write_wav(src, wav)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-filter:a", f"atempo={speed:.4f}", str(dst)], check=True)
    return audio.load_audio(dst)
