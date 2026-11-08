"""Korean meme knowledge base (data/memes.json) + weekly learning job.

Each entry: id, phrase, meaning, usage (when it fits a news story), tone, emoji, status
(hot | steady | fading | retired), sensitive (never use), first_seen, last_verified, sources.

`python -m pipeline.memes update` asks Claude (with web search) what Korean internet memes are
trending *right now*, merges them in and ages out entries nobody mentions any more.
The result is committed back to the repo by the weekly GitHub Action, so the channel's
"meme sense" keeps up without anyone hand-editing the file.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import date, timedelta
from typing import List, Literal, Optional

from pydantic import BaseModel

from .config import DATA, MODEL

DB = DATA / "memes.json"


class MemeEntry(BaseModel):
    id: str
    phrase: str
    meaning: str
    usage: str
    tone: str
    emoji: Optional[str] = None
    status: Literal["hot", "steady", "fading", "retired"] = "steady"
    sensitive: bool = False
    first_seen: Optional[str] = None
    last_verified: Optional[str] = None
    sources: List[str] = []


class MemeReport(BaseModel):
    trending: List[MemeEntry]
    still_alive_ids: List[str]
    dead_ids: List[str]


def load() -> list[dict]:
    return json.loads(DB.read_text())["memes"]


def save(memes: list[dict]):
    DB.write_text(json.dumps({"updated": date.today().isoformat(), "memes": memes}, ensure_ascii=False, indent=1) + "\n")


def usable_memes() -> list[dict]:
    """What the script writer is allowed to use today (hot first)."""
    order = {"hot": 0, "steady": 1, "fading": 2}
    ok = [m for m in load() if not m.get("sensitive") and m.get("status") in order]
    ok.sort(key=lambda m: order[m["status"]])
    return [{k: m.get(k) for k in ("id", "phrase", "meaning", "usage", "tone", "emoji", "status")} for m in ok]


PROMPT = """한국 인터넷 밈 트렌드 리서처로서 웹 검색으로 '지금(최근 2~3주)' 한국 온라인(유튜브 쇼츠, 인스타 릴스,
틱톡, X, 커뮤니티, 예능)에서 실제로 많이 쓰이는 밈/유행어를 조사해라.
오늘 날짜: {today}

조건:
- 뉴스 쇼츠 자막 스티커(12자 이내)로 쓸 수 있는 '문구형' 밈 위주. 특정 이미지·영상 저작물을 그대로 써야만 하는 밈은 제외.
- 혐오/비하/성적/특정 정치인·정당 조롱/실존 일반인 대상 밈은 sensitive=true로 표시.
- 각 밈마다 의미, 어떤 뉴스에 어울리는지(usage), 톤, 어울리는 이모지, 근거 URL(sources) 포함.
- status: 최근 급상승=hot, 꾸준히 쓰임=steady.
- 아래 기존 사전 중 아직 살아있는 id는 still_alive_ids에, 이제 안 쓰이는(촌스러워진) id는 dead_ids에 넣어라.

기존 사전:
{existing}

마지막에 반드시 아래 형식의 JSON 하나만 ```json 코드블록으로 출력:
{{"trending": [MemeEntry...], "still_alive_ids": [...], "dead_ids": [...]}}
MemeEntry = {{"id": "영문-kebab", "phrase", "meaning", "usage", "tone", "emoji", "status", "sensitive", "sources": [...]}}
"""


def research() -> MemeReport:
    import anthropic

    client = anthropic.Anthropic()
    existing = [{k: m[k] for k in ("id", "phrase", "status")} for m in load()]
    msgs = [{"role": "user", "content": PROMPT.format(today=date.today().isoformat(), existing=json.dumps(existing, ensure_ascii=False))}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 12,
              "user_location": {"type": "approximate", "country": "KR", "timezone": "Asia/Seoul"}}]
    for _ in range(4):   # server tools may pause long turns; continue until finished
        resp = client.messages.create(model=MODEL, max_tokens=32000, messages=msgs, tools=tools,
                                      output_config={"effort": "high"})
        if resp.stop_reason != "pause_turn":
            break
        msgs = msgs + [{"role": "assistant", "content": resp.content}]
    if resp.stop_reason == "refusal":
        raise RuntimeError("meme research refused")
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"```json\s*(\{.*\})\s*```", text, re.S)
    if not m:
        raise RuntimeError("no JSON in meme research output")
    return MemeReport.model_validate_json(m.group(1))


def merge(memes: list[dict], rep: MemeReport, today: date | None = None) -> list[dict]:
    today = today or date.today()
    by = {m["id"]: m for m in memes}
    for e in rep.trending:
        d = e.model_dump()
        if e.id in by:
            old = by[e.id]
            old.update({k: v for k, v in d.items() if v and k not in ("first_seen",)})
            old["last_verified"] = today.isoformat()
        else:
            d["first_seen"] = d["last_verified"] = today.isoformat()
            by[e.id] = d
    for i in rep.still_alive_ids:
        if i in by:
            by[i]["last_verified"] = today.isoformat()
    for i in rep.dead_ids:
        if i in by:
            by[i]["status"] = "retired"
    # ageing: hot -> steady after 3 weeks unverified, -> fading after 8, -> retired after 16
    for m in by.values():
        lv = date.fromisoformat(m.get("last_verified") or today.isoformat())
        age = (today - lv).days
        if m["status"] == "hot" and age > 21:
            m["status"] = "steady"
        if m["status"] == "steady" and age > 56:
            m["status"] = "fading"
        if m["status"] == "fading" and age > 112:
            m["status"] = "retired"
    return sorted(by.values(), key=lambda m: ({"hot": 0, "steady": 1, "fading": 2, "retired": 3}[m["status"]], m["id"]))


if __name__ == "__main__":
    if sys.argv[1:] == ["update"]:
        memes = merge(load(), research())
        save(memes)
        print(f"[memes] {sum(m['status'] == 'hot' for m in memes)} hot / {len(memes)} total")
    else:
        print(json.dumps(usable_memes(), ensure_ascii=False, indent=1))
