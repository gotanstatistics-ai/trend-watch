# trend-watch

What people are searching for and talking about, **in the last 15 days**, country by country and
city by city, pulled from several free sources and kept fresh by GitHub itself. Made to help pick
the next documentary topic.

## Where to look

| What | Where |
|---|---|
| The readable report, top 50 topics of the last 15 days | `data/REPORT.md` (GitHub shows it as a page) |
| Ranked topics as a table | `data/topics-15d.csv` |
| Top topics for each country | `data/by-country.csv` |
| Top topics for each city | `data/by-city.csv` |
| Everything from the latest run | `data/latest.csv`, `data/latest.json` |
| One file per day, last 15 days only | `data/history/<date>.csv` |
| Which sources worked in the last run | `data/status.json` |

Score in the report = countries x 3 + sources x 4 + days x 2 + rank bonus + size. A topic with many days and
many countries is something people keep looking for, which is what a documentary needs. One day, one
country is passing news.

## Sources

| Source | What it gives | Level | Needs |
|---|---|---|---|
| Google Trends "Trending now" | top ~20 searches with search counts | country | nothing |
| Google Trends city interest | which cities search each top topic (0-100) | city | nothing; slow, so only `deep` countries |
| X (Twitter) via trends24.in | trending hashtags and topics, tweet counts | country and city | nothing |
| Wikipedia (Wikimedia API) | most-read articles | country and language | nothing; one day late |
| Google News | top headlines (context, not scored) | country | nothing |
| YouTube most popular | top 25 videos | country | free API key in a secret |

Countries, cities and languages are in `countries.json`. Edit it to add or remove any.

## How it runs

`.github/workflows/fetch.yml` runs every 6 hours on GitHub's servers, fetches all sources, rebuilds the
report and commits the files. Nothing to install and nothing runs on your PC. To run it now, open the
Actions tab on GitHub, pick "fetch trends", press "Run workflow".

## The Google Sheet (live)

1. Make a new Google Sheet.
2. In cell A1 of the first tab paste
   `=IMPORTDATA("https://raw.githubusercontent.com/gotanstatistics-ai/trend-watch/main/data/topics-15d.csv")`
3. Add tabs the same way for `by-country.csv`, `by-city.csv` and `latest.csv`.

Google refreshes IMPORTDATA about every hour, so the sheet is always close to the latest run.
If you prefer formatted tabs that never show "Loading", use `sheet/Code.gs` (Extensions, Apps Script,
paste, run `refresh` once, then add an hourly trigger).

## Running by hand

```
python -m trendwatch fetch                      # all sources, all countries
python -m trendwatch fetch --countries IN,US    # a few countries
python -m trendwatch fetch --only google-trends,x-trends
python -m trendwatch report                     # rebuild the report from the saved days
python -m trendwatch topics --top 25            # print the ranked topics
python -m trendwatch doctor                     # one quick call per source: what works today
```

Needs Python 3.10 or newer and nothing else. Tests: `pip install pytest` then `python -m pytest -q`
(they use saved sample pages, no internet).

## When a source breaks

These are public pages and feeds, and sites change. `data/status.json` and the Actions log say which
source failed. The parsers are in `trendwatch/sources/`, one small file each. Paste the error into a
Claude session and ask it to fix that one file.

## Rules for Claude sessions working here

- Never add a source that costs money without asking once and explaining the advantage.
- Keep the 15-day window; this is for picking topics, not for history.
- Keep `data/` files in the same columns; the Google Sheet depends on them.
