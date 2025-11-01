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
