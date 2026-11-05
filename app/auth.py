"""
Minimal token auth for admin upload endpoints.
No user accounts, no JWT complexity for Phase 1.
The ADMIN_TOKEN lives in .env and is never hardcoded.
"""
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
):
    """
    Raise 401 unless the Bearer token matches ADMIN_TOKEN.
    Pass token in header:  Authorization: Bearer <ADMIN_TOKEN>
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header required.")
    if credentials.credentials != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token.")
    return credentials.credentials
