"""
Excel (.xlsx) parser — maps named sheets → platform tab data.

Sheet naming convention (case-insensitive, spaces or underscores ok):
  Epidemiology:
    "epi_topline"   → topline KPIs + risk indicators
    "epi_funnel"    → patient funnel stages
    "epi_geography" → country-level burden
    "epi_forecast"  → forecast series (base/bull/bear)
    "epi_reports"   → report metadata

  Trade:
    "trade_topline"   → KPI header row
    "trade_flows"     → origin/dest/value flow table
    "trade_risks"     → risk indicator rows
    "trade_geography" → corridor table
    "trade_forecast"  → forecast series
    "trade_hs"        → HS code rows

  Agriculture:
    "agri_topline"    → KPI header row
    "agri_crops"      → crop yield rows
    "agri_food_sec"   → food security rows
    "agri_inputs"     → input cost rows
    "agri_geography"  → geo yield table
    "agri_forecast"   → forecast series

  Market:
    "mi_topline"    → KPI header row
    "mi_segments"   → segment share rows
    "mi_geography"  → geo market rows
    "mi_forecast"   → forecast series
    "mi_pricing"    → pricing strip rows
"""
import io
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet


def _ws_to_dicts(ws: Worksheet) -> list[dict]:
    """Convert worksheet rows to list of dicts using first row as headers."""
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = [str(c).strip().lower().replace(" ", "_") if c else f"col_{i}" for i, c in enumerate(rows[0])]
    result = []
    for row in rows[1:]:
        if all(v is None for v in row):
            continue
        result.append({headers[i]: row[i] for i in range(len(headers))})
    return result


def _ws_to_kv(ws: Worksheet) -> dict:
    """
    Convert two-column worksheet (key | value) to flat dict.
    Used for KPI header sheets.
    """
    result = {}
    for row in ws.iter_rows(values_only=True):
        if row[0] is not None and len(row) >= 2:
            key = str(row[0]).strip().lower().replace(" ", "_")
            result[key] = row[1]
    return result


SHEET_MAP = {
    # epidemiology
    "epi_topline": ("epidemiology", "topline"),
    "epi_funnel": ("epidemiology", "funnel"),
    "epi_geography": ("epidemiology", "geography"),
    "epi_forecast": ("epidemiology", "forecast"),
    "epi_reports": ("epidemiology", "reports"),
    # trade
    "trade_topline": ("trade", "topline"),
    "trade_flows": ("trade", "flows"),
    "trade_risks": ("trade", "risks"),
    "trade_geography": ("trade", "geography"),
    "trade_forecast": ("trade", "forecast"),
    "trade_hs": ("trade", "hs_codes"),
    # agriculture
    "agri_topline": ("agriculture", "topline"),
    "agri_crops": ("agriculture", "crops"),
    "agri_food_sec": ("agriculture", "food_security"),
    "agri_inputs": ("agriculture", "inputs"),
    "agri_geography": ("agriculture", "geography"),
    "agri_forecast": ("agriculture", "forecast"),
    # market
    "mi_topline": ("market", "topline"),
    "mi_segments": ("market", "segments"),
    "mi_geography": ("market", "geography"),
    "mi_forecast": ("market", "forecast"),
    "mi_pricing": ("market", "pricing"),
}

# Sheets that are key-value (single KPI header) vs row tables
KV_SHEETS = {"epi_topline", "trade_topline", "agri_topline", "mi_topline"}


def parse_excel(file_bytes: bytes) -> dict[tuple[str, str], dict]:
    """
    Parse all known sheets from the uploaded workbook.
    Returns { (platform, tab): payload_dict }
    """
    wb = load_workbook(io.BytesIO(file_bytes), data_only=True)
    results: dict[tuple[str, str], dict] = {}

    for sheet_name in wb.sheetnames:
        normalised = sheet_name.strip().lower().replace(" ", "_").replace("-", "_")
        if normalised not in SHEET_MAP:
            continue

        platform, tab = SHEET_MAP[normalised]
        ws = wb[sheet_name]

        if normalised in KV_SHEETS:
            payload = {"kpis": _ws_to_kv(ws)}
        else:
            payload = {"rows": _ws_to_dicts(ws)}

        results[(platform, tab)] = payload

    return results
