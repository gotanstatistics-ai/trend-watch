"""Wikipedia most-read articles: per country (official Wikimedia API) and per language edition.

Per country: https://wikimedia.org/api/rest_v1/metrics/pageviews/top-per-country/IN/all-access/2026/10/12
Per edition: https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia/all-access/2026/10/12
Data is for yesterday (Wikimedia publishes a day late). Country data gives view ranges, not exact counts."""
from __future__ import annotations

import datetime as dt
import re
import time

from ..model import Entry, to_int

TOP_COUNTRY = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top-per-country/{cc}/all-access/{y}/{m}/{d}"
TOP_EDITION = "https://wikimedia.org/api/rest_v1/metrics/pageviews/top/{lang}.wikipedia/all-access/{y}/{m}/{d}"
SKIP = re.compile(r"^(Main_Page|Special:|Wikipedia:|File:|Help:|Portal:|Talk:|Category:|Template:|-|Wikipédia:|Wikipedia_)")


def _ymd(day):
    return {"y": day.strftime("%Y"), "m": day.strftime("%m"), "d": day.strftime("%d")}


NAMESPACE = re.compile(r"^[^\s:]+:")      # 'Special:Search', 'Speciel:Søgning', 'Wikipedia:...' in any language


def _rank_pages(items, limit):
    out = []
    for it in items:
        title = it.get("article") or it.get("page") or ""
        proj = it.get("project", "")
        if not title or SKIP.match(title) or NAMESPACE.match(title):
            continue
        if proj and not proj.endswith("wikipedia"):      # wiktionary, wikibooks, wikiquote: not topics
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


UA = {"User-Agent": "trend-watch/1.0 (https://github.com/gotanstatistics-ai/trend-watch)"}
PAUSE = 0.6     # Wikimedia asks for a gentle rate


def _get(http, url):
    time.sleep(PAUSE)
    return http.get_json(url, strip_prefix=None, headers=UA)


def latest_day(http, today, log):
    """Wikimedia publishes a day late, sometimes two. Find the newest day that exists."""
    for back in (1, 2, 3):
        day = dt.date.fromisoformat(today) - dt.timedelta(days=back)
        try:
            _get(http, TOP_EDITION.format(lang="en", **_ymd(day)))
            return day
        except Exception as e:
            log(f"  wikipedia: {day} not available yet ({str(e)[:40]})")
    return None


def fetch(http, config, today, fetched_at, log):
    day = latest_day(http, today, log)
    if day is None:
        raise RuntimeError("no Wikipedia day available in the last 3 days")
    ds = day.isoformat()
    out = []
    for c in config["countries"]:
        cc = c["code"]
        try:
            data = _get(http, TOP_COUNTRY.format(cc=cc, **_ymd(day)))
            rows = parse_country(data, cc, ds, fetched_at)
            out.extend(rows)
            log(f"  wikipedia {cc}: {len(rows)} pages")
        except Exception as e:
            log(f"  wikipedia {cc}: FAILED {e}")
    for lang in config.get("wikipedia_editions", []):
        try:
            data = _get(http, TOP_EDITION.format(lang=lang, **_ymd(day)))
            rows = parse_edition(data, lang, ds, fetched_at)
            out.extend(rows)
            log(f"  wikipedia-{lang}: {len(rows)} pages")
        except Exception as e:
            log(f"  wikipedia-{lang}: FAILED {e}")
    return out
