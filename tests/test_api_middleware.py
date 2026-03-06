"""Tests for pysysfan.api.middleware — Token authentication middleware."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from pysysfan.api.middleware import verify_token


class TestVerifyToken:
    """Tests for verify_token middleware."""

    @pytest.mark.asyncio
    async def test_verify_token_success(self):
        """Should return token when valid."""
        test_token = "test-token-12345"
        credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = test_token

        with patch("pysysfan.api.middleware.load_token", return_value=test_token):
            result = await verify_token(credentials)
            assert result == test_token

    @pytest.mark.asyncio
    async def test_verify_token_not_configured(self):
        """Should raise 500 when token not configured."""
        credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = "some-token"

        with patch("pysysfan.api.middleware.load_token", return_value=None):
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(credentials)
            assert exc_info.value.status_code == 500
            assert "not configured" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_token_invalid(self):
        """Should raise 401 when token is invalid."""
        stored_token = "correct-token"
        provided_token = "wrong-token"
        credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = provided_token

        with patch("pysysfan.api.middleware.load_token", return_value=stored_token):
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(credentials)
            assert exc_info.value.status_code == 401
            assert "invalid" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_verify_token_empty_string(self):
        """Should raise 401 when empty token provided."""
        stored_token = "correct-token"
        credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = ""

        with patch("pysysfan.api.middleware.load_token", return_value=stored_token):
            with pytest.raises(HTTPException) as exc_info:
                await verify_token(credentials)
            assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_token_constant_time_comparison(self):
        """Should use secrets.compare_digest for timing-safe comparison."""
        stored_token = "correct-token"
        provided_token = "wrong-token"
        credentials = MagicMock(spec=HTTPAuthorizationCredentials)
        credentials.credentials = provided_token

        with patch("pysysfan.api.middleware.load_token", return_value=stored_token):
            with patch(
                "pysysfan.api.middleware.secrets.compare_digest"
            ) as mock_compare:
                mock_compare.return_value = False
                with pytest.raises(HTTPException):
                    await verify_token(credentials)
                mock_compare.assert_called_once_with(provided_token, stored_token)
