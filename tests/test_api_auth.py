"""Tests for pysysfan.api.auth — API token authentication."""

import os
import stat
from pathlib import Path
from unittest.mock import patch

from pysysfan.api import auth


class TestTokenGeneration:
    """Tests for token generation."""

    def test_generate_token_returns_string(self):
        """generate_token should return a string."""
        token = auth.generate_token()
        assert isinstance(token, str)
        assert len(token) > 0

    def test_generate_token_returns_unique_values(self):
        """generate_token should return unique tokens."""
        tokens = {auth.generate_token() for _ in range(100)}
        assert len(tokens) == 100

    def test_generate_token_format(self):
        """generate_token should return UUID4 format."""
        token = auth.generate_token()
        parts = token.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12


class TestTokenStorage:
    """Tests for token storage and loading."""

    def test_store_token_creates_file(self, tmp_path):
        """store_token should create the token file."""
        with patch.object(auth, "get_token_path", return_value=tmp_path / "api_token"):
            auth.store_token("test-token-123")

            token_path = tmp_path / "api_token"
            assert token_path.exists()
            assert token_path.read_text() == "test-token-123"

    def test_store_token_sets_permissions(self, tmp_path):
        """store_token should set restrictive permissions (0600 on Unix)."""
        with patch.object(auth, "get_token_path", return_value=tmp_path / "api_token"):
            auth.store_token("test-token-123")

            token_path = tmp_path / "api_token"
            mode = token_path.stat().st_mode

            assert mode & stat.S_IRUSR
            assert mode & stat.S_IWUSR

            if os.name != "nt":
                assert not (mode & stat.S_IRGRP)
                assert not (mode & stat.S_IWGRP)
                assert not (mode & stat.S_IROTH)
                assert not (mode & stat.S_IWOTH)

    def test_load_token_returns_none_if_not_exists(self, tmp_path):
        """load_token should return None if token file doesn't exist."""
        with patch.object(auth, "get_token_path", return_value=tmp_path / "api_token"):
            result = auth.load_token()
            assert result is None

    def test_load_token_returns_token(self, tmp_path):
        """load_token should return the stored token."""
        with patch.object(auth, "get_token_path", return_value=tmp_path / "api_token"):
            auth.store_token("test-token-456")

            result = auth.load_token()
            assert result == "test-token-456"

    def test_load_token_strips_whitespace(self, tmp_path):
        """load_token should strip whitespace from token."""
        token_path = tmp_path / "api_token"
        token_path.write_text("  test-token-789  \n")

        with patch.object(auth, "get_token_path", return_value=token_path):
            result = auth.load_token()
            assert result == "test-token-789"

    def test_load_token_returns_none_for_empty_file(self, tmp_path):
        """load_token should return None for empty token file."""
        token_path = tmp_path / "api_token"
        token_path.write_text("")

        with patch.object(auth, "get_token_path", return_value=token_path):
            result = auth.load_token()
            assert result is None

    def test_load_token_returns_none_for_whitespace_only(self, tmp_path):
        """load_token should return None for whitespace-only token file."""
        token_path = tmp_path / "api_token"
        token_path.write_text("  \n  ")

        with patch.object(auth, "get_token_path", return_value=token_path):
            result = auth.load_token()
            assert result is None


class TestTokenManagement:
    """Tests for get_or_create_token and validate_token."""

    def test_get_or_create_token_creates_new_if_missing(self, tmp_path):
        """get_or_create_token should create a new token if none exists."""
        with patch.object(auth, "get_token_path", return_value=tmp_path / "api_token"):
            token = auth.get_or_create_token()

            assert token is not None
            assert len(token) > 0
            assert (tmp_path / "api_token").exists()

    def test_get_or_create_token_returns_existing(self, tmp_path):
        """get_or_create_token should return existing token if present."""
        with patch.object(auth, "get_token_path", return_value=tmp_path / "api_token"):
            auth.store_token("existing-token")

            token = auth.get_or_create_token()
            assert token == "existing-token"

    def test_validate_token_returns_true_for_match(self, tmp_path):
        """validate_token should return True for matching tokens."""
        with patch.object(auth, "get_token_path", return_value=tmp_path / "api_token"):
            auth.store_token("correct-token")

            result = auth.validate_token("correct-token")
            assert result is True

    def test_validate_token_returns_false_for_mismatch(self, tmp_path):
        """validate_token should return False for non-matching tokens."""
        with patch.object(auth, "get_token_path", return_value=tmp_path / "api_token"):
            auth.store_token("correct-token")

            result = auth.validate_token("wrong-token")
            assert result is False

    def test_validate_token_returns_false_if_no_token_stored(self, tmp_path):
        """validate_token should return False if no token is stored."""
        with patch.object(auth, "get_token_path", return_value=tmp_path / "api_token"):
            result = auth.validate_token("any-token")
            assert result is False

    def test_validate_token_returns_false_for_empty_token(self, tmp_path):
        """validate_token should return False for empty provided token."""
        with patch.object(auth, "get_token_path", return_value=tmp_path / "api_token"):
            auth.store_token("stored-token")

            result = auth.validate_token("")
            assert result is False

    def test_rotate_token_replaces_existing(self, tmp_path):
        """rotate_token should generate and store a new token."""
        with patch.object(auth, "get_token_path", return_value=tmp_path / "api_token"):
            old_token = auth.get_or_create_token()

            new_token = auth.rotate_token()

            assert new_token != old_token
            assert auth.load_token() == new_token

    def test_rotate_token_creates_if_missing(self, tmp_path):
        """rotate_token should create a token even if none exists."""
        with patch.object(auth, "get_token_path", return_value=tmp_path / "api_token"):
            new_token = auth.rotate_token()

            assert new_token is not None
            assert auth.load_token() == new_token


class TestGetTokenPath:
    """Tests for get_token_path."""

    def test_get_token_path_returns_path(self, tmp_path):
        """get_token_path should return a Path object."""
        with patch.object(Path, "home", return_value=tmp_path):
            path = auth.get_token_path()

            assert isinstance(path, Path)
            assert path.name == "api_token"
            assert ".pysysfan" in str(path)

    def test_get_token_path_creates_directory(self, tmp_path):
        """get_token_path should create the .pysysfan directory if needed."""
        with patch.object(Path, "home", return_value=tmp_path):
            config_dir = tmp_path / ".pysysfan"
            assert not config_dir.exists()

            auth.get_token_path()

            assert config_dir.exists()
