"""API token authentication for pysysfan.

This module provides token-based authentication for the pysysfan API.
Tokens are stored in ~/.pysysfan/api_token and used to authenticate
API requests from the GUI.

Security model:
- Tokens are UUID4 random strings
- Tokens are generated on first daemon start
- Tokens persist across daemon restarts
- Tokens are file-permission restricted (owner read/write only)
"""

from __future__ import annotations

import logging
import os
import stat
import uuid
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

TOKEN_FILE: Final[str] = "api_token"


def get_token_path() -> Path:
    """Get the path to the API token file.

    Returns:
        Path to ~/.pysysfan/api_token
    """
    config_dir = Path.home() / ".pysysfan"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / TOKEN_FILE


def generate_token() -> str:
    """Generate a new random API token.

    Uses UUID4 for cryptographically secure random tokens.

    Returns:
        A new token string (UUID4 format)
    """
    return str(uuid.uuid4())


def store_token(token: str) -> None:
    """Store an API token to disk.

    The token file is created with restrictive permissions (0600)
    to prevent unauthorized access.

    Args:
        token: The token string to store

    Raises:
        OSError: If the file cannot be written
    """
    token_path = get_token_path()

    token_path.write_text(token, encoding="utf-8")

    os.chmod(token_path, stat.S_IRUSR | stat.S_IWUSR)

    logger.debug(f"API token stored to {token_path}")


def load_token() -> str | None:
    """Load an existing API token from disk.

    Returns:
        The token string if found, or None if no token exists
    """
    token_path = get_token_path()

    if not token_path.exists():
        return None

    try:
        token = token_path.read_text(encoding="utf-8").strip()
        if not token:
            return None
        return token
    except OSError as e:
        logger.warning(f"Failed to read API token: {e}")
        return None


def get_or_create_token() -> str:
    """Get existing token or create a new one.

    This is the main entry point for token management. It will:
    1. Load existing token if available
    2. Generate and store a new token if not

    Returns:
        The token string (either loaded or newly created)
    """
    existing_token = load_token()
    if existing_token:
        logger.debug("Using existing API token")
        return existing_token

    new_token = generate_token()
    store_token(new_token)
    logger.info("Generated new API token")
    return new_token


def validate_token(provided_token: str) -> bool:
    """Validate a provided token against the stored token.

    Args:
        provided_token: The token to validate

    Returns:
        True if the token matches, False otherwise
    """
    stored_token = load_token()
    if not stored_token:
        logger.warning("No stored token found, authentication will fail")
        return False

    if not provided_token:
        return False

    return provided_token == stored_token


def rotate_token() -> str:
    """Generate and store a new token, replacing any existing token.

    This should be used if token compromise is suspected.

    Returns:
        The new token string
    """
    new_token = generate_token()
    store_token(new_token)
    logger.info("Rotated API token (old token invalidated)")
    return new_token
