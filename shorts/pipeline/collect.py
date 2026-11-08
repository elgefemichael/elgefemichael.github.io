"""Step 1 — collect last night's top news from Korean RSS feeds.

Stories reported by several outlets are clustered together; the number of outlets covering a story
is the main "importance" signal handed to the script writer.
"""
from __future__ import annotations

import calendar
import html
import json
import re
import time
import urllib.request
from pathlib import Path

import feedparser

from .config import FEEDS, NEWS_WINDOW_HOURS

UA = "Mozilla/5.0 (compatible; morning30-news-bot/1.0)"


def _clean(s: str) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    return re.sub(r"\s+", " ", s).strip()


def _bigrams(s: str) -> set:
    s = re.sub(r"[^가-힣A-Za-z0-9]", "", s)
    return {s[i:i + 2] for i in range(len(s) - 1)}


def fetch_all() -> list[dict]:
    cutoff = time.time() - NEWS_WINDOW_HOURS * 3600
    items = []
    for name, url in FEEDS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            raw = urllib.request.urlopen(req, timeout=20).read()
            feed = feedparser.parse(raw)
        except Exception as e:  # one dead feed must never kill the run
            print(f"[collect] {name}: {e}")
            continue
        for en in feed.entries:
            ts = en.get("published_parsed") or en.get("updated_parsed")
            ts = calendar.timegm(ts) if ts else time.time()
            if ts < cutoff:
                continue
            title = _clean(en.get("title", ""))
            title = re.sub(r"\s+-\s+[^-]+$", "", title) if "news.google" in url else title  # strip " - 언론사"
            if len(title) < 8:
                continue
            items.append({"source": name, "title": title, "summary": _clean(en.get("summary", ""))[:500],
                          "link": en.get("link", ""), "ts": ts})
        print(f"[collect] {name}: ok")
    return items


def cluster(items: list[dict], thr: float = 0.33) -> list[dict]:
    clusters: list[dict] = []
    for it in sorted(items, key=lambda x: -x["ts"]):
        bg = _bigrams(it["title"])
        best, score = None, 0.0
        for c in clusters:
            j = len(bg & c["bg"]) / max(1, len(bg | c["bg"]))
            if j > score:
                best, score = c, j
        if best is not None and score >= thr:
            best["items"].append(it)
            best["bg"] |= bg
        else:
            clusters.append({"bg": set(bg), "items": [it]})
    out = []
    for i, c in enumerate(clusters):
        srcs = {x["source"].split()[0] for x in c["items"]}
        rep = max(c["items"], key=lambda x: len(x["summary"]))
        out.append({
            "id": f"n{i:03d}",
            "title": c["items"][0]["title"],
            "alt_titles": list({x["title"] for x in c["items"][1:4]}),
            "summary": rep["summary"],
            "facts_text": " ".join({x["title"] + " " + x["summary"] for x in c["items"]})[:2000],
            "links": [x["link"] for x in c["items"][:3]],
            "outlets": len(srcs),
            "latest": max(x["ts"] for x in c["items"]),
        })
    out.sort(key=lambda c: (-c["outlets"], -c["latest"]))
    return out


def run(workdir: Path, top: int = 30) -> list[dict]:
    news = cluster(fetch_all())[:top]
    if not news:
        raise RuntimeError("no news collected — all feeds failed?")
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "news.json").write_text(json.dumps(news, ensure_ascii=False, indent=1))
    print(f"[collect] {len(news)} story clusters")
    return news
