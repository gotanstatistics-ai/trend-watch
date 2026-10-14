import datetime as dt
import json
import os

from conftest import FakeHttp, fixture
from trendwatch.model import Entry
from trendwatch.store import save_fetch, read_csv, load_window, day_path, prune
from trendwatch.report import rank_topics, write_report, by_place
from trendwatch import cli

T = "2026-10-13"


def e(topic, source="google-trends", country="IN", date=T, rank=1, traffic=0, city="", note=""):
    return Entry(date=date, fetched_at="f", source=source, country=country, city=city, rank=rank,
                 topic=topic, traffic=traffic, note=note)


def test_save_merges_same_day_keeps_best_rank(tmp_path):
    d = str(tmp_path)
    save_fetch(d, [e("Diwali", rank=5), e("Kohli", rank=1)], T, {})
    save_fetch(d, [e("Diwali", rank=2), e("Metro", rank=3)], T, {})
    rows = read_csv(day_path(d, T))
    assert {(r.topic, r.rank) for r in rows} == {("Diwali", 2), ("Kohli", 1), ("Metro", 3)}
    latest = read_csv(os.path.join(d, "latest.csv"))
    assert [r.topic for r in latest] == ["Diwali", "Metro"]
    assert json.load(open(os.path.join(d, "latest.json")))["count"] == 2


def test_prune_keeps_15_days(tmp_path):
    d = str(tmp_path)
    today = dt.date.fromisoformat(T)
    for i in (0, 14, 15, 40):
        day = (today - dt.timedelta(days=i)).isoformat()
        save_fetch(d, [e("x", date=day)], day, {})
    removed = prune(d, T)
    assert sorted(removed) == ["2026-09-03.csv", "2026-09-28.csv"]
    assert len(load_window(d, T)) == 2


def test_rank_topics_rewards_breadth_and_days():
    entries = [e("Diwali", country="IN"), e("Diwali", country="GB", source="x-trends"),
               e("Diwali", country="IN", date="2026-10-12", source="wikipedia", traffic=80000),
               e("Diwali", country="IN", date="2026-10-11"),
               e("#Diwali", city="Bangalore", source="x-trends"),
               e("Local thing", rank=10),
               e("Diwali lamps sell out", source="google-news", note="The Hindu")]
    rows = rank_topics(entries, T)
    assert rows[0]["topic"] == "Diwali" and rows[0]["rank"] == 1
    assert rows[0]["days"] == 3 and rows[0]["countries"] == 2 and rows[0]["sources"] == 3
    assert rows[0]["city_list"] == "Bangalore" and rows[0]["peak_traffic"] == 80000
    assert rows[0]["score"] > rows[1]["score"] and rows[1]["topic"] == "Local thing"
    assert all(r["topic"] != "Diwali lamps sell out" for r in rows)      # news is context, not a topic


def test_by_place():
    rows = by_place([e("A", city="Bangalore", source="x-trends"), e("A", city="Bangalore", date="2026-10-12", source="x-trends"),
                     e("B", city="Mumbai")], "city")
    assert rows[0]["city"] == "Bangalore" and rows[0]["days"] == 2 and rows[1]["city"] == "Mumbai"


def test_write_report_files(tmp_path):
    d = str(tmp_path)
    save_fetch(d, [e("Diwali", traffic=1000), e("Kohli", rank=2, city="Bangalore", source="x-trends")], T, {})
    topics = write_report(d, T, log=lambda *a: None)
    assert [t["topic"] for t in topics] == ["Diwali", "Kohli"] or [t["topic"] for t in topics] == ["Kohli", "Diwali"]
    for name in ("REPORT.md", "topics-15d.csv", "by-country.csv", "by-city.csv"):
        assert os.path.exists(os.path.join(d, name))
    text = open(os.path.join(d, "REPORT.md"), encoding="utf-8").read()
    assert "Bangalore" in text and "Diwali" in text and "last 15 days" in text


def test_cli_fetch_with_fakes(tmp_path, monkeypatch):
    d = str(tmp_path / "data")
    http = FakeHttp({"trending/rss": fixture("google_trends.rss"), "top-per-country": fixture("wiki_country.json"),
                     "top/en.wikipedia": fixture("wiki_edition.json"), "trends24.in": fixture("trends24.html"),
                     "news.google.com": fixture("google_news.rss")})
    monkeypatch.setattr(cli, "Http", lambda **kw: http)
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    cfg = tmp_path / "c.json"
    cfg.write_text(json.dumps({"countries": [{"code": "IN", "name": "India", "news": ["en-IN", "IN:en"], "x": "india",
                                              "cities": ["bangalore"]}], "wikipedia_editions": ["en"]}))
    rc = cli.main(["fetch", "--data", d, "--config", str(cfg), "--today", T])
    assert rc == 0
    status = json.load(open(os.path.join(d, "status.json")))
    assert status["sources"]["google-trends"]["rows"] == 3 and status["sources"]["youtube"]["rows"] == 0
    assert os.path.exists(os.path.join(d, "history", T + ".csv"))
    assert os.path.exists(os.path.join(d, "history", "2026-10-12.csv"))     # wikipedia rows land on yesterday
    assert cli.main(["topics", "--data", d, "--top", "3"]) == 0
    top = open(os.path.join(d, "topics-15d.csv"), encoding="utf-8").read().splitlines()
    assert "Virat Kohli" in top[1] or "Diwali" in top[1]


def test_cli_fetch_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "Http", lambda **kw: FakeHttp({}))
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    d = str(tmp_path / "data")
    assert cli.main(["fetch", "--data", d, "--today", T, "--only", "google-news", "--countries", "IN"]) == 1
    assert not os.path.exists(d)
