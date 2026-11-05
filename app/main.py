"""
Intelligence Platform — Backend API
Entry point for the FastAPI application.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

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

# CORS — allow configured frontend origins (set ALLOWED_ORIGINS in .env)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(upload.router)
app.include_router(data.router)


@app.get("/", tags=["health"])
async def root():
    return {
        "service": "Intelligence Platform API",
        "status": "ok",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}
