"""Google Trends 'Trending now' per country (RSS), plus which cities search for a topic (explore API).

RSS:    https://trends.google.com/trending/rss?geo=IN      (official feed, about 20 items, with traffic)
Cities: the unofficial explore API used by the Trends website. Needs two calls per topic and
        returns a 0-100 score per city (100 = the city that searches it most). It is rate-limited,
        so only `deep` countries and only their top few topics are asked."""
from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET

from ..model import Entry, to_int
from ..http import quote

RSS = "https://trends.google.com/trending/rss?geo={geo}"
RSS_OLD = "https://trends.google.com/trends/trendingsearches/daily/rss?geo={geo}"
EXPLORE = "https://trends.google.com/trends/api/explore?hl=en-US&tz=-330&req={req}"
GEO = "https://trends.google.com/trends/api/widgetdata/comparedgeo?hl=en-US&tz=-330&req={req}&token={token}"
DEBUG_DIR = None
NS = {"ht": "https://trends.google.com/trending/rss"}
NS_OLD = {"ht": "https://trends.google.com/trends/trendingsearches/daily"}


def parse_rss(text, country, today, fetched_at):
    root = ET.fromstring(text)
    ns = NS if "trending/rss" in text[:2000] else NS_OLD
    out = []
    for i, item in enumerate(root.iter("item"), 1):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        traffic = to_int(item.findtext("ht:approx_traffic", default="", namespaces=ns))
        news = item.find("ht:news_item", ns)
        note = url = ""
        if news is not None:
            note = (news.findtext("ht:news_item_title", default="", namespaces=ns) or "").strip()
            url = (news.findtext("ht:news_item_url", default="", namespaces=ns) or "").strip()
        if not url:
            url = (item.findtext("link") or "").strip()
        out.append(Entry(date=today, fetched_at=fetched_at, source="google-trends", country=country,
                         rank=i, topic=title, traffic=traffic, period="24h", url=url, note=note))
    return out


def fetch_country(http, country, today, fetched_at, log):
    try:
        text = http.get(RSS.format(geo=country), accept="application/rss+xml, application/xml, text/xml")
    except Exception as e:
        log(f"  google-trends {country}: new feed failed ({e}); trying old feed")
        text = http.get(RSS_OLD.format(geo=country), accept="application/xml")
    return parse_rss(text, country, today, fetched_at)


# ---- cities for a topic --------------------------------------------------------------

def _strip(text):
    return json.loads(text.split("\n", 1)[1] if text.startswith(")]}'") else text)


def parse_geo(text):
    """-> list of (geoName, value 0-100) sorted by value."""
    data = _strip(text)
    rows = []
    for g in data.get("default", {}).get("geoMapData", []):
        vals = g.get("value") or [0]
        if g.get("hasData", [True])[0] and vals[0]:
            rows.append((g.get("geoName", ""), int(vals[0])))
    rows.sort(key=lambda r: -r[1])
    return rows


def cities_for(http, topic, country, resolution="CITY", log=print):
    req = json.dumps({"comparisonItem": [{"keyword": topic, "geo": country, "time": "today 1-m"}],
                      "category": 0, "property": ""}, separators=(",", ":"))
    explore = http.get(EXPLORE.format(req=quote(req)), accept="application/json",
                       headers={"Referer": "https://trends.google.com/trends/explore"})
    data = _strip(explore)
    widget = next((w for w in data.get("widgets", []) if w.get("id") == "GEO_MAP"), None)
    if not widget:
        raise ValueError("no GEO_MAP widget")
    request = dict(widget["request"])
    request["resolution"] = resolution
    url = GEO.format(req=quote(json.dumps(request, separators=(",", ":"))), token=widget["token"])
    text = http.get(url, accept="application/json", headers={"Referer": "https://trends.google.com/trends/explore"})
    rows = parse_geo(text)
    if not rows and resolution == "CITY":
        # cities came back empty (Google often has no city split for 7 days): fall back to states
        request["resolution"] = "REGION"
        url = GEO.format(req=quote(json.dumps(request, separators=(",", ":"))), token=widget["token"])
        text2 = http.get(url, accept="application/json", headers={"Referer": "https://trends.google.com/trends/explore"})
        rows = [(name, v) for name, v in parse_geo(text2)]
        if rows:
            log(f"  google-cities: no city split for '{topic}', using states")
        elif DEBUG_DIR:
            os.makedirs(DEBUG_DIR, exist_ok=True)
            with open(os.path.join(DEBUG_DIR, f"geo-{country}-{resolution}.json"), "w", encoding="utf-8") as f:
                f.write(text[:100000])
    return rows


def fetch_cities(http, entries, country, today, fetched_at, log, top=5, pause=3.0):
    """For the top `top` trends of a country, ask which cities search them. Best effort."""
    out = []
    http.get("https://trends.google.com/trends/explore?geo=" + country, accept="text/html")  # cookies
    for e in entries[:top]:
        try:
            rows = cities_for(http, e.topic, country, "CITY", log)
        except Exception as ex:
            log(f"  google-cities {country} '{e.topic}': {ex}")
            time.sleep(pause)
            continue
        for rank, (city, value) in enumerate(rows[:15], 1):
            out.append(Entry(date=today, fetched_at=fetched_at, source="google-cities", country=country,
                             city=city, rank=rank, topic=e.topic, traffic=value, period="30d",
                             note="interest 0-100, 100 = city that searches it most"))
        time.sleep(pause)
    return out


def fetch(http, config, today, fetched_at, log):
    global DEBUG_DIR
    DEBUG_DIR = config.get("_debug_dir")
    out = []
    for c in config["countries"]:
        code = c["code"]
        try:
            rows = fetch_country(http, code, today, fetched_at, log)
        except Exception as e:
            log(f"  google-trends {code}: FAILED {e}")
            continue
        out.extend(rows)
        log(f"  google-trends {code}: {len(rows)} topics")
        if c.get("deep") and rows:
            cities = fetch_cities(http, rows, code, today, fetched_at, log)
            log(f"  google-cities {code}: {len(cities)} city rows")
            out.extend(cities)
    return out
