# trend-watch

What people are searching for and talking about, **in the last 15 days**, country by country and
city by city, pulled from several free sources and kept fresh by GitHub itself. Made to help pick
the next documentary topic.

## Where to look

| What | Where |
|---|---|
| The readable report, top 50 topics of the last 15 days | `data/REPORT.md` (GitHub shows it as a page) |
| Ranked topics as a table (with a `lane` column) | `data/topics-15d.csv` |
| **Trending topics in your lanes only** (science, space, nature, markets, medical, tech, history) | `data/lane-topics.csv` |
| **Fresh headlines in your lanes** from NASA, ISRO, science and market feeds, last 3 days | `data/lane-news.csv` |
| Top topics for each country | `data/by-country.csv` |
| Top topics for each city | `data/by-city.csv` |
| Everything from the latest run | `data/latest.csv`, `data/latest.json` |
| One file per day, last 15 days only | `data/history/<date>.csv` |
| Which sources worked in the last run | `data/status.json` |

Score in the report = countries x 3 + sources x 4 + days x 2 + rank bonus + size. A topic with many days and
many countries is something people keep looking for, which is what a documentary needs. One day, one
country is passing news.

## Lanes: the subjects worth posting about

Most of what trends is cricket, films and politics. A *lane* is a subject group worth a post or a video:
`space`, `science`, `nature` (earthquakes, cyclones, floods...), `markets`, `medical`, `tech`, `history`.
Every topic in every CSV carries a `lane` column (empty when it is none of these), and two files hold only
lane material: `lane-topics.csv` (what is trending in a lane) and `lane-news.csv` (fresh headlines from the
feeds below plus any Google News top story that fits a lane).

The word lists live in **`lanes.json`**: `lanes` (words per lane, `*` at the end means starts-with),
`block` (games and films that share a word, never a lane), `skip` (war, crime, politics and sport words
that veto a headline), `skip_ignores` (lanes specific enough to win anyway), and `feeds`. Edit it on GitHub;
the next run picks it up.

## Sources

| Source | What it gives | Level | Needs |
|---|---|---|---|
| Google Trends "Trending now" | top ~20 searches with search counts | country | nothing |
| Google Trends city interest | which cities search each top topic (0-100) | city | nothing; slow, so only `deep` countries |
| X (Twitter) via trends24.in | trending hashtags and topics, tweet counts | country and city | nothing |
| Wikipedia (Wikimedia API) | most-read articles | country and language | nothing; one day late |
| Google News | top headlines (context, not scored) | country | nothing |
| YouTube search suggestions | what people type into YouTube's search box (completions of a to z, "how to", "what is"...) | country | nothing |
| YouTube most popular | top 25 videos | country | free API key in a secret |
| Lane feeds (`lanes.json`) | NASA, ESA, Space.com, Phys.org, ScienceDaily, Nature, USGS earthquakes, WHO, and Google News Science / Technology / Business / Health for India and the US, plus ISRO, India-disaster and archaeology searches | worldwide or country | nothing |

Countries, cities and languages are in `countries.json`. Edit it to add or remove any.

### Quick explainer picks

`data/REPORT.md` has a section "Quick explainer picks": real topics that trend today in two or more
sources, one of them YouTube. These suit a 5-minute explainer video made within a day ("Why is
everyone searching X this week?"). Lasting topics (3+ days) suit full documentaries.

### The YouTube key (optional, 5 minutes, free)

1. https://console.cloud.google.com, create a project, "APIs and services", "Enable APIs", enable
   "YouTube Data API v3", then "Credentials", "Create credentials", "API key". Copy it.
2. On GitHub: the repository's Settings, "Secrets and variables", "Actions", "New repository secret",
   name `YOUTUBE_API_KEY`, paste the key. The next run adds YouTube's most popular videos per country.

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

### The dashboard (Apps Script)

For a proper dashboard, India first, with a country picker and a city picker:

1. In the Sheet: Extensions, Apps Script.
2. Replace the contents of `Code.gs` with `sheet/Code.gs`. Add a file named `Index.html` (the + button,
   HTML) and paste `sheet/Index.html` into it. Save.
3. Pick the function `setup` at the top and press Run. Approve the permissions once. This fills the tabs,
   builds the **Dashboard** tab and sets an hourly refresh.
4. The Dashboard tab shows: your lanes first (trending topics worth a post, then fresh headlines), then
   worldwide top 25, India top 25, every Indian city, and on the right three pickers (cell F3 country,
   cell F4 city, cell F5 lane) whose lists update as you choose.
5. Optional phone page: Deploy, New deployment, Web app, execute as you, access only you. Open the URL.
   It has the same pickers, a lane picker and a search box; the two "Your lane" panels sit at the top.

A menu "Trend watch" appears in the sheet with "Refresh now" and "Rebuild dashboard".

## Running by hand

```
python -m trendwatch fetch                      # all sources, all countries
python -m trendwatch fetch --countries IN,US    # a few countries
python -m trendwatch fetch --only google-trends,x-trends
python -m trendwatch fetch --only lane-news            # just the science/space/market feeds
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

## Instagram posters (`posts/`)

`posts/make_poster.py` turns a small JSON file (headline, 3-4 facts, source, lane) into a branded feed poster
(1080x1350), a story poster (1080x1920) and a caption with hashtags. Brand colours, handle and hashtags are
in `posts/brand.json`; fonts (Poppins, open licence) and the logo ship in `posts/fonts` and `posts/brand`.

```
python posts/make_poster.py --date 2026-10-16        # renders every posts/queue/2026-10-16-*.json
```

Post files live in `posts/queue/<date>-<slug>.json`; output lands in `posts/out/<date>/`. The stories are
picked from `data/lane-topics.csv` and `data/lane-news.csv`; the facts are written from the source article
and the source is named on the poster and in the caption. Needs `pip install pillow`.
