import json
import logging

from conftest import FakeHttp, fixture
from trendwatch.sources import google_trends, wikipedia, x_trends, google_news, youtube
from trendwatch.model import key, to_int

T = "2026-10-13"
F = "2026-10-13T06:00Z"
CFG = {"countries": [{"code": "IN", "name": "India", "news": ["en-IN", "IN:en"], "x": "india",
                      "cities": ["bangalore"], "deep": False}], "wikipedia_editions": ["en"]}
log = lambda *a: None


def test_to_int_and_key():
    assert to_int("200K+") == 200000
    assert to_int("1.2M") == 1200000
    assert to_int("Under 10K") == 10000
    assert to_int("1,234") == 1234
    assert to_int("") == 0
    assert key("#ViratKohli") == key("Virat_Kohli") == key("virat kohli") == "virat kohli"
    assert key("Jurassic Park (film)") == "jurassic park film"


def test_google_trends_rss():
    rows = google_trends.parse_rss(fixture("google_trends.rss"), "IN", T, F)
    assert [r.topic for r in rows] == ["Virat Kohli", "Chandrayaan 4", "Diwali 2026"]
    assert rows[0].traffic == 200000 and rows[0].note.startswith("Kohli scores")
    assert rows[0].url == "https://example.com/kohli"
    assert rows[2].traffic == 1000000 and rows[2].rank == 3
    assert rows[0].source == "google-trends" and rows[0].country == "IN"


def test_google_trends_falls_back_to_old_feed():
    http = FakeHttp({"trending/rss": RuntimeError("503"), "trendingsearches/daily/rss": fixture("google_trends.rss")})
    rows = google_trends.fetch(http, CFG, T, F, log)
    assert len(rows) == 3 and http.calls == 2


def test_google_cities():
    http = FakeHttp({"api/explore": fixture("explore.json"), "widgetdata/comparedgeo": fixture("geo.json"),
                     "trends/explore?geo": "<html>"})
    rows = google_trends.cities_for(http, "cricket", "IN", log=log)
    assert rows == [("Mumbai", 100), ("Bengaluru", 87)]
    assert "geo-token" in http.urls[-1] and "CITY" in http.urls[-1]
    cfg = json.loads(json.dumps(CFG))
    cfg["countries"][0]["deep"] = True
    http.routes["trending/rss"] = fixture("google_trends.rss")
    all_rows = google_trends.fetch(http, cfg, T, F, log)
    cities = [r for r in all_rows if r.source == "google-cities"]
    assert cities and cities[0].city == "Mumbai" and cities[0].traffic == 100


def test_wikipedia_country_and_edition():
    rows = wikipedia.parse_country(json.loads(fixture("wiki_country.json")), "IN", "2026-10-12", F)
    assert [r.topic for r in rows] == ["Virat Kohli", "Diwali"]          # Main_Page and Special: skipped
    assert rows[0].traffic == 99999 and rows[0].url.endswith("/wiki/Virat_Kohli") and rows[0].rank == 1
    rows = wikipedia.parse_edition(json.loads(fixture("wiki_edition.json")), "en", "2026-10-12", F)
    assert rows[1].topic == "Jurassic Park (film)" and rows[1].source == "wikipedia-en" and rows[1].country == ""
    http = FakeHttp({"top-per-country/IN": fixture("wiki_country.json"), "top/en.wikipedia": fixture("wiki_edition.json")})
    rows = wikipedia.fetch(http, CFG, T, F, log)
    assert {r.date for r in rows} == {"2026-10-12"}                         # yesterday
    assert "2026/10/12" in http.urls[0]


def test_x_trends_page():
    rows = x_trends.parse_page(fixture("trends24.html"), "IN", "Bangalore", T, F)
    assert [r.topic for r in rows] == ["#ViratKohli", "Diwali", "Namma Metro"]   # only the newest list
    assert rows[0].traffic == 120000 and rows[2].traffic == 10000 and rows[1].traffic == 0
    assert rows[0].url == "https://trends24.in/india/bangalore/#kohli"
    assert rows[0].city == "Bangalore" and rows[0].source == "x-trends"


def test_x_trends_bad_layout():
    import pytest
    with pytest.raises(ValueError):
        x_trends.parse_page("<html>nothing</html>", "IN", "", T, F)
    http = FakeHttp({"trends24.in/india/bangalore/": fixture("trends24.html"), "trends24.in/india/": "<html></html>"})
    rows = x_trends.fetch(http, CFG, T, F, log)        # country page fails, city page works
    assert len(rows) == 3 and rows[0].city == "Bangalore"


def test_google_news():
    rows = google_news.parse_rss(fixture("google_news.rss"), "IN", T, F)
    assert rows[0].topic == "Kohli century lights up Bengaluru" and rows[0].note == "The Hindu"
    assert rows[1].url == "https://example.com/b"
    http = FakeHttp({"news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en": fixture("google_news.rss")})
    assert len(google_news.fetch(http, CFG, T, F, log)) == 2


def test_youtube_without_key(monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    assert youtube.fetch(FakeHttp({}), CFG, T, F, log) == []
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    data = {"items": [{"id": "abc", "snippet": {"title": "Big video", "channelTitle": "Chan"}, "statistics": {"viewCount": "12"}}]}
    http = FakeHttp({"chart=mostPopular&regionCode=IN": json.dumps(data)})
    rows = youtube.fetch(http, CFG, T, F, log)
    assert rows[0].topic == "Big video" and rows[0].traffic == 12 and rows[0].url.endswith("abc")


def test_youtube_suggest():
    from trendwatch.sources import youtube_suggest
    text = '["how to", ["how to make paneer", "how to", "how to tie a tie", "ab"]]'
    rows = youtube_suggest.parse(text, "how to ", "IN", T, F)
    assert [r.topic for r in rows] == ["how to make paneer", "how to tie a tie"]
    assert rows[0].source == "youtube-suggest" and rows[0].rank == 1 and "search_query=" in rows[0].url
    http = FakeHttp({"suggestqueries.google.com": '["a", ["apple recipe", "apple recipe", "amazon sale"]]'})
    rows = youtube_suggest.fetch(http, CFG, T, F, log)
    assert {r.topic for r in rows} == {"apple recipe", "amazon sale"}       # duplicates merged
    assert http.calls == len(youtube_suggest.SEEDS)
