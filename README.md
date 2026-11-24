# The 8PM Problem - Case Study B

A multi-tool analysis of road traffic, Namma Metro ridership, weather, and public search interest across Bengaluru, covering **October 2025 - September 2026** (13 road routes, hourly granularity).

---

## Research Question

How do commuting patterns across weekdays, Fridays and weekends influence traffic congestion in Bengaluru, and how are those patterns associated with metro ridership, weather and google trends searches for the same?

---

## Repository Layout

```
dst-1.2.0/
├── final_data/                  # Source CSVs (checked in; large files zipped)
│   ├── traffic_bangalore_clean_2025-10_2026-09.csv
│   ├── bengaluru_13_routes_weather_aug_sep_2025.csv
│   ├── bengaluru_13_routes_weather_oct_2025_sep_2026.csv
│   ├── hourly_station_entry_exit.csv
│   ├── Metro_dailyticket_Aug25_Nov26.csv
│   ├── bengaluru_holiday_festival_calendar.csv
│   ├── trends_daily_traffic.csv
│   └── trends_daily_metro.csv
│
├── excel/                       # Excel pivot tables and workbooks
│   ├── Bengaluru_Traffic_Analysis.xlsx
│   └── excel_pivot_values.xlsx
│
├── pandas/                      # Python/pandas analysis
│   ├── traffic_pandas_analysis.py
│   ├── weekday_hour_pivot.csv
│   ├── weekday_hour_heatmap.png
│   ├── hourly_average.csv
│   ├── weekday_average.csv
│   ├── busiest_hour_per_day.csv
│   └── excel_pandas_difference.csv  # Cross-validation vs Excel
│
├── sql/                         # MySQL schema, queries, and ERD
│   ├── sql_tables.sql
│   ├── sql_queries.sql
│   ├── bengaluru_mobility_ERD.mwb
│   └── bengaluru_mobility_ER.png
│
├── pyspark/                     # PySpark analysis and charts
│   ├── pyspark_traffic_weather.py   # Main PySpark job
│   ├── make_charts.py               # Chart generation from PySpark outputs
│   ├── heatmap_weekday_hour.csv
│   ├── heatmap_pivot.csv
│   ├── route_ranking.csv
│   ├── rain_effect_controlled.csv
│   ├── rain_effect_simple.csv
│   ├── pyspark_row_counts.csv       # Row-count audit log
│   └── charts/                      # PNG outputs from make_charts.py
│
└── themes/                      # Google Trends "related queries" analysis
    ├── text_themes.py
    ├── themes_summary.csv
    ├── themes_chart.png
    └── searched_with_*.csv          # Raw exports from Google Trends
```

---

## Data Sources

| Dataset                        | Source                      | Period              | Granularity        |
| ------------------------------ | --------------------------- | ------------------- | ------------------ |
| Road traffic (13 routes)       | Google Maps travel-time API | Oct 2025 – Sep 2026 | Hourly per route   |
| Weather (rain, temp, humidity) | Open-Meteo                  | Aug 2025 – Sep 2026 | Hourly per route   |
| Metro station ridership        | Namma Metro (BMRCL)         | Aug 2025 – Nov 2026 | Hourly per station |
| Metro daily tickets            | Namma Metro (BMRCL)         | Aug 2025 – Nov 2026 | Daily              |
| Google Trends                  | Google Trends (Karnataka)   | Oct 2025 – Nov 2026 | Daily              |
| Holiday / festival calendar    | Karnataka Govt + manual     | Oct 2025 – Sep 2026 | Daily              |

---

## Tools Used

| Tool              | Script / File                               | What it produces                                                   |
| ----------------- | ------------------------------------------- | ------------------------------------------------------------------ |
| **Excel**         | `Bengaluru_Traffic_Analysis.xlsx`           | Pivot tables, charts                                               |
| **pandas**        | `pandas/traffic_pandas_analysis.py`         | Hour × weekday pivot, heatmap, cross-validation vs Excel           |
| **MySQL**         | `sql/sql_tables.sql`, `sql/sql_queries.sql` | Normalised schema (7 tables, 5 views), 6 analytical queries        |
| **PySpark**       | `pyspark/pyspark_traffic_weather.py`        | Resampled hourly table, traffic–weather join, rain-effect analysis |
| **matplotlib**    | `pyspark/make_charts.py`                    | 5 publication-ready PNG charts                                     |
| **Google Trends** | `themes/text_themes.py`                     | Theme tagging and share-of-interest chart                          |

---

## Quickstart

> **Prerequisites:** Python 3.10+, Java 11/17/21 (for PySpark), MySQL 8+ (for SQL). Run everything from the repo root.

### 1. Install dependencies

```bash
pip install pandas matplotlib numpy pyspark openpyxl
```

### 2. pandas analysis

```bash
python pandas/traffic_pandas_analysis.py
# Outputs → pandas/
```

### 3. PySpark — traffic + weather join

```bash
python pyspark/pyspark_traffic_weather.py
# Reads  → final_data/
# Outputs → pyspark/
```

### 4. Charts

```bash
python pyspark/make_charts.py
# Reads  → pyspark/
# Outputs → pyspark/charts/
```

### 5. Google Trends theme analysis

```bash
python themes/text_themes.py themes/ themes/output traffic
# Reads  → themes/searched_with_*.csv
# Outputs → themes/output/
```

### 6. SQL

Load `sql/sql_tables.sql` then `sql/sql_queries.sql` into MySQL Workbench (schema: `bengaluru_mobility`). Import the CSVs from `final_data/` using MySQL's Table Data Import Wizard.

---

## Key Findings (summary)

- **Double peak:** Weekday roads clog at ~8 AM and ~6–7 PM; Sundays stay consistently below 1.5× free-flow travel time.
- **Friday effect:** Friday mornings are lighter than Mon–Thu, but Friday evenings run busier past 7 PM.
- **Rain confounding:** Raw data overstates the rain effect — once hour, day-type, and month are held constant, light rain adds only ~0.01–0.02 to the congestion index vs the raw gap of ~0.1+.
- **Most congested routes:** Silk Board and Hebbal corridors rank highest by z-score.
- **Search behaviour:** "Fines / challans" and "Congestion / live traffic" dominate top-search interest; rising searches spike around new metro line inauguration news.

---

## Notes

- `row_status = 'observed'` rows are real readings. Interpolated and `missing_hour` rows are excluded from all averages.
- Weather was fetched with `timezone=Asia/Kolkata`; a time-zone sanity check (average temperature peaks at ~14–15 h IST) is logged by the PySpark job.
- Rain thresholds used: Light < 2.5 mm/h, Moderate 2.5–7.6 mm/h, Heavy > 7.6 mm/h.
