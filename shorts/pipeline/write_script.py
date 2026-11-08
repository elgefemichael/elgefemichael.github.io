"""Step 2 — Claude picks the stories and writes a ≤30s two-anchor script with graphics + memes."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic

from .config import DATA, MAX_SECONDS, MODEL
from .memes import usable_memes
from .schema import Episode

KST = timezone(timedelta(hours=9))
WD = "월화수목금토일"

SYSTEM = """너는 유튜브 쇼츠 '모닝 30'의 메인 작가다. 매일 아침 30초 안에 밤사이 핵심 뉴스를
두 명의 가상 앵커(하루=여, 도윤=남)가 번갈아 전하는, 선거 개표방송처럼 박진감 넘치는 뉴스 쇼츠를 쓴다.

{style_guide}

## 출력 규칙 (반드시 지킬 것)
- items는 3~4개. 첫 번째 아이템이 가장 '와 진짜?' 반응이 나올 뉴스여야 한다(훅).
- intro.line + 모든 narration + outro.line 의 한글 글자 수 합계가 {max_chars}자 이하.
- 각 narration은 25~45자, 한두 문장, 구어체. 앵커 이름/인사 반복 금지.
- headline은 16자 이내, 2~4어절. highlight는 headline 안에 실제로 있는 한 어절.
- viz의 숫자(value, delta, versus/ranking의 value)는 반드시 해당 뉴스의 facts_text에 그대로 나오는 숫자만 쓴다.
  숫자가 없으면 kind=stamp(짧은 2~4자 도장 문구) 또는 kind=keyword(이모지+짧은 문구)를 쓴다. 숫자를 지어내면 안 된다.
- meme은 아래 밈 사전에 있는 것만, 뉴스 톤에 맞을 때만 쓴다. 사건·사고·사망·재난·범죄 피해·혐오 관련 뉴스엔 meme=null.
  정치 뉴스엔 특정 진영을 조롱하는 밈 금지. 밈은 3개 아이템 중 최대 2~3개, 같은 밈 반복 금지.
- source_ids에 근거로 쓴 뉴스 id를 넣는다.
- youtube.title은 40자 이내, 가장 센 뉴스 키워드 + '#Shorts'. description엔 뉴스 3~4줄 요약과 'AI 가상 앵커가 진행합니다' 고지.
"""


def _date_label(now: datetime) -> str:
    return f"{now:%m.%d} ({WD[now.weekday()]})"


def _prompt(news: list[dict], now: datetime) -> str:
    memes = usable_memes()
    slim = [{k: n[k] for k in ("id", "title", "alt_titles", "facts_text", "outlets")} for n in news]
    return (
        f"오늘은 {now:%Y년 %m월 %d일} {WD[now.weekday()]}요일 아침이다. date_label은 '{_date_label(now)}'로 써라.\n"
        f"intro.title_lines는 ['{now.month}월 {now.day}일', '아침 30초 ⚡'] 같은 2줄.\n\n"
        f"## 밈 사전 (현재 사용 가능)\n{json.dumps(memes, ensure_ascii=False)}\n\n"
        f"## 밤사이 뉴스 (outlets = 보도한 언론사 수, 클수록 중요)\n{json.dumps(slim, ensure_ascii=False)}"
    )


def _call(client, **kw):
    """Opus with server-side refusal fallback enabled; retried without it if the account lacks the beta."""
    try:
        return client.messages.parse(**kw, extra_headers={"anthropic-beta": "server-side-fallback-2026-07-01"},
                                     extra_body={"fallbacks": "default"})
    except anthropic.BadRequestError:
        return client.messages.parse(**kw)


def write(news: list[dict], workdir: Path, now: datetime | None = None, attempts: int = 3) -> Episode:
    now = now or datetime.now(KST)
    style = (DATA / "style_guide.md").read_text()
    max_chars = int((MAX_SECONDS - 6) * 7.3)   # ~7.3 syllables/sec at our TTS pace
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": _prompt(news, now)}]
    by_id = {n["id"]: n for n in news}
    for i in range(attempts):
        resp = _call(client, model=MODEL, max_tokens=16000,
                     system=SYSTEM.format(style_guide=style, max_chars=max_chars),
                     output_config={"effort": "high"}, messages=messages, output_format=Episode)
        if resp.stop_reason == "refusal" or resp.parsed_output is None:
            raise RuntimeError(f"script generation failed: {resp.stop_reason}")
        ep: Episode = resp.parsed_output
        problems = check(ep, by_id, max_chars)
        if not problems:
            break
        print(f"[script] attempt {i + 1} problems: {problems}")
        messages += [{"role": "assistant", "content": ep.model_dump_json()},
                     {"role": "user", "content": "다음 문제를 고쳐서 전체를 다시 써라:\n- " + "\n- ".join(problems)}]
    ep = enforce(ep, by_id)
    workdir.mkdir(parents=True, exist_ok=True)
    (workdir / "episode.json").write_text(ep.model_dump_json(indent=1))
    return ep


# ---------------- fact & length checks ----------------
def _nums(s) -> list[str]:
    return [x.replace(",", "") for x in re.findall(r"\d[\d,]*\.?\d*", str(s or ""))]


def _viz_numbers(v) -> list[str]:
    out = []
    if v.kind == "counter":
        if v.value is not None:
            out.append(f"{v.value:.{v.decimals or 0}f}".rstrip("0").rstrip(".") if v.decimals else str(int(v.value)))
        out += _nums(v.delta)
    if v.kind == "versus":
        out += _nums(v.left.value if v.left else "") + _nums(v.right.value if v.right else "")
    if v.kind == "ranking":
        for it in v.items or []:
            out += _nums(it.value)
    return [n for n in out if n]


def _unsupported(item, by_id) -> list[str]:
    text = " ".join(by_id[s]["facts_text"] for s in item.source_ids if s in by_id).replace(",", "")
    return [n for n in _viz_numbers(item.viz) if n not in text]


def check(ep: Episode, by_id: dict, max_chars: int) -> list[str]:
    probs = []
    spoken = ep.intro.line + "".join(i.narration for i in ep.items) + ep.outro.line
    n = len(re.sub(r"[^가-힣A-Za-z0-9]", "", spoken))
    if n > max_chars:
        probs.append(f"대사 총 {n}자 → {max_chars}자 이하로 줄일 것")
    if not 3 <= len(ep.items) <= 4:
        probs.append("items는 3~4개")
    for k, it in enumerate(ep.items):
        bad = _unsupported(it, by_id)
        if bad:
            probs.append(f"items[{k}] viz 숫자 {bad} 가 원문에 없음 → 원문 숫자를 쓰거나 stamp/keyword로")
        if it.highlight and it.highlight not in it.headline:
            probs.append(f"items[{k}] highlight가 headline에 없음")
        if len(it.headline) > 18:
            probs.append(f"items[{k}] headline 18자 초과")
    return probs


def enforce(ep: Episode, by_id: dict) -> Episode:
    """Last line of defence: any graphic with a number we cannot find in the source becomes a keyword card."""
    from .schema import Viz
    for it in ep.items:
        if _unsupported(it, by_id):
            print(f"[factcheck] downgraded viz for: {it.headline}")
            it.viz = Viz(kind="keyword", emoji="📰", text=it.headline)
    return ep
