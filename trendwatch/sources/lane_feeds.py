"""Science, space, nature, markets, medical, tech and history news from RSS/Atom feeds listed in lanes.json.

These are headlines, not trends: like Google News they are context, not scored into the topic list.
They feed data/lane-news.csv, the list of fresh stories in the subjects worth posting about."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from ..lane import lanes
from ..model import Entry

NS = {"atom": "http://www.w3.org/2005/Atom"}
_tag = re.compile(r"<[^>]+>")


def _clean(s):
    s = _tag.sub("", s or "")
    return re.sub(r"\s+", " ", s).strip()


def parse_feed(text, feed, today, fetched_at, limit=20):
    """RSS 2.0 or Atom. Returns Entry rows, rank in feed order. note = lane|publisher."""
    root = ET.fromstring(text)
    items = list(root.iter("item")) or root.findall(".//atom:entry", NS) or list(root.iter("{http://www.w3.org/2005/Atom}entry"))
    out = []
    for i, item in enumerate(items, 1):
        if item.tag == "item":
            title = _clean(item.findtext("title"))
            link = (item.findtext("link") or "").strip()
            if not link:
                enc = item.find("enclosure")
                link = enc.get("url", "") if enc is not None else ""
        else:
            title = _clean(item.findtext("atom:title", default="", namespaces=NS))
            link = ""
            for l in item.findall("atom:link", NS):
                if l.get("rel", "alternate") == "alternate" and l.get("href"):
                    link = l.get("href")
                    break
        if not title:
            continue
        publisher = feed["name"]
        if "news.google.com" in feed["url"]:
            t, _, pub = title.rpartition(" - ")
            if t:
                title, publisher = t, pub
        out.append(Entry(date=today, fetched_at=fetched_at, source="lane-news", country=feed.get("country", ""),
                         rank=i, topic=title[:200], period="now", url=link, note=f"{feed['lane']}|{publisher}"))
        if i >= limit:
            break
    return out


def fetch(http, config, today, fetched_at, log):
    out = []
    want = {c["code"] for c in config["countries"]}
    for feed in lanes().feeds:
        if feed.get("country") and feed["country"] not in want:
            continue
        try:
            rows = parse_feed(http.get(feed["url"], accept="application/rss+xml, application/atom+xml, application/xml, text/xml"),
                              feed, today, fetched_at)
            out.extend(rows)
            log(f"  lane-news {feed['name']}: {len(rows)} headlines")
        except Exception as e:
            log(f"  lane-news {feed['name']}: FAILED {e}")
    return out
