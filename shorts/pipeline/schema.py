"""Data model for one episode script (what the LLM writes) — validated with pydantic."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Side(BaseModel):
    label: str
    value: Optional[str] = None


class RankItem(BaseModel):
    label: str
    value: Optional[str] = None


class Viz(BaseModel):
    """One graphic per story. Numbers MUST come from the source article (checked in factcheck.py)."""
    kind: Literal["counter", "versus", "ranking", "stamp", "keyword"]
    # counter
    label: Optional[str] = None
    value: Optional[float] = None
    decimals: Optional[int] = None
    unit: Optional[str] = None
    delta: Optional[str] = None
    direction: Optional[Literal["up", "down", "flat"]] = None
    # versus
    left: Optional[Side] = None
    right: Optional[Side] = None
    # ranking
    items: Optional[List[RankItem]] = None
    # stamp / keyword
    text: Optional[str] = None
    sub: Optional[str] = None
    emoji: Optional[str] = None


class Meme(BaseModel):
    id: Optional[str] = Field(None, description="memes.json id this caption is based on")
    text: str = Field(..., description="sticker caption, max ~12 chars")
    emoji: Optional[str] = None


class Item(BaseModel):
    category: Literal["경제", "증시", "정치", "사회", "국제", "IT", "과학", "스포츠", "생활", "날씨", "문화"]
    headline: str = Field(..., description="on-screen headline, max ~16 chars, 2-4 words")
    highlight: Optional[str] = Field(None, description="one word of the headline to highlight")
    narration: str = Field(..., description="spoken line, 45-75 Korean characters")
    viz: Viz
    meme: Optional[Meme] = None
    source_ids: List[str] = Field(default_factory=list)


class Intro(BaseModel):
    line: str
    title_lines: List[str]
    sub: str
    teasers: List[str]


class Outro(BaseModel):
    line: str
    cta: str


class YouTubeMeta(BaseModel):
    title: str
    description: str
    tags: List[str]


class Episode(BaseModel):
    date_label: str
    intro: Intro
    items: List[Item]
    outro: Outro
    youtube: YouTubeMeta
