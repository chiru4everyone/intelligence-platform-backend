"""
Intelligence Platform — Backend API
Entry point for the FastAPI application.

GET /           → Login page (HTML)
GET /health     → Health check (JSON)
GET /api/...    → Platform data endpoints (JSON)
POST /admin/... → Admin upload endpoints (JSON, Bearer-token protected)
GET /docs       → Swagger UI
GET /redoc      → ReDoc UI
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path

from app.config import settings
from app.database import init_db
from app.routers import upload, data


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Intelligence Platform API",
    description=(
        "Backend API for the Intelligence Platform portals. "
        "Accepts Excel / PowerPoint / Word uploads, parses them into platform tab data, "
        "and serves structured JSON to the frontend portals. "
        "\n\n**Admin endpoints** require `Authorization: Bearer <ADMIN_TOKEN>` header."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(upload.router)
app.include_router(data.router)

# ── Static assets (CSS, JS, images if any) ───────────────────────────────────
_STATIC_DIR = Path(__file__).parent / "static"
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# ── Login page — served at root ───────────────────────────────────────────────
_LOGIN_HTML = _STATIC_DIR / "login.html"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request):
    """Serve the analyst login page as the homepage."""
    if _LOGIN_HTML.exists():
        return HTMLResponse(content=_LOGIN_HTML.read_text(encoding="utf-8"))
    # Fallback if static file is missing
    return HTMLResponse(content="""
    <!doctype html><html><head><meta charset="utf-8">
    <title>Intelligence Platform</title>
    <style>body{font-family:system-ui;background:#0d1017;color:#f0f2f7;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;}</style>
    </head><body>
    <div style="text-align:center">
      <h2 style="font-weight:300;color:#8a95a8">Intelligence Platform API</h2>
      <p style="color:#4a5568;font-size:13px;margin-top:8px">
        Login page not found. Visit <a href="/docs" style="color:#2ec4b6">/docs</a> for the API.
      </p>
    </div></body></html>
    """)


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": "0.1.0"}
