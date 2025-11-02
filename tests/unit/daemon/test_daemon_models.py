"""Tests for daemon models."""

from src.daemon.models import Source, SourceType


def test_source_from_dict_gdrive():
    """Test creating Google Drive source from dict."""
    data = {
        "id": 1,
        "name": "Work Drive",
        "source_type": "gdrive",
        "enabled": 1,
        "folder_id": "abc123",
        "ingestion_mode": "accessed",
        "days_back": 730,
        "local_path": None,
        "recursive": 1
    }

    source = Source.from_dict(data)

    assert source.id == 1
    assert source.name == "Work Drive"
    assert source.source_type == SourceType.GDRIVE
    assert source.enabled is True
    assert source.folder_id == "abc123"
    assert source.ingestion_mode == "accessed"
    assert source.days_back == 730


def test_source_from_dict_local():
    """Test creating local source from dict."""
    data = {
        "id": 2,
        "name": "Personal Notes",
        "source_type": "local",
        "enabled": 1,
        "folder_id": None,
        "ingestion_mode": "accessed",
        "days_back": 730,
        "local_path": "/Users/test/notes",
        "recursive": 1
    }

    source = Source.from_dict(data)

    assert source.id == 2
    assert source.name == "Personal Notes"
    assert source.source_type == SourceType.LOCAL
    assert source.local_path == "/Users/test/notes"
    assert source.recursive is True
