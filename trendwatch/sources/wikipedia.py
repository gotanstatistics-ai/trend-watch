"""Wikipedia most-read articles: per country (official Wikimedia API) and per language edition.

Per country: https://wikimedia.org/api/rest_v1/metrics/pageviews/top-per-country/IN/all-access/2026/10/12
Per edition: https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/2026/10/12
Data is for yesterday (Wikimedia publishes a day late). Country data gives view ranges, not exact counts."""
from __future__ import annotations

import datetime as dt
import re

from ..model import Entry, to_int

TOP_COUNTRY = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top-per-country/{cc}/all-access/{y}/{m}/{d}"
TOP_EDITION = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{lang}.wikipedia/all-access/{y}/{m}/{d}"
SKIP = re.compile(r"^(Main_Page|Special:|Wikipedia:|File:|Help:|Portal:|Talk:|Category:|Template:|-|Wikipédia:|Wikipedia_)")


def _ymd(day):
    return {"y": day.strftime("%Y"), "m": day.strftime("%m"), "d": day.strftime("%d")}


def _rank_pages(items, limit):
    out = []
    for it in items:
        title = it.get("article") or it.get("page") or ""
        if not title or SKIP.match(title):
            continue
        out.append((title.replace("_", " "), title, it))
        if len(out) >= limit:
            break
    return out


def parse_country(data, cc, day, fetched_at, limit=25):
    items = data.get("items", [{}])[0].get("articles", [])
    out = []
    for rank, (topic, raw, it) in enumerate(_rank_pages(items, limit), 1):
        views = it.get("views_ceil") or to_int(str(it.get("views", "")))
        proj = it.get("project", "en.wikipedia")
        out.append(Entry(date=day, fetched_at=fetched_at, source="wikipedia", country=cc, rank=rank,
                         topic=topic, traffic=int(views or 0), period="day",
                         url=f"https://{proj}.org/wiki/{raw}", note=proj))
    return out


def parse_edition(data, lang, day, fetched_at, limit=25):
    items = data.get("items", [{}])[0].get("articles", [])
    out = []
    for rank, (topic, raw, it) in enumerate(_rank_pages(items, limit), 1):
        out.append(Entry(date=day, fetched_at=fetched_at, source="wikipedia-" + lang, country="", rank=rank,
                         topic=topic, traffic=int(it.get("views", 0)), period="day",
                         url=f"https://{lang}.wikipedia.org/wiki/{raw}", note=lang + ".wikipedia"))
    return out


def fetch(http, config, today, fetched_at, log):
    day = dt.date.fromisoformat(today) - dt.timedelta(days=1)
    ds = day.isoformat()
    out = []
    for c in config["countries"]:
        cc = c["code"]
        try:
            data = http.get_json(TOP_COUNTRY.format(cc=cc, **_ymd(day)), strip_prefix=None)
            rows = parse_country(data, cc, ds, fetched_at)
            out.extend(rows)
            log(f"  wikipedia {cc}: {len(rows)} pages")
        except Exception as e:
            log(f"  wikipedia {cc}: FAILED {e}")
    for lang in config.get("wikipedia_editions", []):
        try:
            data = http.get_json(TOP_EDITION.format(lang=lang, **_ymd(day)), strip_prefix=None)
            rows = parse_edition(data, lang, ds, fetched_at)
            out.extend(rows)
            log(f"  wikipedia-{lang}: {len(rows)} pages")
        except Exception as e:
            log(f"  wikipedia-{lang}: FAILED {e}")
    return out
