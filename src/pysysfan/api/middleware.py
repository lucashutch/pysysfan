"""FastAPI middleware for token authentication."""

from __future__ import annotations

import secrets
from typing import Final

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from pysysfan.api.auth import load_token

security: Final = HTTPBearer()


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> str:
    """Verify Bearer token matches stored token.

    Args:
        credentials: The HTTP Authorization credentials containing the Bearer token.

    Returns:
        The verified token string.

    Raises:
        HTTPException: If the token is invalid or not configured.
    """
    stored_token = load_token()

    if not stored_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API token not configured",
        )

    provided_token = credentials.credentials

    if not secrets.compare_digest(provided_token, stored_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return provided_token
