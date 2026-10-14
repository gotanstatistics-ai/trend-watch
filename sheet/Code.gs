// Google Apps Script for the trend-watch sheet (optional; the IMPORTDATA formulas work without it).
// Extensions -> Apps Script -> paste -> set REPO -> run `refresh` once -> Triggers -> time-driven, hourly.
// This version pulls the CSV files itself and formats the tabs, so the sheet never shows "Loading...".
const REPO = "gotanstatistics-ai/trend-watch";
const BASE = "https://raw.githubusercontent.com/" + REPO + "/main/data/";
const TABS = {"Topics 15 days": "topics-15d.csv", "By country": "by-country.csv",
              "By city": "by-city.csv", "Latest fetch": "latest.csv"};

function refresh() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  for (const [name, file] of Object.entries(TABS)) {
    const text = UrlFetchApp.fetch(BASE + file + "?t=" + Date.now()).getContentText();
    const rows = Utilities.parseCsv(text);
    let sh = ss.getSheetByName(name) || ss.insertSheet(name);
    sh.clearContents();
    if (rows.length) sh.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
    sh.setFrozenRows(1);
    sh.getRange(1, 1, 1, rows[0] ? rows[0].length : 1).setFontWeight("bold");
  }
  let info = ss.getSheetByName("Info") || ss.insertSheet("Info");
  info.getRange("A1").setValue("Last refresh: " + new Date().toUTCString());
  info.getRange("A2").setValue("Source files: https://github.com/" + REPO + "/tree/main/data");
}
