"""Tests for main daemon process."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from daemon import PersonalRAGDaemon


def test_daemon_initialization():
    """Test daemon initializes with all components."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "daemon.db"
        daemon = PersonalRAGDaemon(db_path=db_path, port=8999)

        assert daemon.state is not None
        assert daemon.scheduler is not None
        assert daemon.app is not None
        assert daemon.port == 8999


@patch('daemon.signal.signal')  # Mock signal handler registration
@patch('uvicorn.run')
def test_daemon_start(mock_uvicorn, mock_signal):
    """Test daemon starts scheduler and web server."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "daemon.db"
        daemon = PersonalRAGDaemon(db_path=db_path, port=8999)

        # Mock scheduler start
        with patch.object(daemon.scheduler, 'start') as mock_scheduler_start:
            # Call start() - uvicorn.run is mocked so won't block
            daemon.start()

            # Verify scheduler was started
            mock_scheduler_start.assert_called_once()

            # Verify uvicorn.run was called with correct params
            mock_uvicorn.assert_called_once()
            call_args = mock_uvicorn.call_args
            assert call_args[1]['port'] == 8999
            assert call_args[1]['host'] == '0.0.0.0'


def test_daemon_stop():
    """Test daemon stops scheduler."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "daemon.db"
        daemon = PersonalRAGDaemon(db_path=db_path, port=8999)

        # Mock scheduler stop
        with patch.object(daemon.scheduler, 'stop') as mock_scheduler_stop:
            daemon.stop()

            # Verify scheduler was stopped
            mock_scheduler_stop.assert_called_once()
