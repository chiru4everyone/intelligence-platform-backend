"""
POST /admin/upload
  Upload Excel, PowerPoint, or Word file; parse and store all recognised tabs.

POST /admin/upload/{platform}
  Same but restricts storage to a single platform (useful for platform-specific files).
"""
from fastapi import APIRouter, Depends, File, UploadFile, Form
from app.auth import require_admin
from app.services.ingest import ingest_file

router = APIRouter(prefix="/admin", tags=["admin-upload"])


@router.post("/upload", summary="Upload a file (all platforms)")
async def upload_any(
    file: UploadFile = File(...),
    version: str = Form(default="latest"),
    _token: str = Depends(require_admin),
):
    """
    Upload an Excel / PowerPoint / Word file.
    The parser detects platform and tab from sheet/slide/heading names automatically.
    Returns a list of tab ingestion results.
    """
    results = await ingest_file(file, version=version)
    return {"ingested": results, "count": len(results)}


@router.post("/upload/{platform}", summary="Upload a file for a specific platform")
async def upload_for_platform(
    platform: str,
    file: UploadFile = File(...),
    version: str = Form(default="latest"),
    _token: str = Depends(require_admin),
):
    """
    Same as /admin/upload but pins the platform.
    Useful when file naming conventions don't include the platform prefix.
    """
    allowed = {"epidemiology", "trade", "agriculture", "market"}
    if platform not in allowed:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"platform must be one of {allowed}")
    results = await ingest_file(file, platform_hint=platform, version=version)
    return {"platform": platform, "ingested": results, "count": len(results)}
