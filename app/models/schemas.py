"""
Pydantic response schemas shared across all platform routers.
Data shapes mirror the JS variable names used in each frontend portal.
"""
from pydantic import BaseModel, Field
from typing import Any, Optional


# ─── Generic ───────────────────────────────────────────────────────────────────

class TabDataResponse(BaseModel):
    platform: str
    tab: str
    version: str = "latest"
    source_file: str = ""
    created_at: str = ""
    data: dict[str, Any]


class UploadResponse(BaseModel):
    platform: str
    tab: str
    rows_parsed: int
    fields_found: list[str]
    message: str


class ManifestEntry(BaseModel):
    platform: str
    tab: str
    version: str
    source_file: str
    source_type: str
    uploaded_by: str
    created_at: str


# ─── KPI tile (shared across all portals) ──────────────────────────────────────

class KpiCard(BaseModel):
    label: str
    value: str
    sub: str = ""
    delta: str = ""
    delta_type: str = "warn"   # ok | warn | alert


# ─── Epidemiology ──────────────────────────────────────────────────────────────

class EpiTopline(BaseModel):
    kpis: list[KpiCard] = Field(default_factory=list)
    risk_indicators: list[dict[str, Any]] = Field(default_factory=list)


class EpiFunnel(BaseModel):
    disease: str = ""
    stages: list[dict[str, Any]] = Field(default_factory=list)   # name, value, pct
    year: int = 2025


class EpiGeoRow(BaseModel):
    country: str
    prevalence_per_100k: float = 0
    treatment_rate_pct: float = 0
    undiagnosed_pct: float = 0
    mortality_per_100k: float = 0
    opportunity_score: float = 0


class EpiForecast(BaseModel):
    disease: str = ""
    years: list[int] = Field(default_factory=list)
    base_case: list[float] = Field(default_factory=list)
    bull_case: list[float] = Field(default_factory=list)
    bear_case: list[float] = Field(default_factory=list)


# ─── Trade Intelligence ────────────────────────────────────────────────────────

class TradeFlowRow(BaseModel):
    origin: str
    destination: str
    value_usd_bn: float
    pct_of_total: float


class TradeRiskRow(BaseModel):
    dot: str
    name: str
    detail: str
    score: float
    score_color: str = "var(--coral)"


class GeoCorridorRow(BaseModel):
    corridor: str
    value_usd_bn: float
    yoy_pct: float
    tariff_pct: float
    fta: str
    risk: str


class TradeToplineKpis(BaseModel):
    global_pharma_trade_value_usd_bn: float = 842
    supply_chain_risk_score: float = 6.8
    tariff_affected_value_usd_bn: float = 124
    hs_codes_tracked: int = 84


# ─── Agriculture Intelligence ──────────────────────────────────────────────────

class CropYieldRow(BaseModel):
    crop: str
    yield_mt_ha: float
    area_mha: float
    production_mt: float
    yoy_change_pct: float


class FoodSecurityRow(BaseModel):
    country: str
    score: float
    status: str   # Secure | At-Risk | Crisis
    import_dependency_pct: float = 0


class AgriInputCost(BaseModel):
    name: str
    price: str
    change_pct: float
    direction: str = "up"   # up | down | flat


class AgriToplineKpis(BaseModel):
    global_crop_production_bn_t: float = 9.2
    food_insecure_population_m: float = 735
    commodity_price_index: float = 118.4
    input_cost_index: float = 142.8


# ─── Market Intelligence ───────────────────────────────────────────────────────

class MarketSegmentRow(BaseModel):
    segment: str
    value_usd_bn: float
    share_pct: float
    cagr_pct: float


class GeoMarketRow(BaseModel):
    region: str
    tam_usd_bn: float
    cagr_pct: float
    opportunity: str   # High | Medium | Low


class MarketToplineKpis(BaseModel):
    global_tam_usd_t: float = 1.62
    sam_usd_bn: float = 284
    som_usd_bn: float = 18.4
    opportunity_score: float = 8.4
