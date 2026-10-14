"""One trend entry = one row in the CSV. Keep this flat so Google Sheets likes it."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, asdict, field

COLUMNS = ["date", "fetched_at", "source", "country", "region", "city", "rank",
           "topic", "traffic", "period", "url", "note"]


@dataclass
class Entry:
    date: str              # YYYY-MM-DD the trend belongs to
    fetched_at: str        # ISO time of the fetch
    source: str            # google-trends, google-cities, wikipedia, wikipedia-<lang>, x-trends, google-news, youtube
    country: str           # ISO code, "" for worldwide
    region: str = ""       # state/province when known
    city: str = ""         # city when known
    rank: int = 0
    topic: str = ""
    traffic: int = 0       # searches / views / tweets, 0 when unknown
    period: str = "day"    # day, 24h, now
    url: str = ""
    note: str = ""         # a headline or short hint

    def row(self):
        d = asdict(self)
        return [d[c] for c in COLUMNS]


_punct = re.compile(r"[^\w\s]", re.UNICODE)
_space = re.compile(r"\s+")


def key(topic: str) -> str:
    """Normalised form used to recognise the same topic across sources.
    'Virat_Kohli', '#ViratKohli' and 'virat kohli' all become 'virat kohli'."""
    t = unicodedata.normalize("NFKC", topic or "").replace("_", " ")
    t = t.strip().lstrip("#")
    # split CamelCase hashtags: ViratKohli -> Virat Kohli
    t = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", t)
    t = _punct.sub(" ", t).lower()
    return _space.sub(" ", t).strip()


def to_int(s) -> int:
    """'200K+' -> 200000, '1.2M' -> 1200000, '1,234' -> 1234, 'Under 10K' -> 10000."""
    if isinstance(s, (int, float)):
        return int(s)
    s = (s or "").strip().upper().replace(",", "").replace("+", "")
    m = re.search(r"([\d.]+)\s*([KMB]?)", s)
    if not m:
        return 0
    n = float(m.group(1))
    mult = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000}.get(m.group(2), 1)
    return int(n * mult)
