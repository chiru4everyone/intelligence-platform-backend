# Intelligence Platform — Backend API

A FastAPI backend that accepts Excel, PowerPoint, and Word file uploads, parses the data
into structured payloads per platform and tab, stores them in SQLite, and serves them
to the intelligence platform frontends via a CORS-enabled REST API.

---

## Architecture

```
Your Excel / PowerPoint / Word file
        │
        ▼
POST /admin/upload
        │
   File parser
   (excel_parser | pptx_parser | docx_parser)
        │
   Identifies platform + tab from sheet/slide/heading names
        │
   Stores JSON payload in SQLite (data/store/platform.db)
        │
        ▼
GET /api/{platform}/{tab}
        │
   Frontend portal reads and renders
```

---

## Platforms & Tabs

| Platform        | Tabs available                                              |
|-----------------|-------------------------------------------------------------|
| `epidemiology`  | topline · funnel · geography · forecast · reports           |
| `trade`         | topline · flows · risks · geography · forecast · hs_codes   |
| `agriculture`   | topline · crops · food_security · inputs · geography · forecast |
| `market`        | topline · segments · geography · forecast · pricing         |

---

## Quick Start

### 1. Clone and install

```bash
git clone https://github.com/chiru4everyone/intelligence-platform-backend.git
cd intelligence-platform-backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env:
#   ADMIN_TOKEN=your-secret-token-here
#   ALLOWED_ORIGINS=https://your-frontend.vercel.app
```

### 3. Generate sample Excel template

```bash
python scripts/create_sample_excel.py
# → templates/sample_data_model.xlsx
```

### 4. Run locally

```bash
uvicorn app.main:app --reload --port 8000
# API docs: http://localhost:8000/docs
```

### 5. Upload your first data file

```bash
curl -X POST http://localhost:8000/admin/upload \
  -H "Authorization: Bearer your-secret-token-here" \
  -F "file=@templates/sample_data_model.xlsx" \
  -F "version=latest"
```

### 6. Fetch data from the API

```bash
# Full tab data
curl http://localhost:8000/api/epidemiology/topline

# Just KPIs
curl http://localhost:8000/api/trade/topline/kpis

# Row data with pagination
curl "http://localhost:8000/api/agriculture/crops/rows?limit=10&offset=0"

# What's been uploaded for a platform
curl http://localhost:8000/api/epidemiology/manifest
```

---

## File Naming Conventions

See [`templates/README_TEMPLATES.md`](templates/README_TEMPLATES.md) for the full naming guide.

**Quick summary:**

- **Excel**: Name sheet tabs exactly (e.g. `epi_topline`, `trade_flows`, `agri_crops`)
- **PowerPoint**: Set slide title to the tab identifier (e.g. `trade_geography`)
- **Word**: Use Heading 1 for platform name, Heading 2 for tab name

---

## API Reference

### Admin Endpoints (require `Authorization: Bearer <ADMIN_TOKEN>`)

| Method | Path                           | Description                          |
|--------|--------------------------------|--------------------------------------|
| POST   | `/admin/upload`                | Upload file — auto-detects all tabs  |
| POST   | `/admin/upload/{platform}`     | Upload file pinned to one platform   |

### Public Data Endpoints

| Method | Path                               | Description                          |
|--------|------------------------------------|--------------------------------------|
| GET    | `/api/{platform}/manifest`         | List all stored tabs                 |
| GET    | `/api/{platform}/{tab}`            | Full tab payload                     |
| GET    | `/api/{platform}/{tab}/kpis`       | KPI fields only                      |
| GET    | `/api/{platform}/{tab}/rows`       | Row data with `?limit=&offset=`      |
| GET    | `/health`                          | Health check                         |
| GET    | `/docs`                            | Swagger UI                           |

---

## Deployment to Vercel

```bash
npm i -g vercel
vercel login
vercel --prod
# Set env vars in Vercel dashboard:
#   ADMIN_TOKEN, ALLOWED_ORIGINS, DATABASE_URL
```

> **Note:** Vercel's serverless functions are stateless — SQLite at a local path will
> reset on each cold start. For persistent storage, switch `DATABASE_URL` to a
> hosted Postgres/MySQL (e.g. Supabase, PlanetScale) in Phase 2.

---

## Connecting the Frontend (Phase 2)

Replace hardcoded JS data variables in each portal with fetch calls:

```js
// Before (hardcoded in the portal HTML):
const FLOWS = [
  { origin: "EU", destination: "USA", val: 142.4, pct: 16.9 },
  ...
];

// After (fetching from backend):
async function loadFlows() {
  const res = await fetch(`${API_BASE}/api/trade/flows/rows`);
  const { rows } = await res.json();
  FLOWS = rows.map(r => ({
    origin: r.origin,
    destination: r.destination,
    val: r.value_usd_bn,
    pct: r.pct_of_total,
  }));
  renderFlowsTable();
}
```

Set `API_BASE` via the frontend's `config.js` (already in the repo) — no hardcoded URLs.

---

## Security Notes

- `ADMIN_TOKEN` lives only in `.env` — never committed to git
- `.gitignore` excludes `.env`, `data/uploads/`, `data/store/`
- No payment infrastructure, no Razorpay, no API keys in code
- CORS restricted to `ALLOWED_ORIGINS` list in `.env`
- File size limit: `MAX_UPLOAD_MB` (default 50 MB)
- File type validation on both MIME type and extension

---

## Phase 2 Roadmap (do not implement yet)

- [ ] Switch SQLite → hosted Postgres for Vercel compatibility
- [ ] Wire frontend portals to API (`config.js` → `API_BASE`)
- [ ] Versioned data snapshots (upload with `version=Q4-2025`)
- [ ] Webhook on upload → frontend cache invalidation
- [ ] Auth upgrade: per-client API keys instead of single admin token
