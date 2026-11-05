"""
Word (.docx) parser — extracts structured data from heading-delimited sections.

Document structure convention:
  Heading 1 → platform identifier (e.g. "Epidemiology Intelligence")
  Heading 2 → tab identifier (e.g. "Topline" or "Geography")
  Body paragraphs → key: value pairs
  Tables → parsed as row dicts under the most recent Heading 2

Supported platform headings (case-insensitive):
  Epidemiology Intelligence / Epidemiology
  Trade Intelligence / Trade
  Agriculture Intelligence / Agriculture
  Market Intelligence / Market

Supported tab headings (case-insensitive, matched to canonical tab names):
  Topline, Dashboard, Geography, Forecast, Reports, Funnel,
  Flows, Risks, HS Codes, Crops, Food Security, Inputs,
  Segments, Pricing, EI Query, Agriculture Intelligence,
  Trade Intelligence, Market Intelligence
"""
import io
import re
from docx import Document

PLATFORM_MAP = {
    "epidemiology intelligence": "epidemiology",
    "epidemiology": "epidemiology",
    "trade intelligence": "trade",
    "trade": "trade",
    "agriculture intelligence": "agriculture",
    "agriculture": "agriculture",
    "market intelligence": "market",
    "market": "market",
}

TAB_MAP = {
    "topline": "topline",
    "dashboard": "dashboard",
    "geography": "geography",
    "forecast": "forecast",
    "reports": "reports",
    "reports & model": "reports",
    "funnel": "funnel",
    "flows": "flows",
    "trade flows": "flows",
    "risks": "risks",
    "risk indicators": "risks",
    "hs codes": "hs_codes",
    "hs code": "hs_codes",
    "crops": "crops",
    "crop yields": "crops",
    "food security": "food_security",
    "inputs": "inputs",
    "input costs": "inputs",
    "segments": "segments",
    "market segments": "segments",
    "pricing": "pricing",
    "ei query": "ei_query",
    "agriculture intelligence": "agi",
    "trade intelligence tab": "ti",
    "market intelligence tab": "mi",
}


def _normalise(text: str) -> str:
    return text.strip().lower()


def _coerce(val: str):
    try:
        f = float(val.replace(",", "").replace("%", "").replace("$", "").replace("₹", "").strip())
        return int(f) if f == int(f) else f
    except (ValueError, AttributeError):
        return val.strip()


def _table_to_dicts(table) -> list[dict]:
    """Convert docx Table to list of row dicts."""
    rows = []
    headers = [cell.text.strip().lower().replace(" ", "_") for cell in table.rows[0].cells]
    for row in table.rows[1:]:
        vals = [cell.text.strip() for cell in row.cells]
        if all(v == "" for v in vals):
            continue
        rows.append({headers[i]: _coerce(vals[i]) for i in range(len(headers))})
    return rows


def parse_docx(file_bytes: bytes) -> dict[tuple[str, str], dict]:
    """
    Parse all heading-delimited sections.
    Returns { (platform, tab): payload_dict }
    """
    doc = Document(io.BytesIO(file_bytes))
    results: dict[tuple[str, str], dict] = {}

    current_platform: str | None = None
    current_tab: str | None = None
    current_kv: dict = {}
    current_rows: list[dict] = []

    def flush():
        """Save the current platform+tab buffer."""
        if current_platform and current_tab:
            payload: dict = {}
            if current_kv:
                payload["kpis"] = dict(current_kv)
            if current_rows:
                payload["rows"] = list(current_rows)
            results[(current_platform, current_tab)] = payload

    for block in doc.element.body:
        tag = block.tag.split("}")[-1]  # "p" or "tbl"

        if tag == "p":
            # Access via python-docx paragraph
            # We need to find the paragraph object matching this element
            para_text = "".join(r.text for r in block.iter() if r.tag.endswith("}t"))
            style_name = ""
            # Grab style from paragraph properties
            pPr = block.find(".//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pStyle")
            if pPr is not None:
                style_name = pPr.get("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val", "").lower()

            if "heading1" in style_name or style_name == "heading1":
                flush()
                current_platform = PLATFORM_MAP.get(_normalise(para_text))
                current_tab = None
                current_kv = {}
                current_rows = []

            elif "heading2" in style_name or style_name == "heading2":
                flush()
                current_tab = TAB_MAP.get(_normalise(para_text))
                current_kv = {}
                current_rows = []

            else:
                # Body paragraph — look for key: value
                if ":" in para_text and current_platform and current_tab:
                    parts = para_text.split(":", 1)
                    k = parts[0].strip().lower().replace(" ", "_")
                    v = parts[1].strip()
                    current_kv[k] = _coerce(v)

        elif tag == "tbl" and current_platform and current_tab:
            # Reconstruct table using python-docx
            from docx.oxml.table import CT_Tbl
            from docx.table import Table
            tbl_obj = Table(block, doc)
            if len(tbl_obj.rows) >= 2:
                current_rows.extend(_table_to_dicts(tbl_obj))

    flush()
    return results
