"""Turn 15 days of entries into ranked topics and the files Google Sheets reads."""
from __future__ import annotations

import csv
import datetime as dt
import math
import os
import re
from collections import Counter, defaultdict

from . import WINDOW_DAYS
from .model import key

MATCH = re.compile(r"\b(vs\.?|v|versus|contra|standings|live stream|lineup|line-up|score|fixtures?|highlights?)\b|"
                   r" - | – |\bweather( today| update)?\b", re.I)


def kind_of(topic):
    """'match' for sports fixtures and scores, 'news' for weather and the like, else 'topic'."""
    t = topic.lower()
    if re.search(r"\bweather\b", t):
        return "news"
    if MATCH.search(t):
        return "match"
    return "topic"


TOPIC_COLUMNS = ["rank", "topic", "kind", "score", "days", "countries", "cities", "sources", "first_seen", "last_seen",
                 "peak_traffic", "country_list", "city_list", "source_list", "headline", "url"]

# Headlines from Google News are full sentences; they rarely match other sources and would
# flood the topic list, so they are kept as context (the 'headline' column) but not scored.
SCORED = ("google-trends", "google-cities", "wikipedia", "x-trends", "youtube", "youtube-suggest")


def _weight(source):
    if source.startswith("wikipedia"):
        return 1.0
    return {"google-trends": 1.5, "x-trends": 1.0, "youtube": 1.2, "youtube-suggest": 1.2, "google-cities": 0.0}.get(source, 1.0)


def rank_topics(entries, today):
    groups = defaultdict(list)
    for e in entries:
        if e.source.startswith(SCORED):
            groups[key(e.topic)].append(e)
    headlines = {}
    for e in entries:
        if e.source == "google-news":
            headlines.setdefault(key(e.topic), e)
    rows = []
    for k, es in groups.items():
        if not k or len(k) < 2:
            continue
        days = sorted({e.date for e in es})
        countries = sorted({e.country for e in es if e.country})
        cities = sorted({e.city for e in es if e.city})
        sources = sorted({e.source.split("-")[0] if e.source.startswith("wikipedia") else e.source for e in es})
        peak = max(e.traffic for e in es)
        # score: breadth across countries and sources matters most, then persistence, then size
        score = (len(countries) * 3 + len(sources) * 4 + len(days) * 2
                 + sum(_weight(e.source) * max(0, 1 - (e.rank - 1) / 25) for e in es) * 0.5
                 + (math.log10(peak) if peak > 0 else 0))
        best = max(es, key=lambda e: (e.traffic, -e.rank))
        names = Counter(e.topic for e in es)
        display = max(names, key=lambda t: (not t.startswith("#"), names[t], t == t.title(), len(t)))
        head = headlines.get(k)
        rows.append({"topic": display, "kind": kind_of(display), "score": round(score, 1), "days": len(days), "countries": len(countries),
                     "cities": len(cities), "sources": len(sources), "first_seen": days[0], "last_seen": days[-1],
                     "peak_traffic": peak, "country_list": " ".join(countries), "city_list": ", ".join(cities),
                     "source_list": " ".join(sources), "headline": (head.note + ": " + head.topic) if head else best.note,
                     "url": best.url or (head.url if head else "")})
    rows.sort(key=lambda r: (-r["score"], -r["peak_traffic"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def _write(path, columns, rows):
    tmp = path + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, path)


def by_place(entries, field):
    """Top topics per country (or per city) over the window: topic, times seen, best rank, sources."""
    agg = {}
    for e in entries:
        place = getattr(e, field)
        if not place:
            continue
        k = (place, key(e.topic))
        a = agg.setdefault(k, {"place": place, "country": e.country, "topic": e.topic, "seen": 0, "best_rank": 999,
                               "sources": set(), "days": set(), "peak_traffic": 0})
        a["seen"] += 1
        a["best_rank"] = min(a["best_rank"], e.rank)
        a["sources"].add(e.source)
        a["days"].add(e.date)
        a["peak_traffic"] = max(a["peak_traffic"], e.traffic)
    rows = []
    for a in agg.values():
        rows.append({field: a["place"], "country": a["country"], "topic": a["topic"], "days": len(a["days"]),
                     "seen": a["seen"], "best_rank": a["best_rank"], "peak_traffic": a["peak_traffic"],
                     "sources": " ".join(sorted(a["sources"]))})
    rows.sort(key=lambda r: (r[field], -r["days"], -r["seen"], r["best_rank"]))
    return rows


DAILY_COLUMNS = ["date", "topic", "countries", "sources", "cities", "best_rank", "peak_traffic"]


def daily_rows(entries, topics, limit=500):
    """One row per (day, topic) for the top `limit` topics: how wide it was that day."""
    keep = {key(t["topic"]): t["topic"] for t in topics[:limit]}
    agg = {}
    for e in entries:
        k = key(e.topic)
        if k not in keep or not e.source.startswith(SCORED):
            continue
        a = agg.setdefault((e.date, k), {"date": e.date, "topic": keep[k], "countries": set(), "sources": set(),
                                         "cities": set(), "best_rank": 999, "peak_traffic": 0})
        if e.country:
            a["countries"].add(e.country)
        if e.city:
            a["cities"].add(e.city)
        a["sources"].add(e.source.split("-")[0] if e.source.startswith("wikipedia") else e.source)
        a["best_rank"] = min(a["best_rank"], e.rank)
        a["peak_traffic"] = max(a["peak_traffic"], e.traffic)
    rows = []
    for a in agg.values():
        rows.append({"date": a["date"], "topic": a["topic"], "countries": len(a["countries"]), "sources": len(a["sources"]),
                     "cities": len(a["cities"]), "best_rank": a["best_rank"], "peak_traffic": a["peak_traffic"]})
    rows.sort(key=lambda r: (r["date"], -r["countries"]))
    return rows


def write_report(data_dir, today, log=print, top=50):
    from .store import load_window
    entries = load_window(data_dir, today)
    topics = rank_topics(entries, today)
    _write(os.path.join(data_dir, "topics-15d.csv"), TOPIC_COLUMNS, topics)
    _write(os.path.join(data_dir, "topics-daily.csv"), DAILY_COLUMNS, daily_rows(entries, topics))
    cols = ["country", "topic", "days", "seen", "best_rank", "peak_traffic", "sources"]
    _write(os.path.join(data_dir, "by-country.csv"), cols, by_place(entries, "country"))
    _write(os.path.join(data_dir, "by-city.csv"), ["city"] + cols, by_place(entries, "city"))
    days = sorted({e.date for e in entries})
    lines = [f"# What the world searched for: last {WINDOW_DAYS} days", "",
             f"Updated {dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC. "
             f"{len(entries)} entries from {len(days)} days "
             f"({days[0] if days else '-'} to {days[-1] if days else '-'}).", "",
             "Score = countries x 3 + sources x 4 + days x 2 + rank bonus + size. "
             "High days and many countries = a subject people keep looking for, good for a documentary. "
             "One day, one country = passing news.", "",
             f"## Top {top} topics", "",
             "| # | Topic | Score | Days | Countries | Sources | Cities | Peak | Headline |",
             "|--:|---|--:|--:|---|---|---|--:|---|"]
    for r in [t for t in topics if t["kind"] == "topic"][:top]:
        head = (r["headline"] or "").replace("|", "/")[:90]
        lines.append(f"| {r['rank']} | {r['topic'].replace('|', '/')} | {r['score']} | {r['days']} | "
                     f"{r['country_list'][:40]} | {r['source_list']} | {r['city_list'][:50]} | "
                     f"{r['peak_traffic']:,} | {head} |")
    today_s = days[-1] if days else ""
    quick = [r for r in topics if r["kind"] == "topic" and r["last_seen"] == today_s and r["sources"] >= 2
             and "youtube" in r["source_list"]][:10]
    lines += ["", "## Quick explainer picks (5-minute videos): trending today in several sources, including YouTube", ""]
    lines += [f"- **{r['topic']}**: {r['country_list'][:30] or 'worldwide'}; {r['source_list']}; "
              f"{(r['headline'] or '')[:80]}" for r in quick] or ["- none today"]
    lines += ["", "## Sports matches and passing news (not documentary subjects)", ""]
    passing = [r for r in topics if r["kind"] != "topic"][:25]
    lines += [", ".join(r["topic"] for r in passing) or "none"]
    lines += ["", "## Lasting topics (seen on 3 or more days)", ""]
    lasting = [r for r in topics if r["days"] >= 3][:30]
    lines += [f"- **{r['topic']}** ({r['days']} days, {r['country_list'] or 'worldwide'})" for r in lasting] or ["- none yet"]
    latest_day = days[-1] if days else ""
    lines += ["", "## By platform, India, today", ""]
    for src, title in (("google-trends", "Google searches"), ("youtube-suggest", "YouTube searches (typed into the search box)"),
                       ("x-trends", "Instagram-ready picks (hashtags trending on X)")):
        rows = sorted([e for e in entries if e.source == src and e.country == "IN" and not e.city and e.date == latest_day],
                      key=lambda e: e.rank)[:10]
        lines.append(f"- **{title}**: " + (", ".join(e.topic for e in rows) if rows else "no data yet"))
    lines += ["", "## India, by city (X trends and Google city interest)", ""]
    india = [e for e in entries if e.country == "IN" and e.city]
    seen = defaultdict(list)
    for e in sorted(india, key=lambda e: (e.date, e.rank), reverse=True):
        if len(seen[e.city]) < 5 and e.topic not in seen[e.city]:
            seen[e.city].append(e.topic)
    lines += [f"- **{city}**: {', '.join(t)}" for city, t in sorted(seen.items())] or ["- no city data yet"]
    lines += ["", "Files: `data/topics-15d.csv`, `data/by-country.csv`, `data/by-city.csv`, "
              "`data/latest.csv`, `data/history/<date>.csv`, `data/status.json`.", ""]
    with open(os.path.join(data_dir, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"report: {len(topics)} topics, {len(entries)} entries, {len(days)} days")
    return topics
