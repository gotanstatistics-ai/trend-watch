"""Saving and loading the CSV files under data/. One file per day; last 15 days kept."""
from __future__ import annotations

import csv
import datetime as dt
import json
import os

from . import WINDOW_DAYS
from .model import COLUMNS, Entry


def history_dir(data_dir):
    return os.path.join(data_dir, "history")


def day_path(data_dir, day):
    return os.path.join(history_dir(data_dir), f"{day}.csv")


def write_csv(path, rows):
    tmp = path + ".tmp"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLUMNS)
        for r in rows:
            w.writerow(r.row() if isinstance(r, Entry) else r)
    os.replace(tmp, path)


def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        out = []
        for d in csv.DictReader(f):
            d["rank"] = int(d.get("rank") or 0)
            d["traffic"] = int(d.get("traffic") or 0)
            out.append(Entry(**{k: d.get(k, "") for k in COLUMNS}))
        return out


def save_fetch(data_dir, entries, today, status):
    """Merge this fetch into the day files it belongs to (Wikipedia rows are for yesterday).
    Within a day, a (source, country, city, topic) is kept once, with its best rank."""
    by_day = {}
    for e in entries:
        by_day.setdefault(e.date, []).append(e)
    for day, rows in by_day.items():
        path = day_path(data_dir, day)
        merged = {}
        for e in read_csv(path) + rows:
            k = (e.source, e.country, e.city, e.topic)
            if k not in merged or e.rank < merged[k].rank:
                merged[k] = e
        write_csv(path, sorted(merged.values(), key=lambda e: (e.source, e.country, e.city, e.rank)))
    write_csv(os.path.join(data_dir, "latest.csv"), entries)
    with open(os.path.join(data_dir, "latest.json"), "w", encoding="utf-8") as f:
        json.dump({"fetched_at": entries[0].fetched_at if entries else "", "count": len(entries),
                   "entries": [dict(zip(COLUMNS, e.row())) for e in entries]}, f, ensure_ascii=False, indent=0)
    with open(os.path.join(data_dir, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)
    prune(data_dir, today)


def prune(data_dir, today):
    keep_from = dt.date.fromisoformat(today) - dt.timedelta(days=WINDOW_DAYS - 1)
    removed = []
    if not os.path.isdir(history_dir(data_dir)):
        return removed
    for name in os.listdir(history_dir(data_dir)):
        if name.endswith(".csv"):
            try:
                day = dt.date.fromisoformat(name[:-4])
            except ValueError:
                continue
            if day < keep_from:
                os.remove(os.path.join(history_dir(data_dir), name))
                removed.append(name)
    return removed


def load_window(data_dir, today, days=WINDOW_DAYS):
    """All entries of the last `days` days, newest first."""
    end = dt.date.fromisoformat(today)
    out = []
    for i in range(days):
        day = (end - dt.timedelta(days=i)).isoformat()
        out.extend(read_csv(day_path(data_dir, day)))
    return out
