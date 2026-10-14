"""YouTube most popular videos per country. Needs a free YouTube Data API key
(Google Cloud console -> enable 'YouTube Data API v3' -> create API key) in the
YOUTUBE_API_KEY secret. Without the key this source is skipped quietly."""
from __future__ import annotations

import os

from ..model import Entry

URL = ("https://www.googleapis.com/youtube/v3/videos?part=snippet,statistics&chart=mostPopular"
       "&regionCode={cc}&maxResults=25&key={key}")


def parse(data, cc, today, fetched_at):
    out = []
    for rank, v in enumerate(data.get("items", []), 1):
        sn = v.get("snippet", {})
        out.append(Entry(date=today, fetched_at=fetched_at, source="youtube", country=cc, rank=rank,
                         topic=sn.get("title", ""), traffic=int(v.get("statistics", {}).get("viewCount", 0)),
                         period="now", url="https://www.youtube.com/watch?v=" + v.get("id", ""),
                         note=sn.get("channelTitle", "")))
    return out


def fetch(http, config, today, fetched_at, log):
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        log("  youtube: no YOUTUBE_API_KEY, skipped")
        return []
    out = []
    for c in config["countries"]:
        try:
            rows = parse(http.get_json(URL.format(cc=c["code"], key=key), strip_prefix=None), c["code"], today, fetched_at)
            out.extend(rows)
            log(f"  youtube {c['code']}: {len(rows)} videos")
        except Exception as e:
            log(f"  youtube {c['code']}: FAILED {e}")
    return out
