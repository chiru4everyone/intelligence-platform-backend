"""
Generates a sample Excel workbook with correctly named sheets for all 4 platforms.
Run once to produce the template file you can fill with real data.

Usage:
    python scripts/create_sample_excel.py

Output:
    templates/sample_data_model.xlsx
"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from pathlib import Path

H_FILL = PatternFill(fill_type="solid", fgColor="1a2535")
H_FONT = Font(bold=True, color="7ec67a")
TEAL_FONT = Font(bold=True, color="2ec4b6")
SAPPH_FONT = Font(bold=True, color="4a7fe8")
GOLD_FONT = Font(bold=True, color="c8a96e")


def header_row(ws, cols: list[str], row=1):
    for i, col in enumerate(cols, 1):
        c = ws.cell(row=row, column=i, value=col)
        c.font = H_FONT
        c.fill = H_FILL
        c.alignment = Alignment(horizontal="center")


def sample_row(ws, values: list, row: int):
    for i, v in enumerate(values, 1):
        ws.cell(row=row, column=i, value=v)


def kv_sheet(ws, pairs: list[tuple]):
    ws.cell(1, 1, "Field").font = H_FONT
    ws.cell(1, 2, "Value").font = H_FONT
    for i, (k, v) in enumerate(pairs, 2):
        ws.cell(i, 1, k)
        ws.cell(i, 2, v)
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 20


wb = Workbook()
wb.remove(wb.active)   # remove default sheet

# ── EPIDEMIOLOGY ───────────────────────────────────────────
ws = wb.create_sheet("epi_topline")
kv_sheet(ws, [
    ("total_adult_population", "814.9M"),
    ("prevalent_cases_all_diseases", "380.6M"),
    ("new_incident_cases", "25.6M"),
    ("diagnosed_cases", "189.7M"),
    ("eligible_for_treatment", "145.6M"),
    ("currently_treated", "105.9M"),
    ("disease_deaths_annual", "3.08M"),
    ("forecast_population_2035", "527.6M"),
])

ws = wb.create_sheet("epi_funnel")
header_row(ws, ["stage", "value", "pct"])
sample_data = [
    ("Prevalent Cases", 380.6, 100),
    ("Diagnosed", 189.7, 49.8),
    ("Eligible for Treatment", 145.6, 38.3),
    ("Currently Treated", 105.9, 27.8),
    ("Adherent at 12 months", 88.7, 23.3),
]
for i, row in enumerate(sample_data, 2):
    sample_row(ws, list(row), i)

ws = wb.create_sheet("epi_geography")
header_row(ws, ["country", "prevalence_per_100k", "treatment_rate_pct", "undiagnosed_pct", "mortality_per_100k", "opportunity_score"])
for i, row in enumerate([
    ("India", 44200, 42, 58, 312, 8.2),
    ("United States", 56800, 68, 32, 198, 6.4),
    ("Brazil", 41000, 38, 62, 287, 8.7),
    ("Germany", 38400, 74, 26, 142, 5.1),
], 2):
    sample_row(ws, list(row), i)

ws = wb.create_sheet("epi_forecast")
header_row(ws, ["year", "base_case_m", "bull_case_m", "bear_case_m"])
for i, row in enumerate([
    (2025, 380.6, 380.6, 380.6),
    (2026, 393.2, 398.4, 388.1),
    (2027, 406.4, 417.3, 395.8),
    (2028, 420.0, 437.2, 403.7),
    (2029, 434.1, 458.3, 411.8),
    (2030, 448.7, 480.6, 420.1),
    (2035, 527.6, 572.4, 487.9),
], 2):
    sample_row(ws, list(row), i)

# ── TRADE INTELLIGENCE ────────────────────────────────────────
ws = wb.create_sheet("trade_topline")
kv_sheet(ws, [
    ("global_pharma_trade_value_usd_bn", 842),
    ("supply_chain_risk_score", 6.8),
    ("tariff_affected_value_usd_bn", 124),
    ("hs_codes_tracked", 84),
])

ws = wb.create_sheet("trade_flows")
header_row(ws, ["origin", "destination", "value_usd_bn", "pct_of_total"])
for i, row in enumerate([
    ("EU", "USA", 142.4, 16.9),
    ("China", "USA", 98.2, 11.7),
    ("India", "USA", 76.8, 9.1),
    ("Switzerland", "Global", 64.3, 7.6),
    ("USA", "EU", 58.7, 7.0),
], 2):
    sample_row(ws, list(row), i)

ws = wb.create_sheet("trade_risks")
header_row(ws, ["dot", "name", "detail", "score", "score_color"])
for i, row in enumerate([
    ("▲", "Tariff Escalation Risk", "US-China bilateral pharma tariffs above 25%", 8.4, "var(--coral)"),
    ("▲", "API Concentration Risk", "60% API supply from single country", 7.9, "var(--coral)"),
    ("●", "FTA Coverage Gap", "35% of trade flows lack preferential tariff access", 6.1, "var(--gold)"),
], 2):
    sample_row(ws, list(row), i)

ws = wb.create_sheet("trade_geography")
header_row(ws, ["corridor", "value_usd_bn", "yoy_pct", "tariff_pct", "fta", "risk"])
for i, row in enumerate([
    ("EU → USA", 142.4, 4.2, 0.0, "Yes", "Low"),
    ("China → USA", 98.2, -2.1, 25.0, "No", "High"),
    ("India → USA", 76.8, 8.4, 0.0, "No", "Medium"),
], 2):
    sample_row(ws, list(row), i)

ws = wb.create_sheet("trade_forecast")
header_row(ws, ["year", "base_case_usd_bn", "bull_case_usd_bn", "bear_case_usd_bn"])
for i, row in enumerate([
    (2025, 842, 842, 842),
    (2026, 898, 921, 874),
    (2027, 958, 1004, 906),
    (2028, 1021, 1092, 938),
    (2030, 1162, 1294, 1004),
], 2):
    sample_row(ws, list(row), i)

# ── AGRICULTURE ──────────────────────────────────────────────
ws = wb.create_sheet("agri_topline")
kv_sheet(ws, [
    ("global_crop_production_bn_t", 9.2),
    ("food_insecure_population_m", 735),
    ("commodity_price_index", 118.4),
    ("input_cost_index", 142.8),
])

ws = wb.create_sheet("agri_crops")
header_row(ws, ["crop", "yield_mt_ha", "area_mha", "production_mt", "yoy_change_pct"])
for i, row in enumerate([
    ("Wheat", 3.4, 222, 755, 1.8),
    ("Rice", 4.7, 165, 776, 2.4),
    ("Maize", 5.8, 198, 1148, 3.1),
    ("Soybean", 2.9, 126, 366, 4.2),
    ("Sugar cane", 72.1, 27, 1947, 1.4),
], 2):
    sample_row(ws, list(row), i)

ws = wb.create_sheet("agri_food_sec")
header_row(ws, ["country", "score", "status", "import_dependency_pct"])
for i, row in enumerate([
    ("India", 56.4, "At-Risk", 12),
    ("China", 71.2, "Secure", 8),
    ("Brazil", 74.8, "Secure", 6),
    ("Nigeria", 34.1, "Crisis", 42),
    ("USA", 83.7, "Secure", 4),
    ("Ethiopia", 28.6, "Crisis", 55),
], 2):
    sample_row(ws, list(row), i)

ws = wb.create_sheet("agri_inputs")
header_row(ws, ["name", "price", "change_pct", "direction"])
for i, row in enumerate([
    ("Urea Fertiliser", "₹14,200/MT", 8.4, "up"),
    ("Diesel", "₹92.4/L", 2.1, "up"),
    ("Hybrid Seeds", "₹680/kg", -1.2, "down"),
    ("Pesticides", "₹820/L", 3.8, "up"),
    ("Irrigation (power)", "₹4.2/kWh", 0.0, "flat"),
], 2):
    sample_row(ws, list(row), i)

ws = wb.create_sheet("agri_geography")
header_row(ws, ["country", "top_crop", "yield_2025", "yoy_change", "food_security", "climate_risk"])
for i, row in enumerate([
    ("India", "Rice", "4.2 t/ha", "+1.8%", "At-Risk", "High"),
    ("China", "Wheat", "5.6 t/ha", "+2.4%", "Secure", "Medium"),
    ("Brazil", "Soybean", "3.4 t/ha", "+8.4%", "Secure", "Medium"),
    ("USA", "Maize", "11.2 t/ha", "+1.2%", "Secure", "Low"),
    ("Australia", "Wheat", "2.1 t/ha", "-3.8%", "Secure", "High"),
    ("Nigeria", "Maize", "1.6 t/ha", "-2.1%", "Crisis", "High"),
], 2):
    sample_row(ws, list(row), i)

ws = wb.create_sheet("agri_forecast")
header_row(ws, ["year", "crop", "country", "base_case_mt_ha", "bull_case_mt_ha", "bear_case_mt_ha"])
for i, row in enumerate([
    (2025, "Wheat", "India", 3.4, 3.4, 3.4),
    (2026, "Wheat", "India", 3.5, 3.6, 3.3),
    (2027, "Wheat", "India", 3.6, 3.8, 3.2),
    (2030, "Wheat", "India", 3.9, 4.3, 3.0),
    (2035, "Wheat", "India", 4.4, 5.1, 2.8),
], 2):
    sample_row(ws, list(row), i)

# ── MARKET INTELLIGENCE ────────────────────────────────────────
ws = wb.create_sheet("mi_topline")
kv_sheet(ws, [
    ("global_tam_usd_t", 1.62),
    ("sam_usd_bn", 284),
    ("som_usd_bn", 18.4),
    ("opportunity_score", 8.4),
    ("avg_price_per_treatment_course_usd", 4280),
    ("generic_penetration_pct", 38),
    ("premium_brand_premium_x", 2.8),
])

ws = wb.create_sheet("mi_segments")
header_row(ws, ["segment", "value_usd_bn", "share_pct", "cagr_pct"])
for i, row in enumerate([
    ("Oncology", 148.2, 52.2, 12.4),
    ("Metabolic Disorders", 86.4, 30.4, 9.1),
    ("CNS & Neurology", 49.4, 17.4, 8.6),
], 2):
    sample_row(ws, list(row), i)

ws = wb.create_sheet("mi_geography")
header_row(ws, ["region", "tam_usd_bn", "cagr_pct", "opportunity"])
for i, row in enumerate([
    ("North America", 112.4, 8.4, "High"),
    ("Europe", 76.2, 6.1, "Medium"),
    ("Asia-Pacific", 54.8, 14.2, "High"),
    ("Latin America", 24.6, 11.8, "Medium"),
    ("Middle East & Africa", 16.0, 9.4, "Medium"),
], 2):
    sample_row(ws, list(row), i)

ws = wb.create_sheet("mi_forecast")
header_row(ws, ["year", "tam_base_usd_bn", "tam_bull_usd_bn", "tam_bear_usd_bn"])
for i, row in enumerate([
    (2025, 284, 284, 284),
    (2026, 310, 318, 302),
    (2027, 338, 354, 320),
    (2028, 368, 393, 338),
    (2030, 437, 486, 374),
    (2035, 621, 724, 512),
], 2):
    sample_row(ws, list(row), i)

ws = wb.create_sheet("mi_pricing")
header_row(ws, ["metric", "value", "sub", "trend"])
for i, row in enumerate([
    ("Avg Price per Treatment Course", "$4,280", "US reference pricing", "↑ 3.2% yr/yr price erosion adjusted"),
    ("Generic Penetration", "38%", "Volume share · Branded vs generic", "↑ 6 pts over 3 yrs"),
    ("Premium Brand Premium", "2.8×", "vs generic price ratio", "Stable · ±0.1× yr/yr"),
], 2):
    sample_row(ws, list(row), i)

# Save
out = Path("templates/sample_data_model.xlsx")
out.parent.mkdir(exist_ok=True)
wb.save(out)
print(f"✅  Saved: {out.resolve()}")
print("   Sheets:", wb.sheetnames)
