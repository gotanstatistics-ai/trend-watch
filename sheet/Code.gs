// trend-watch Google Apps Script: pulls the CSV files from GitHub into tabs, builds a Dashboard tab,
// and serves a small web page with country and city pickers.
//
// Set up once:
//   1. New Google Sheet -> Extensions -> Apps Script.
//   2. Replace Code.gs with this file; add a file "Index.html" with sheet/Index.html.
//   3. Set REPO below if your GitHub name is different.
//   4. Run `setup` once (approve the permissions it asks for). It fills all tabs and adds an hourly refresh.
//   5. Optional web page: Deploy -> New deployment -> Web app -> "Execute as: me", "Who has access: only myself"
//      -> copy the URL and open it on your phone.
// After that the sheet refreshes itself every hour. The menu "Trend watch" has "Refresh now".

const REPO = "gotanstatistics-ai/trend-watch";
const BASE = "https://raw.githubusercontent.com/" + REPO + "/main/data/";
const TABS = {"Topics 15 days": "topics-15d.csv", "By country": "by-country.csv",
              "By city": "by-city.csv", "Daily": "topics-daily.csv", "Latest fetch": "latest.csv"};
const HOME = "IN";              // the country shown first on the dashboard
const HOME_NAME = "India";

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
  const byCountry = table(ss, "By country");
  const byCity = table(ss, "By city");
  let sh = ss.getSheetByName("Dashboard") || ss.insertSheet("Dashboard", 0);
  sh.clear();
  sh.getRange("A1").setValue("Trend watch, last 15 days").setFontSize(16).setFontWeight("bold");
  sh.getRange("A2").setValue("Updated " + new Date().toUTCString() + ". Pick a country in F3 and a city in F4; the lists on the right follow.");

  // Left: worldwide top 25 and HOME country top 25
  const block = (row, col, title, head, lines) => {
    sh.getRange(row, col).setValue(title).setFontWeight("bold").setFontSize(12);
    sh.getRange(row + 1, col, 1, head.length).setValues([head]).setFontWeight("bold");
    if (lines.length) sh.getRange(row + 2, col, lines.length, head.length).setValues(lines);
    return row + 2 + Math.max(lines.length, 1) + 1;
  };
  let row = 4;
  row = block(row, 1, "Worldwide: best documentary candidates (many countries, many days)",
    ["Topic", "Score", "Days", "Countries", "Sources", "Headline"],
    topics.slice(0, 25).map(t => [t.topic, t.score, t.days, t.country_list, t.source_list, t.headline]));
  row = block(row, 1, HOME_NAME + ": top topics",
    ["Topic", "Days", "Seen", "Best rank", "Sources"],
    topFor(byCountry, "country", HOME, 25).map(t => [t.topic, t.days, t.seen, t.best_rank, t.sources]));
  const homeCities = [...new Set(byCity.filter(r => r.country === HOME).map(r => r.city))].sort();
  for (const city of homeCities) {
    row = block(row, 1, HOME_NAME + " / " + city, ["Topic", "Days", "Seen", "Best rank", "Sources"],
      topFor(byCity, "city", city, 8).map(t => [t.topic, t.days, t.seen, t.best_rank, t.sources]));
  }

  // Right: pickers with live FILTER formulas
  const countries = [...new Set(byCountry.map(r => r.country))].filter(Boolean).sort();
  const cities = [...new Set(byCity.map(r => r.city))].filter(Boolean).sort();
  sh.getRange("E3").setValue("Country:").setFontWeight("bold");
  sh.getRange("F3").setValue(HOME).setDataValidation(
    SpreadsheetApp.newDataValidation().requireValueInList(countries, true).build());
  sh.getRange("E4").setValue("City:").setFontWeight("bold");
  sh.getRange("F4").setValue(cities.includes("Bangalore") ? "Bangalore" : (cities[0] || ""))
    .setDataValidation(SpreadsheetApp.newDataValidation().requireValueInList(cities, true).build());
  sh.getRange("H3").setValue("Country picked: top 30").setFontWeight("bold");
  sh.getRange("H4").setFormula(
    '=IFERROR(QUERY(\'By country\'!A:G, "select B,C,D,E,G where A = \'"&F3&"\' order by C desc, D desc, E asc limit 30", 1), "no data")');
  sh.getRange("N3").setValue("City picked: top 30").setFontWeight("bold");
  sh.getRange("N4").setFormula(
    '=IFERROR(QUERY(\'By city\'!A:H, "select C,D,E,F,H where A = \'"&F4&"\' order by D desc, E desc, F asc limit 30", 1), "no data")');
  sh.setColumnWidth(1, 320);
  sh.setColumnWidth(6, 420);
  sh.setFrozenRows(2);

  // A bar chart of the top 15 real topics, placed to the right of the pickers
  sh.getCharts().forEach(c => sh.removeChart(c));
  const real = topics.filter(t => t.kind === "topic").slice(0, 15);
  if (real.length) {
    let cs = ss.getSheetByName("_chart") || ss.insertSheet("_chart");
    cs.clearContents();
    cs.getRange(1, 1, real.length + 1, 2).setValues([["Topic", "Score"], ...real.map(t => [t.topic, Number(t.score)])]);
    cs.hideSheet();
    const chart = sh.newChart().setChartType(Charts.ChartType.BAR)
      .addRange(cs.getRange(1, 1, real.length + 1, 2))
      .setPosition(6, 8, 0, 0).setOption("title", "Top 15 topics, last 15 days")
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
          byCountry: table(ss, "By country"), byCity: table(ss, "By city"),
          daily: table(ss, "Daily"), latest: latest, home: HOME, updated: String(info)});
}
