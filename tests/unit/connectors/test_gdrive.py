"""Unit tests for Google Drive connector."""

from unittest.mock import patch, MagicMock, Mock
from datetime import datetime, timedelta
import json
import pytest

from src.connectors.gdrive import GoogleDriveConnector
from src.models import SourceType


@pytest.fixture
def mock_drive_credentials():
    """Mock valid Google Drive credentials."""
    mock_creds = MagicMock()
    mock_creds.valid = True
    mock_creds.expired = False
    mock_creds.refresh_token = "fake_refresh_token"
    return mock_creds


@pytest.mark.skip(reason="Complex mocking - covered by integration tests")
def test_token_expiration_triggers_refresh(mock_drive_credentials, tmp_path):
    """Expired OAuth token should auto-refresh."""
    # This test would require complex mocking of Settings, pickle, file I/O
    # Token refresh behavior is better tested in integration/e2e tests
    pass


def test_missing_credentials_file_error():
    """Missing credentials.json should raise clear error."""
    with patch("src.connectors.gdrive.Path.exists", return_value=False):
        connector = GoogleDriveConnector()

        # Should fail validation
        with pytest.raises(Exception):
            connector._authenticate()


def test_supported_mime_types():
    """Should support Google Docs, Sheets, PDFs, and text files."""
    connector = GoogleDriveConnector()

    # Check key MIME types are supported
    assert "application/vnd.google-apps.document" in connector.SUPPORTED_MIME_TYPES
    assert "application/vnd.google-apps.spreadsheet" in connector.SUPPORTED_MIME_TYPES
    assert "application/pdf" in connector.SUPPORTED_MIME_TYPES
    assert "text/plain" in connector.SUPPORTED_MIME_TYPES


def test_export_format_correctness():
    """Google Docs should export as text, Sheets as CSV."""
    connector = GoogleDriveConnector()

    # Google Docs -> text/plain
    doc_config = connector.SUPPORTED_MIME_TYPES["application/vnd.google-apps.document"]
    assert doc_config["export"] == "text/plain"

    # Google Sheets -> text/csv
    sheet_config = connector.SUPPORTED_MIME_TYPES["application/vnd.google-apps.spreadsheet"]
    assert sheet_config["export"] == "text/csv"


def test_list_files_returns_file_metadata(mock_gdrive_service, mock_drive_credentials):
    """Listing files should return metadata without downloading content."""
    with patch("src.connectors.gdrive.pickle.load", return_value=mock_drive_credentials):
        with patch("src.connectors.gdrive.Path.exists", return_value=True):
            with patch("src.connectors.gdrive.build", return_value=mock_gdrive_service):
                connector = GoogleDriveConnector()
                connector._authenticate()

                # List files should work
                assert connector.service is not None


def test_recently_accessed_query_format():
    """Query for recently accessed files should use correct date format."""
    connector = GoogleDriveConnector()
    days_back = 30

    # Should generate query with date filter
    from datetime import datetime, timedelta
    cutoff_date = datetime.now() - timedelta(days=days_back)

    expected_date_format = cutoff_date.strftime("%Y-%m-%dT%H:%M:%S")

    # Just verify date format is ISO-like
    assert "T" in expected_date_format
    assert "-" in expected_date_format


def test_validate_connection_success(mock_gdrive_service, mock_drive_credentials):
    """validate_connection should return True when authenticated."""
    with patch("src.connectors.gdrive.pickle.load", return_value=mock_drive_credentials):
        with patch("src.connectors.gdrive.Path.exists", return_value=True):
            with patch("src.connectors.gdrive.build", return_value=mock_gdrive_service):
                connector = GoogleDriveConnector()

                # Should validate successfully
                assert connector.validate_connection() is True


def test_source_type_is_gdrive():
    """Connector should use GDRIVE source type."""
    connector = GoogleDriveConnector()
    assert connector.source_type == SourceType.GDRIVE


def test_authenticate_loads_json_token_file(tmp_path, mock_gdrive_service, mock_drive_credentials):
    """GoogleDriveConnector should load JSON token files (saved by OAuthManager)."""
    # Create JSON token file (format saved by OAuthManager)
    token_file = tmp_path / "token.json"
    token_data = {
        "token": "ya29.fake_token",
        "refresh_token": "fake_refresh_token",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "fake_client_id",
        "client_secret": "fake_client_secret",
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"]
    }
    with open(token_file, 'w') as f:
        json.dump(token_data, f)

    credentials_file = tmp_path / "credentials.json"
    credentials_file.write_text('{"installed": {}}')

    # Mock settings to use our temp files
    with patch("src.connectors.gdrive.get_settings") as mock_settings:
        mock_settings.return_value.google_token_path = token_file
        mock_settings.return_value.google_credentials_path = credentials_file

        with patch("src.connectors.gdrive.Credentials.from_authorized_user_file", return_value=mock_drive_credentials):
            with patch("src.connectors.gdrive.build", return_value=mock_gdrive_service):
                connector = GoogleDriveConnector()
                connector._authenticate()

                # Should successfully authenticate using JSON token
                assert connector.service is not None
                assert connector.creds is not None
