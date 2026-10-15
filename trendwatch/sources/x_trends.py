"""X (Twitter) trending topics by country and by city, read from trends24.in.

Pages look like https://trends24.in/india/ and https://trends24.in/india/bangalore/ .
The page holds several hourly lists; the first list is the newest. Each item is a link whose text
is the topic, often followed by a tweet count. This is a public web page, not an API, so the parser
is written loosely and the `doctor` command tells you if it stops matching."""
from __future__ import annotations

import html
import os
import re

from ..model import Entry, to_int

BASE = "https://trends24.in/{slug}/"
CARD = re.compile(r'<ol[^>]*class="[^"]*trend-card__list[^"]*"[^>]*>(.*?)</ol>', re.S)
ITEM = re.compile(r"<li[^>]*>(.*?)</li>", re.S)
LINK = re.compile(r"<a[^>]*href=\"([^\"]*)\"[^>]*>(.*?)</a>", re.S)
COUNT = re.compile(r"<span[^>]*class=\"[^\"]*tweet-count[^\"]*\"[^>]*>(.*?)</span>", re.S)
TAG = re.compile(r"<[^>]+>")


CARD_LOOSE = re.compile(r"<ol[^>]*>(.*?)</ol>", re.S)
DEBUG_DIR = None     # set by fetch(): where to save a page that could not be parsed


def first_list(text):
    cards = CARD.findall(text)
    if cards:
        return cards[0]
    # layout changed: take the first <ol> that holds links with a hashtag or a trend-looking path
    for ol in CARD_LOOSE.findall(text):
        if ol.count("<li") >= 5 and LINK.search(ol):
            return ol
    return None


def parse_page(text, country, city, today, fetched_at, limit=30):
    card = first_list(text)
    if card is None:
        if DEBUG_DIR:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            with open(os.path.join(DEBUG_DIR, f"trends24-{country}-{city or 'country'}.html"), "w", encoding="utf-8") as f:
                f.write(text[:200000])
        raise ValueError("no trend list found on page (layout changed?)")
    out = []
    for rank, li in enumerate(ITEM.findall(card), 1):
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
    global DEBUG_DIR
    DEBUG_DIR = config.get("_debug_dir")
    out = []
    saved = 0
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
                saved += 1
                if saved >= 2 and DEBUG_DIR:
                    DEBUG_DIR = None      # two saved pages are enough to fix the parser
    return out
