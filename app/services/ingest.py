"""
File ingestion service — dispatches to the right parser, then writes to DB.
"""
import aiofiles
import os
from pathlib import Path
from fastapi import UploadFile, HTTPException

from app.config import settings
from app.database import upsert_tab_data, log_upload
from app.parsers.excel_parser import parse_excel
from app.parsers.pptx_parser import parse_pptx
from app.parsers.docx_parser import parse_docx


ALLOWED_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}

EXTENSION_FALLBACK = {
    ".xlsx": "xlsx",
    ".pptx": "pptx",
    ".docx": "docx",
}


def _detect_type(file: UploadFile) -> str:
    mime = ALLOWED_TYPES.get(file.content_type or "")
    if mime:
        return mime
    ext = Path(file.filename or "").suffix.lower()
    mime = EXTENSION_FALLBACK.get(ext)
    if mime:
        return mime
    raise HTTPException(
        status_code=415,
        detail=f"Unsupported file type. Upload .xlsx, .pptx, or .docx. Got: {file.content_type}",
    )


async def ingest_file(
    file: UploadFile,
    platform_hint: str | None = None,   # optional override
    version: str = "latest",
    uploaded_by: str = "admin",
) -> list[dict]:
    """
    Read the uploaded file, parse it, store each (platform, tab) slice.
    Returns a list of ingestion result dicts.
    """
    file_type = _detect_type(file)
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    file_bytes = await file.read()

    if len(file_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_MB} MB limit.")

    # Save original to uploads dir
    safe_name = Path(file.filename or "upload").name
    save_path = settings.upload_path / safe_name
    async with aiofiles.open(save_path, "wb") as f:
        await f.write(file_bytes)

    # Parse
    if file_type == "xlsx":
        parsed = parse_excel(file_bytes)
    elif file_type == "pptx":
        parsed = parse_pptx(file_bytes)
    else:
        parsed = parse_docx(file_bytes)

    if not parsed:
        raise HTTPException(
            status_code=422,
            detail=(
                "No recognised sheet/slide/heading names found. "
                "Check the naming convention in the API docs (/docs)."
            ),
        )

    results = []
    for (platform, tab), payload in parsed.items():
        # platform_hint overrides only if a single-platform file is intended
        effective_platform = platform_hint if platform_hint else platform

        rows = len(payload.get("rows", payload.get("kpis", [])))
        try:
            await upsert_tab_data(
                platform=effective_platform,
                tab=tab,
                payload=payload,
                source_file=safe_name,
                source_type=file_type,
                uploaded_by=uploaded_by,
                version=version,
            )
            await log_upload(effective_platform, tab, safe_name, file_type, "success")
            results.append({"platform": effective_platform, "tab": tab, "rows": rows, "status": "ok"})
        except Exception as exc:
            await log_upload(effective_platform, tab, safe_name, file_type, "error", str(exc))
            results.append({"platform": effective_platform, "tab": tab, "rows": 0, "status": "error", "detail": str(exc)})

    return results
