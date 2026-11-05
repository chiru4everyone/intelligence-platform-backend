# Data Model Templates — Naming Conventions

Each template file tells the backend exactly which platform and tab to populate.
Follow the naming conventions below — the parser matches on these exactly.

---

## Excel (.xlsx) — Sheet Tab Names

Create one workbook per upload (or one workbook with all sheets).
Name each sheet tab exactly as listed.

| Sheet Tab Name     | Platform      | Portal Tab       | Expected columns / keys                                          |
|--------------------|---------------|------------------|------------------------------------------------------------------|
| `epi_topline`      | Epidemiology  | Topline          | key, value (two-column KV sheet)                                 |
| `epi_funnel`       | Epidemiology  | Dashboard funnel | stage, value, pct                                                |
| `epi_geography`    | Epidemiology  | Geography        | country, prevalence_per_100k, treatment_rate_pct, undiagnosed_pct, mortality_per_100k, opportunity_score |
| `epi_forecast`     | Epidemiology  | Forecast         | year, base_case, bull_case, bear_case                            |
| `epi_reports`      | Epidemiology  | Reports          | title, type, pages, date, access                                 |
| `trade_topline`    | Trade         | Topline          | key, value (KV sheet)                                            |
| `trade_flows`      | Trade         | Topline flows    | origin, destination, value_usd_bn, pct_of_total                  |
| `trade_risks`      | Trade         | Topline risks    | dot, name, detail, score, score_color                            |
| `trade_geography`  | Trade         | Geography        | corridor, value_usd_bn, yoy_pct, tariff_pct, fta, risk           |
| `trade_forecast`   | Trade         | Forecast         | year, base_case, bull_case, bear_case                            |
| `trade_hs`         | Trade         | HS Codes         | hs_code, description, value_usd_bn, yoy_pct                      |
| `agri_topline`     | Agriculture   | Topline          | key, value (KV sheet)                                            |
| `agri_crops`       | Agriculture   | Topline crops    | crop, yield_mt_ha, area_mha, production_mt, yoy_change_pct       |
| `agri_food_sec`    | Agriculture   | Topline food sec | country, score, status, import_dependency_pct                    |
| `agri_inputs`      | Agriculture   | Topline inputs   | name, price, change_pct, direction                               |
| `agri_geography`   | Agriculture   | Geography        | country, top_crop, yield_2025, yoy_change, food_security, climate_risk |
| `agri_forecast`    | Agriculture   | Forecast         | year, crop, country, base_case, bull_case, bear_case             |
| `mi_topline`       | Market        | Topline          | key, value (KV sheet)                                            |
| `mi_segments`      | Market        | Topline segments | segment, value_usd_bn, share_pct, cagr_pct                       |
| `mi_geography`     | Market        | Geography        | region, tam_usd_bn, cagr_pct, opportunity                        |
| `mi_forecast`      | Market        | Forecast         | year, tam_base, tam_bull, tam_bear                               |
| `mi_pricing`       | Market        | Topline pricing  | metric, value, sub, trend                                        |

**KV sheet format (topline sheets):** two columns — column A = field name, column B = value.
Example:
```
global_pharma_trade_value_usd_bn  |  842
supply_chain_risk_score           |  6.8
tariff_affected_value_usd_bn      |  124
hs_codes_tracked                  |  84
```

---

## PowerPoint (.pptx) — Slide Title Naming

Each slide's title must start with the identifier below (case-insensitive).
Add data as text boxes (key: value) or tables on the same slide.

| Slide Title         | Platform      | Tab              |
|---------------------|---------------|------------------|
| `epi_topline`       | Epidemiology  | Topline          |
| `epi_funnel`        | Epidemiology  | Dashboard funnel |
| `epi_geography`     | Epidemiology  | Geography        |
| `epi_forecast`      | Epidemiology  | Forecast         |
| `trade_topline`     | Trade         | Topline          |
| `trade_flows`       | Trade         | Flows table      |
| `trade_risks`       | Trade         | Risk indicators  |
| `trade_geography`   | Trade         | Geography        |
| `trade_forecast`    | Trade         | Forecast         |
| `agri_topline`      | Agriculture   | Topline          |
| `agri_crops`        | Agriculture   | Crop yields      |
| `agri_food_sec`     | Agriculture   | Food security    |
| `agri_geography`    | Agriculture   | Geography        |
| `mi_topline`        | Market        | Topline          |
| `mi_segments`       | Market        | Segments         |
| `mi_geography`      | Market        | Geography        |
| `mi_forecast`       | Market        | Forecast         |

**Text box key:value format:**
```
Global Pharma Trade Value: $842B
Supply Chain Risk Score: 6.8
```

**Table format:** First row = column headers, subsequent rows = data.

---

## Word (.docx) — Heading Conventions

Use Heading 1 for the platform name, Heading 2 for the tab name.
Under each Heading 2, write key: value pairs as normal paragraphs, or insert a Word table.

**Heading 1 options (platform):**
- Epidemiology Intelligence  
- Trade Intelligence  
- Agriculture Intelligence  
- Market Intelligence  

**Heading 2 options (tab):**
Topline · Dashboard · Geography · Forecast · Reports · Funnel · Flows · Risks · HS Codes · Crops · Food Security · Inputs · Segments · Pricing

**Example document structure:**
```
# Trade Intelligence            ← Heading 1

## Topline                      ← Heading 2
Global Pharma Trade Value: 842  ← body paragraph (key: value)
Supply Chain Risk Score: 6.8
Tariff Affected Value: 124

[Table with columns: Origin | Destination | Value USD bn | % of Total]

## Geography                    ← Heading 2
[Table with columns: Corridor | Value USD bn | YoY % | Tariff % | FTA | Risk]
```
