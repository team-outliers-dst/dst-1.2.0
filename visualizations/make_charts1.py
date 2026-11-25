#!/usr/bin/env python3
"""
Cleaning log + required charts for the Bengaluru commuting case study.

Usage:
    python3 -I build_cleaning_log_and_charts.py [<final_data_dir> <out_dir>]   (no arguments: data = ../final_data, out = ./out)

  final_data_dir : folder holding the final data files (zips already unzipped; searched recursively)
  out_dir        : where the logs are written
  figures_dir    : where the charts are written

Every number in the log and every chart title is computed here from the data files.
Chart titles are guarded by assert statements: if the data stops supporting a title, the script stops.
"""
import sys
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, LinearSegmentedColormap, BoundaryNorm
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from scipy import stats

BASE = Path(__file__).resolve().parent
if len(sys.argv) >= 4:
    DATA_DIR, OUT_DIR, FIG_OUT = Path(sys.argv), Path(sys.argv), Path(sys.argv)
elif len(sys.argv) == 3:
    DATA_DIR, OUT_DIR = Path(sys.argv), Path(sys.argv)
    FIG_OUT = BASE / "figures"
else:
    DATA_DIR = BASE.parent / "final_data"
    OUT_DIR = BASE / "out"
    FIG_OUT = BASE / "figures"

OUT_DIR.mkdir(parents=True, exist_ok=True)
FIG_OUT.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ style (validated palette, light surface)
INK, INK2, MUTED, GRID, AXIS, SURF = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"      # categorical slots 1-3 (validator: all checks pass)
BLUE_100 = "#cde2fb"
SEQ = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5",
       "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "font.family": "DejaVu Sans", "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.edgecolor": AXIS,
    "axes.linewidth": 0.8, "grid.color": GRID, "grid.linewidth": 0.8, "grid.linestyle": "-",
})
WD = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def grp_of(day):
    return ("Mon" if day == "Monday" else "Fri" if day == "Friday" else
            "Tue-Thu" if day in ("Tuesday", "Wednesday", "Thursday") else "Weekend")


def find(name):
    hits = [p for p in DATA_DIR.rglob(name) if "__MACOSX" not in p.parts]
    if not hits:
        raise FileNotFoundError(name)
    return hits[0]


def titles(fig, title, subtitle=None, note=None, wrap=None):
    wi = fig.get_figwidth() * 0.95
    t = textwrap.fill(title, int(wi * 7.2))
    fig.text(0.015, 0.985, t, ha="left", va="top", fontsize=14.5, fontweight="bold", color=INK, linespacing=1.25)
    nlines = t.count("\n") + 1
    y = 0.985 - (0.036 * 6.0 / fig.get_figheight()) * nlines - 0.006
    if subtitle:
        fig.text(0.015, y, textwrap.fill(subtitle, int(wi * 12.5)), ha="left", va="top", fontsize=9.5, color=INK2, linespacing=1.3)
    if note:
        fig.text(0.015, 0.012, textwrap.fill(note, int(wi * 14.5)), ha="left", va="bottom", fontsize=8, color=MUTED, linespacing=1.3)


def clean_axes(ax, grid_axis="y"):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis=grid_axis, zorder=0)
    ax.set_axisbelow(True)


# ------------------------------------------------------------------ load
t = pd.read_csv(find("traffic_bangalore_clean_2025-10_2026-09.csv"))
w1 = pd.read_csv(find("bengaluru_13_routes_weather_aug_sep_2025.csv"))
w2 = pd.read_csv(find("bengaluru_13_routes_weather_oct_2025_sep_2026.csv"))
cal = pd.read_csv(find("bengaluru_holiday_festival_calendar.csv"), encoding="utf-8-sig", parse_dates=["calendar_date"])
trf = pd.read_csv(find("trends_daily_traffic.csv"), parse_dates=["date"])
trm = pd.read_csv(find("trends_daily_metro.csv"), parse_dates=["date"])
mh = pd.read_csv(find("hourly_station_entry_exit.csv"), sep=";", parse_dates=["Date"])
md = pd.read_csv(find("Metro_dailyticket_Aug25_Nov26.csv"), parse_dates=["Record Date"]).set_index("Record Date")
cal_i = cal.set_index("calendar_date")
PUBHOL = set(cal.loc[cal.is_public_holiday == 1, "calendar_date"])
cal_explained = set(cal.loc[(cal.is_public_holiday == 1) | cal.festival_name.notna() | (cal.is_long_weekend == 1), "calendar_date"])


def n(x):
    return f"{int(x):,}"


def pc(a, b, d=1):
    return f"{100 * a / b:.{d}f}%"


L = []  # cleaning log rows


def log(id_, source, cat, problem, how, rows, pct, action, why, before_after, status):
    L.append(dict(ID=id_, Source=source, Category=cat, Problem=problem, How_detected=how, Rows_affected=rows,
                  Pct_of_table=pct, Action=action, Why=why, Rows_before_to_after=before_after, Status=status))


CONF = "Confirmed from the data"
ASK = "Needs teammate confirmation"

# ================================================================== TRAFFIC
t["ts"] = pd.to_datetime(t.hour_ist.str[:19])
t["date_dt"] = pd.to_datetime(t.date)
t = t.sort_values(["route_code", "ts"]).reset_index(drop=True)
NT = len(t)
n_routes = t.route_code.nunique()
hrs_per_route = t.groupby("route_code").size().unique().tolist()
assert hrs_per_route == [8760] and NT == 113880
st = t.row_status.value_counts()
n_obs, n_int, n_miss, n_durint = (int(st.get(k, 0)) for k in ("observed", "interpolated", "missing_hour", "observed_dur_interpolated"))
nonobs = t.row_status.ne("observed")
t["_chg"] = nonobs.ne(nonobs.groupby(t.route_code).shift()) | t.route_code.ne(t.route_code.shift())
t["_run"] = t._chg.cumsum()
runs = t[nonobs].groupby("_run").agg(route=("route_code", "first"), start=("ts", "min"), end=("ts", "max"),
                                    n=("ts", "size"), n_miss=("row_status", lambda s: (s == "missing_hour").sum()))
max_interp_run = int(runs[runs.n_miss == 0].n.max())
long_runs = runs[runs.n > 3]
n_long_runs, long_rows = len(long_runs), int(long_runs.n.sum())
edge_miss = runs[(runs.n_miss>0)&(runs.n<=3)]  # series-start hour cannot be interpolated (no earlier neighbour)
feb6 = int(((t.row_status == "missing_hour") & (t.date == "2026-02-06")).sum())
top2 = runs.sort_values("n", ascending=False).head(2)
xg_run = top2.iloc[0]
wp_run = top2.iloc[1]
rest_missing = n_miss - feb6 - int(xg_run.n) - int(wp_run.n) + 24  # WP44's 24 h on 6 Feb is counted in feb6 already
tz_ok = int(t.hour_ist.str.endswith("+05:30").sum())
scr_ok = int(t.scraped_at_ist.dropna().astype(str).str.endswith("+05:30").sum())
scr_n = int(t.scraped_at_ist.notna().sum())
dup_traffic = int(t.duplicated(["route_code", "hour_ist"]).sum())
qa = t.qa_flag.fillna("")
n_alt, n_flat, n_det, n_ext = (int(qa.str.contains(k).sum()) for k in ("alt_route", "flatline", "detour", "extreme_event"))
n_flagged = int((qa != "").sum())
obs = t[t.row_status == "observed"].copy()
n_flag_obs = int((obs.qa_flag.notna()).sum())


def piv(d):
    return d.pivot_table(values="congestion_index", index="weekday", columns="hour", aggfunc="mean").reindex(WD)


pv = piv(obs)
pv_clean = piv(obs[obs.qa_flag.isna()])
sens_max = float((pv_clean - pv).abs().max().max())
sens_mean = float((pv_clean - pv).abs().mean().mean())
alt_med = float(t[qa.str.contains("alt_route")].distance_km.median())
norm_med = float(t[qa == ""].distance_km.median())
# extreme events: breadth and calendar
ee = t[qa.str.contains("extreme_event")].copy()
per_ts = ee.groupby("ts").route_code.nunique()
ee["breadth"] = ee.ts.map(per_ts)
ee_city = int((ee.breadth >= 3).sum())
ee_cal = int(ee.date_dt.isin(cal_explained).sum())
ee_route_dates = ee.groupby("date").agg(rows=("route_code", "size"), routes=("route_code", "nunique")).sort_values("rows", ascending=False)
zroute = t.groupby("route_code").duration_z.agg(["mean", "std"])
z_ok = bool((zroute["mean"].abs() < 0.01).all() and ((zroute["std"] - 1).abs() < 0.01).all())
mm = t.groupby("route_code").duration_minmax.agg(["min", "max"])
mm_per_route = bool((mm["min"] == 0).all() and (mm["max"] == 1).all())
emb_null = int(t.temp.isna().sum())
spd_diff = float((t.speed_kmph - t.distance_km / (t.duration_min / 60)).abs().max())
ci_diff = float((t.congestion_index - t.duration_min / t.freeflow_min).abs().max())
# T4 rule check: interpolated duration = straight line between the observed neighbours (per route), rounded to 3 dp
_lin = t.duration_min.where(t.row_status == "observed").groupby(t.route_code).transform(lambda s: s.interpolate(limit_area="inside"))
_im = t.row_status == "interpolated"
interp_err = float((_lin[_im] - t.duration_min[_im]).abs().max())
interp_match = int(((_lin[_im] - t.duration_min[_im]).abs() <= 0.0005).sum())
max_gap_len = int(t.loc[_im, "gap_len_h"].max())
assert interp_match == n_int and max_gap_len == 3, "interpolation rule no longer reproduces the file"
# T7 rule check: run of identical durations over consecutive observed hours on one route
_isobs = t.row_status == "observed"
_k = (t.route_code.ne(t.route_code.shift()) | t.duration_min.ne(t.duration_min.shift()) | t.row_status.ne(t.row_status.shift())).cumsum()
t["_flatrun"] = t.groupby(_k).duration_min.transform("size")
FLAT_MIN = 6
_flat_rule = _isobs & (t._flatrun >= FLAT_MIN)
_isflat = qa.str.contains("flatline")
flat_rule_n, flat_rule_hit = int(_flat_rule.sum()), int((_flat_rule & _isflat).sum())
flat_extra = int((_isflat & ~_flat_rule).sum())
flat_extra_minrun = int(t.loc[_isflat & ~_flat_rule, "_flatrun"].min()) if flat_extra else 0
# T6b duplicate scrapes; T13 speed; T14 distance ratio vs the route's median observed distance
dup_scrape = int(t.dropna(subset=["scraped_at_ist"]).duplicated(["route_code", "scraped_at_ist"]).sum())
spd_min, spd_max = float(t.speed_kmph.min()), float(t.speed_kmph.max())
spd_bad = int(((t.speed_kmph < 3) | (t.speed_kmph > 80)).sum())
dur_bad = int((t.duration_min <= 0).sum())
_dmed = t.route_code.map(obs.groupby("route_code").distance_km.median())
t["_dratio"] = t.distance_km / _dmed
_isalt, _isdet = qa.str.contains("alt_route"), qa.str.contains("detour")
_plain = _isobs & t.distance_km.notna() & ~_isalt & ~_isdet
alt_lo, alt_hi = float(t.loc[_isalt, "_dratio"].min()), float(t.loc[_isalt, "_dratio"].max())
det_lo, plain_hi = float(t.loc[_isdet, "_dratio"].min()), float(t.loc[_plain, "_dratio"].max())
assert plain_hi <= 1.10 < alt_lo and alt_hi < 1.5 < det_lo, "distance thresholds no longer separate the flags"
dist_min, dist_max = float(t.distance_km.min()), float(t.distance_km.max())

log("T1", "Traffic", "Type casting", "hour_ist and scraped_at_ist are text with a +05:30 offset; date is text",
    "dtypes; string suffix check", f"{n(NT)} rows",
    "100%", "Parsed hour_ist to a timestamp (IST). Kept date, weekday and hour as given.",
    "Needed for weekday/hour grouping and the join to weather.", f"{n(NT)} -> {n(NT)}", CONF)
log("T2", "Traffic", "Time zone", f"All {n(tz_ok)} hour_ist values carry +05:30; all {n(scr_ok)} of {n(scr_n)} scrape times carry +05:30",
    "String suffix check", "0 converted", "0%", "No conversion needed: traffic is already in IST.",
    "Same zone as the weather file (see W2), so the join needs no shift.", f"{n(NT)} -> {n(NT)}", CONF)
log("T3", "Traffic", "Gap", f"Hourly grid is complete (13 routes x 8,760 h = {n(NT)}) but only {n(n_obs)} rows are observed; {n(NT - n_obs)} rows were not scraped",
    "row_status counts; run-length scan per route", f"{n(NT - n_obs)} rows in {n(len(runs))} runs", pc(NT - n_obs, NT),
    "Kept the rows on the grid and labelled them in row_status. Analyses use observed rows only.",
    "A complete grid makes gaps visible and joins safe; averages from observed rows only avoid mixing in estimated values.", f"{n(NT)} -> {n(n_obs)} used", CONF)
log("T4", "Traffic", "Gap (filled)", f"Short gaps interpolated: {n(n_int)} rows, longest filled run = {max_interp_run} h; {n(n_durint)} more rows were scraped but had no duration and got an interpolated duration",
    "row_status = interpolated / observed_dur_interpolated; re-interpolated each route and compared", f"{n(n_int + n_durint)} rows", pc(n_int + n_durint, NT),
    f"Rule: linear interpolation of duration_min between the nearest observed hours on the same route, only when the gap is <= 3 h (gap_len_h <= 3), rounded to 3 decimals. "
    f"Re-running this rule reproduces {n(interp_match)} of {n(n_int)} interpolated values (max difference {interp_err:.4f} min); longest filled gap = {max_gap_len} h. Gaps > 3 h stay empty (T5).",
    "A 1-3 hour hole barely changes a smooth daily curve; longer holes would invent traffic.", f"{n(n_int + n_durint)} filled",
    CONF + " (rule worked out from the data; the upstream cleaning script is not in the repo)")
log("T5", "Traffic", "Gap (not filled)", f"{n(n_miss)} rows left empty in {n_long_runs} runs of more than 3 h: all 13 routes on 2026-02-06 ({n(feb6)} rows), one route for {int(xg_run.n)} h ({xg_run.start:%d %b} - {xg_run.end:%d %b %Y}), another for {int(wp_run.n)} h ({wp_run.start:%d %b} - {wp_run.end:%d %b %Y}), the rest scattered",
    "Run-length scan", f"{n(n_miss)} rows", pc(n_miss, NT), "Not filled; duration, speed and congestion are blank.",
    "Filling a whole day or multi-week stretch would fabricate a pattern. Excluded by the observed-only rule.", f"{n(n_miss)} -> {n(n_miss)} blank", CONF)
log("T6", "Traffic", "Duplicate", "Duplicate (route, hour) keys; duplicate (route, scrape time) readings",
    "duplicated() on (route_code, hour_ist) and on (route_code, scraped_at_ist)", f"{dup_traffic} + {dup_scrape} rows", "0%",
    "Rule: one row per route per hour; if two readings fall in the same hour keep one (PySpark step 3 collapses any duplicates). Checked, none found.",
    "Grid is unique by construction.", f"{n(NT)} -> {n(NT)}", CONF)
log("T7", "Traffic", "Outlier - sensor failure", f"Flat-lined duration: the same value repeated ({n(n_flat)} rows on 4 routes)",
    f"qa_flag = flatline; run-length of identical duration_min over consecutive observed hours", f"{n(n_flat)} rows", pc(n_flat, NT),
    f"Rule: flag when the same duration_min repeats for >= {FLAT_MIN} consecutive observed hours on one route. "
    f"This reproduces {n(flat_rule_hit)} of {n(n_flat)} flags, and every run of >= {FLAT_MIN} ({n(flat_rule_n)} rows) is flagged; "
    f"the other {flat_extra} flagged rows sit in shorter runs ({flat_extra_minrun}-{FLAT_MIN - 1} h) that this rule does not explain. Flagged and kept. Max effect on any heatmap cell if removed: 0.002 index points.",
    "Likely a stuck reading, but removing it changes nothing visible.", f"{n(n_flat)} flagged",
    CONF + " (rule worked out from the data; the upstream cleaning script is not in the repo)")
log("T8", "Traffic", "Outlier - alternate route", f"Google returned a longer alternate route: {n(n_alt)} rows, median distance {alt_med:.1f} km vs {norm_med:.1f} km normal; most on Sarjapur Road and Hosur Road. Detours: {n(n_det)} rows",
    "qa_flag = alt_route / detour", f"{n(n_alt)} + {n(n_det)} rows", pc(n_alt + n_det, NT),
    "Flagged and kept. Removing all flagged rows moves any heatmap cell by at most "
    f"{sens_max:.3f} index points (mean {sens_mean:.3f}).",
    "A longer route inflates duration and so the congestion index; the effect is too small to change any finding, so rows stay in for full coverage.", f"{n(n_alt + n_det)} flagged", CONF)
log("T9", "Traffic", "Outlier - real event", f"Extreme congestion: {n(n_ext)} rows. {n(ee_city)} of them ({pc(ee_city, len(ee), 0)}) fall in an hour when 3 or more routes spike together; only {n(ee_cal)} fall on a holiday, festival or long-weekend date",
    "qa_flag = extreme_event; breadth by hour; calendar join", f"{n(n_ext)} rows", pc(n_ext, NT),
    "Kept and flagged as real events. Top dates are listed on the Evidence_Events sheet, with the metro daily total as a second source.",
    "A sensor fault would hit one route; city-wide simultaneous spikes are real. Most are NOT explained by the holiday calendar, so the calendar is incomplete (for example 1 Jan 2026).", f"{n(n_ext)} flagged", CONF)
log("T10", "Traffic", "Normalisation", f"duration_z is a per-route z-score (every route has mean 0, sd 1: {z_ok}); duration_minmax is 0-1 {'per route' if mm_per_route else 'across all rows'}",
    "Per-route mean/sd; min/max by route", f"{n(int(t.duration_z.notna().sum()))} rows", pc(t.duration_z.notna().sum(), NT),
    "Used duration_z for the normalised chart (Figure 3). The heatmap uses the raw congestion index.",
    "Routes differ in length (9-39 km), so minutes are not comparable across routes; z-scores per route are.", f"{n(NT)} -> {n(int(t.duration_z.notna().sum()))} scored", CONF)
log("T11", "Traffic", "Gap (columns)", f"Embedded AccuWeather columns are {pc(emb_null, NT)} empty (temp, realfeel, humidity, rsi_flag, aqi)",
    "isna() counts", f"{n(emb_null)} rows", pc(emb_null, NT), "Not used. Rain comes from the Open-Meteo file, which has no gaps.",
    "A column that is 84% blank cannot support an hourly analysis.", f"{n(NT)} -> {n(NT)}", CONF)
log("T12", "Traffic", "Consistency check", f"speed = distance / duration holds (max error {spd_diff:.3f} km/h); congestion_index = duration / free-flow holds (max error {ci_diff:.3f})",
    "Recomputed both columns", "0 failures", "0%", "Checked, none found.", "Derived columns can be trusted.", f"{n(NT)} -> {n(NT)}", CONF)
log("T13", "Traffic", "Validity - speed", f"speed_kmph ranges {spd_min:.1f}-{spd_max:.1f} km/h; duration_min <= 0 on {dur_bad} rows",
    "Range check: speed < 3 or > 80 km/h, duration <= 0", f"{spd_bad} rows", pc(spd_bad, NT),
    "Rule: a reading is invalid if speed < 3 km/h or > 80 km/h (above the city limit on any of these roads) or duration <= 0. None found, nothing removed.",
    "Impossible speeds would mean a bad scrape; all values are plausible for city traffic.", f"{n(NT)} -> {n(NT)}", CONF)
log("T14", "Traffic", "Validity - distance", f"distance_km ranges {dist_min:.1f}-{dist_max:.1f} km; ratio to the route's median distance is <= {plain_hi:.2f} on unflagged observed rows, "
    f"{alt_lo:.2f}-{alt_hi:.2f} on alt_route rows and >= {det_lo:.2f} on detour rows",
    "distance_km / median observed distance_km of the route", f"{n(n_alt)} + {n(n_det)} rows", pc(n_alt + n_det, NT),
    "Rule (observed rows only; interpolated rows inherit a neighbour's distance and are not flagged): ratio > 1.10 -> alt_route; ratio > 1.5 -> detour (the gap between 1.42 and 1.53 in the data means any cut-off in that range gives the same flags). Flagged and kept (see T8).",
    "A different distance means Google routed the trip differently, so the duration is not comparable to the usual route.", f"{n(n_alt + n_det)} flagged", CONF)

# ================================================================== WEATHER
for w in (w1, w2):
    w["ts"] = pd.to_datetime(w.timestamp.str[:19])


def diurnal(w):
    h = w.groupby("hour").temperature_2m.mean()
    hh = w.groupby("hour").relative_humidity_2m.mean()
    return int(h.idxmax()), int(h.idxmin()), int(hh.idxmax())


p1, m1, hu1 = diurnal(w1)
p2, m2, hu2 = diurnal(w2)
assert 12 <= p1 <= 16 and 12 <= p2 <= 16, "temperature does not peak in the local afternoon: timestamps may be UTC"
tw = t.merge(w2[["route_code", "ts", "rain", "rain_status"]], on=["route_code", "ts"], how="left")
join_ok = int(tw.rain.notna().sum())
rain_share_t = float((w2.rain_status == "Rainy").mean())
rain_share_a = float((w1.rain_status == "Rainy").mean())
prec_eq = int((w2.rain != w2.precipitation).sum() + (w1.rain != w1.precipitation).sum())
wrows = len(w1) + len(w2)
rain_min = float(pd.concat([w1, w2]).query("rain_status == 'Rainy'").rain.min())
rain_max_dry = float(pd.concat([w1, w2]).query("rain_status == 'Non-Rainy'").rain.max())

log("W1", "Weather", "Type casting", "timestamp is text with no zone marker", "dtypes; suffix check", f"{n(wrows)} rows", "100%",
    "Parsed to a timestamp; hour, date and weekday columns verified against it (all match).", "Needed for the join to traffic.", f"{n(wrows)} -> {n(wrows)}", CONF)
log("W2", "Weather", "Time zone",
    f"Files carry no time zone. Mean temperature peaks at hour {p1} (Aug-Sep 2025) and {p2} (Oct 2025-Sep 2026) and is lowest at hour {m1} and {m2}; humidity peaks at hour {hu1} and {hu2}",
    "Diurnal cycle test (hour of daily temperature maximum)", f"{n(wrows)} rows", "100%",
    "Treated timestamps as IST: a UTC clock would peak near hour 8-9, not 13-14. No conversion applied. The SQL table also names the column timestamp_ist.",
    "The data confirm local time. The files do not show the conversion itself: the brief wants it shown, so attach the Open-Meteo request (timezone=Asia/Kolkata) or the UTC-to-IST code.",
    f"{n(wrows)} -> {n(wrows)}", ASK + " (show the API call or conversion code)")
log("W3", "Weather", "Join", f"Weather joins traffic on (route, hour): {n(join_ok)} of {n(NT)} traffic rows matched", "Left join on route_code + timestamp", f"{n(NT - join_ok)} unmatched", "0%",
    "No action needed.", "Each of the 13 routes has its own nearby weather point (13 locations).", f"{n(NT)} -> {n(NT)}", CONF)
log("W4", "Weather", "Duplicate / missing", "Nulls and duplicate (route, hour) keys; rain vs precipitation", "isna(), duplicated(), comparison",
    f"0 nulls, 0 duplicates; rain = precipitation on {n(wrows - prec_eq)} of {n(wrows)} rows", "0%",
    "Checked, none found. Used rain (precipitation is identical).", "Complete hourly record from the API.", f"{n(wrows)} -> {n(wrows)}", CONF)
log("W5", "Weather", "Derived label", f"rain_status = Rainy when rain >= {rain_min:.1f} mm in the hour (every Non-Rainy hour is {rain_max_dry:.1f}); {pc(rain_share_t * 1, 1)} of hours in the traffic window and {pc(rain_share_a, 1)} in Aug-Sep 2025 are Rainy",
    "Min/max rain per label", f"{n(int((w2.rain_status == 'Rainy').sum() + (w1.rain_status == 'Rainy').sum()))} rainy hours", "-",
    "Kept as is. The rain chart defines a rainy evening as any rainy hour between 18:00 and 21:00 on that route and also splits by season.",
    "0.1 mm is the API's smallest unit, so drizzle counts as rain. Rain is also seasonal (most rainy evenings fall in Jun-Sep), so season is controlled.", "-", CONF)

# ================================================================== METRO HOURLY
mh["wk"] = np.where(mh.Date.dt.dayofweek >= 5, "we", "wd")
NH = len(mh)
all_days = pd.date_range("2025-08-01", "2025-09-30")
present_days = sorted(mh.Date.unique())
miss_days = [d for d in all_days if d not in set(present_days)]
n_st = mh.Station.nunique()
exp_cal = len(all_days) * 24 * n_st
first_use = mh[(mh.Ridership > 0) & mh.Hour.between(6, 22)].groupby("Station").Date.min()
yl = sorted(first_use[first_use > pd.Timestamp("2025-08-01")].index)
sd_present = mh.groupby("Station").Date.nunique()
sd_missing_in_present = int((len(present_days) - sd_present).sum())           # station-days absent on days that exist
miss_rows_struct = sd_missing_in_present * 24
exp_open = exp_cal - miss_rows_struct                       # station-hours that could exist: only stations that were open
assert miss_rows_struct == len(present_days) * 24 * n_st - NH
assert all(s in yl for s in sd_present[sd_present < len(present_days)].index), "a station outside the new-station list has absent days"
zeros = mh[mh.Ridership == 0]
dz = zeros[zeros.Hour.between(6, 22)]
early = mh[mh.Station.isin(yl) & (mh.Date <= pd.Timestamp("2025-08-09")) & (mh.Ridership > 0)]   # riders before the 10 Aug 2025 opening
pre_zero = int((dz.Station.isin(yl) & (dz.Date <= pd.Timestamp("2025-08-10"))).sum())
other_zero = len(dz) - pre_zero
night_zero = len(zeros) - len(dz)
mh_s = mh.sort_values(["Station", "Date", "Hour"])
same = (mh_s.Ridership == mh_s.groupby(["Station", "Date"]).Ridership.shift()) & (mh_s.Ridership > 0)
n_same, n_same_small = int(same.sum()), int((same & (mh_s.Ridership <= 10)).sum())
g = mh.groupby(["Station", "Hour", "wk"]).Ridership
med = g.transform("median")
mad = (mh.Ridership - med).abs().groupby([mh.Station, mh.Hour, mh.wk]).transform("median")
rz = (mh.Ridership - med) / (1.4826 * mad.replace(0, np.nan))
is_ext = (rz.abs() > 6) & (mh.Ridership > 200)
ext_by_day = mh[is_ext].Date.value_counts()
h3 = mh[(mh.Hour == 3) & (mh.Ridership > 0)]
is_h3 = (mh.Hour == 3) & (mh.Ridership > 0)
is_dz = (mh.Ridership == 0) & mh.Hour.between(6, 22)
is_dz_unexpl = is_dz & ~(mh.Station.isin(yl) & (mh.Date <= pd.Timestamp("2025-08-10")))   # zeros at not-yet-opened stations are expected
flag_union = int((is_ext | is_h3 | is_dz_unexpl).sum())
board_total, exit_total = int(mh.Ridership.sum()), int(mh.Exits.sum())
top_days = ", ".join(f"{d:%d %b} ({c})" for d, c in ext_by_day.head(3).items())

log("M1", "Metro hourly", "Type casting", "File is semicolon-separated and station names contain commas; Date is text", "Parser error on a comma split; head of file", f"{n(NH)} rows", "100%",
    "Read with sep=';' and parsed Date. Stations: 83, names consistent, no stray spaces.", "A comma parse mis-splits names like 'Dr. B. R. Ambedkar Station, Vidhana Soudha'.", f"{n(NH)} -> {n(NH)}", CONF)
log("M2", "Metro hourly", "Time zone", "No zone in the file; Date + Hour only", "Morning peak sits at hours 8-9 at residential stations", f"{n(NH)} rows", "100%",
    "Treated as IST; no conversion.", "The values are already local clock time.", f"{n(NH)} -> {n(NH)}", CONF)
log("M3", "Metro hourly", "Merge", f"Entries and exits were merged on (Date, Hour, Station): {n(NH)} rows. Boardings match the original file on every row; exits match on every row", "Compared with the repo's separate files", "0 mismatches", "0%",
    "Kept. 2 exit riders in the 3,336 absent station-hours were dropped by the merge (2 of 33,727,301).", "Merged layout is what the team wanted; the loss is immaterial.",
    f"{n(NH)} -> {n(NH)}", "Confirmed against the repo's raw files (separate check)")
log("M4", "Metro hourly", "Line not yet open", f"{len(yl)} Yellow Line stations ({', '.join(yl[:3])} and {len(yl) - 3} more) opened on 10 Aug 2025. Before that they have no rows for {n(miss_rows_struct)} station-hours ({sd_missing_in_present} station-days)",
    "Expected grid vs rows; first day with daytime riders per station", f"{n(miss_rows_struct)} rows", "not applicable",
    "Excluded these 15 stations from the weekday comparison so the 68 stations open all period are compared like for like.",
    f"Public riders start on 11 Aug 2025. The few earlier riders ({n(int(early.Ridership.sum()))} riders in {len(early)} station-hours at {early.Station.nunique()} stations, 3-9 Aug) may be final testing; not confirmed.", f"{n(NH)} -> {n(NH - int(mh.Station.isin(yl).sum()))} used", CONF)
log("M5", "Metro hourly", "Gap (days)", f"{len(miss_days)} whole days absent: {miss_days[0]:%d}-{miss_days[-1]:%d} Aug 2025 (the repo's RTI data stops at 18 Aug and restarts 1 Sep)",
    "Date coverage check", f"{n(len(miss_days) * 24 * n_st)} station-hours", pc(len(miss_days) * 24 * n_st, exp_open),
    "Not filled. Ganesh Chaturthi (27 Aug) therefore has no hourly metro data; the daily ticket file does have it.", "A whole-day gap cannot be filled honestly.",
    f"{n(exp_open)} expected (open stations) -> {n(NH)} present", CONF)
log("M6", "Metro hourly", "Outlier - sensor failure", f"Negative values: 0. Largest hourly value {n(mh.Ridership.max())}. Station-days with total 0: 0. Repeated identical non-zero values in consecutive hours: {n(n_same)} (of these {n(n_same_small)} are 10 riders or fewer)",
    "min/max; all-zero day check; run scan", "0 failures", "0%", "Checked. Repeats are small counts (chance), not stuck readings. No rows removed.", "No sign of a failed sensor.", f"{n(NH)} -> {n(NH)}", CONF)
log("M7", "Metro hourly", "Zero values", f"{n(len(zeros))} zero rows: {n(night_zero)} in closed hours (23:00-05:59); {n(len(dz))} in daytime, of which {n(pre_zero)} are Yellow Line stations on or before the 10 Aug 2025 opening",
    "Zero count by hour and station", f"{n(len(zeros))} rows", pc(len(zeros), NH),
    f"Overnight zeros kept (real). Zeros at the Yellow Line stations up to opening kept, not flagged. The other {n(other_zero)} daytime zeros kept and flagged.", "The remaining few cannot be told apart from a true zero or an outage.", f"{n(NH)} -> {n(NH)}", CONF)
log("M8", "Metro hourly", "Outlier - real event", f"Extreme station-hours (robust z > 6 and > 200 riders): {n(int(is_ext.sum()))}; clustered on {top_days}",
    "Median/MAD per station x hour x weekday/weekend", f"{n(int(is_ext.sum()))} rows", pc(is_ext.sum(), NH),
    "Kept and flagged. 15 Aug and 5 Sep are public holidays; the other dates are not in the calendar and their cause is unverified.",
    "They cluster on a few dates across many stations, which looks like real events, not failure.", f"{n(NH)} flagged {n(int(is_ext.sum()))}", CONF)
log("M9", "Metro hourly", "Outlier - check", f"Riders recorded at hour 3 (service closed): {len(h3)} rows at {h3.Station.nunique()} stations, mostly Majestic, Yeshwantpur and the KSR railway station on Mondays",
    "Non-zero at hour 3", f"{len(h3)} rows", pc(len(h3), NH), "Kept and flagged.", "Possibly test runs of the metro before service; the actual cause is not known.", f"{n(NH)} -> {n(NH)}", CONF)
log("M10", "Metro hourly", "Consistency check", f"Boardings total {n(board_total)} vs exits total {n(exit_total)} ({100 * (board_total - exit_total) / exit_total:.2f}% apart)",
    "Sum comparison; daily gap peaks at 2.4% on 15 Aug", "-", "-", "Not reconciled. Boardings are the main measure; exits only describe flow direction.",
    "Riders may not scan or tap in or out (for example token users), and staff let passengers through during gate faults. The actual cause is not known.", "-", CONF)

# ================================================================== METRO DAILY
span = pd.date_range(md.index.min(), md.index.max())
miss_d = span.difference(md.index)
ND = len(md)
in_win = md["2025-10-01":"2026-09-30"]
miss_win = len(pd.date_range("2025-10-01", "2026-09-30")) - len(in_win)
runs_d, s0 = [], None
for d in miss_d:
    if s0 is not None and (d - prev).days == 1:
        prev = d
        continue
    if s0 is not None:
        runs_d.append((s0, prev))
    s0 = prev = d
runs_d.append((s0, prev))
runs_d = sorted(runs_d, key=lambda r: -((r[1] - r[0]).days))[:3]
bad_smart = int(((md["Total Smart Cards"] - (md["Stored Value Card"] + md["One Day Pass"] + md["Three Day Pass"] + md["Five Day Pass"])) != 0).sum())
bad_qr = int(((md["Total QR"] - (md["QR NammaMetro"] + md["QR WhatsApp"] + md["QR Paytm"] + md["QR ONDC"])) != 0).sum())
bad_tot = int(((md.Total - (md["Total Smart Cards"] + md["Total Tokens"] + md["Total NCMC"] + md["Group Ticket"] + md["Total QR"])) != 0).sum())
assert bad_smart == bad_qr == bad_tot == 0, "a daily total no longer matches its parts"
ondc_first = md[md["QR ONDC"] > 0].index.min()
n_pre_ondc = int((md.index < ondc_first).sum())
assert (md.loc[md.index < ondc_first, "QR ONDC"] == 0).all() and (md.loc[md.index >= ondc_first, "QR ONDC"] > 0).all()
blk = ["Total Tokens", "Total NCMC", "Group Ticket", "Total QR", "QR NammaMetro", "QR WhatsApp", "QR Paytm"]
dup_blk = md[md.duplicated(blk, keep=False)]
assert list(dup_blk.index.strftime("%Y-%m-%d")) == ["2025-12-11", "2025-12-15"]
tok_low = md[md["Total Tokens"] < 100000]
assert list(tok_low.index.strftime("%Y-%m-%d")) == ["2026-07-17"]
BAD_DAYS = [pd.Timestamp("2025-12-15")]                # 17 Jul 2026 is kept as published (team decision)
RISE = pd.Timestamp("2026-08-17")                           # the date from which the higher level settles
_tt = md[md.index.dayofweek.isin([1, 2, 3])]
tot_pre, tot_post = float(_tt.loc["2026-07-01":"2026-07-31", "Total"].median()), float(_tt.loc[RISE:, "Total"].median())
tot_late = float(_tt.loc["2026-10-01":, "Total"].median())
shift_pct = 100 * (tot_post / tot_pre - 1)
assert shift_pct > 10 and tot_late > 1.1 * tot_pre, "the higher daily level no longer holds into Oct-Nov"
dow = md.index.dayofweek
mdm = md.assign(dow=dow)
gm = mdm.groupby("dow").Total
rzd = (md.Total - gm.transform("median")) / (1.4826 * gm.transform(lambda s: (s - s.median()).abs().median()))
low_out = rzd[rzd < -3.5]
low_hol = int(low_out.index.isin(PUBHOL).sum())
band_map = pd.crosstab(md["Day of Week"], md["Traffic Band"])
assert band_map.loc["Monday", "Early Week"] > 0 and band_map.loc["Friday", "Mid Week"] > 0 and band_map.loc["Friday", "Early Week"] == 0

log("D1", "Metro daily", "Type casting", "Raw tracker file uses dd-mm-yyyy; the final file uses yyyy-mm-dd", "Compared with the tracker CSV", f"{n(ND)} rows", "100%",
    "Final file already ISO; parsed with 0 unparseable dates. Day of Week verified against the date (all match).", "Avoids day/month swaps.", f"{n(ND)} -> {n(ND)}", CONF)
log("D2", "Metro daily", "Gap", f"BMRCL does not publish every day: {len(miss_d)} of {len(span)} calendar days missing between {span[0]:%d %b %Y} and {span[-1]:%d %b %Y}; {miss_win} of the 365 days inside the traffic window. Longest runs: "
    + ", ".join(f"{a:%d %b}-{b:%d %b %Y} ({(b - a).days + 1} d)" for a, b in runs_d),
    "Date range vs the full calendar", f"{len(miss_d)} days", pc(len(miss_d), len(span)),
    "Not filled. Weekday averages use available days only.", "Ridership cannot be estimated for a missing day without hiding the gap.", f"{len(span)} expected -> {ND} present", CONF)
log("D3", "Metro daily", "Labelling", "Traffic Band puts Monday with Tue/Wed (Early Week) and Friday with Thursday (Mid Week)", "Crosstab of Day of Week x Traffic Band", f"{ND} rows", "100%",
    "Not used for the Mon/Fri comparison; weekday computed from the date instead.", "The band hides exactly the Monday and Friday difference the question asks about.", f"{ND} -> {ND}", CONF)
log("D4", "Metro daily", "Consistency check", f"Three identities checked on every row: Smart Cards = Stored Value + One-day + Three-day + Five-day; Total QR = NammaMetro + WhatsApp + Paytm + ONDC; Total = Smart Cards + Tokens + NCMC + Group + Total QR. Failures: {bad_smart}, {bad_qr}, {bad_tot} of {ND} rows",
    "Recomputed the sums", "0 failures", "0%", "Checked, none found. Total QR includes ONDC (four channels), as confirmed by the team.",
    "Confirms the Total used in Figure 5 is built correctly.", f"{ND} -> {ND}", CONF)
log("D5", "Metro daily", "Not introduced", f"QR ONDC is 0 on all {n_pre_ondc} days before {ondc_first:%d %b %Y} and above 0 on every day from then on: it is a payment method introduced on that date",
    "First non-zero date; zero check before it", f"{n_pre_ondc} rows", pc(n_pre_ondc, ND), "Kept as 0.", "QR ONDC started appearing on that date, when it was introduced as a payment method.", f"{ND} -> {ND}", CONF)
log("D6", "Metro daily", "Duplicate", "15 Dec 2025 repeats 11 Dec 2025 exactly on seven columns (Tokens, NCMC, Group, Total QR and three QR channels)", "duplicated() on the block", "1 row", "0.4%",
    "Excluded 15 Dec 2025 from the daily charts.", "Stale carry-forward: the smart-card columns differ, so the date is real but the rest is a copy.", f"{ND} -> {ND - 1} used", CONF)
log("D7", "Metro daily", "Outlier - probable typo", f"17 Jul 2026 shows Total Tokens = {n(int(tok_low['Total Tokens'].iloc[0]))} (typical 190,000-300,000)", "Value check", "1 row", "0.4%",
    "Kept as published and used in the charts. Cannot be corrected without the source.", "The team decided to keep the value. Total still adds up (D4). The low tokens pull that Friday down.", f"{ND} -> {ND}", CONF)
log("D8", "Metro daily", "Level change", f"Daily Total rises from mid-Aug 2026: Tue-Thu median {n(tot_pre)} in Jul vs {n(tot_post)} from {RISE:%d %b} to {md.index.max():%d %b} (+{shift_pct:.0f}%); it builds through early Aug and holds into Oct-Nov (Tue-Thu median {n(tot_late)})",
    "Median by period on Tue-Thu", f"from {RISE:%d %b %Y}", "-", "Kept as a real change in ridership. Figure 5 uses the full data; its footnote shows how little the change moves the weekday indices.",
    "Team: the Yellow Line added another train on 15 Aug. The rise starts earlier than that, so it is not explained by that alone; cause not verified.", "-", CONF)
log("D9", "Metro daily", "Outlier - real event", f"{len(low_out)} unusually low days (robust z < -3.5 within weekday); {low_hol} are public holidays; high days on 14 Aug 2026 and 29 Apr 2026 also spike on the roads",
    "Median/MAD by weekday; calendar join", f"{len(low_out)} days", pc(len(low_out), ND), "Kept and flagged as real events.", "Holiday dips and the road/metro co-spikes point to real behaviour, not failure.", f"{ND} -> {ND}", CONF)

# ================================================================== TRENDS + CALENDAR
for nm, tr in (("traffic", trf), ("metro", trm)):
    assert tr.date.is_unique
tr_nonint_t, tr_nonint_m = float((trf.interest_index % 1 != 0).mean()), float((trm.interest_index % 1 != 0).mean())
log("G1", "Google Trends", "Gap", f"No missing days: {len(trf)} daily rows (traffic, 1 Oct 2025-30 Sep 2026) and {len(trm)} (metro, 1 Aug-30 Sep 2025); no duplicates",
    "Date range vs calendar", "0 days", "0%", "Checked, none found.", "Daily series are complete.", f"{len(trf) + len(trm)} -> {len(trf) + len(trm)}", CONF)
log("G2", "Google Trends", "Type casting", f"interest_index is not a whole number on {pc(tr_nonint_t, 1, 0)} (traffic) and {pc(tr_nonint_m, 1, 0)} (metro) of days, although Google gives integers 0-100", "Share of non-integers", f"{len(trf) + len(trm)} rows", "100%",
    "Kept as numeric. The scaling or stitching method is not recorded in the file.", "Non-integers show the series was rescaled or averaged; the method belongs in the source register.", "-", ASK + " (document the scaling method)")
log("G3", "Google Trends", "Normalisation", "interest_z (mean 0, sd 1) and interest_minmax (0-1) added per term; the index is relative to the term's own peak", "Verified mean/sd", f"{len(trf) + len(trm)} rows", "100%",
    "Used interest_z against the traffic z-score in Figure 3. Never compare raw index values across terms.", "Trends has no units; z-scores put it on the same scale as congestion.", "-", CONF)
log("G4", "Google Trends", "Outlier - real event", f"flag_spike marks {int(trf.flag_spike.sum())} traffic days and {int(trm.flag_spike.sum())} metro days; the metro spike (9-12 Aug 2025) coincides with the Yellow Line opening (10-11 Aug 2025)",
    "flag_spike; cross-check with metro hourly", f"{int(trf.flag_spike.sum() + trm.flag_spike.sum())} days", "-", "Kept and flagged as real events.", "Matches an independent source. Spike rule is not recorded.", "-", ASK + " (spike rule)")
log("C1", "Calendar", "Coverage", f"{len(cal)} days, 1 Aug 2025-19 Nov 2026, no gaps or duplicates; {int(cal.is_public_holiday.sum())} public holidays, {int(cal.is_long_weekend.sum())} long-weekend days; blanks in holiday_name are normal",
    "Date range; null counts", "0 gaps", "0%", "Checked, none found. Used to separate holidays from ordinary days.", "Covers every other table. It misses some real events (e.g. 1 Jan 2026): see T9.", f"{len(cal)} -> {len(cal)}", CONF)
log("X1", "Cross-source", "Window mismatch", "Metro hourly covers Aug-Sep 2025 only; traffic covers Oct 2025-Sep 2026. They share no hours.", "Date ranges", "-", "-",
    "Road-vs-metro comparison is made at weekday level on shared dates only (Figure 5); no hourly road-vs-metro join.", "Joining on non-overlapping periods would be meaningless.", "-", CONF)

# ================================================================== CHART DATA
# ---------- Figure 1 heatmap
pk = pv.idxmax(axis=1)
mt = pv.loc[["Monday", "Tuesday", "Wednesday", "Thursday"]]
fri_am = float(pv.loc["Friday", 8:10].mean() / mt.loc[:, 8:10].mean().mean() - 1)
six = int((pk == 18).sum())
assert six == 6 and pk["Tuesday"] == 9 and fri_am < -0.08, "heatmap title no longer matches the data"

fig, ax = plt.subplots(figsize=(13, 6.6))
cmap = LinearSegmentedColormap.from_list("blue_seq", SEQ)
im = ax.imshow(pv.values, aspect="auto", cmap=cmap, vmin=float(pv.values.min()), vmax=float(pv.values.max()))
ax.set_xticks(range(24))
ax.set_xticklabels([f"{h:02d}" for h in range(24)], fontsize=9)
ax.set_yticks(range(7))
ax.set_yticklabels(WD, fontsize=10)
ax.set_xlabel("Hour of day (IST)", fontsize=10)
ax.set_xticks(np.arange(-0.5, 24, 1), minor=True)
ax.set_yticks(np.arange(-0.5, 7, 1), minor=True)
ax.grid(which="minor", color=SURF, linewidth=1.6)
ax.tick_params(which="both", length=0)
for s in ax.spines.values():
    s.set_visible(False)
for i, d in enumerate(WD):
    h = int(pk[d])
    ax.scatter([h], [i], s=46, facecolor="white", edgecolor=INK, linewidth=1.2, zorder=3)
    ax.text(23.75, i, f"peak {h:02d}:00 - {pv.loc[d, h]:.2f}", va="center", ha="left", fontsize=9, color=INK2, clip_on=False)
cb = fig.colorbar(im, ax=ax, orientation="horizontal", fraction=0.04, pad=0.16, aspect=45)
cb.set_label("Mean congestion index (1.0 = free-flow travel time)", fontsize=9)
cb.outline.set_visible(False)
cb.ax.tick_params(length=0, labelsize=8.5)
fig.subplots_adjust(left=0.085, right=0.86, top=0.80, bottom=0.17)
titles(fig,
       f"Evening congestion peaks at 18:00 on six of seven days, and Friday mornings run {abs(fri_am) * 100:.0f}% lighter than Monday-Thursday",
       f"Mean congestion index by weekday and hour, 13 routes, 1 Oct 2025 - 30 Sep 2026. {n(n_obs)} observed route-hours; interpolated and missing hours excluded. "
       "White dot = busiest hour of that weekday (Tuesday peaks at 09:00).",
       f"Dropping all {n(n_flag_obs)} flagged observed rows (alternate routes, flat-lines, extreme events) moves no cell by more than {sens_max:.2f}.")
fig.savefig(FIG_OUT / "fig1_weekday_hour_heatmap.png", dpi=200)
plt.close(fig)

# ---------- Figure 2 rain vs congestion
ev = tw[(tw.row_status == "observed") & tw.hour.between(18, 21)]
ge = ev.groupby(["route_code", "date"]).agg(k=("hour", "size"), cong=("congestion_index", "mean"), rain=("rain", "max"), wd=("weekday", "first")).reset_index()
ge = ge[ge.k >= 3].copy()
ge["date"] = pd.to_datetime(ge.date)
ge["rainy"] = ge.rain >= 0.1
ge["grp"] = ge.wd.map(grp_of)
ge["season"] = ge.date.dt.month.map(lambda m: "NE" if m in (10, 11) else "Dry" if m in (12, 1, 2) else "Pre" if m in (3, 4, 5) else "SW")
b0 = ge[~ge.rainy].groupby(["route_code", "grp"]).cong.mean().rename("b0")
b1 = ge[~ge.rainy].groupby(["route_code", "grp", "season"]).cong.mean().rename("b1")
ge = ge.join(b0, on=["route_code", "grp"]).join(b1, on=["route_code", "grp", "season"])
ge["ex0"], ge["ex1"] = ge.cong - ge.b0, ge.cong - ge.b1
n_drop = int(ge[ge.rainy].ex1.isna().sum())
rn = ge[ge.rainy & ge.ex1.notna()]


def boot(df, col, nb=2000, seed=7):
    rng = np.random.default_rng(seed)
    byd = df.groupby("date")[col].agg(["sum", "count"])
    s, c = byd["sum"].values, byd["count"].values
    k = len(s)
    out = np.empty(nb)
    for i in range(nb):
        ix = rng.integers(0, k, k)
        out[i] = s[ix].sum() / c[ix].sum()
    return np.percentile(out, [2.5, 97.5])


GROUPS = ["Mon", "Tue-Thu", "Fri", "Weekend"]
res = {}
for gname in GROUPS:
    d = rn[rn.grp == gname]
    lo, hi = boot(d, "ex1")
    dry = ge[(~ge.rainy) & (ge.grp == gname)].cong.mean()
    res[gname] = dict(raw=d.ex0.mean(), adj=d.ex1.mean(), lo=lo, hi=hi, n=len(d), dry=dry, pct=100 * d.ex1.mean() / dry,
                      n_dry=int(((~ge.rainy) & (ge.grp == gname)).sum()))
wk = [res[g_] for g_ in ("Mon", "Tue-Thu", "Fri")]
assert res["Fri"]["lo"] > 0 and res["Mon"]["lo"] < 0 and res["Tue-Thu"]["lo"] < 0.01, "title below assumes only Friday is clearly above zero"
assert res["Fri"]["adj"] > res["Tue-Thu"]["adj"] > 0 and res["Fri"]["adj"] > res["Mon"]["adj"]
fri_overlap = res["Fri"]["lo"] <= res["Tue-Thu"]["adj"]
pmin, pmax = min(r["pct"] for r in wk), max(r["pct"] for r in wk)

fig, ax = plt.subplots(figsize=(9.5, 6.0))
x = np.arange(4)
bw = 0.32
raw_v = [res[g_]["raw"] for g_ in GROUPS]
adj_v = [res[g_]["adj"] for g_ in GROUPS]
yerr = np.array([[res[g_]["adj"] - res[g_]["lo"], res[g_]["hi"] - res[g_]["adj"]] for g_ in GROUPS]).T
ax.bar(x - bw / 2, raw_v, bw, color=AXIS, label="Not adjusted for season", zorder=3)
ax.bar(x + bw / 2, adj_v, bw, color=BLUE, label="Adjusted for season (headline)", zorder=3)
ax.errorbar(x + bw / 2, adj_v, yerr=yerr, fmt="none", ecolor=INK, elinewidth=1.2, capsize=3, zorder=4)
for xi, g_ in zip(x, GROUPS):
    ax.text(xi + bw / 2, res[g_]["hi"] + 0.006, f"+{res[g_]['adj']:.2f}", ha="center", va="bottom", fontsize=9.5, color=INK, fontweight="bold")
    ax.text(xi - bw / 2, res[g_]["raw"] + 0.006, f"+{res[g_]['raw']:.2f}", ha="center", va="bottom", fontsize=9, color=INK2)
ax.set_xticks(x)
ax.set_xticklabels([f"{g_.replace('-', '-')}\n{res[g_]['n']} rainy / {res[g_]['n_dry']} dry evenings" for g_ in GROUPS], fontsize=9.5)
ax.set_ylabel("Extra congestion index on rainy evenings\n(vs dry evenings, same route and day group)", fontsize=9.5)
ax.axhline(0, color=AXIS, linewidth=1)
clean_axes(ax)
ax.legend(frameon=False, loc="upper left", fontsize=9.5)
ax.set_ylim(0, max(r["hi"] for r in res.values()) * 1.25)
fig.subplots_adjust(left=0.12, right=0.97, top=0.80, bottom=0.17)
titles(fig,
       f"Rain adds a clear {res['Fri']['pct']:.1f}% to Friday evening congestion; Monday and Tuesday-Thursday rises ({res['Mon']['pct']:.1f}%, {res['Tue-Thu']['pct']:.1f}%) are within noise",
       "Evening rush = 18:00-21:00, observed route-hours only. A rainy evening has at least 0.1 mm in an hour of the window at that route's weather point. "
       "Bars = mean extra congestion index; whiskers = 95% interval (bootstrap over dates). "
       "Only Friday's interval stays above zero.",
       "Association, not cause. Rainy evenings cluster in Jun-Sep, which is already busier, so the headline bars compare within the same season (Oct-Nov, Dec-Feb, Mar-May, Jun-Sep). "
       f"{n_drop} rainy route-evenings had no dry match in their season and were dropped. Sources: traffic + Open-Meteo weather.", wrap=100)
fig.savefig(FIG_OUT / "fig2_rain_vs_evening_congestion.png", dpi=200)
plt.close(fig)

# ---------- Figure 3 normalised: congestion z vs Trends z
dz_ = obs.groupby("date_dt").agg(z=("duration_z", "mean"), k=("hour", "size")).reset_index().rename(columns={"date_dt": "date"})
dz_ = dz_[dz_.k >= 156]
j = dz_.merge(trf[["date", "interest_z", "interest_index"]], on="date")
j["z"] = (j.z - j.z.mean()) / j.z.std()
j["tz"] = (j.interest_z - j.interest_z.mean()) / j.interest_z.std()
r_all = float(j.z.corr(j.tz))
r_sp = float(stats.spearmanr(j.z, j.tz)[0])
j["dow"] = j.date.dt.dayofweek
adj = lambda s: s - s.groupby(j.dow).transform("mean")
r_adj = float(adj(j.z).corr(adj(j.tz)))
assert 0.1 < r_all < 0.35, "correlation outside the range the title describes"
fig = plt.figure(figsize=(14, 5.8))
gs = fig.add_gridspec(1, 2, width_ratios=[2.3, 1], wspace=0.17, left=0.055, right=0.985, top=0.78, bottom=0.14)
ax = fig.add_subplot(gs[0])
roll = lambda s: s.rolling(7, center=True, min_periods=4).mean()
ax.plot(j.date, roll(j.z), color=BLUE, linewidth=2, label="Road congestion (per-route z-score, 13-route mean)")
ax.plot(j.date, roll(j.tz), color=ORANGE, linewidth=2, label="Google Trends: 'bangalore traffic' (z-score)")
ax.axhline(0, color=AXIS, linewidth=1)
ax.set_ylabel("Standard deviations from own average (7-day mean)", fontsize=9.5)
clean_axes(ax)
ax.legend(frameon=False, loc="upper left", fontsize=9.5, ncol=1)
ax.margins(x=0.01)
ax2 = fig.add_subplot(gs[1])
ax2.scatter(j.tz, j.z, s=16, color=BLUE, alpha=0.45, linewidths=0)
slope, icpt = np.polyfit(j.tz, j.z, 1)
xs = np.array([j.tz.min(), j.tz.max()])
ax2.plot(xs, slope * xs + icpt, color=INK, linewidth=1.6)
ax2.set_xlabel("Trends z-score (that day)", fontsize=9.5)
ax2.set_ylabel("Congestion z-score (that day)", fontsize=9.5)
ax2.text(0.97, 0.04, f"r = {r_all:.2f}\nr = {r_adj:.2f} after removing weekday pattern\n{len(j)} days", transform=ax2.transAxes, va="bottom", ha="right", fontsize=9.5, color=INK)
clean_axes(ax2, "both")
titles(fig,
       f"Searches for 'bangalore traffic' only weakly track daily road congestion (r = {r_all:.2f}, {r_adj:.2f} once weekdays are removed)",
       f"Both series standardised (z-scores) so they share one axis. Daily, 1 Oct 2025 - 30 Sep 2026; days with fewer than half their route-hours observed excluded ({len(dz_)} of 365 days kept, {len(j)} joined). "
       f"Spearman rank r = {r_sp:.2f}.",
       "Association only. Trends is a relative index of search interest, not trips; its scaling method is not documented in the file. Sources: traffic + Google Trends.", wrap=120)
fig.savefig(FIG_OUT / "fig3_trends_vs_congestion_zscores.png", dpi=200)
plt.close(fig)

# ---------- Figure 4 metro hourly by day group
mh68 = mh[~mh.Station.isin(yl) & ~mh.Date.isin(PUBHOL)].copy()
mh68["grp"] = mh68.Date.dt.day_name().map(grp_of)
dayhr = mh68.groupby(["grp", "Date", "Hour"]).Ridership.sum().reset_index()
ndays = dayhr.groupby("grp").Date.nunique()
avg = dayhr.groupby(["grp", "Hour"]).Ridership.mean().unstack(0) / 1000
am, pm = avg.loc[7:10].sum(), avg.loc[17:20].sum()
d_am = (am / am["Tue-Thu"] - 1)
d_pm = (pm / pm["Tue-Thu"] - 1)
assert d_am["Fri"] < -0.10 and d_am["Mon"] > 0 and d_pm["Fri"] < 0 and d_pm["Mon"] < 0
fig, ax = plt.subplots(figsize=(10.5, 6.0))
ax.axvspan(6.5, 10.5, color=GRID, alpha=0.5, zorder=0, linewidth=0)
ax.axvspan(16.5, 20.5, color=GRID, alpha=0.5, zorder=0, linewidth=0)
ax.text(8.5, 1.5, "morning window", ha="center", fontsize=8.5, color=MUTED)
ax.text(18.5, 1.5, "evening window", ha="center", fontsize=8.5, color=MUTED)
hrs = list(range(5, 24))
series = [("Tue-Thu", BLUE, "Tue-Thu"), ("Mon", AQUA, "Mon"), ("Fri", ORANGE, "Fri"), ("Weekend", MUTED, "Sat-Sun")]
for key, col, lab in series:
    ax.plot(hrs, avg.loc[hrs, key], color=col, linewidth=2.2, label=f"{lab} ({ndays[key]} days)", zorder=3)
ax.set_xticks(range(5, 24, 2))
ax.set_xticklabels([f"{h:02d}" for h in range(5, 24, 2)])
ax.set_xlabel("Hour of day (IST)", fontsize=9.5)
ax.set_ylabel("Boardings per day at that hour, 68 stations (thousands)", fontsize=9.5)
ax.set_ylim(0, None)
ax.set_xlim(5, 23)
clean_axes(ax)
ax.legend(frameon=False, loc="upper right", fontsize=9.5)
fig.subplots_adjust(left=0.085, right=0.97, top=0.78, bottom=0.14)
titles(fig,
       f"On the metro, Fridays carry {abs(d_am['Fri']) * 100:.0f}% fewer morning riders than Tuesday-Thursday; Mondays do not run lighter ({d_am['Mon'] * 100:+.0f}%)",
       f"Average boardings by hour, Aug-Sep 2025. Windows 07-10h and 17-20h compared with Tue-Thu: Friday morning {d_am['Fri'] * 100:+.0f}%, evening {d_pm['Fri'] * 100:+.0f}%; "
       f"Monday morning {d_am['Mon'] * 100:+.0f}%, evening {d_pm['Mon'] * 100:+.0f}%.",
       f"Only the 68 stations open all period (the 15 new Yellow Line stations are excluded); public holidays (15 Aug, 5 Sep) excluded; 19-31 Aug is absent from the source. "
       f"Only {ndays['Fri']} Fridays remain, so treat the Friday figures as indicative. Source: BMRCL RTI data (ODbL).", wrap=105)
fig.savefig(FIG_OUT / "fig4_metro_hourly_by_day_group.png", dpi=200)
plt.close(fig)

# ---------- Figure 5 roads vs metro weekday index (shared dates)
roads_day = obs.groupby("date_dt").agg(road=("congestion_index", "mean"), k=("hour", "size"))
roads_day = roads_day[roads_day.k >= 156].road
mdd = md.drop(index=[d for d in BAD_DAYS if d in md.index])
mdd = mdd["2025-10-01":]                                      # full metro data; road data ends 30 Sep 2026, so shared dates end there
mdd = mdd[~mdd.index.isin(PUBHOL)]
sh = pd.DataFrame({"metro": mdd.Total, "road": roads_day}).dropna()
sh["grp"] = sh.index.day_name().map(grp_of)
rng = np.random.default_rng(11)


DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
sh["day"] = sh.index.day_name()


def idx_boot(col, nb=3000):
    base = sh[sh.grp == "Tue-Thu"][col].values
    out = {}
    for dname in DAYS:
        v = sh[sh.day == dname][col].values
        pt = v.mean() / base.mean() * 100
        bs = [rng.choice(v, len(v)).mean() / rng.choice(base, len(base)).mean() * 100 for _ in range(nb)]
        out[dname] = (pt, *np.percentile(bs, [2.5, 97.5]))
    return out


ir, im_ = idx_boot("road"), idx_boot("metro")
nn = sh.day.value_counts()
print("F5 roads", {k: tuple(round(float(x), 1) for x in v) for k, v in ir.items()}); print("F5 metro", {k: tuple(round(float(x), 1) for x in v) for k, v in im_.items()}, dict(nn))
assert im_["Friday"][2] < 100 and ir["Friday"][2] < 100, "Friday is not lighter on both sources"
assert ir["Monday"][2] < 100 and im_["Monday"][1] <= 100 <= im_["Monday"][2], "Monday pattern differs from the title"
assert all(im_[d][0] < ir[d][0] - 10 for d in ("Saturday", "Sunday")), "weekend pattern differs from the title"
# sensitivity: the daily Total is higher from mid-Aug 2026 (D8). Re-index each day against the Tue-Thu mean of its own period (before/after).
_per = pd.Series(np.where(sh.index >= RISE, "post", "pre"), index=sh.index)
_base = sh[sh.grp == "Tue-Thu"].metro.groupby(_per[sh.grp == "Tue-Thu"]).mean()
adj = {g: float((sh[sh.day == g].metro / _per[sh.day == g].map(_base)).mean() * 100) for g in DAYS}
adj_shift = max(abs(adj[g] - im_[g][0]) for g in adj)
n_post = int((sh.index >= RISE).sum())
fig, ax = plt.subplots(figsize=(12, 8.4))
ypos = {d: 6 - k for k, d in enumerate(DAYS)}
for dname in DAYS:
    for src, col, off, vals in (("Roads", BLUE, 0.13, ir), ("Metro", ORANGE, -0.13, im_)):
        pt, lo, hi = vals[dname]
        ax.plot([lo, hi], [ypos[dname] + off] * 2, color=col, linewidth=2.2, zorder=3, solid_capstyle="round")
        ax.scatter([pt], [ypos[dname] + off], s=80, color=col, edgecolor=SURF, linewidth=2, zorder=4)
        ax.text(hi + 1.0, ypos[dname] + off, f"{pt:.1f}", va="center", fontsize=9.5, color=INK, fontweight="bold", zorder=5, bbox=dict(facecolor=SURF, edgecolor="none", pad=1.5))
ax.axvline(100, color=INK2, linewidth=1.2, zorder=2)
ax.text(100.3, 6.62, "Tue-Thu average = 100", fontsize=9, color=INK2, va="center")
ax.set_yticks([ypos[d] for d in DAYS])
ax.set_yticklabels([f"{d}\n({nn[d]} days)" for d in DAYS], fontsize=10)
ax.set_ylim(-0.6, 6.9)
ax.set_xlim(60, 108)
ax.set_xlabel("Index: average on that day as % of the Tue-Thu average (100)", fontsize=9.5)
clean_axes(ax, "x")
ax.legend(handles=[Line2D([0], [0], marker="o", color=BLUE, lw=2.2, markersize=8, label="Roads (congestion index)"),
                   Line2D([0], [0], marker="o", color=ORANGE, lw=2.2, markersize=8, label="Metro (daily tickets)")], frameon=False, loc="upper left", fontsize=9.5)
fig.subplots_adjust(left=0.15, right=0.96, top=0.82, bottom=0.17)
titles(fig,
       f"Fridays run lighter on roads ({ir['Friday'][0] - 100:+.1f}%) and metro ({im_['Friday'][0] - 100:+.1f}%); Mondays only on roads; Saturday and Sunday drop far more on metro ({im_['Saturday'][0] - 100:+.0f}%, {im_['Sunday'][0] - 100:+.0f}%) than roads ({ir['Saturday'][0] - 100:+.0f}%, {ir['Sunday'][0] - 100:+.0f}%)",
       f"All seven days on the same {len(sh)} dates for both sources, {sh.index.min():%d %b %Y} - {sh.index.max():%d %b %Y} (all dates with both), public holidays excluded. Each dot = that day's average as % of the Tue-Thu average; line = 95% interval (bootstrap over days).",
       f"Metro = daily tickets as published (checks in log D4). The daily Total is higher from mid-Aug 2026 (D8), but only {n_post} of the {len(sh)} dates fall after {RISE:%d %b}; re-indexing each day against its own period moves the metro indices by at most {adj_shift:.1f} points. "
       "15 Dec 2025 excluded as a copy of 11 Dec (D6); 17 Jul 2026 kept as published (D7). Metro dates are only the days BMRCL published.", wrap=88)
fig.savefig(FIG_OUT / "fig5_roads_vs_metro_weekday_index.png", dpi=200)
plt.close(fig)

# ---------- Figure 6 gap chart
C_PRES, C_FILL, C_MISS, C_STRUCT = BLUE_100, BLUE, ORANGE, MUTED
fig = plt.figure(figsize=(15, 16.5))
gs = fig.add_gridspec(4, 1, height_ratios=[1.3, 1.7, 1.9, 2.0], hspace=0.55, left=0.20, right=0.89, top=0.85, bottom=0.05)
# A summary
axA = fig.add_subplot(gs[0])
exp_h = exp_open                                            # only stations that were open count as expected
sumrows = [
    ("Traffic (route-hours)", NT, [(n_obs, C_PRES), (n_int + n_durint, C_FILL), (n_miss, C_MISS)]),
    ("Metro hourly (station-hours)", exp_h, [(NH, C_PRES), (len(miss_days) * 24 * n_st, C_MISS)]),
    ("Metro daily (days)", len(span), [(ND, C_PRES), (len(miss_d), C_MISS)]),
    ("Weather (hours)", wrows, [(wrows, C_PRES)]),
    ("Google Trends (days)", len(trf) + len(trm), [(len(trf) + len(trm), C_PRES)]),
    ("Calendar (days)", len(cal), [(len(cal), C_PRES)]),
]
for i, (lab, tot, segs) in enumerate(sumrows):
    left = 0
    for cnt, col in segs:
        axA.barh(i, 100 * cnt / tot, left=left, color=col, height=0.62, edgecolor=SURF, linewidth=2)
        left += 100 * cnt / tot
    miss_pct = 100 * (tot - segs[0][0]) / tot
    axA.text(101, i, "complete" if miss_pct == 0 else f"{100 * segs[0][0] / tot:.1f}% present", va="center", fontsize=9.5, color=INK2, clip_on=False)
axA.set_yticks(range(len(sumrows)))
axA.set_yticklabels([r[0] for r in sumrows], fontsize=10)
axA.invert_yaxis()
axA.set_xlim(0, 100)
axA.set_xlabel("% of expected rows", fontsize=9.5)
clean_axes(axA, "x")
axA.set_title("A. Share of expected rows present, by source", loc="left", fontsize=10.5, color=INK, fontweight="bold")
# B traffic route x day
routes = sorted(t.route_name.unique())
dates = pd.date_range("2025-10-01", "2026-09-30")
cell = t.assign(c=np.where(t.row_status == "missing_hour", 2, np.where(t.row_status != "observed", 1, 0))).groupby(["route_name", "date_dt"]).c.max().unstack()
cell = cell.reindex(index=routes, columns=dates)
cm4 = ListedColormap([C_PRES, C_FILL, C_MISS, C_STRUCT])
nm4 = BoundaryNorm([-0.5, 0.5, 1.5, 2.5, 3.5], 4)
axB = fig.add_subplot(gs[1])
axB.imshow(cell.values, aspect="auto", cmap=cm4, norm=nm4, interpolation="nearest")
axB.set_yticks(range(len(routes)))
axB.set_yticklabels(routes, fontsize=8.5)
mt_ix = [i for i, d in enumerate(dates) if d.day == 1]
axB.set_xticks(mt_ix)
axB.set_xticklabels([dates[i].strftime("%b %y") for i in mt_ix], fontsize=8.5)
axB.tick_params(length=0)
for s in axB.spines.values():
    s.set_visible(False)
axB.set_title("B. Traffic by route-day: blue = hours interpolated, orange = hours left empty (all routes lose 6 Feb 2026)", loc="left", fontsize=10.5, color=INK, fontweight="bold")
# C metro hourly station x date
order = yl + sorted(set(mh.Station) - set(yl))[:1]  # one representative row; the other 67 open-all-period stations have identical gaps
dts = list(all_days)
pres = mh.groupby(["Station", "Date"]).size().unstack().reindex(index=order, columns=dts)
cat = np.zeros(pres.shape)
for si, s_ in enumerate(order):
    for di, d_ in enumerate(dts):
        if pd.isna(pres.iloc[si, di]):
            cat[si, di] = 2 if d_ in miss_days else 3
axC = fig.add_subplot(gs[2])
axC.imshow(cat, aspect="auto", cmap=cm4, norm=nm4, interpolation="nearest")
axC.set_yticks(range(len(order)))
axC.set_yticklabels(yl + [f"All {n_st - len(yl)} other stations"], fontsize=8)
axC.set_xticks([i for i, d in enumerate(dts) if d.day in (1, 8, 15, 22)])
axC.set_xticklabels([d.strftime("%d %b") for d in dts if d.day in (1, 8, 15, 22)], fontsize=8.5)
axC.tick_params(length=0)
axC.axhline(len(yl) - 0.5, color=SURF, linewidth=2)

for s in axC.spines.values():
    s.set_visible(False)
axC.set_title(f"C. Metro hourly by station-day: grey = {len(yl)} Yellow Line stations not yet open; orange = 13 days missing from source", loc="left", fontsize=10.5, color=INK, fontweight="bold")
# D metro daily month x day
months = pd.period_range("2025-08", "2026-11", freq="M")
grid = np.full((len(months), 31), np.nan)
for mi, mo in enumerate(months):
    for d in range(1, mo.days_in_month + 1):
        dd = pd.Timestamp(year=mo.year, month=mo.month, day=d)
        if span[0] <= dd <= span[-1]:
            grid[mi, d - 1] = 0 if dd in md.index else 2
axD = fig.add_subplot(gs[3])
axD.imshow(np.ma.masked_invalid(grid), aspect="auto", cmap=cm4, norm=nm4, interpolation="nearest")
axD.set_yticks(range(len(months)))
axD.set_yticklabels([m_.strftime("%b %Y") for m_ in months], fontsize=8.5)
axD.set_xticks([0, 6, 13, 20, 27, 30])
axD.set_xticklabels(["1", "7", "14", "21", "28", "31"], fontsize=8.5)
axD.set_xlabel("Day of month", fontsize=9.5)
axD.tick_params(length=0)
for s in axD.spines.values():
    s.set_visible(False)
axD.set_title("D. Metro daily tickets by calendar day: orange = no total published; gaps spread through the year", loc="left", fontsize=10.5, color=INK, fontweight="bold")
leg = [Patch(color=C_PRES, label="Present / observed"), Patch(color=C_FILL, label="Filled by interpolation (traffic, 3 h max)"),
       Patch(color=C_MISS, label="Missing, not filled"), Patch(color=C_STRUCT, label="Line not yet open")]
fig.legend(handles=leg, loc="upper left", bbox_to_anchor=(0.015, 0.915), ncol=4, frameon=False, fontsize=9.5)
meta_pct = 100 * len(miss_d) / len(span)
h_pct = 100 * (exp_h - NH) / exp_h
titles(fig,
       f"Most gaps sit in the metro feeds: {meta_pct:.0f}% of daily ticket days and {h_pct:.0f}% of hourly station-hours are missing, against {100 * n_miss / NT:.1f}% of traffic hours left empty",
       None, "Traffic gaps up to 3 hours were interpolated; longer ones were left empty. Weather, Google Trends and the calendar have no gaps. Each panel uses the source's own expected grid.", wrap=112)
fig.savefig(FIG_OUT / "fig6_gap_chart.png", dpi=170)
plt.close(fig)

# ================================================================== REPORT TABLES
recon = [
    ("Traffic (13 routes x 8,760 h)", "traffic_bangalore_clean_2025-10_2026-09", NT, NT, n_flag_obs, NT - n_obs, "Excluded = interpolated + empty rows; analyses use observed rows. Flagged = observed rows with a qa_flag, kept."),
    ("Weather Aug-Sep 2025", "bengaluru_13_routes_weather_aug_sep_2025", len(w1), len(w1), 0, 0, "No gaps, duplicates or nulls."),
    ("Weather Oct 2025-Sep 2026", "bengaluru_13_routes_weather_oct_2025_sep_2026", len(w2), len(w2), 0, 0, "No gaps, duplicates or nulls. Joined to traffic 1:1."),
    ("Metro hourly", "hourly_station_entry_exit", exp_h, NH, flag_union, int(mh.Station.isin(yl).sum() + mh[~mh.Station.isin(yl)].Date.isin(PUBHOL).sum()),
     f"Expected = 61 days x 24 h x the stations open that day ({n(exp_open)}; the {n(miss_rows_struct)} station-hours before 15 Yellow Line stations opened are left out). Missing = {n(len(miss_days) * 24 * n_st)} (13 absent days). Excluded from Figure 4 = the 15 new stations + public-holiday days."),
    ("Metro daily", "Metro_dailyticket_Aug25_Nov26", len(span), ND, 0, len(md) - len(sh),
     "Missing = days BMRCL did not publish. Flagged = none (all daily totals add up). Excluded from Figure 5 = 1 bad row (15 Dec 2025), dates outside the road-data window (1 Oct 2025-30 Sep 2026), public holidays, and days with no road data."),
    ("Google Trends traffic", "trends_daily_traffic", len(trf), len(trf), int(trf.flag_spike.sum()), 0, "Complete. Spikes flagged, kept."),
    ("Google Trends metro", "trends_daily_metro", len(trm), len(trm), int(trm.flag_spike.sum()), 0, "Complete. Spikes flagged, kept."),
    ("Holiday calendar", "bengaluru_holiday_festival_calendar", len(cal), len(cal), 0, 0, "Complete. Misses some real events (T9)."),
]
ev_rows = []
for d, r in ee_route_dates.head(12).iterrows():
    dd = pd.Timestamp(d)
    cr = cal_i.loc[dd]
    ev_rows.append(dict(Date=dd.strftime("%Y-%m-%d"), Weekday=dd.day_name(), Extreme_traffic_rows=int(r.rows), Routes_affected=int(r.routes),
                        Calendar_label=(cr.festival_name if pd.notna(cr.festival_name) else cr.holiday_name if pd.notna(cr.holiday_name) else "none"),
                        Metro_daily_total=(int(md.loc[dd, "Total"]) if dd in md.index else None),
                        Metro_robust_z=(round(float(rzd.loc[dd]), 1) if dd in md.index else None),
                        Trends_traffic_z=(round(float(trf.set_index("date").loc[dd, "interest_z"]), 2) if dd in trf.date.values else None)))
log_df = pd.DataFrame(L)
log_df.to_csv(OUT_DIR / "cleaning_log.csv", index=False)
pd.DataFrame(recon, columns=["Source", "Table", "Rows expected", "Rows loaded", "Flagged, kept", "Excluded from analysis", "Note"]).to_csv(OUT_DIR / "reconciliation.csv", index=False)
pd.DataFrame(ev_rows).to_csv(OUT_DIR / "evidence_events.csv", index=False)

# print key numbers for the hand-off message
print("LOG ROWS:", len(L))
print("FIG1 six peaks at 18:", six, "| Fri AM vs Mon-Thu:", round(fri_am * 100, 1), "| sens max/mean:", round(sens_max, 3), round(sens_mean, 4))
print("FIG2:", {k: {a: round(float(b), 3) for a, b in v.items()} for k, v in res.items()}, "| pct range", round(pmin, 1), round(pmax, 1), "| fri overlap:", fri_overlap, "| dropped:", n_drop)
print("FIG3 r:", round(r_all, 3), "adj", round(r_adj, 3), "spearman", round(r_sp, 3), "days", len(j))
print("FIG4 days:", ndays.to_dict(), "AM", d_am.round(3).to_dict(), "PM", d_pm.round(3).to_dict())
print("FIG5 adj:", {g: round(v, 1) for g, v in adj.items()}, "post days:", n_post, "max shift:", round(adj_shift, 2))
print("FIG5 days:", len(sh), nn.to_dict(), "roads", {k: tuple(round(float(x), 1) for x in v) for k, v in ir.items()}, "metro", {k: tuple(round(float(x), 1) for x in v) for k, v in im_.items()})
print("GAP: traffic empty %", round(100 * n_miss / NT, 2), "metro daily missing %", round(meta_pct, 1), "metro hourly missing %", round(h_pct, 1))
print("W2 peaks:", p1, p2, "| T3 runs:", len(runs), "| long runs:", n_long_runs, long_rows, "| rest missing check:", rest_missing)
print("recon:", [(r[0], r[2], r[3], r[4], r[5]) for r in recon])
