"""
Public read-only data endpoints — consumed by the frontend portals.

GET /api/{platform}/manifest         → list all stored tabs for a platform
GET /api/{platform}/{tab}            → fetch tab data payload
GET /api/{platform}/{tab}/kpis       → fetch only the KPI slice
GET /api/{platform}/{tab}/rows       → fetch only the rows slice

Platforms:  epidemiology | trade | agriculture | market
Tabs per platform:
  epidemiology  : topline, funnel, geography, forecast, reports
  trade         : topline, flows, risks, geography, forecast, hs_codes
  agriculture   : topline, crops, food_security, inputs, geography, forecast
  market        : topline, segments, geography, forecast, pricing
"""
from fastapi import APIRouter, HTTPException, Query
from app.database import get_tab_data, get_platform_manifest

router = APIRouter(prefix="/api", tags=["data"])

PLATFORMS = {"epidemiology", "trade", "agriculture", "market"}


def _check_platform(platform: str):
    if platform not in PLATFORMS:
        raise HTTPException(status_code=404, detail=f"Unknown platform '{platform}'. Valid: {sorted(PLATFORMS)}")


@router.get("/{platform}/manifest", summary="List all stored tabs for a platform")
async def platform_manifest(platform: str):
    _check_platform(platform)
    rows = await get_platform_manifest(platform)
    return {"platform": platform, "tabs": rows, "count": len(rows)}


@router.get("/{platform}/{tab}", summary="Fetch full tab data")
async def tab_data(
    platform: str,
    tab: str,
    version: str = Query(default="latest"),
):
    _check_platform(platform)
    result = await get_tab_data(platform, tab, version)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"No data for {platform}/{tab} (version={version}). Upload a file first via /admin/upload.",
        )
    return result


@router.get("/{platform}/{tab}/kpis", summary="Fetch only KPI fields")
async def tab_kpis(platform: str, tab: str, version: str = Query(default="latest")):
    _check_platform(platform)
    result = await get_tab_data(platform, tab, version)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No data for {platform}/{tab}")
    kpis = result["data"].get("kpis", {})
    return {"platform": platform, "tab": tab, "kpis": kpis, "meta": result["meta"]}


@router.get("/{platform}/{tab}/rows", summary="Fetch only row data")
async def tab_rows(
    platform: str,
    tab: str,
    version: str = Query(default="latest"),
    limit: int = Query(default=200, le=1000),
    offset: int = Query(default=0, ge=0),
):
    _check_platform(platform)
    result = await get_tab_data(platform, tab, version)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No data for {platform}/{tab}")
    rows = result["data"].get("rows", [])
    total = len(rows)
    return {
        "platform": platform,
        "tab": tab,
        "total": total,
        "offset": offset,
        "limit": limit,
        "rows": rows[offset: offset + limit],
        "meta": result["meta"],
    }
