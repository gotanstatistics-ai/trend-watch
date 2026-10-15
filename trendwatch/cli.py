"""Commands:
  python -m trendwatch fetch   [--data data] [--only google-trends,x-trends] [--countries IN,US] [--cache dir]
  python -m trendwatch report  [--data data]
  python -m trendwatch doctor  [--countries IN]     one quick call per source, tells what works
  python -m trendwatch topics  [--top 25]            print the ranked topics from the report files"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import time

from . import WINDOW_DAYS, __version__
from .http import Http
from .sources import google_trends, wikipedia, x_trends, google_news, youtube, youtube_suggest
from .store import save_fetch
from .report import write_report

SOURCES = {"google-trends": google_trends, "wikipedia": wikipedia, "x-trends": x_trends,
           "google-news": google_news, "youtube": youtube, "youtube-suggest": youtube_suggest}
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config(path, countries=None):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    if countries:
        want = {c.strip().upper() for c in countries.split(",")}
        cfg["countries"] = [c for c in cfg["countries"] if c["code"] in want]
    return cfg


def cmd_fetch(args, log):
    cfg = load_config(args.config, args.countries)
    cfg["_debug_dir"] = os.path.join(args.data, "debug")
    today = args.today or dt.date.today().isoformat()
    fetched_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    http = Http(cache_dir=args.cache, log=log)
    names = [s.strip() for s in args.only.split(",")] if args.only else list(SOURCES)
    entries, status = [], {"fetched_at": fetched_at, "sources": {}}
    for name in names:
        mod = SOURCES[name]
        log(f"{name}:")
        t0 = time.time()
        try:
            rows = mod.fetch(http, cfg, today, fetched_at, log)
            entries.extend(rows)
            status["sources"][name] = {"ok": True, "rows": len(rows), "seconds": round(time.time() - t0)}
        except Exception as e:
            log(f"  {name}: FAILED {e}")
            status["sources"][name] = {"ok": False, "error": str(e)[:200], "rows": 0}
    log(f"{len(entries)} entries in {http.calls} requests")
    if entries:
        save_fetch(args.data, entries, today, status)
    else:
        log("nothing fetched; files left as they were")
        return 1
    write_report(args.data, today, log)
    return 0


def cmd_report(args, log):
    write_report(args.data, args.today or dt.date.today().isoformat(), log)
    return 0


def cmd_doctor(args, log):
    cfg = load_config(args.config, args.countries or "IN")
    cfg["countries"] = cfg["countries"][:1]
    cfg["countries"][0]["cities"] = cfg["countries"][0]["cities"][:1]
    cfg["countries"][0]["deep"] = False
    cfg["wikipedia_editions"] = cfg["wikipedia_editions"][:1]
    today = dt.date.today().isoformat()
    http = Http(tries=1, log=log)
    ok = True
    for name, mod in SOURCES.items():
        try:
            rows = mod.fetch(http, cfg, today, "doctor", log)
            log(f"{name}: OK, {len(rows)} rows" + (f", e.g. '{rows[0].topic}'" if rows else ""))
        except Exception as e:
            ok = False
            log(f"{name}: FAILED {e}")
    if cfg["countries"][0]["code"] in ("IN", "US", "GB"):
        try:
            rows = google_trends.cities_for(http, "cricket", cfg["countries"][0]["code"], log=log)
            log(f"google-cities: OK, top city {rows[0] if rows else '-'}")
        except Exception as e:
            log(f"google-cities: FAILED {e} (this source is often rate-limited; the others still work)")
    return 0 if ok else 1


def cmd_topics(args, log):
    path = os.path.join(args.data, "topics-15d.csv")
    if not os.path.exists(path):
        log("no report yet; run fetch first")
        return 1
    with open(path, newline="", encoding="utf-8") as f:
        for r in list(csv.DictReader(f))[:args.top]:
            print(f"{r['rank']:>3}. {r['topic']}  [{r['score']}]  {r['days']} days  {r['country_list']}  ({r['source_list']})")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="trendwatch", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name, fn in (("fetch", cmd_fetch), ("report", cmd_report), ("doctor", cmd_doctor), ("topics", cmd_topics)):
        s = sub.add_parser(name)
        s.set_defaults(fn=fn)
        s.add_argument("--data", default=os.path.join(HERE, "data"))
        s.add_argument("--config", default=os.path.join(HERE, "countries.json"))
        s.add_argument("--countries", default="", help="comma-separated ISO codes, e.g. IN,US")
        s.add_argument("--only", default="", help="comma-separated sources: " + ",".join(SOURCES))
        s.add_argument("--cache", default="", help="folder to cache responses in")
        s.add_argument("--today", default="", help="override the date (tests)")
        s.add_argument("--top", type=int, default=25)
    args = p.parse_args(argv)
    args.cache = args.cache or None
    return args.fn(args, lambda *a: print(*a, file=sys.stderr, flush=True))
