"""Which lane a topic belongs to: space, science, nature, markets, medical, tech, history, or '' for none.

The word lists live in lanes.json (next to countries.json) so they can be edited without touching code.
A topic is matched on its own text plus its headline; the first lane with a hit wins, in the order the
lanes are listed. Topics in the block list never get a lane (games and films that share a word)."""
from __future__ import annotations

import json
import os
import re

from .model import key

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(HERE, "lanes.json")
LANES = ["space", "science", "nature", "markets", "medical", "tech", "history"]


def _pattern(words):
    parts = []
    for w in words:
        w = w.strip().lower()
        if not w:
            continue
        if w.endswith("*"):
            parts.append(re.escape(w[:-1]) + r"\w*")
        else:
            parts.append(re.escape(w))
    # \b does not work next to '&' or '-' at the edges, so use lookarounds on word characters
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)", re.I) if parts else None


class Lanes:
    def __init__(self, path=DEFAULT_PATH):
        with open(path, encoding="utf-8") as f:
            cfg = json.load(f)
        self.order = list(cfg["lanes"])
        self.patterns = {name: _pattern(words) for name, words in cfg["lanes"].items()}
        self.block = {key(b) for b in cfg.get("block", [])}
        self.skip = _pattern(cfg.get("skip", []))
        self.skip_ignores = set(cfg.get("skip_ignores", []))
        self.feeds = cfg.get("feeds", [])

    def of(self, topic, headline=""):
        """Lane name or ''. The topic text decides first; the headline only helps when the topic alone says nothing."""
        k = key(topic)
        if not k or k in self.block:
            return ""
        # k is the normalised topic: '#JioIPO' -> 'jio ipo', so hashtags match too
        for t in (k, (headline or "").replace("_", " ")):
            if not t:
                continue
            # war, crime, politics, sport: not a lane even when a science word appears,
            # except for lanes in skip_ignores (an earthquake in Russia is still an earthquake)
            skipped = bool(self.skip and self.skip.search(t))
            for name in self.order:
                if skipped and name not in self.skip_ignores:
                    continue
                p = self.patterns[name]
                if p and p.search(t):
                    return name
        return ""


_default = None


def lanes():
    global _default
    if _default is None:
        _default = Lanes()
    return _default


def lane_of(topic, headline=""):
    return lanes().of(topic, headline)
