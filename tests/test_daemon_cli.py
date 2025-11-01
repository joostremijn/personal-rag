"""Tests for CLI tool."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from daemon_cli import DaemonCLI


def test_cli_status_command():
    """Test status command fetches and displays status."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "scheduler_state": "running",
        "interval": 60,
        "run_mode": "awake-only",
        "last_run": {
            "success": True,
            "processed_docs": 10,
            "skipped_docs": 90,
            "timestamp": "2025-10-31T12:00:00"
        }
    }
    mock_response.status_code = 200

    with patch('requests.get', return_value=mock_response) as mock_get:
        cli = DaemonCLI(base_url="http://localhost:8001")
        cli.status()

        mock_get.assert_called_once_with("http://localhost:8001/api/status")


def test_cli_trigger_command():
    """Test trigger command sends POST request."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "triggered"}
    mock_response.status_code = 200

    with patch('requests.post', return_value=mock_response) as mock_post:
        cli = DaemonCLI(base_url="http://localhost:8001")
        cli.trigger()

        mock_post.assert_called_once_with("http://localhost:8001/api/trigger")


def test_cli_config_update():
    """Test config command updates configuration."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"status": "updated"}
    mock_response.status_code = 200

    with patch('requests.post', return_value=mock_response) as mock_post:
        cli = DaemonCLI(base_url="http://localhost:8001")
        cli.config(interval=30, run_mode="plugged-in-only")

        mock_post.assert_called_once_with(
            "http://localhost:8001/api/config",
            json={"interval": 30, "run_mode": "plugged-in-only"}
        )


def test_cli_history_command():
    """Test history command fetches run history."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "history": [
            {"success": True, "processed_docs": 10, "timestamp": "2025-10-31T12:00:00"},
            {"success": False, "error": "Network error", "timestamp": "2025-10-31T11:00:00"}
        ]
    }
    mock_response.status_code = 200

    with patch('requests.get', return_value=mock_response) as mock_get:
        cli = DaemonCLI(base_url="http://localhost:8001")
        cli.history(limit=20)

        mock_get.assert_called_once_with("http://localhost:8001/api/history?limit=20")
