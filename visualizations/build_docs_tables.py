#!/usr/bin/env python3
"""
Data inventory, V profile and source register for the Bengaluru commuting case study.

Usage:  python charting/build_docs_tables.py
Reads every file in final_data/ and writes three CSVs to charting/out/:
  data_inventory.csv   one row per field: level of measurement, structure, counts
  v_profile.csv        one row per table: rows, MB, arrival rate, format, dominant V
  source_register.csv  one row per source: URL, access date, method, terms of use
Counts (rows, MB, nulls, distinct values, date ranges) are computed here, not typed in.
The level of measurement for each field is a judgement, set in LEVEL below.
buildxlsx.py adds the three CSVs to cleaning_log.xlsx as extra sheets.
"""
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE.parent / "final_data"
OUT = BASE / "out"
OUT.mkdir(parents=True, exist_ok=True)

TABLES = {  # table -> (file, read options, source id, grain, time column)
    "traffic":        ("traffic_bangalore_clean_2025-10_2026-09.csv", {}, "S1", "route x hour", "hour_ist"),
    "weather_aug_sep": ("bengaluru_13_routes_weather_aug_sep_2025.csv", {}, "S2", "route x hour", "timestamp"),
    "weather_oct_sep": ("bengaluru_13_routes_weather_oct_2025_sep_2026.csv", {}, "S2", "route x hour", "timestamp"),
    "metro_hourly":   ("hourly_station_entry_exit.csv", {"sep": ";"}, "S3", "station x hour", "Date"),
    "metro_daily":    ("Metro_dailyticket_Aug25_Nov26.csv", {}, "S4", "day", "Record Date"),
    "trends_traffic": ("trends_daily_traffic.csv", {}, "S5", "day", "date"),
    "trends_metro":   ("trends_daily_metro.csv", {}, "S5", "day", "date"),
    "calendar":       ("bengaluru_holiday_festival_calendar.csv", {"encoding": "utf-8-sig"}, "S6", "day", "calendar_date"),
}

# ---------------------------------------------------------------- level of measurement (judgement)
N, O, D, C = "Nominal", "Ordinal", "Discrete", "Continuous"
LEVEL = {
    # identifiers, names, labels, links
    **{k: N for k in ["route_code", "route_name", "origin_name", "dest_name", "origin_code", "dest_code",
                      "accuweather_station", "map_link", "route", "weather_location", "Station", "term",
                      "holiday_name", "festival_name", "source_note", "row_status", "qa_flag", "rain_status",
                      "weather_code", "rsi_flag", "Traffic Band"]},
    # yes/no flags are nominal (two categories)
    **{k: N for k in ["is_weekend", "flag_spike", "is_second_saturday", "is_fourth_saturday", "is_public_holiday",
                      "is_karnataka_govt_general_holiday", "is_long_weekend"]},
    # ordered categories and positions in time
    **{k: O for k in ["weekday", "day_of_week", "Day of Week", "day_type", "time_band", "month", "month_name",
                      "weekday_num", "hour", "Hour", "date", "Date", "Record Date", "calendar_date",
                      "hour_ist", "timestamp", "scraped_at_ist"]},
    # counts
    **{k: D for k in ["Ridership", "Exits", "gap_len_h", "relative_humidity_2m", "humidity", "aqi",
                      "Total Smart Cards", "Stored Value Card", "One Day Pass", "Three Day Pass", "Five Day Pass",
                      "Total QR", "QR NammaMetro", "QR WhatsApp", "QR Paytm", "QR ONDC", "Total Tokens",
                      "Total NCMC", "Group Ticket", "Total"]},
    # measurements
    **{k: C for k in ["duration_min", "distance_km", "speed_kmph", "freeflow_min", "congestion_index", "duration_z",
                      "duration_minmax", "temp", "realfeel", "apparent_temperature", "temperature_2m",
                      "precipitation", "rain", "interest_index", "interest_z", "interest_minmax"]},
}
NOTE = {
    "hour": "0-23; ordered and interval-like, treated as ordinal for grouping",
    "Hour": "0-23; ordered and interval-like, treated as ordinal for grouping",
    "weather_code": "WMO weather code: a number, but each value names a category",
    "relative_humidity_2m": "Whole-number %, so stored as discrete; physically continuous",
    "interest_index": "0-100 relative index; Google gives whole numbers but this file has decimals (cleaning log G2)",
    "Traffic Band": "Label from the tracker; order unclear (cleaning log D3)",
    "hour_ist": "Timestamp; interval scale, used here as an ordered time key",
    "timestamp": "Timestamp; interval scale, used here as an ordered time key",
}
UNSTRUCTURED = {"map_link", "source_note"}  # free text / URL inside a structured table

inv, prof = [], []
for tbl, (fname, opts, src, grain, tcol) in TABLES.items():
    path = DATA / fname
    df = pd.read_csv(path, low_memory=False, **opts)
    for col in df.columns:
        s = df[col]
        lvl = LEVEL.get(col)
        assert lvl, f"no level of measurement set for {tbl}.{col}"
        structure = "Unstructured (free text / URL)" if col in UNSTRUCTURED else (
            "Semi-structured (text that packs several values)" if col in {"qa_flag", "route_code", "hour_ist", "scraped_at_ist"} else "Structured")
        inv.append(dict(Table=tbl, File=fname, Field=col, Pandas_type=str(s.dtype), Level=lvl, Structure=structure,
                        Non_null=int(s.notna().sum()), Null_pct=round(100 * s.isna().mean(), 1),
                        Distinct=int(s.nunique()), Example=str(s.dropna().iloc[0])[:60] if s.notna().any() else "",
                        Note=NOTE.get(col, "")))
    t = pd.to_datetime(df[tcol].astype(str).str[:19], errors="coerce")
    days = int(t.dt.normalize().nunique())
    span = (t.min().normalize(), t.max().normalize())
    prof.append(dict(Table=tbl, File=fname, Source_id=src, Grain=grain, Rows=len(df), Columns=df.shape[1],
                     Size_MB=round(path.stat().st_size / 1e6, 2), First_date=f"{span[0]:%Y-%m-%d}", Last_date=f"{span[1]:%Y-%m-%d}",
                     Days_with_data=days, Rows_per_day=round(len(df) / days, 1),
                     MB_per_month=round(path.stat().st_size / 1e6 / (days / 30.4), 3),
                     Format="CSV, ';'-separated" if opts.get("sep") == ";" else "CSV, ','-separated" + (" (UTF-8 BOM)" if "encoding" in opts else "")))

inv = pd.DataFrame(inv)
prof = pd.DataFrame(prof)

# arrival rate and dominant V (judgement, using the counts above)
ARRIVAL = {
    "traffic": "Hourly scrape, 13 readings per hour (one per route)",
    "weather_aug_sep": "Hourly, 13 rows per hour; pulled once as a historical batch",
    "weather_oct_sep": "Hourly, 13 rows per hour; pulled once as a historical batch",
    "metro_hourly": "Hourly per station; released in one RTI batch",
    "metro_daily": "Daily, but published irregularly by BMRCL (gaps of several days)",
    "trends_traffic": "Daily index; downloaded once as a batch",
    "trends_metro": "Daily index; downloaded once as a batch",
    "calendar": "Static; compiled once from the yearly government notifications",
}
def dominant(r):
    if r.Table == "traffic":
        return "Volume + Velocity: largest table (most rows and MB), arriving every hour from a live scrape"
    if r.Table.startswith("weather"):
        return "Volume: one row per route per hour (13 x 24 = 312 rows a day)"
    if r.Table == "metro_hourly":
        return "Variety: semicolon format, station names with commas, entries and exits merged from two files"
    if r.Table == "metro_daily":
        return "Veracity: missing days, Total QR not matching its channels, one duplicated and one typo row"
    if r.Table.startswith("trends"):
        return "Veracity: relative 0-100 index, rescaled (non-integer values); not a count of trips"
    return "Variety: hand-compiled from government notifications and festival lists"
prof["Arrival_rate"] = prof.Table.map(ARRIVAL)
prof["Dominant_V"] = prof.apply(dominant, axis=1)
prof["Share_of_all_rows_pct"] = (100 * prof.Rows / prof.Rows.sum()).round(1)
prof = prof[["Table", "File", "Source_id", "Grain", "Rows", "Columns", "Size_MB", "Share_of_all_rows_pct", "First_date", "Last_date",
             "Days_with_data", "Rows_per_day", "MB_per_month", "Arrival_rate", "Format", "Dominant_V"]]

# ---------------------------------------------------------------- source register
# Access date = when the file was first committed to this repo (from git log); change it if you downloaded earlier.
# "TO FILL" = not recorded anywhere in the repo; do not guess.
cal = pd.read_csv(DATA / TABLES["calendar"][0], encoding="utf-8-sig")
cal_notes = "; ".join(sorted(cal.source_note.dropna().unique()))
reg = pd.DataFrame([
    dict(Source_id="S1", Source="Google Maps travel times (13 routes)", Tables="traffic",
         URL="https://www.google.com/maps (one maps.app.goo.gl link per route is stored in the map_link column)",
         Access_date="Scraped hourly 2025-10-01 to 2026-09-30; committed 2026-11-21",
         Method="Automated scraper: Google Maps duration and distance for each route every hour (scraped_at_ist), then cleaned upstream (gaps up to 3 h interpolated, qa_flag added)",
         Terms_of_use="Google Maps Platform / Google Terms of Service. Automated scraping of Google Maps is not permitted under these terms; academic use only, raw pages not redistributed.",
         Licence_or_owner="Google LLC", Status="Scraper script and its exact run dates: TO FILL"),
    dict(Source_id="S2", Source="Open-Meteo historical weather (one point per route)", Tables="weather_aug_sep, weather_oct_sep",
         URL="https://archive-api.open-meteo.com/v1/archive", Access_date="Committed 2026-11-22",
         Method="HTTP API, hourly variables temperature_2m, apparent_temperature, relative_humidity_2m, precipitation, rain, weather_code; timezone Asia/Kolkata",
         Terms_of_use="Free for non-commercial use; data licensed CC BY 4.0, attribution to Open-Meteo.com required",
         Licence_or_owner="CC BY 4.0 (Open-Meteo)", Status="Exact access date: TO FILL"),
    dict(Source_id="S3", Source="Namma Metro hourly station entries and exits (RTI)", Tables="metro_hourly",
         URL="TO FILL (GitHub repository that hosts the RTI release)", Access_date="Committed 2026-11-22",
         Method="Downloaded CSVs released under an RTI request to BMRCL; entries and exits merged on Date, Hour, Station",
         Terms_of_use="Open Database Licence (ODbL) as stated by the hosting repository; attribution and share-alike",
         Licence_or_owner="ODbL; data owner BMRCL", Status="Repository URL: TO FILL"),
    dict(Source_id="S4", Source="BMRCL daily ridership by ticket type", Tables="metro_daily",
         URL="TO FILL (BMRCL daily ridership posts / tracker CSV used)", Access_date="Committed 2026-11-22",
         Method="Daily figures compiled from BMRCL's published ridership updates into a tracker CSV; dates converted to ISO",
         Terms_of_use="Public government data; no explicit licence found. Cite BMRCL.",
         Licence_or_owner="BMRCL", Status="URL and licence: TO FILL"),
    dict(Source_id="S5", Source="Google Trends daily interest", Tables="trends_traffic, trends_metro",
         URL="https://trends.google.com/trends/explore?geo=IN-KA (terms 'bangalore traffic', 'bangalore metro')", Access_date="Committed 2026-11-21",
         Method="Trends export (or pytrends) for each term; series stitched/rescaled to daily (non-integer values), z-score and min-max added",
         Terms_of_use="Google Terms of Service; Trends data may be used and cited with attribution to Google Trends",
         Licence_or_owner="Google LLC", Status="Download method and stitching rule: TO FILL"),
    dict(Source_id="S6", Source="Bengaluru holiday and festival calendar", Tables="calendar",
         URL="https://dpar.karnataka.gov.in (Karnataka DPAR holiday notifications 2025 and 2026)", Access_date="Committed 2026-11-22",
         Method=f"Compiled by hand from the notifications; source_note values in the file: {cal_notes}",
         Terms_of_use="Government notification, public domain information",
         Licence_or_owner="Government of Karnataka", Status="Confirmed from the file's source_note column"),
])

inv.to_csv(OUT / "data_inventory.csv", index=False)
prof.to_csv(OUT / "v_profile.csv", index=False)
reg.to_csv(OUT / "source_register.csv", index=False)
print(f"data_inventory: {len(inv)} fields in {inv.Table.nunique()} tables")
print(inv.groupby(["Level"]).size().to_string())
print(prof[["Table", "Rows", "Size_MB", "Rows_per_day", "Dominant_V"]].to_string(index=False))
