"""X (Twitter) trending topics by country and by city, read from trends24.in.

Pages look like https://trends24.in/india/ and https://trends24.in/india/bangalore/ .
The page holds several hourly lists; the first list is the newest. Each item is a link whose text
is the topic, often followed by a tweet count. This is a public web page, not an API, so the parser
is written loosely and the `doctor` command tells you if it stops matching."""
from __future__ import annotations

import html
import re

from ..model import Entry, to_int

BASE = "https://trends24.in/{slug}/"
CARD = re.compile(r'<ol[^>]*class="[^"]*trend-card__list[^"]*"[^>]*>(.*?)</ol>', re.S)
ITEM = re.compile(r"<li[^>]*>(.*?)</li>", re.S)
LINK = re.compile(r"<a[^>]*href=\"([^\"]*)\"[^>]*>(.*?)</a>", re.S)
COUNT = re.compile(r"<span[^>]*class=\"[^\"]*tweet-count[^\"]*\"[^>]*>(.*?)</span>", re.S)
TAG = re.compile(r"<[^>]+>")


def parse_page(text, country, city, today, fetched_at, limit=30):
    cards = CARD.findall(text)
    if not cards:
        raise ValueError("no trend list found on page (layout changed?)")
    out = []
    for rank, li in enumerate(ITEM.findall(cards[0]), 1):
        m = LINK.search(li)
        if not m:
            continue
        topic = html.unescape(TAG.sub("", m.group(2))).strip()
        if not topic:
            continue
        cm = COUNT.search(li)
        traffic = to_int(TAG.sub("", cm.group(1))) if cm else 0
        url = html.unescape(m.group(1))
        if url.startswith("/"):
            url = "https://trends24.in" + url
        out.append(Entry(date=today, fetched_at=fetched_at, source="x-trends", country=country, city=city,
                         rank=rank, topic=topic, traffic=traffic, period="now", url=url))
        if rank >= limit:
            break
    return out


def fetch(http, config, today, fetched_at, log):
    out = []
    for c in config["countries"]:
        slug = c.get("x")
        if not slug:
            continue
        pages = [(slug, "")] + [(f"{slug}/{city}", city.replace("-", " ").title()) for city in c.get("cities", [])]
        for path, city in pages:
            try:
                rows = parse_page(http.get(BASE.format(slug=path), accept="text/html"), c["code"], city, today, fetched_at)
                out.extend(rows)
                log(f"  x-trends {c['code']} {city or 'country'}: {len(rows)}")
            except Exception as e:
                log(f"  x-trends {c['code']} {city or 'country'}: FAILED {e}")
    return out
