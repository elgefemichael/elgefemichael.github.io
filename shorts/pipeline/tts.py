"""Korean TTS with word timings.

Default engine: Microsoft Edge neural voices via `edge-tts` (free, decent Korean, gives word boundaries).
For a more natural "real anchor" voice, plug in a commercial Korean TTS (e.g. Typecast, Supertone,
ElevenLabs) by adding a function with the same signature and selecting it with TTS_ENGINE.
"""
from __future__ import annotations

import asyncio
import os
import re
from pathlib import Path

from .config import TTS_PITCH, TTS_RATE

ENGINE = os.getenv("TTS_ENGINE", "edge")


async def _edge(text: str, voice: str, out: Path):
    import edge_tts

    kw = {"rate": TTS_RATE, "pitch": TTS_PITCH, "boundary": "WordBoundary"}
    if os.getenv("HTTPS_PROXY"):
        kw["proxy"] = os.environ["HTTPS_PROXY"]
    com = edge_tts.Communicate(text, voice, **kw)
    words = []
    with open(out, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                words.append({"w": ch["text"], "s": s, "e": s + ch["duration"] / 1e7})
    return words


def synth(text: str, voice: str, out: Path) -> list[dict]:
    """Writes audio to `out` and returns word timings [{w, s, e}] relative to the clip start."""
    if ENGINE == "edge":
        words = asyncio.run(_edge(text, voice, out))
    else:
        raise ValueError(f"unknown TTS_ENGINE {ENGINE}")
    return align_to_text(text, words)


def align_to_text(text: str, words: list[dict]) -> list[dict]:
    """Edge returns boundaries without punctuation; re-attach the original tokens (with punctuation)
    so captions read naturally."""
    toks = text.split()
    if not words:
        return estimate(text)
    out, wi = [], 0
    for tok in toks:
        core = re.sub(r"[^\w%.,]", "", tok)
        # consume boundary words until we've covered this token
        start, end, acc = None, None, ""
        while wi < len(words) and len(acc) < len(re.sub(r"[^\w]", "", core)):
            w = words[wi]
            start = w["s"] if start is None else start
            end = w["e"]
            acc += re.sub(r"[^\w]", "", w["w"])
            wi += 1
        if start is None:   # boundary list exhausted -> extrapolate
            start = out[-1]["e"] if out else 0
            end = start + 0.12 * max(1, len(core))
        out.append({"w": tok, "s": start, "e": end})
    return out


def estimate(text: str, sps: float = 7.6) -> list[dict]:
    """Fallback timings when no TTS is available (offline preview): ~7.6 syllables/sec."""
    t, out = 0.0, []
    for tok in text.split():
        syl = len(re.sub(r"[^가-힣A-Za-z0-9]", "", tok)) or 1
        d = syl / sps
        out.append({"w": tok, "s": t, "e": t + d})
        t += d + (0.22 if re.search(r"[.,!?…]$", tok) else 0.04)
    return out
