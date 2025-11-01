"""Tests for macOS notification system."""

from unittest.mock import patch, MagicMock
from src.daemon.notifications import send_notification


@patch('subprocess.run')
def test_send_notification(mock_run):
    """Test sending macOS notification."""
    mock_run.return_value = MagicMock(returncode=0)

    send_notification("Test Title", "Test message")

    # Verify osascript was called
    assert mock_run.called
    call_args = mock_run.call_args[0][0]
    assert call_args[0] == 'osascript'
    assert call_args[1] == '-e'
    assert 'Test Title' in call_args[2]
    assert 'Test message' in call_args[2]


@patch('subprocess.run')
def test_send_notification_handles_error(mock_run):
    """Test notification handles errors gracefully."""
    mock_run.side_effect = Exception("osascript failed")

    # Should not raise exception
    send_notification("Title", "Message")
