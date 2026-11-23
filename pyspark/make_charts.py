"""
Make the report charts from the PySpark output CSVs.

Usage:
  python make_charts.py [INPUT_DIR] [OUT_DIR] [TRAFFIC_CSV]
    INPUT_DIR   folder with the PySpark outputs        (default: pyspark_output)
    OUT_DIR     folder for the PNG charts              (default: charts)
    TRAFFIC_CSV optional: the cleaned traffic CSV, only needed for the gap chart

Needs: pip install pandas matplotlib numpy
Chart titles are built from the numbers, so they stay true if the data changes.
"""
import os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

IN = sys.argv[1] if len(sys.argv) > 1 else "pyspark"
OUT = sys.argv[2] if len(sys.argv) > 2 else "pyspark/charts"
TRAFFIC_CSV = sys.argv[3] if len(sys.argv) > 3 else "final_data/traffic_bangalore_clean_2025-10_2026-09.csv"
os.makedirs(OUT, exist_ok=True)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left"})
SRC = "Source: Google Maps travel-time readings, 13 Bengaluru routes, Oct 2025 - Sep 2026 (observed hours only)"

def save(fig, name):
    fig.savefig(f"{OUT}/{name}.png", dpi=200, bbox_inches="tight"); plt.close(fig); print("saved", name)

def fmt_hour(h):
    return f"{(h % 12) or 12} {'AM' if h < 12 else 'PM'}"

# ---------------------------------------------------------------- 1. hour x weekday heatmap
pv = pd.read_csv(f"{IN}/heatmap_pivot.csv", index_col=0).reindex(DAYS)
pv.columns = pv.columns.astype(int)
wk = pv.loc[DAYS[:5]].mean()                              # average weekday profile
am = int(wk.loc[6:12].idxmax()); pm = int(wk.loc[15:22].idxmax())
sun_max = pv.loc["Sunday"].max()
fig, ax = plt.subplots(figsize=(11, 3.9))
im = ax.imshow(pv.values, aspect="auto", cmap="YlOrRd")
ax.set_xticks(range(24)); ax.set_xticklabels([str(h) for h in pv.columns], fontsize=8)
ax.set_yticks(range(7)); ax.set_yticklabels(DAYS)
ax.set_xlabel("Hour of day (IST, 24-hour clock)")
for r in range(7):
    for c in range(24):
        v = pv.values[r, c]
        ax.text(c, r, f"{v:.1f}", ha="center", va="center", fontsize=6, color="white" if v > 1.95 else "black")
cb = fig.colorbar(im, ax=ax, pad=0.01); cb.set_label("Congestion index (1.0 = free-flowing)")
ax.set_title(f"Weekday roads clog twice a day, peaking at {fmt_hour(am)} and {fmt_hour(pm)};\n"
             f"Sundays never exceed {sun_max:.1f}x free-flow travel time", pad=10)
fig.text(0.01, -0.03, SRC, fontsize=7, color="gray")
save(fig, "01_heatmap_hour_by_weekday")

# ---------------------------------------------------------------- 2. Friday vs Mon-Thu vs weekend profiles
long = pd.read_csv(f"{IN}/heatmap_weekday_hour.csv")
def grp(n): return "Mon-Thu" if n <= 3 else ("Friday" if n == 4 else ("Saturday" if n == 5 else "Sunday"))
long["group"] = long["weekday_num"].map(grp)
prof = (long.assign(w=long["avg_congestion"] * long["n_rows"]).groupby(["group", "hour"])
        .apply(lambda d: d["w"].sum() / d["n_rows"].sum(), include_groups=False).unstack(0))
fri_am, mt_am = prof.loc[6:12, "Friday"].max(), prof.loc[6:12, "Mon-Thu"].max()
fri_late, mt_late = prof.loc[19:23, "Friday"].mean(), prof.loc[19:23, "Mon-Thu"].mean()
fig, ax = plt.subplots(figsize=(9, 4.2))
sty = {"Mon-Thu": ("#4c72b0", "-"), "Friday": ("#c44e52", "-"), "Saturday": ("#55a868", "--"), "Sunday": ("#8c8c8c", ":")}
for g, (col, ls) in sty.items():
    ax.plot(prof.index, prof[g], color=col, ls=ls, lw=2.2 if g == "Friday" else 1.6, label=g)
ax.set_xticks(range(0, 24, 2)); ax.set_xlabel("Hour of day (IST)"); ax.set_ylabel("Congestion index (1.0 = free-flowing)")
ax.legend(frameon=False, ncol=4, loc="upper left")
ax.set_title(f"Friday's morning peak is lighter than Mon-Thu ({fri_am:.2f} vs {mt_am:.2f}),\n"
             f"but Friday nights stay busier after 7 PM ({fri_late:.2f} vs {mt_late:.2f})", pad=10)
fig.text(0.01, -0.03, SRC, fontsize=7, color="gray")
save(fig, "02_friday_vs_weekday_profiles")

# ---------------------------------------------------------------- 3. rain: raw vs controlled (joined chart)
simple = pd.read_csv(f"{IN}/rain_effect_simple.csv").set_index("rain_band")
ctrl = pd.read_csv(f"{IN}/rain_effect_controlled.csv").set_index("rain_band")
order = ["No rain", "Light (<2.5 mm/h)", "Moderate (2.5-7.6 mm/h)", "Heavy (>7.6 mm/h)"]
simple = simple.reindex([b for b in order if b in simple.index]); ctrl = ctrl.reindex([b for b in order[1:] if b in ctrl.index])
base = simple.loc["No rain", "avg_congestion"]
raw_diff = simple["avg_congestion"] - base
short = lambda s: s.split(" (")[0] + ("\n(" + s.split(" (")[1] if " (" in s else "")
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1.1, 1]})
bars = a1.bar([short(b) for b in raw_diff.index], simple["avg_congestion"], color="#9ecae1")
for b, n in zip(bars, simple["n_rows"]): a1.text(b.get_x() + b.get_width() / 2, b.get_height() + 0.02, f"n={n:,}", ha="center", fontsize=8)
a1.set_ylim(0, simple["avg_congestion"].max() * 1.18); a1.set_ylabel("Average congestion index")
a1.set_title("A. Raw comparison", fontsize=10)
cols = ["#fdae6b" if n >= 100 else "#d9d9d9" for n in ctrl["rows_compared"]]
bars = a2.bar([short(b) for b in ctrl.index], ctrl["extra_congestion_vs_no_rain"], color=cols)
for b, n, v in zip(bars, ctrl["rows_compared"], ctrl["extra_congestion_vs_no_rain"]):
    a2.text(b.get_x() + b.get_width() / 2, max(v, 0) + 0.004, f"{v:+.3f}\nn={n:,}" + ("\n(too few rows)" if n < 100 else "\n(smaller sample)" if n < 1000 else ""), ha="center", fontsize=8)
a2.set_ylim(0, max(ctrl["extra_congestion_vs_no_rain"].max(), 0.1) * 1.45)
a2.set_ylabel("Extra congestion vs no rain"); a2.set_title("B. Same month, day type and hour as the no-rain hours", fontsize=10)
light_raw, light_ctrl = raw_diff.iloc[1], ctrl["extra_congestion_vs_no_rain"].iloc[0]
fig.suptitle(f"Light rain looks like +{light_raw:.2f} congestion, but only +{light_ctrl:.3f} once timing is held constant:\n"
             "most of the raw gap is explained by when it rains (hour, day type, month)", x=0.01, ha="left", fontsize=12, fontweight="bold")
fig.text(0.01, -0.02, "Source: Google Maps travel times joined to Open-Meteo hourly rain. Grey bar rests on too few rows to trust. Association, not proof of cause.",
         fontsize=7, color="gray")
fig.tight_layout(rect=(0, 0.02, 1, 0.86)); save(fig, "03_rain_effect_raw_vs_controlled")

# ---------------------------------------------------------------- 4. route ranking (z-scores)
rt = pd.read_csv(f"{IN}/route_ranking.csv").sort_values("congestion_z")
fig, ax = plt.subplots(figsize=(8, 5))
ax.barh(rt["route_name"], rt["congestion_z"], color=["#c44e52" if z > 0 else "#4c72b0" for z in rt["congestion_z"]])
for y, (z, c) in enumerate(zip(rt["congestion_z"], rt["avg_congestion"])):
    ax.text(z + (0.05 if z >= 0 else -0.05), y, f"{c:.2f}", va="center", ha="left" if z >= 0 else "right", fontsize=8)
ax.axvline(0, color="black", lw=0.8); ax.set_xlabel("Z-score of average congestion index (label = raw index)")
ax.set_xlim(rt["congestion_z"].min() - 0.5, rt["congestion_z"].max() + 0.5)
ax.set_title(f"{rt.iloc[-1]['route_name']} and {rt.iloc[-2]['route_name']} are the most congested corridors; "
             f"{rt.iloc[0]['route_name']} the least", pad=10, wrap=True)
fig.text(0.01, -0.03, SRC + "\nIndex is relative to each route's own free-flow time, so long and short routes compare fairly.", fontsize=7, color="gray")
save(fig, "04_route_ranking_zscore")

# ---------------------------------------------------------------- 5. gap chart (needs the traffic CSV)
if TRAFFIC_CSV and os.path.exists(TRAFFIC_CSV):
    t = pd.read_csv(TRAFFIC_CSV, usecols=["route_name", "date", "row_status"])
    t["date"] = pd.to_datetime(t["date"]); t["gap"] = t["row_status"].isin(["missing_hour", "interpolated"]).astype(int)
    g = t.groupby(["route_name", "date"])["gap"].sum().unstack(0).fillna(0)
    miss, interp = (t["row_status"] == "missing_hour").sum(), (t["row_status"] == "interpolated").sum()
    fig, ax = plt.subplots(figsize=(11, 4.2))
    im = ax.imshow(g.T.values, aspect="auto", cmap="Reds", vmin=0, vmax=24, interpolation="nearest")
    ax.set_yticks(range(g.shape[1])); ax.set_yticklabels(g.columns, fontsize=8)
    ticks = list(range(0, len(g), 30)); ax.set_xticks(ticks); ax.set_xticklabels([g.index[i].strftime("%d %b %y") for i in ticks], fontsize=8)
    fig.colorbar(im, ax=ax, pad=0.01).set_label("Missing or filled-in hours per day")
    worst_route, worst_day = g.sum().idxmax(), g.sum(axis=1).idxmax()
    ax.set_title(f"{miss:,} route-hours are missing and {interp:,} were filled in; worst route: {worst_route} "
                 f"({int(g[worst_route].sum()):,} hours), worst day: {worst_day:%d %b %Y} ({int(g.loc[worst_day].sum())} hours)", pad=10, fontsize=11)
    fig.text(0.01, -0.03, "Gaps of up to 3 hours were interpolated; longer outages were left empty, never invented.", fontsize=7, color="gray")
    save(fig, "05_gap_chart")
else:
    print("gap chart skipped (pass the cleaned traffic CSV as the 3rd argument to make it)")