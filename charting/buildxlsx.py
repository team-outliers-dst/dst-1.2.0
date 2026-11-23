import sys, pandas as pd
from pathlib import Path
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

BASE = Path(__file__).resolve().parent
src = BASE/"out"
dst = BASE/"out"/"cleaning_log.xlsx"
log = pd.read_csv(src / "cleaning_log.csv"); rec = pd.read_csv(src / "reconciliation.csv"); ev = pd.read_csv(src / "evidence_events.csv")
F = lambda **k: Font(name="Arial", size=k.pop("size", 10), **k)
hdr_fill = PatternFill("solid", fgColor="1F3A5F"); ask_fill = PatternFill("solid", fgColor="FFF2CC")
thin = Side(style="thin", color="D0D0D0"); bd = Border(left=thin, right=thin, top=thin, bottom=thin)
wrap = Alignment(wrap_text=True, vertical="top")
wb = Workbook()

def table(ws, df, widths, start=1):
    for j, c in enumerate(df.columns, 1):
        cell = ws.cell(start, j, c.replace("_", " ")); cell.font = F(bold=True, color="FFFFFF"); cell.fill = hdr_fill; cell.alignment = Alignment(wrap_text=True, vertical="center"); cell.border = bd
    for i, row in enumerate(df.itertuples(index=False), start + 1):
        for j, v in enumerate(row, 1):
            if pd.isna(v): v = None
            cell = ws.cell(i, j, v); cell.font = F(); cell.alignment = wrap; cell.border = bd
    for j, w in enumerate(widths, 1): ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = ws.cell(start + 1, 2)

ws = wb.active; ws.title = "Cleaning_Log"
table(ws, log, [6, 14, 16, 42, 28, 14, 10, 52, 46, 20, 28])
for r in range(2, len(log) + 2):
    if str(ws.cell(r, 11).value).startswith("Needs"):
        for c in range(1, 12): ws.cell(r, c).fill = ask_fill
ws.auto_filter.ref = f"A1:K{len(log)+1}"

ws2 = wb.create_sheet("Reconciliation")
cols = ["Source", "Table", "Rows expected", "Rows loaded", "Missing rows", "Missing %", "Flagged, kept", "Flagged % of loaded", "Excluded from analysis", "Rows analysed", "Note"]
for j, c in enumerate(cols, 1):
    cell = ws2.cell(1, j, c); cell.font = F(bold=True, color="FFFFFF"); cell.fill = hdr_fill; cell.alignment = Alignment(wrap_text=True, vertical="center"); cell.border = bd
for i, r in enumerate(rec.itertuples(index=False), 2):
    vals = [r[0], r[1], r[2], r[3], f"=C{i}-D{i}", f"=IF(C{i}=0,0,E{i}/C{i})", r[4], f"=IF(D{i}=0,0,G{i}/D{i})", r[5], f"=D{i}-I{i}", r[6]]
    for j, v in enumerate(vals, 1):
        cell = ws2.cell(i, j, v); cell.font = F(color="0000FF" if j in (3, 4, 7, 9) else "000000"); cell.alignment = wrap; cell.border = bd
        if j in (3, 4, 5, 7, 9, 10): cell.number_format = "#,##0"
        if j in (6, 8): cell.number_format = "0.0%"
n = len(rec) + 1
ws2.cell(n + 2, 1, "Blue = counted by the build script from the raw files; black = formula. 'Rows analysed' = rows loaded minus rows excluded from the analyses (the exclusion rule differs per source: see Note).").font = F(italic=True, color="595959")
for j, w in enumerate([30, 40, 13, 13, 13, 10, 12, 12, 14, 13, 70], 1): ws2.column_dimensions[get_column_letter(j)].width = w
ws2.freeze_panes = "C2"

ws3 = wb.create_sheet("Evidence_Events")
table(ws3, ev, [12, 12, 14, 12, 18, 16, 14, 14])
for r in range(2, len(ev) + 2):
    for c in (6,): ws3.cell(r, c).number_format = "#,##0"
ws3.cell(len(ev) + 3, 1, "Dates with the most traffic rows flagged extreme_event. Calendar_label 'none' = the holiday/festival calendar has no entry for that date. Metro robust z = median/MAD z-score of the daily total.").font = F(italic=True, color="595959")

for name, csv, widths in [("Data_Inventory", "data_inventory.csv", [16, 30, 26, 10, 12, 26, 10, 8, 9, 30, 50]),
                           ("V_Profile", "v_profile.csv", [16, 30, 8, 14, 9, 8, 8, 10, 11, 11, 9, 9, 9, 40, 22, 60]),
                           ("Source_Register", "source_register.csv", [8, 30, 22, 45, 26, 55, 60, 22, 34])]:
    p = src / csv
    if not p.exists(): sys.exit(f"{p} missing: run build_docs_tables.py first")
    d = pd.read_csv(p); w = wb.create_sheet(name); table(w, d, widths); w.auto_filter.ref = w.dimensions
    if name == "Source_Register":
        for r in range(2, len(d) + 2):
            if "TO FILL" in " ".join(str(w.cell(r, c).value) for c in range(1, d.shape[1] + 1)):
                for c in range(1, d.shape[1] + 1): w.cell(r, c).fill = ask_fill

ws4 = wb.create_sheet("Read_Me")
lines = [("Cleaning log: Bengaluru weekday commuting case study (Case Study B)", True),
 ("One row per cleaning decision: problem, how it was found, rows affected, action, why. Every number is computed by build_cleaning_log_and_charts.py from the final data, not typed in.", False),
 ("Yellow rows = need a teammate to confirm (method detail that is not visible in the data files). On Source_Register, yellow = a field marked TO FILL.", False),
 (f"Sheets: Cleaning_Log ({len(log)} decisions), Reconciliation (rows expected / loaded / missing / flagged / excluded per source, with formulas), Evidence_Events (extreme-traffic dates checked against calendar, metro and Trends), "
  "Data_Inventory (every field: level of measurement and structure), V_Profile (rows, MB, arrival rate, format and dominant V per table), Source_Register (URL, access date, method, terms of use).", False),
 ("Assumptions: Metro hourly expected grid = 61 days x 24 h x 83 stations. Weekday groups: Mon, Tue-Thu, Fri, Weekend. Rainy evening = at least 0.1 mm in an hour of 18:00-21:00. Traffic interpolation = linear, gaps of 3 hours or less (rule reproduced from the data, see T4).", False),
 ("To reproduce: python charting/cleanchart.py, then python charting/build_docs_tables.py, then python charting/buildxlsx.py.", False)]
for i, (t, b) in enumerate(lines, 1):
    c = ws4.cell(i, 1, t); c.font = F(bold=b, size=12 if b else 10); c.alignment = Alignment(wrap_text=True, vertical="top")
ws4.column_dimensions["A"].width = 120
wb.save(dst)