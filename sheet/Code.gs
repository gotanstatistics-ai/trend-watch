// trend-watch Google Apps Script: pulls the CSV files from GitHub into tabs, builds a Dashboard tab,
// and serves a small web page with country, city and lane pickers.
//
// Set up once:
//   1. New Google Sheet -> Extensions -> Apps Script.
//   2. Replace Code.gs with this file; add a file "Index.html" with sheet/Index.html.
//   3. Set REPO below if your GitHub name is different.
//   4. Run `setup` once (approve the permissions it asks for). It fills all tabs and adds an hourly refresh.
//   5. Optional web page: Deploy -> New deployment -> Web app -> "Execute as: me", "Who has access: only myself"
//      -> copy the URL and open it on your phone.
// After that the sheet refreshes itself every hour. The menu "Trend watch" has "Refresh now".
//
// Lanes: every topic carries a "lane" (space, science, nature, markets, medical, tech, history, or empty).
// "Lane topics" = trending topics in a lane; "Lane news" = fresh headlines from the science/space/market feeds.
// The lists of words that define each lane are in lanes.json in the GitHub repo.

const REPO = "gotanstatistics-ai/trend-watch";
const BASE = "https://raw.githubusercontent.com/" + REPO + "/main/data/";
const TABS = {"Topics 15 days": "topics-15d.csv", "Lane topics": "lane-topics.csv", "Lane news": "lane-news.csv",
              "By country": "by-country.csv", "By city": "by-city.csv", "Daily": "topics-daily.csv",
              "Latest fetch": "latest.csv"};
const HOME = "IN";              // the country shown first on the dashboard
const HOME_NAME = "India";
const LANES = ["space", "science", "nature", "markets", "medical", "tech", "history"];

function onOpen() {
  SpreadsheetApp.getUi().createMenu("Trend watch")
    .addItem("Refresh now", "refresh")
    .addItem("Rebuild dashboard", "buildDashboard")
    .addToUi();
}

function setup() {
  refresh();
  ScriptApp.getProjectTriggers().forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger("refresh").timeBased().everyHours(1).create();
}

function fetchCsv(file) {
  const r = UrlFetchApp.fetch(BASE + file + "?t=" + Date.now(), {muteHttpExceptions: true});
  if (r.getResponseCode() !== 200) throw new Error(file + " not found on GitHub yet (" + r.getResponseCode() + ")");
  return Utilities.parseCsv(r.getContentText());
}

function refresh() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  for (const [name, file] of Object.entries(TABS)) {
    let rows;
    try { rows = fetchCsv(file); } catch (e) {
      Logger.log(e.message);
      SpreadsheetApp.getActiveSpreadsheet().toast(name + ": " + e.message, "Trend watch", 10);
      continue;
    }
    if (!rows.length) continue;
    let sh = ss.getSheetByName(name) || ss.insertSheet(name);
    sh.clearContents();
    sh.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, rows[0].length).setFontWeight("bold");
  }
  let info = ss.getSheetByName("Info") || ss.insertSheet("Info");
  info.getRange("A1").setValue("Last refresh: " + new Date().toUTCString());
  buildDashboard();
}

// ---------- Dashboard tab ----------------------------------------------------------------

function table(ss, name) {
  const sh = ss.getSheetByName(name);
  if (!sh || sh.getLastRow() < 2) return [];
  const v = sh.getDataRange().getValues();
  const head = v[0];
  return v.slice(1).map(r => Object.fromEntries(head.map((h, i) => [h, r[i]])));
}

function topFor(rows, field, value, n) {
  return rows.filter(r => r[field] === value)
             .sort((a, b) => (b.days - a.days) || (b.seen - a.seen) || (a.best_rank - b.best_rank))
             .slice(0, n);
}

function buildDashboard() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const topics = table(ss, "Topics 15 days");
  const laneTopics = table(ss, "Lane topics");
  const laneNews = table(ss, "Lane news");
  const byCountry = table(ss, "By country");
  const byCity = table(ss, "By city");
  let sh = ss.getSheetByName("Dashboard") || ss.insertSheet("Dashboard", 0);
  sh.clear();
  sh.getRange("A1").setValue("Trend watch, last 15 days").setFontSize(16).setFontWeight("bold");
  sh.getRange("A2").setValue("Updated " + new Date().toUTCString() + ". Pick a country in F3, a city in F4 and a lane in F5; the lists on the right follow.");

  const block = (row, col, title, head, lines) => {
    sh.getRange(row, col).setValue(title).setFontWeight("bold").setFontSize(12);
    sh.getRange(row + 1, col, 1, head.length).setValues([head]).setFontWeight("bold");
    if (lines.length) sh.getRange(row + 2, col, lines.length, head.length).setValues(lines);
    return row + 2 + Math.max(lines.length, 1) + 1;
  };
  let row = 4;

  // 1. Your lane: trending topics worth a post, grouped by lane
  row = block(row, 1, "YOUR LANE: trending topics worth a post (science, space, nature, markets, medical, tech, history)",
    ["Lane", "Topic", "World rank", "Days", "Countries", "In India?", "Headline"],
    LANES.flatMap(l => laneTopics.filter(t => t.lane === l && t.kind === "topic").slice(0, 6)
      .map(t => [t.lane, t.topic, t.rank, t.days, t.countries, String(t.country_list).split(" ").includes(HOME) ? "yes" : "", t.headline])));

  // 2. Your lane: fresh headlines from the feeds (last 3 days)
  row = block(row, 1, "YOUR LANE: fresh headlines from NASA, ISRO, science and market feeds (last 3 days)",
    ["Lane", "Headline", "Publisher", "Country", "Date", "Link"],
    LANES.flatMap(l => laneNews.filter(n => n.lane === l).slice(0, 6)
      .map(n => [n.lane, n.topic, n.publisher, n.country, n.date, n.url])));

  // 3. Worldwide top 25 and HOME country top 25 (everything, for context)
  row = block(row, 1, "Worldwide: best documentary candidates (many countries, many days)",
    ["Topic", "Lane", "Score", "Days", "Countries", "Sources", "Headline"],
    topics.slice(0, 25).map(t => [t.topic, t.lane, t.score, t.days, t.country_list, t.source_list, t.headline]));
  row = block(row, 1, HOME_NAME + ": top topics",
    ["Topic", "Lane", "Days", "Seen", "Best rank", "Sources"],
    topFor(byCountry, "country", HOME, 25).map(t => [t.topic, t.lane, t.days, t.seen, t.best_rank, t.sources]));
  const homeCities = [...new Set(byCity.filter(r => r.country === HOME).map(r => r.city))].sort();
  for (const city of homeCities) {
    row = block(row, 1, HOME_NAME + " / " + city, ["Topic", "Lane", "Days", "Seen", "Best rank", "Sources"],
      topFor(byCity, "city", city, 8).map(t => [t.topic, t.lane, t.days, t.seen, t.best_rank, t.sources]));
  }

  // Right: pickers with live QUERY formulas
  const countries = [...new Set(byCountry.map(r => r.country))].filter(Boolean).sort();
  const cities = [...new Set(byCity.map(r => r.city))].filter(Boolean).sort();
  sh.getRange("E3").setValue("Country:").setFontWeight("bold");
  sh.getRange("F3").setValue(HOME).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(countries, true).build());
  sh.getRange("E4").setValue("City:").setFontWeight("bold");
  sh.getRange("F4").setValue(cities.includes("Bangalore") ? "Bangalore" : (cities[0] || ""))
    .setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(cities, true).build());
  sh.getRange("E5").setValue("Lane:").setFontWeight("bold");
  sh.getRange("F5").setValue("space").setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(LANES, true).build());
  // By country: A country, B topic, C days, D seen, E best_rank, F peak, G sources, H lane
  sh.getRange("H3").setValue("Country picked: top 30").setFontWeight("bold");
  sh.getRange("H4").setFormula(
    '=IFERROR(QUERY(\'By country\'!A:H, "select B,H,C,D,E,G where A = \'"&F3&"\' order by C desc, D desc, E asc limit 30", 1), "no data")');
  // By city: A city, B country, C topic, D days, E seen, F best_rank, G peak, H sources, I lane
  sh.getRange("O3").setValue("City picked: top 30").setFontWeight("bold");
  sh.getRange("O4").setFormula(
    '=IFERROR(QUERY(\'By city\'!A:I, "select C,I,D,E,F,H where A = \'"&F4&"\' order by D desc, E desc, F asc limit 30", 1), "no data")');
  // Lane picked, in the country picked: trending topics (Lane topics: A rank, B topic, L country_list, Q lane)
  sh.getRange("V3").setValue("Lane picked, trending in the country picked").setFontWeight("bold");
  sh.getRange("V4").setFormula(
    '=IFERROR(QUERY(\'Lane topics\'!A:Q, "select A,B,E,F,O where Q = \'"&F5&"\' and L contains \'"&F3&"\' order by A asc limit 30", 1), "nothing trending in this lane here")');
  sh.setColumnWidth(1, 120);
  sh.setColumnWidth(2, 340);
  sh.setColumnWidth(7, 420);
  sh.setFrozenRows(2);

  // A bar chart of the top 15 lane topics, placed to the right of the pickers
  sh.getCharts().forEach(c => sh.removeChart(c));
  const real = laneTopics.filter(t => t.kind === "topic").slice(0, 15);
  if (real.length) {
    let cs = ss.getSheetByName("_chart") || ss.insertSheet("_chart");
    cs.clearContents();
    cs.getRange(1, 1, real.length + 1, 2).setValues([["Topic", "Score"], ...real.map(t => [t.lane + ": " + t.topic, Number(t.score)])]);
    cs.hideSheet();
    const chart = sh.newChart().setChartType(Charts.ChartType.BAR)
      .addRange(cs.getRange(1, 1, real.length + 1, 2))
      .setPosition(7, 8, 0, 0).setOption("title", "Top 15 topics in your lanes, last 15 days")
      .setOption("legend", {position: "none"}).setOption("width", 700).setOption("height", 420).build();
    sh.insertChart(chart);
  }
}

// ---------- Web page (optional) ------------------------------------------------------------

function doGet() {
  return HtmlService.createHtmlOutputFromFile("Index").setTitle("Trend watch");
}

function getData() {
  // Sent as text: the sheet turns dates into Date objects, which cannot travel to the page.
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const info = (ss.getSheetByName("Info") || {getRange: () => ({getValue: () => ""})}).getRange("A1").getValue();
  // the latest fetch, only what the platform columns need (top 15 per source and place)
  const latest = table(ss, "Latest fetch").filter(r => +r.rank <= 15 &&
    ["google-trends", "youtube-suggest", "youtube", "x-trends"].includes(r.source));
  return JSON.stringify({topics: table(ss, "Topics 15 days").slice(0, 600),
          laneTopics: table(ss, "Lane topics"), laneNews: table(ss, "Lane news"),
          byCountry: table(ss, "By country"), byCity: table(ss, "By city"),
          daily: table(ss, "Daily"), latest: latest, home: HOME, lanes: LANES, updated: String(info)});
}
