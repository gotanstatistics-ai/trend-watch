from trendwatch.lane import lane_of
from trendwatch.sources.lane_feeds import parse_feed
from trendwatch.report import lane_news
from trendwatch.model import Entry

T = "2026-10-13"


def test_lane_of_matches_whole_words_and_hashtags():
    assert lane_of("Tesla Roadster", "Tesla unveils a flying car") == "tech"
    assert lane_of("#JioIPO") == "markets"
    assert lane_of("Earthquake of magnitude 7 strikes Russia") == "nature"
    assert lane_of("Nobel Prize in Physics") == "science"
    assert lane_of("Starlink") == "space"
    assert lane_of("Virat Kohli") == ""
    assert lane_of("Drone strikes hit Kyiv power grid") == ""        # war, not tech
    assert lane_of("Three killed as 16-year-old opens fire") == ""   # crime, not history
    assert lane_of("Bigg Boss 10") == ""


def test_lane_of_blocks_games_and_films():
    assert lane_of("GTA 6", "Grand Theft Auto VI Launch Trailer") == ""
    assert lane_of("bruno mars") == ""
    assert lane_of("Rocket League") == ""


def test_lane_of_uses_headline_only_as_fallback():
    assert lane_of("Canada", "Canada's inflation rate eases slightly") == "markets"
    assert lane_of("Canada", "Doug Ford warns Trump's tariff war is here to stay") == ""   # politics: skipped
    assert lane_of("cat", "Reading mother told a friend she feared her son") == ""


RSS = """<rss><channel><item><title>Comet seen from Earth - NASA</title><link>https://x/1</link></item>
<item><title>Second story</title><link>https://x/2</link></item></channel></rss>"""
ATOM = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>M 7.0 - near Kamchatka</title>
<link rel="alternate" href="https://usgs/1"/></entry></feed>"""


def test_parse_feed_rss_and_atom():
    rows = parse_feed(RSS, {"name": "NASA", "lane": "space", "country": "", "url": "https://www.nasa.gov/feed"}, T, "f")
    assert [r.topic for r in rows] == ["Comet seen from Earth - NASA", "Second story"]
    assert rows[0].source == "lane-news" and rows[0].note == "space|NASA" and rows[0].url == "https://x/1"
    g = parse_feed(RSS, {"name": "GN", "lane": "space", "country": "IN", "url": "https://news.google.com/rss/x"}, T, "f")
    assert g[0].topic == "Comet seen from Earth" and g[0].note == "space|NASA"      # Google News titles end with the publisher
    rows = parse_feed(ATOM, {"name": "USGS", "lane": "nature", "country": "", "url": "https://usgs/feed"}, T, "f")
    assert rows[0].topic == "M 7.0 - near Kamchatka" and rows[0].url == "https://usgs/1"


def test_lane_news_merges_feeds_and_google_news_and_dedupes():
    es = [Entry(date=T, fetched_at="f", source="lane-news", country="", rank=1, topic="Comet seen from Earth", note="space|NASA", url="u1"),
          Entry(date=T, fetched_at="f", source="lane-news", country="", rank=2, topic="Comet seen from Earth", note="space|ESA", url="u2"),
          Entry(date=T, fetched_at="f", source="google-news", country="IN", rank=3, topic="Sensex jumps 1,500 points", note="Mint", url="u3"),
          Entry(date=T, fetched_at="f", source="google-news", country="IN", rank=1, topic="Actor wins award", note="NDTV", url="u4"),
          Entry(date="2026-10-01", fetched_at="f", source="lane-news", country="", rank=1, topic="Old story", note="space|NASA", url="u5")]
    rows = lane_news(es, T)
    assert [(r["lane"], r["topic"]) for r in rows] == [("space", "Comet seen from Earth"), ("markets", "Sensex jumps 1,500 points")]
    assert rows[1]["publisher"] == "Mint"
