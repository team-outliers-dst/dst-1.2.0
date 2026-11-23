"""
Tag Google Trends 'related queries' exports into themes, and chart them.

Reads the raw exports you download from Trends (columns: query, search interest, increase percent), e.g.
  searched_with_top-searches_queries_IN-KA_20251001-0000_....csv
  searched_with_rising-searches_queries_IN-KA_20251117-0000_....csv
The list type (top / rising) and the window START date are read from the file name.
NOTE: the end date is not in the file name - write each window's end date in your source register.

Usage : python text_themes.py INPUT_DIR [OUT_DIR] [traffic|metro]   (keep traffic and metro files in separate folders)
Output: queries_all.csv, themes_summary.csv, unmatched_queries.csv, themes_chart.png
Needs : pip install pandas matplotlib
"""
import glob, os, re, sys
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

IN = sys.argv[1] if len(sys.argv) > 1 else "."
OUT = sys.argv[2] if len(sys.argv) > 2 else "text_output"
os.makedirs(OUT, exist_ok=True)

# Theme sets: theme -> keywords (lower-case substrings). A query can match several themes.
# Edit after reading unmatched_queries.csv. Choose a set with the 3rd argument: traffic (default) or metro.
THEME_SETS = {
    "traffic": ("bangalore traffic", {
        "Fines / challans / penalties": ["fine", "fines", "challan", "violation", "penalt", "discount", "rebate", "e-challan", "parivahan", "pay "],
        "Congestion / live traffic": ["today", "live", "jam", "news", "update", "advisory", "restriction", "so much traffic", "long weekend",
                                      "traffic in bangalore", "bengaluru traffic"],
        "Police / BTP": ["police", "btp"],
        "Specific junctions / roads": ["silk board", "hebbal", "kr puram", "marathahalli", "outer ring", "orr ", "electronic city", "whitefield",
                                       "hosur", "sarjapur", "mysore road", "airport road", "flyover", "junction"],
        "Rain / weather": ["rain", "flood", "waterlog", "weather"],
        "Metro / transit": ["metro", "bmtc", "bus ", "purple line", "yellow line"],
    }),
    "metro": ("bangalore metro", {
        "New / yellow / pink lines (launch news)": ["yellow line", "pink line", "blue line", "orange line", "phase 3", "new metro line", "upcoming",
                                                    "inauguration", "bommasandra", "rv road", "modi", "when will", "completion", "is yellow line"],
        "Maps / routes / stations": ["map", "route", "stops", "station", "nearest", "near me", "line"],
        "Timings / schedule": ["timing", "first metro", "last metro", "start", "starting", "starts", "what time", "frequency", "metro time"],
        "Tickets / cards / app": ["ticket", "card", "recharge", "qr", "whatsapp", "app", "fare", "balance"],
        "Places / visitor trips (not commuting)": ["palace", "lalbagh", "iskcon", "ikea", "mall", "temple", "hospital", "places to visit", "commercial street",
                                                   "bus stand", "railway", "orion", "botanical"],
    }),
}
MODE = sys.argv[3] if len(sys.argv) > 3 else "traffic"
TERM, THEMES = THEME_SETS[MODE]

frames = []
for p in sorted(glob.glob(f"{IN}/searched_with_*queries*.csv")):
    name = os.path.basename(p)
    kind = "rising" if "rising" in name else "top"
    start = re.search(r"_(\d{8})-\d{4}_", name)
    start = pd.to_datetime(start.group(1)).strftime("%d %b %Y") if start else "?"
    d = pd.read_csv(p)
    d.columns = ["query", "search_interest", "increase_percent"]
    d["list"], d["window_start"], d["file"] = kind, start, name
    frames.append(d)
if not frames: sys.exit(f"No searched_with_*queries*.csv files found in {IN}")
df = pd.concat(frames, ignore_index=True)
df["label"] = df["list"].str.capitalize() + " (from " + df["window_start"] + ")"
df["q"] = " " + df["query"].str.lower() + " "
for t, kws in THEMES.items():
    df[t] = df["q"].apply(lambda s: any(k in s for k in kws))
df["Other"] = ~df[list(THEMES)].any(axis=1)
themes = list(THEMES) + ["Other"]
df.drop(columns="q").to_csv(f"{OUT}/queries_all.csv", index=False)
df[df["Other"]][["label", "query", "search_interest", "increase_percent"]].to_csv(f"{OUT}/unmatched_queries.csv", index=False)

rows = []
for lab, g in df.groupby("label"):
    tot = g["search_interest"].sum()
    for t in themes:
        rows.append(dict(window=lab, list=g["list"].iloc[0], theme=t, n_queries=int(g[t].sum()), n_total=len(g),
                         share_of_queries=round(g[t].mean(), 3), share_of_search_interest=round(g.loc[g[t], "search_interest"].sum() / tot, 3)))
S = pd.DataFrame(rows); S.to_csv(f"{OUT}/themes_summary.csv", index=False)

fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=True)
for ax, kind in zip(axes, ["top", "rising"]):
    piv = S[S["list"] == kind].pivot(index="theme", columns="window", values="share_of_search_interest").reindex(themes)
    piv.plot.barh(ax=ax, width=0.8); ax.invert_yaxis(); ax.set_ylabel("")
    ax.set_title("Top searches" if kind == "top" else "Rising searches", fontsize=10)
    ax.set_xlabel("Share of the list's total search interest"); ax.legend(frameon=False, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
top_all = S[S.window.str.startswith("Top")].groupby("theme")["share_of_search_interest"].mean().drop("Other").idxmax()
fig.suptitle(f"What people search alongside \"{TERM}\": '{top_all}' leads the top searches", x=0.01, ha="left", fontsize=12, fontweight="bold")
fig.text(0.01, -0.02, "Source: Google Trends related queries, Karnataka. A query can fall under several themes, so shares can exceed 100% in total.", fontsize=7, color="gray")
fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(f"{OUT}/themes_chart.png", dpi=200, bbox_inches="tight")

print(S.pivot(index="theme", columns="window", values="share_of_search_interest").reindex(themes).round(2).to_string())
print(f"\n{int(df['Other'].sum())} of {len(df)} queries matched no theme -> review {OUT}/unmatched_queries.csv")
