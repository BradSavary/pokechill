"""
What's new: the latest changes of the game, shown on the title screen.

They are data (data/news.json, newest first), so adding one needs no code.
Only what is already in the game goes there: the next steps of the roadmap
are not announced.
"""

import json
from dataclasses import dataclass
from datetime import date
from functools import cache

from django.conf import settings

NEWS_FILE = settings.BASE_DIR / "data" / "news.json"


class NewsError(ValueError):
    """The news file is malformed."""


@dataclass(frozen=True)
class News:
    day: date
    text: str


def parse_news(raw: object) -> tuple[News, ...]:
    """Validate the content of the news file: a list of {"date", "text"}, newest first."""
    if not isinstance(raw, list):
        raise NewsError("the news file holds a list")
    news = []
    for item in raw:
        if not isinstance(item, dict) or item.keys() != {"date", "text"}:
            raise NewsError(f'each news is {{"date": ..., "text": ...}}, got {item!r}')
        try:
            day = date.fromisoformat(item["date"])
        except (TypeError, ValueError) as error:
            raise NewsError(f"invalid date {item['date']!r}") from error
        if not isinstance(item["text"], str) or not item["text"].strip():
            raise NewsError(f"a news needs a text, got {item['text']!r}")
        news.append(News(day, item["text"].strip()))
    if news != sorted(news, key=lambda n: n.day, reverse=True):
        raise NewsError("the news must be sorted, newest first")
    return tuple(news)


@cache  # read once per process: the file only changes with a deployment
def all_news() -> tuple[News, ...]:
    return parse_news(json.loads(NEWS_FILE.read_text(encoding="utf-8")))


def latest(count: int = 3) -> tuple[News, ...]:
    """The `count` most recent changes."""
    return all_news()[:count]
