"""Channel-wide settings. Override anything with environment variables."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent          # shorts/
DATA = ROOT / "data"
RUNS = ROOT / "runs"                                    # per-day working dirs (git-ignored)
RENDERER = ROOT / "renderer"

BRAND = os.getenv("SHORTS_BRAND", "모닝 30")
FPS = 30
MAX_SECONDS = 30.0            # hard cap for the whole short
SR = 48000                    # audio sample rate

# Two alternating virtual anchors. preset F/M picks the character art in renderer/anchors.js.
ANCHORS = {
    "F": {"name": os.getenv("ANCHOR_F_NAME", "하루"), "role": "앵커", "voice": os.getenv("VOICE_F", "ko-KR-SunHiNeural")},
    "M": {"name": os.getenv("ANCHOR_M_NAME", "도윤"), "role": "앵커", "voice": os.getenv("VOICE_M", "ko-KR-InJoonNeural")},
}
TTS_RATE = os.getenv("TTS_RATE", "+18%")    # snappy morning-news pace
TTS_PITCH = os.getenv("TTS_PITCH", "+0Hz")

MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")

# Korean news RSS feeds (headline + summary only; the script is always rewritten in our own words)
FEEDS = [
    ("연합뉴스", "https://www.yna.co.kr/rss/news.xml"),
    ("연합뉴스 경제", "https://www.yna.co.kr/rss/economy.xml"),
    ("연합뉴스 국제", "https://www.yna.co.kr/rss/international.xml"),
    ("연합뉴스 IT", "https://www.yna.co.kr/rss/industry.xml"),
    ("한국경제", "https://www.hankyung.com/feed/all-news"),
    ("매일경제", "https://www.mk.co.kr/rss/30000001/"),
    ("SBS", "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=01"),
    ("SBS 경제", "https://news.sbs.co.kr/news/SectionRssFeed.do?sectionId=02"),
    ("Google 뉴스", "https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko"),
]
NEWS_WINDOW_HOURS = int(os.getenv("NEWS_WINDOW_HOURS", "20"))   # "어제 저녁 ~ 오늘 새벽"

# YouTube
YT_PRIVACY = os.getenv("YT_PRIVACY", "private")         # private + publishAt => review window
YT_PUBLISH_AT_KST = os.getenv("YT_PUBLISH_AT_KST", "07:00")  # empty string = publish immediately
YT_CATEGORY_ID = "25"   # News & Politics
