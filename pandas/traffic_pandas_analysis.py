
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# =====================================================
# 1. CONFIGURATION
# =====================================================

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_PATH = BASE_DIR / "final_data" / "traffic_bangalore_clean_2025-10_2026-09.csv"

OUTPUT_DIR = BASE_DIR / "pandas"
OUTPUT_DIR.mkdir(exist_ok=True)

EXCEL_PATH = BASE_DIR / "excel" / "excel_pivot_values.xlsx"

WEEKDAY_ORDER = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday"
]


# =====================================================
# 2. LOAD DATASET
# =====================================================

print("\n========== LOADING DATASET ==========")

df = pd.read_csv(DATA_PATH)

print("Dataset loaded successfully!")
print("Number of rows:", len(df))
print("Number of columns:", len(df.columns))

print("\nFirst five records:")
print(df.head())


# =====================================================
# 3. EXPLORATORY DATA ANALYSIS
# =====================================================

print("\n========== DATASET INSPECTION ==========")

print("\nColumn names:")
print(df.columns.tolist())

print("\nData types:")
print(df.dtypes)

print("\nMissing values:")
print(df.isnull().sum())

print("\nRow status distribution:")
print(df["row_status"].value_counts(dropna=False))


# =====================================================
# 4. DATA PREPROCESSING
# =====================================================

print("\n========== DATA PREPROCESSING ==========")

# Keep only observed records
df_observed = df[
    df["row_status"].astype(str).str.strip() == "observed"
].copy()

print("Original records:", len(df))
print("Observed records:", len(df_observed))

# Convert required columns to numeric
df_observed["hour"] = pd.to_numeric(
    df_observed["hour"], errors="coerce"
)

df_observed["congestion_index"] = pd.to_numeric(
    df_observed["congestion_index"], errors="coerce"
)

# Convert date to datetime
df_observed["date"] = pd.to_datetime(
    df_observed["date"], errors="coerce"
)

# Remove records that cannot be used in this analysis
before_validation = len(df_observed)

df_observed = df_observed.dropna(
    subset=[
        "weekday",
        "hour",
        "congestion_index",
        "date"
    ]
).copy()

# Validate hour range
df_observed = df_observed[
    df_observed["hour"].between(0, 23)
].copy()

print(
    "Records removed during required-field validation:",
    before_validation - len(df_observed)
)

print("Records available for analysis:", len(df_observed))


# =====================================================
# 5. CREATE HOUR-BY-WEEKDAY PIVOT TABLE
# =====================================================

print("\n========== CREATING PIVOT TABLE ==========")

# Standardise weekday labels
df_observed["weekday"] = (
    df_observed["weekday"]
    .astype(str)
    .str.strip()
)

# Keep valid weekday names
df_observed = df_observed[
    df_observed["weekday"].isin(WEEKDAY_ORDER)
].copy()

# Create ordered weekday category
df_observed["weekday"] = pd.Categorical(
    df_observed["weekday"],
    categories=WEEKDAY_ORDER,
    ordered=True
)

# Create the Pivot Table
pivot = pd.pivot_table(
    df_observed,
    values="congestion_index",
    index="weekday",
    columns="hour",
    aggfunc="mean",
    observed=False
)

# Ensure all weekdays and hours are represented
pivot = pivot.reindex(
    index=WEEKDAY_ORDER,
    columns=range(24)
)

print("\nHour-by-Weekday Average Congestion:")
print(pivot.round(2))


# =====================================================
# 6. SAVE PIVOT TABLE
# =====================================================

print("\n========== SAVING RESULTS ==========")

pivot_path = OUTPUT_DIR / "weekday_hour_pivot.csv"

pivot.to_csv(pivot_path)

print("Pivot Table saved:", pivot_path)


# =====================================================
# 7. HOURLY AVERAGE CONGESTION
# =====================================================

hourly_avg = df_observed.groupby(
    "hour"
)["congestion_index"].mean()

hourly_avg = hourly_avg.reindex(range(24))

hourly_avg.to_csv(
    OUTPUT_DIR / "hourly_average.csv",
    header=["average_congestion"]
)

busiest_hour = hourly_avg.idxmax()

print("\n========== HOURLY ANALYSIS ==========")

print("Busiest hour:", busiest_hour)
print(
    "Highest average congestion:",
    round(hourly_avg.max(), 2)
)


# =====================================================
# 8. WEEKDAY AVERAGE CONGESTION
# =====================================================

weekday_avg = df_observed.groupby(
    "weekday",
    observed=True
)["congestion_index"].mean()

weekday_avg = weekday_avg.reindex(WEEKDAY_ORDER)

weekday_avg.to_csv(
    OUTPUT_DIR / "weekday_average.csv",
    header=["average_congestion"]
)

busiest_day = weekday_avg.idxmax()
least_congested_day = weekday_avg.idxmin()

print("\n========== WEEKDAY ANALYSIS ==========")

print("Weekday averages:")
print(weekday_avg.round(2))

print("\nHighest congestion weekday:", busiest_day)
print("Lowest congestion weekday:", least_congested_day)


# =====================================================
# 9. BUSIEST HOUR FOR EACH WEEKDAY
# =====================================================

print("\n========== DAILY PEAK ANALYSIS ==========")

busiest_hour_per_day = pivot.idxmax(axis=1)

print("Busiest hour for each weekday:")
print(busiest_hour_per_day)

busiest_hour_per_day.to_csv(
    OUTPUT_DIR / "busiest_hour_per_day.csv",
    header=["busiest_hour"]
)


# =====================================================
# 10. GENERATE HEATMAP
# =====================================================

print("\n========== GENERATING HEATMAP ==========")

plt.figure(figsize=(16, 7))

plt.imshow(
    pivot.astype(float),
    aspect="auto",
    cmap="YlOrRd",
    interpolation="nearest"
)

plt.colorbar(
    label="Average Congestion Index"
)

plt.xticks(
    range(24),
    range(24)
)

plt.yticks(
    range(7),
    WEEKDAY_ORDER
)

plt.xlabel("Hour of Day")
plt.ylabel("Day of Week")

plt.title(
    "Average Traffic Congestion Across "
    "Weekdays and Hours in Bengaluru"
)

plt.tight_layout()

heatmap_path = OUTPUT_DIR / "weekday_hour_heatmap.png"

plt.savefig(
    heatmap_path,
    dpi=300,
    bbox_inches="tight"
)

plt.show()

print("Heatmap saved:", heatmap_path)


# =====================================================
# 11. COMPARE WITH EXCEL PIVOT TABLE
# =====================================================

print("\n========== EXCEL AND PANDAS COMPARISON ==========")

if EXCEL_PATH.exists():

    excel_pivot = pd.read_excel(
        EXCEL_PATH,
        index_col=0
    )

    # Clean weekday labels
    excel_pivot.index = (
        excel_pivot.index.astype(str).str.strip()
    )

    # Convert Excel column labels to numeric hours
    excel_pivot.columns = pd.to_numeric(
        excel_pivot.columns,
        errors="coerce"
    )

    # Remove invalid columns, if any
    excel_pivot = excel_pivot.loc[
        :,
        excel_pivot.columns.notna()
    ]

    # Align both tables
    excel_pivot.columns = excel_pivot.columns.astype(int)

    excel_pivot = excel_pivot.reindex(
        index=WEEKDAY_ORDER,
        columns=range(24)
    )

    pandas_pivot = pivot.reindex(
        index=WEEKDAY_ORDER,
        columns=range(24)
    )

    # Calculate absolute differences
    difference = (
        excel_pivot.astype(float)
        - pandas_pivot.astype(float)
    ).abs()

    print("\nMaximum absolute difference:")
    print(difference.max().max())

    print("\nAverage absolute difference:")
    print(difference.stack().mean())

    # Save comparison output
    difference.to_csv(
        OUTPUT_DIR / "excel_pandas_difference.csv"
    )

    if difference.fillna(0).to_numpy().max() < 0.000001:
        print("\nExcel and pandas results MATCH!")
    else:
        print(
            "\nDifferences found. "
            "Check filters, source values and rounding."
        )

else:

    print(
        "Excel comparison file not found."
    )

    print(
        "Create excel/excel_pivot_values.xlsx "
        "to perform the comparison."
    )


# =====================================================
# 12. FINAL SUMMARY
# =====================================================

print("\n========== FINAL SUMMARY ==========")

print("Total original records:", len(df))
print("Observed records:", len(df_observed))

print("Busiest hour:", busiest_hour)
print("Highest congestion weekday:", busiest_day)
print("Lowest congestion weekday:", least_congested_day)

print("\nAll analysis steps completed successfully!")
