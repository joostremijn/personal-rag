"""Tests for OAuth integration."""

import pickle
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
from google.oauth2.credentials import Credentials
from src.daemon.oauth import OAuthManager


def test_oauth_status_not_authenticated(tmp_path):
    """Test OAuth status when not authenticated."""
    token_path = tmp_path / "token.json"
    creds_path = tmp_path / "credentials.json"

    manager = OAuthManager(
        credentials_path=creds_path,
        token_path=token_path
    )

    status = manager.get_status()
    assert status["authenticated"] is False
    assert status["email"] is None


def test_oauth_status_authenticated(tmp_path):
    """Test OAuth status when authenticated."""
    token_path = tmp_path / "token.json"
    creds_path = tmp_path / "credentials.json"

    # Create dummy token file
    import json
    token_path.write_text(json.dumps({
        "token": "test_token",
        "refresh_token": "test_refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_id",
        "client_secret": "test_secret",
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"]
    }))

    with patch("src.daemon.oauth.Credentials") as mock_creds:
        mock_cred_instance = MagicMock()
        mock_cred_instance.valid = True
        mock_creds.from_authorized_user_file.return_value = mock_cred_instance

        with patch("src.daemon.oauth.build") as mock_build:
            mock_service = MagicMock()
            mock_service.about().get().execute.return_value = {
                "user": {"emailAddress": "test@example.com"}
            }
            mock_build.return_value = mock_service

            manager = OAuthManager(
                credentials_path=creds_path,
                token_path=token_path
            )

            status = manager.get_status()
            assert status["authenticated"] is True
            assert status["email"] == "test@example.com"


def test_oauth_status_handles_pickle_token(tmp_path):
    """Test OAuth status with legacy pickle-format token."""
    token_path = tmp_path / "token.json"
    creds_path = tmp_path / "credentials.json"

    # Create pickle-format token (legacy format from GoogleDriveConnector)
    legacy_creds = Credentials(
        token="test_token",
        refresh_token="test_refresh",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="test_id",
        client_secret="test_secret",
        scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )

    with open(token_path, "wb") as f:
        pickle.dump(legacy_creds, f)

    # Should handle pickle format and return authenticated status
    with patch("src.daemon.oauth.build") as mock_build:
        mock_service = MagicMock()
        mock_service.about().get().execute.return_value = {
            "user": {"emailAddress": "test@example.com"}
        }
        mock_build.return_value = mock_service

        manager = OAuthManager(
            credentials_path=creds_path,
            token_path=token_path
        )

        status = manager.get_status()
        assert status["authenticated"] is True
        assert status["email"] == "test@example.com"
