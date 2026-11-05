"""
Async SQLite database layer using aiosqlite directly.
Stores parsed platform data as JSON blobs keyed by (platform, tab, version).
"""
import aiosqlite
import json
from pathlib import Path
from datetime import datetime, timezone
from app.config import settings

DB_PATH = Path(settings.DATABASE_URL.replace("sqlite+aiosqlite:///", ""))


async def get_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    """Create tables on startup."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS platform_data (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                platform    TEXT NOT NULL,
                tab         TEXT NOT NULL,
                version     TEXT NOT NULL DEFAULT 'latest',
                uploaded_by TEXT,
                source_file TEXT,
                source_type TEXT,  -- xlsx | pptx | docx
                payload     TEXT NOT NULL,  -- JSON blob
                created_at  TEXT NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS idx_platform_tab_version
                ON platform_data (platform, tab, version);

            CREATE TABLE IF NOT EXISTS upload_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                platform    TEXT NOT NULL,
                tab         TEXT NOT NULL,
                filename    TEXT NOT NULL,
                file_type   TEXT NOT NULL,
                status      TEXT NOT NULL,  -- success | error
                message     TEXT,
                created_at  TEXT NOT NULL
            );
        """)
        await db.commit()


async def upsert_tab_data(
    platform: str,
    tab: str,
    payload: dict,
    source_file: str = "",
    source_type: str = "",
    uploaded_by: str = "admin",
    version: str = "latest",
):
    """Insert or replace platform/tab data."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO platform_data
                (platform, tab, version, uploaded_by, source_file, source_type, payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(platform, tab, version) DO UPDATE SET
                uploaded_by = excluded.uploaded_by,
                source_file = excluded.source_file,
                source_type = excluded.source_type,
                payload     = excluded.payload,
                created_at  = excluded.created_at
            """,
            (platform, tab, version, uploaded_by, source_file, source_type, json.dumps(payload), now),
        )
        await db.commit()


async def get_tab_data(platform: str, tab: str, version: str = "latest") -> dict | None:
    """Fetch the stored payload for a given platform/tab."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT payload, created_at, source_file FROM platform_data WHERE platform=? AND tab=? AND version=?",
            (platform, tab, version),
        )
        row = await cur.fetchone()
        if row is None:
            return None
        return {
            "data": json.loads(row["payload"]),
            "meta": {
                "source_file": row["source_file"],
                "created_at": row["created_at"],
                "platform": platform,
                "tab": tab,
                "version": version,
            },
        }


async def get_platform_manifest(platform: str) -> list[dict]:
    """Return all tabs stored for a platform, without the payload."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """SELECT tab, version, source_file, source_type, uploaded_by, created_at
               FROM platform_data WHERE platform=? ORDER BY tab, created_at DESC""",
            (platform,),
        )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def log_upload(platform: str, tab: str, filename: str, file_type: str, status: str, message: str = ""):
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO upload_log (platform,tab,filename,file_type,status,message,created_at) VALUES (?,?,?,?,?,?,?)",
            (platform, tab, filename, file_type, status, message, now),
        )
        await db.commit()
