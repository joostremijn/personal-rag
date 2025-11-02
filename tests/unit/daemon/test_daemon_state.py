"""Tests for daemon state persistence."""

import tempfile
from pathlib import Path
from datetime import datetime

from src.daemon.state import DaemonState, RunResult


def test_state_initialization():
    """Test creating new state database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        state = DaemonState(db_path)

        # Should have default config
        assert state.get_config("interval") == "60"
        assert state.get_config("run_mode") == "awake-only"
        assert state.get_config("scheduler_state") == "running"


def test_config_update():
    """Test updating configuration."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        state = DaemonState(db_path)

        state.set_config("interval", "10")
        assert state.get_config("interval") == "10"


def test_record_run():
    """Test recording run results."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        state = DaemonState(db_path)

        result = RunResult(
            success=True,
            duration=2.5,
            processed_docs=5,
            skipped_docs=95,
            total_chunks=10,
            error=None,
            timestamp=datetime.now()
        )

        state.record_run(result)

        history = state.get_history(limit=1)
        assert len(history) == 1
        assert history[0]["success"] == 1  # SQLite stores boolean as integer
        assert history[0]["duration"] == 2.5


def test_sources_table_exists(tmp_path):
    """Test that sources table is created on init."""
    db_path = tmp_path / "test.db"
    state = DaemonState(db_path)

    import sqlite3
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sources'"
        )
        assert cursor.fetchone() is not None


def test_create_source(tmp_path):
    """Test creating a new source."""
    db_path = tmp_path / "test.db"
    state = DaemonState(db_path)

    source_data = {
        "name": "Test Drive",
        "source_type": "gdrive",
        "enabled": True,
        "folder_id": None,
        "ingestion_mode": "accessed",
        "days_back": 730
    }

    source_id = state.create_source(source_data)
    assert source_id is not None
    assert source_id > 0


def test_get_sources(tmp_path):
    """Test listing all sources."""
    db_path = tmp_path / "test.db"
    state = DaemonState(db_path)

    # Create two sources
    state.create_source({"name": "Source 1", "source_type": "gdrive"})
    state.create_source({"name": "Source 2", "source_type": "local", "local_path": "/test"})

    sources = state.get_sources()
    assert len(sources) == 2
    # Check both sources are present (order may vary with identical timestamps)
    names = {s["name"] for s in sources}
    assert names == {"Source 1", "Source 2"}


def test_get_enabled_sources(tmp_path):
    """Test listing only enabled sources."""
    db_path = tmp_path / "test.db"
    state = DaemonState(db_path)

    state.create_source({"name": "Enabled", "source_type": "gdrive", "enabled": True})
    state.create_source({"name": "Disabled", "source_type": "gdrive", "enabled": False})

    sources = state.get_sources(enabled_only=True)
    assert len(sources) == 1
    assert sources[0]["name"] == "Enabled"


def test_update_source(tmp_path):
    """Test updating a source."""
    db_path = tmp_path / "test.db"
    state = DaemonState(db_path)

    source_id = state.create_source({"name": "Test", "source_type": "gdrive"})
    state.update_source(source_id, {"name": "Updated", "days_back": 365})

    sources = state.get_sources()
    assert sources[0]["name"] == "Updated"
    assert sources[0]["days_back"] == 365


def test_delete_source(tmp_path):
    """Test deleting a source."""
    db_path = tmp_path / "test.db"
    state = DaemonState(db_path)

    source_id = state.create_source({"name": "Test", "source_type": "gdrive"})
    state.delete_source(source_id)

    sources = state.get_sources()
    assert len(sources) == 0
