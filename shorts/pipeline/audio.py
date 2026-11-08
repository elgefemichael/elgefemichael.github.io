"""Procedural audio: original BGM + SFX synthesised with numpy (no licensing issues), and the final mix."""
from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import numpy as np
from scipy.signal import lfilter

from .config import SR

rng = np.random.default_rng(42)


def _t(sec):
    return np.arange(int(sec * SR)) / SR


def _env(n, a=0.005, r=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / r)


def _lp(x, alpha):
    """one-pole low-pass"""
    return lfilter([alpha], [1, alpha - 1], x)


def whoosh(d=0.45):
    n = int(d * SR)
    noise = rng.standard_normal(n)
    # band sweep: mix of two low-pass filtered versions, crossfaded
    lo, hi = _lp(noise, 0.02), noise - _lp(noise, 0.15)
    k = np.linspace(0, 1, n)
    x = lo * (1 - k) * 3 + hi * k * 0.6
    env = np.sin(np.pi * k) ** 1.5
    return x * env * 0.35


def hit(d=0.6):
    t = _t(d)
    f = 120 * np.exp(-t * 18) + 45
    boom = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 6)
    crack = rng.standard_normal(len(t)) * np.exp(-t * 40) * 0.5
    return (boom * 0.9 + crack) * 0.6


def pop(d=0.18):
    t = _t(d)
    f = 500 + 1400 * np.exp(-t * 30)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 22) * 0.45


def ding(d=0.9):
    t = _t(d)
    x = sum(np.sin(2 * np.pi * f * t) * a for f, a in [(1318.5, 1), (1975.5, .5), (2637, .25)])
    return x * np.exp(-t * 4) * 0.22


def ticks(d=1.2, n=14):
    out = np.zeros(int(d * SR))
    for i in range(n):
        p = int(d * SR * (1 - (1 - i / n) ** 2) * 0.95)
        c = np.sin(2 * np.pi * 2200 * _t(0.02)) * np.exp(-_t(0.02) * 300) * 0.25
        out[p:p + len(c)] += c[: len(out) - p]
    return out


def bgm(duration, bpm=124):
    """Driving news-bed: four-on-the-floor kick, offbeat hats, synth bass arpeggio, pad stabs."""
    n = int(duration * SR)
    out = np.zeros(n)
    beat = 60 / bpm
    kick = (lambda t: np.sin(2 * np.pi * np.cumsum(55 + 110 * np.exp(-t * 35)) / SR) * np.exp(-t * 9))(_t(0.35))
    hat = rng.standard_normal(int(0.05 * SR))
    hat = (hat - _lp(hat, 0.3)) * np.exp(-_t(0.05) * 90) * 0.18
    chords = [(45, 52, 57), (41, 48, 53), (43, 50, 55), (40, 47, 52)]  # Am F G Em (midi)
    mtof = lambda m: 440 * 2 ** ((m - 69) / 12)
    i = 0
    while True:
        t0 = i * beat / 2           # 8th notes
        p = int(t0 * SR)
        if p >= n:
            break
        bar = int(t0 / (beat * 4)) % 4
        if i % 2 == 0:
            seg = kick[: n - p]
            out[p:p + len(seg)] += seg * 0.55
        else:
            seg = hat[: n - p]
            out[p:p + len(seg)] += seg
        # bass arpeggio on 8ths
        root = chords[bar][0] - 12
        note = root + [0, 12, 7, 12][i % 4]
        tt = _t(beat / 2)
        bass = np.sign(np.sin(2 * np.pi * mtof(note) * tt)) * 0.5 + np.sin(2 * np.pi * mtof(note) * tt)
        bass = _lp(bass * np.exp(-tt * 6), 0.08) * 0.32
        seg = bass[: n - p]
        out[p:p + len(seg)] += seg
        # pad stab at bar start
        if i % 8 == 0:
            tt = _t(beat * 1.5)
            pad = sum(np.sin(2 * np.pi * mtof(m + 12) * tt) + 0.5 * np.sin(2 * np.pi * mtof(m + 24) * tt * 1.003) for m in chords[bar])
            pad *= np.minimum(1, tt / 0.01) * np.exp(-tt * 2.5) * 0.06
            seg = pad[: n - p]
            out[p:p + len(seg)] += seg
        i += 1
    # fade in/out
    f = int(0.3 * SR)
    out[:f] *= np.linspace(0, 1, f)
    out[-int(0.8 * SR):] *= np.linspace(1, 0, int(0.8 * SR))
    return out


def load_audio(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
                         check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).astype(np.float64)


def write_wav(path: Path, x: np.ndarray):
    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def envelope(x: np.ndarray, fps: int, n_frames: int) -> np.ndarray:
    """Per-video-frame loudness 0..1 used to drive the anchors' mouths."""
    hop = SR // fps
    out = np.zeros(n_frames)
    for f in range(n_frames):
        seg = x[f * hop:(f + 1) * hop]
        if len(seg):
            out[f] = np.sqrt(np.mean(seg ** 2))
    if out.max() > 0:
        out = out / np.percentile(out[out > 0], 95)
    return np.clip(out, 0, 1) ** 0.7


def mix(duration, voice: np.ndarray | None, events: list[tuple[float, str]]) -> np.ndarray:
    n = int(duration * SR)
    v = np.zeros(n)
    if voice is not None:
        v[: min(n, len(voice))] = voice[:n]
    music = bgm(duration)
    # side-chain duck the music under the voice
    if voice is not None:
        blk = 480
        pad = np.pad(np.abs(v), (0, (-n) % blk))
        env = _lp(pad.reshape(-1, blk).max(axis=1).repeat(blk)[:n], 0.0008)
        duck = 1 - 0.6 * np.clip(env * 6, 0, 1)
    else:
        duck = np.full(n, 0.8)
    sfx = np.zeros(n)
    bank = {"whoosh": whoosh(), "hit": hit(), "pop": pop(), "ding": ding(), "ticks": ticks()}
    for t, kind in events:
        s = bank[kind]
        p = max(0, int(t * SR))
        if p >= n:
            continue
        seg = s[: n - p]
        sfx[p:p + len(seg)] += seg
    out = v * 1.0 + music * 0.33 * duck + sfx * 0.7
    peak = np.max(np.abs(out)) or 1
    return out / peak * 0.92
