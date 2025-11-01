"""Tests for macOS system condition checks."""

from src.daemon.conditions import is_plugged_in, is_mac_sleeping, should_run


def test_is_plugged_in():
    """Test power status check."""
    # This will return True or False depending on actual state
    result = is_plugged_in()
    assert isinstance(result, bool)


def test_is_mac_sleeping():
    """Test sleep state check."""
    # Should return False when running tests (Mac is awake)
    result = is_mac_sleeping()
    assert result is False  # Can't run tests while sleeping!


def test_should_run_awake_only():
    """Test should_run with awake-only mode."""
    should, reason = should_run("awake-only")
    assert isinstance(should, bool)
    assert isinstance(reason, str)
    # If we're running this test, Mac is awake
    assert should is True
    assert "awake" in reason.lower()


def test_should_run_plugged_in_only():
    """Test should_run with plugged-in-only mode."""
    should, reason = should_run("plugged-in-only")
    assert isinstance(should, bool)
    assert isinstance(reason, str)
