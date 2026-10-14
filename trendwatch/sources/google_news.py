"""Google News top stories per country (RSS). Gives the headlines behind the trends.

https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..model import Entry

RSS = "https://news.google.com/rss?hl={hl}&gl={gl}&ceid={ceid}"


def parse_rss(text, country, today, fetched_at, limit=20):
    root = ET.fromstring(text)
    out = []
    for i, item in enumerate(root.iter("item"), 1):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        # Google News titles end with " - Publisher"
        topic, _, publisher = title.rpartition(" - ")
        if not topic:
            topic, publisher = title, ""
        out.append(Entry(date=today, fetched_at=fetched_at, source="google-news", country=country, rank=i,
                         topic=topic, period="now", url=(item.findtext("link") or "").strip(), note=publisher))
        if i >= limit:
            break
    return out


def fetch(http, config, today, fetched_at, log):
    out = []
    for c in config["countries"]:
        hl, ceid = c.get("news", ["en", c["code"] + ":en"])
        try:
            rows = parse_rss(http.get(RSS.format(hl=hl, gl=c["code"], ceid=ceid), accept="application/rss+xml, application/xml"),
                             c["code"], today, fetched_at)
            out.extend(rows)
            log(f"  google-news {c['code']}: {len(rows)} headlines")
        except Exception as e:
            log(f"  google-news {c['code']}: FAILED {e}")
    return out
