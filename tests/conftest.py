import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return f.read()


class FakeHttp:
    """Answers URLs from a dict of substring -> fixture text. Unknown URLs raise."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = 0
        self.urls = []

    def get(self, url, **kw):
        self.calls += 1
        self.urls.append(url)
        for needle, text in self.routes.items():
            if needle in url:
                if isinstance(text, Exception):
                    raise text
                return text
        raise RuntimeError("no route for " + url)

    def get_json(self, url, strip_prefix=")]}'", **kw):
        import json
        text = self.get(url)
        if strip_prefix and text.startswith(strip_prefix):
            text = text[len(strip_prefix):]
        return json.loads(text.lstrip(", \n"))
