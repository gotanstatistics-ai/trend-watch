"""What people type into YouTube's search box: the suggestions YouTube offers for short starting words.

YouTube suggests the most-searched completions for a prefix in a country and language. Asking for
a few dozen prefixes (a to z, "how to", "what is", "why") gives a picture of the day's searches.
No key needed. Endpoint (the same one the YouTube page uses):
  https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=en&gl=IN&q=how+to
Answer: ["how to", ["how to make ...", "how to ...", ...]]"""
from __future__ import annotations

import json
import time

from ..model import Entry
from ..http import quote

URL = "https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl={hl}&gl={gl}&q={q}"
SEEDS = [c for c in "abcdefghijklmnopqrstuvwxyz"] + ["how to ", "what is ", "why ", "best ", "new ", "top 10 "]
PAUSE = 0.15


def parse(text, seed, country, today, fetched_at):
    data = json.loads(text)
    out = []
    for rank, s in enumerate(data[1] if len(data) > 1 else [], 1):
        s = (s or "").strip()
        if len(s) < 3 or s == seed.strip():
            continue
        out.append(Entry(date=today, fetched_at=fetched_at, source="youtube-suggest", country=country, rank=rank,
                         topic=s, period="now", note="typed after: " + seed.strip(),
                         url="https://www.youtube.com/results?search_query=" + quote(s)))
    return out


def fetch(http, config, today, fetched_at, log):
    out = []
    for c in config["countries"]:
        hl = (c.get("news") or ["en"])[0].split("-")[0]
        rows, failed = [], 0
        for seed in SEEDS:
            try:
                rows += parse(http.get(URL.format(hl=hl, gl=c["code"], q=quote(seed)), accept="application/json"),
                              seed, c["code"], today, fetched_at)
            except Exception as e:
                failed += 1
                if failed >= 3:
                    log(f"  youtube-suggest {c['code']}: stopping after 3 failures ({str(e)[:80]})")
                    break
            time.sleep(PAUSE)
        # the same suggestion can come from several seeds: keep its best rank
        best = {}
        for r in rows:
            k = r.topic.lower()
            if k not in best or r.rank < best[k].rank:
                best[k] = r
        rows = sorted(best.values(), key=lambda r: r.rank)
        out.extend(rows)
        log(f"  youtube-suggest {c['code']}: {len(rows)} searches")
    return out
