"""Small HTTP helper: retries, browser-like headers, a cookie jar and an optional on-disk cache."""
from __future__ import annotations

import gzip
import hashlib
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/129.0 Safari/537.36")


class HttpError(Exception):
    def __init__(self, url, status, body=""):
        super().__init__(f"{status} for {url}")
        self.url, self.status, self.body = url, status, body


class Http:
    """get(url) returns text. Failures raise HttpError after `tries` attempts.

    cache_dir: when set, responses are stored there and reused (handy for tests and
    for re-running the report without hitting the sites again)."""

    def __init__(self, cache_dir=None, tries=3, timeout=30, pause=1.0, log=print):
        self.cache_dir = cache_dir
        self.tries = tries
        self.timeout = timeout
        self.pause = pause
        self.log = log
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.calls = 0

    def _cache_path(self, url):
        if not self.cache_dir:
            return None
        key = hashlib.sha1(url.encode()).hexdigest()[:20]
        return os.path.join(self.cache_dir, key + ".txt")

    def get(self, url, headers=None, accept="*/*"):
        path = self._cache_path(url)
        if path and os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return f.read()
        hdrs = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.8",
                "Accept-Encoding": "gzip"}
        hdrs.update(headers or {})
        last = None
        for attempt in range(self.tries):
            try:
                self.calls += 1
                req = urllib.request.Request(url, headers=hdrs)
                with self.opener.open(req, timeout=self.timeout) as r:
                    raw = r.read()
                    if r.headers.get("Content-Encoding") == "gzip":
                        raw = gzip.decompress(raw)
                    text = raw.decode(r.headers.get_content_charset() or "utf-8", "replace")
                if path:
                    os.makedirs(self.cache_dir, exist_ok=True)
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(text)
                return text
            except urllib.error.HTTPError as e:
                body = ""
                try:
                    body = e.read()[:300].decode("utf-8", "replace")
                except Exception:
                    pass
                last = HttpError(url, e.code, body)
                if e.code in (400, 401, 403, 404):
                    break           # retrying will not help
                if e.code == 429:
                    time.sleep(self.pause * 10 * (attempt + 1))
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last = HttpError(url, 0, str(e))
            time.sleep(self.pause * (attempt + 1))
        raise last

    def get_json(self, url, strip_prefix=")]}'", **kw):
        text = self.get(url, accept="application/json", **kw)
        if strip_prefix and text.startswith(strip_prefix):
            text = text[len(strip_prefix):]
        return json.loads(text.lstrip(", \n"))


def quote(s):
    return urllib.parse.quote(s, safe="")
