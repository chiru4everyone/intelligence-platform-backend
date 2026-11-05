"""
PowerPoint (.pptx) parser — extracts slide data into platform tab payloads.

Slide identification convention (slide title or notes tag):
  First line of slide title OR the first line of the notes pane must start with
  one of the platform prefixes below (case-insensitive).

  Slide structure:
    - Title text → used as tab identifier
    - Body text boxes → parsed as key:value pairs (separated by ":" or "→")
    - Tables → parsed as list of row dicts
    - Notes → stored as "notes" string

Supported slide title prefixes:
  EPI_TOPLINE, EPI_FUNNEL, EPI_GEOGRAPHY, EPI_FORECAST, EPI_REPORTS
  TRADE_TOPLINE, TRADE_FLOWS, TRADE_RISKS, TRADE_GEOGRAPHY, TRADE_FORECAST, TRADE_HS
  AGRI_TOPLINE, AGRI_CROPS, AGRI_FOOD_SEC, AGRI_INPUTS, AGRI_GEOGRAPHY, AGRI_FORECAST
  MI_TOPLINE, MI_SEGMENTS, MI_GEOGRAPHY, MI_FORECAST, MI_PRICING
"""
import io
import re
from pptx import Presentation
from pptx.util import Pt

SLIDE_MAP = {
    "epi_topline": ("epidemiology", "topline"),
    "epi_funnel": ("epidemiology", "funnel"),
    "epi_geography": ("epidemiology", "geography"),
    "epi_forecast": ("epidemiology", "forecast"),
    "epi_reports": ("epidemiology", "reports"),
    "trade_topline": ("trade", "topline"),
    "trade_flows": ("trade", "flows"),
    "trade_risks": ("trade", "risks"),
    "trade_geography": ("trade", "geography"),
    "trade_forecast": ("trade", "forecast"),
    "trade_hs": ("trade", "hs_codes"),
    "agri_topline": ("agriculture", "topline"),
    "agri_crops": ("agriculture", "crops"),
    "agri_food_sec": ("agriculture", "food_security"),
    "agri_inputs": ("agriculture", "inputs"),
    "agri_geography": ("agriculture", "geography"),
    "agri_forecast": ("agriculture", "forecast"),
    "mi_topline": ("market", "topline"),
    "mi_segments": ("market", "segments"),
    "mi_geography": ("market", "geography"),
    "mi_forecast": ("market", "forecast"),
    "mi_pricing": ("market", "pricing"),
}


def _get_slide_key(slide) -> str | None:
    """Return the normalised SLIDE_MAP key from slide title or notes."""
    # Try title placeholder first
    for shape in slide.shapes:
        if shape.has_text_frame and shape.shape_type in (13, 1):
            title_text = shape.text_frame.text.strip().lower()
            key = re.sub(r"[\s\-]+", "_", title_text.split("\n")[0])
            if key in SLIDE_MAP:
                return key

    # Fall back to notes
    if slide.has_notes_slide:
        notes = slide.notes_slide.notes_text_frame.text.strip().lower()
        first_line = re.sub(r"[\s\-]+", "_", notes.split("\n")[0])
        if first_line in SLIDE_MAP:
            return first_line

    return None


def _parse_text_boxes(slide) -> dict:
    """Extract key:value pairs from non-title text boxes."""
    kv = {}
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        text = shape.text_frame.text.strip()
        for line in text.split("\n"):
            if ":" in line:
                parts = line.split(":", 1)
                k = parts[0].strip().lower().replace(" ", "_")
                v = parts[1].strip()
                kv[k] = _coerce(v)
            elif "→" in line:
                parts = line.split("→", 1)
                k = parts[0].strip().lower().replace(" ", "_")
                v = parts[1].strip()
                kv[k] = _coerce(v)
    return kv


def _parse_tables(slide) -> list[list[dict]]:
    """Extract all tables from a slide as list of row-dicts."""
    tables = []
    for shape in slide.shapes:
        if not shape.has_table:
            continue
        tbl = shape.table
        headers = [tbl.cell(0, c).text.strip().lower().replace(" ", "_") for c in range(tbl._tbl.shape[1])]
        rows = []
        for r in range(1, tbl._tbl.shape[0]):
            row = {headers[c]: _coerce(tbl.cell(r, c).text.strip()) for c in range(len(headers))}
            if any(v not in ("", None) for v in row.values()):
                rows.append(row)
        tables.append(rows)
    return tables


def _coerce(val: str):
    """Try to convert to float/int, else keep as string."""
    try:
        f = float(val.replace(",", "").replace("%", "").replace("$", "").replace("₹", ""))
        return int(f) if f == int(f) else f
    except (ValueError, AttributeError):
        return val


def _get_notes(slide) -> str:
    if slide.has_notes_slide:
        return slide.notes_slide.notes_text_frame.text.strip()
    return ""


def parse_pptx(file_bytes: bytes) -> dict[tuple[str, str], dict]:
    """
    Parse all slides with known prefixes.
    Returns { (platform, tab): payload_dict }
    """
    prs = Presentation(io.BytesIO(file_bytes))
    results: dict[tuple[str, str], dict] = {}

    for slide in prs.slides:
        key = _get_slide_key(slide)
        if key is None:
            continue

        platform, tab = SLIDE_MAP[key]
        kv = _parse_text_boxes(slide)
        tables = _parse_tables(slide)
        notes = _get_notes(slide)

        payload: dict = {}
        if kv:
            payload["kpis"] = kv
        if tables:
            payload["rows"] = tables[0]  # first table is primary data
            if len(tables) > 1:
                payload["secondary_tables"] = tables[1:]
        if notes:
            payload["notes"] = notes

        results[(platform, tab)] = payload

    return results
