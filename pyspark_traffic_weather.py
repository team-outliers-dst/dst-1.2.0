"""
PySpark job: traffic + weather  ->  hourly table, join, hour-by-weekday heatmap, rain effect.

Run:   python pyspark_traffic_weather.py  [DATA_DIR]  [OUT_DIR]
Needs: Java 11/17/21, `pip install pyspark pandas`.

What it does (and logs row counts for, as the brief requires):
  1. Load the traffic CSV (your largest table) and the two weather CSVs
  2. Cast types, drop rows with null keys
  3. Resample traffic to one row per route-hour (collapses any duplicate readings)
  4. Union the two weather files, de-duplicate, sanity-check the time zone
  5. Join traffic to weather on route_code + date + hour
  6. Aggregate: hour-by-weekday heatmap, route ranking, rain effect with hour/day-type/month held constant
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
import pandas as pd
from pyspark.sql import SparkSession, functions as F

# ------------------------- CONFIG (edit file names if yours differ) -------------------------
DATA_DIR = sys.argv[1] if len(sys.argv) > 1 else "final_data"
OUT_DIR = sys.argv[2] if len(sys.argv) > 2 else "pyspark"
TRAFFIC_CSV = f"{DATA_DIR}/traffic_bangalore_clean_2025-10_2026-09.csv"
WEATHER_CSVS = [f"{DATA_DIR}/bengaluru_13_routes_weather_aug_sep_2025.csv",
                f"{DATA_DIR}/bengaluru_13_routes_weather_oct_2025_sep_2026.csv"]
MIN_CELL_ROWS = 5          # ignore hour/day-type/month cells with fewer rows in the rain comparison
# ---------------------------------------------------------------------------------------------

os.makedirs(OUT_DIR, exist_ok=True)
spark = (SparkSession.builder.appName("bengaluru_mobility").master("local[*]")
         .config("spark.sql.shuffle.partitions", "8").config("spark.sql.execution.arrow.pyspark.enabled", "false")
         .config("spark.sql.session.timeZone", "Asia/Kolkata").getOrCreate())
spark.sparkContext.setLogLevel("ERROR")

LOG = []
def count(step, df, note=""):
    n = df.count()
    LOG.append({"step": step, "rows": n, "note": note})
    print(f"{step:<52}{n:>10,}  {note}")
    return n

def require(df, cols, name):
    missing = set(cols) - set(df.columns)
    if missing:
        sys.exit(f"{name} is missing columns {sorted(missing)}. Columns found: {df.columns}")

# ============================== 1. TRAFFIC ==============================
t_raw = spark.read.option("header", True).option("inferSchema", True).csv(TRAFFIC_CSV)
require(t_raw, ["route_code", "date", "hour", "congestion_index", "speed_kmph", "duration_min", "row_status"], "Traffic file")
n_raw = count("traffic: rows loaded from CSV", t_raw)

t = (t_raw
     .withColumn("date", F.to_date("date"))
     .withColumn("hour", F.col("hour").cast("int"))
     .withColumn("congestion_index", F.col("congestion_index").cast("double"))
     .withColumn("speed_kmph", F.col("speed_kmph").cast("double"))
     .withColumn("duration_min", F.col("duration_min").cast("double")))
t = t.dropna(subset=["route_code", "date", "hour"])
n_keys = count("traffic: after dropping rows with null keys", t, f"{n_raw - t.count():,} dropped")

# Resample to ONE row per route-hour. The cleaned file is already hourly, so this mostly confirms
# there are no duplicates; if you point it at the raw 30-minute file it genuinely collapses to hourly.
name_col = "route_name" if "route_name" in t.columns else "route_code"
hourly = (t.groupBy("route_code", "date", "hour")
            .agg(F.first(name_col).alias("route_name"),
                 F.avg("congestion_index").alias("congestion_index"),
                 F.avg("speed_kmph").alias("speed_kmph"),
                 F.avg("duration_min").alias("duration_min"),
                 F.count("*").alias("readings_in_hour"),
                 F.min(F.when(F.col("row_status") == "observed", 1).otherwise(0)).alias("is_observed")))
n_hourly = count("traffic: after resample to one row per route-hour", hourly,
                 f"{n_keys - hourly.count():,} duplicate readings collapsed")

hourly = (hourly
          .withColumn("weekday_num", (F.dayofweek("date") + 5) % 7)          # Monday = 0
          .withColumn("weekday", F.date_format("date", "EEEE"))
          .withColumn("month", F.month("date"))
          .withColumn("day_type", F.when(F.col("weekday_num") == 4, "Friday")
                                   .when(F.col("weekday_num") >= 5, "Weekend").otherwise("Mon-Thu")))

# ============================== 2. WEATHER ==============================
w_parts = []
for p in WEATHER_CSVS:
    w = spark.read.option("header", True).option("inferSchema", True).csv(p)
    require(w, ["route_code", "date", "hour", "rain"], f"Weather file {os.path.basename(p)}")
    count(f"weather: rows loaded from {os.path.basename(p)}", w)
    w_parts.append(w)
keep = ["route_code", "date", "hour", "temperature_2m", "apparent_temperature",
        "relative_humidity_2m", "precipitation", "rain", "weather_code"]
w_all = w_parts[0].select([c for c in keep if c in w_parts[0].columns])
for w in w_parts[1:]:
    w_all = w_all.unionByName(w.select([c for c in keep if c in w.columns]), allowMissingColumns=True)
w_all = (w_all.withColumn("date", F.to_date("date")).withColumn("hour", F.col("hour").cast("int"))
              .withColumn("rain", F.col("rain").cast("double")))
n_w_union = count("weather: after combining both files", w_all)
weather = w_all.dropDuplicates(["route_code", "date", "hour"])
count("weather: after removing duplicate route-hours", weather, f"{n_w_union - weather.count():,} duplicates removed")

# Time-zone sanity check: Bengaluru temperature should peak mid-afternoon IST (about 13-17h).
if "temperature_2m" in weather.columns:
    tz = weather.groupBy("hour").agg(F.avg("temperature_2m").alias("t")).toPandas()
    peak = int(tz.loc[tz["t"].idxmax(), "hour"])
    ok = 12 <= peak <= 17
    print(f"time-zone check: average temperature peaks at hour {peak} -> " +
          ("looks like IST" if ok else "WARNING: does not look like IST (GMT would peak about 5.5 h earlier). Re-fetch with timezone=Asia/Kolkata."))
    LOG.append({"step": "weather: time-zone check", "rows": None, "note": f"temperature peaks at hour {peak}" + ("" if ok else " - CHECK TIMEZONE")})

# ============================== 3. JOIN ==============================
joined = hourly.join(weather, ["route_code", "date", "hour"], "left")
count("join: traffic LEFT JOIN weather", joined, "should equal the resampled traffic rows")
unmatched = joined.filter(F.col("rain").isNull()).count()
LOG.append({"step": "join: traffic rows with no weather match", "rows": unmatched, "note": "expected 0"})
print(f"{'join: traffic rows with no weather match':<52}{unmatched:>10,}  expected 0")

joined = joined.withColumn("rain_band",
    F.when(F.col("rain").isNull(), "No weather data")
     .when(F.col("rain") == 0, "No rain")
     .when(F.col("rain") < 2.5, "Light (<2.5 mm/h)")
     .when(F.col("rain") < 7.6, "Moderate (2.5-7.6 mm/h)")
     .otherwise("Heavy (>7.6 mm/h)"))       # illustrative thresholds - state yours in the report

strict = joined.filter((F.col("is_observed") == 1) & F.col("congestion_index").isNotNull())
count("analysis set: observed rows only", strict, "interpolated / missing rows excluded from the averages")

# ============================== 4. AGGREGATIONS ==============================
heat = (strict.groupBy("weekday_num", "weekday", "hour")
        .agg(F.avg("congestion_index").alias("avg_congestion"), F.avg("speed_kmph").alias("avg_speed_kmph"),
             F.count("*").alias("n_rows")).orderBy("weekday_num", "hour").toPandas())
heat.to_csv(f"{OUT_DIR}/heatmap_weekday_hour.csv", index=False)
heat.pivot(index="weekday", columns="hour", values="avg_congestion").reindex(
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]).round(3).to_csv(f"{OUT_DIR}/heatmap_pivot.csv")

routes = (strict.groupBy("route_code", "route_name")
          .agg(F.avg("congestion_index").alias("avg_congestion"), F.avg("duration_min").alias("avg_duration_min"),
               F.count("*").alias("n_rows")).orderBy(F.desc("avg_congestion")).toPandas())
routes["congestion_z"] = (routes["avg_congestion"] - routes["avg_congestion"].mean()) / routes["avg_congestion"].std()
routes.to_csv(f"{OUT_DIR}/route_ranking.csv", index=False)

# Rain effect with hour, day type and month held constant: compare each rain band with "No rain"
# inside the same (month, day_type, hour) cell, then average the differences weighted by cell size.
cell = (strict.filter(F.col("rain_band") != "No weather data")
        .groupBy("month", "day_type", "hour", "rain_band")
        .agg(F.avg("congestion_index").alias("avg_c"), F.count("*").alias("n")).filter(F.col("n") >= MIN_CELL_ROWS))
base = cell.filter(F.col("rain_band") == "No rain").select("month", "day_type", "hour", F.col("avg_c").alias("base_c"))
rain = (cell.filter(F.col("rain_band") != "No rain").join(base, ["month", "day_type", "hour"])
        .withColumn("diff", F.col("avg_c") - F.col("base_c"))
        .groupBy("rain_band")
        .agg((F.sum(F.col("diff") * F.col("n")) / F.sum("n")).alias("extra_congestion_vs_no_rain"),
             F.sum("n").alias("rows_compared"), F.count("*").alias("matched_cells")).toPandas())
rain.round(4).to_csv(f"{OUT_DIR}/rain_effect_controlled.csv", index=False)

# Simple (uncontrolled) rain comparison, for contrast
simple = (strict.groupBy("rain_band").agg(F.avg("congestion_index").alias("avg_congestion"), F.count("*").alias("n_rows"))
          .toPandas()); simple.round(4).to_csv(f"{OUT_DIR}/rain_effect_simple.csv", index=False)

pd.DataFrame(LOG).to_csv(f"{OUT_DIR}/pyspark_row_counts.csv", index=False)
print("\nSaved to", OUT_DIR, ":", sorted(os.listdir(OUT_DIR)))
print("\nControlled rain effect:\n", rain.round(3).to_string(index=False))
spark.stop()