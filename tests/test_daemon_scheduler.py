"""Tests for scheduler component."""

import tempfile
from pathlib import Path
from time import sleep
from unittest.mock import MagicMock, patch

from src.daemon.scheduler import DaemonScheduler
from src.daemon.state import DaemonState


def test_scheduler_initialization():
    """Test scheduler initializes correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        state = DaemonState(db_path)

        scheduler = DaemonScheduler(state)

        assert scheduler.state == state
        assert scheduler.scheduler is not None


@patch('src.daemon.scheduler.IngestionRunner')
@patch('src.daemon.scheduler.should_run')
def test_scheduler_job_execution(mock_should_run, mock_runner):
    """Test scheduler executes job."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        state = DaemonState(db_path)

        # Mock conditions to allow run
        mock_should_run.return_value = (True, "Test condition met")

        # Mock runner
        from src.daemon.state import RunResult
        from datetime import datetime
        mock_runner_instance = MagicMock()
        mock_runner.return_value = mock_runner_instance
        mock_result = RunResult(
            success=True,
            duration=1.0,
            processed_docs=5,
            skipped_docs=95,
            total_chunks=10,
            error=None,
            timestamp=datetime.now()
        )
        mock_runner_instance.run_ingestion.return_value = mock_result

        scheduler = DaemonScheduler(state)
        scheduler._run_job()

        # Verify runner was called
        assert mock_runner_instance.run_ingestion.called


@patch('src.daemon.scheduler.should_run')
def test_scheduler_skips_when_conditions_not_met(mock_should_run):
    """Test scheduler skips run when conditions not met."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        state = DaemonState(db_path)

        # Mock conditions to skip run
        mock_should_run.return_value = (False, "Mac is sleeping")

        scheduler = DaemonScheduler(state)

        with patch.object(scheduler, '_execute_ingestion') as mock_execute:
            scheduler._run_job()

            # Should not execute ingestion
            assert not mock_execute.called
