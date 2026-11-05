"""
Vercel ASGI entry point.
Vercel looks for `app` in this file — we import it from the main FastAPI app.
"""
import sys
import os

# Make sure the project root is on the path so `app.*` imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app  # noqa: F401 — Vercel picks up `app` from this module
