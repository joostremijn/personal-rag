"""macOS system condition checks for conditional execution."""

import subprocess
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def is_plugged_in() -> bool:
    """Check if Mac is connected to AC power.

    Returns:
        True if plugged in, False if on battery
    """
    try:
        result = subprocess.run(
            ['pmset', '-g', 'batt'],
            capture_output=True,
            text=True,
            timeout=5
        )

        output = result.stdout.lower()

        # Look for "ac power" or "'ac power'" in output
        if 'ac power' in output or "'ac power'" in output:
            return True

        # Also check for "discharging" which means on battery
        if 'discharging' in output or 'battery power' in output:
            return False

        # Default to True if we can't determine (fail safe)
        logger.warning(f"Could not determine power state from: {output}")
        return True

    except Exception as e:
        logger.error(f"Error checking power state: {e}")
        return True  # Fail safe: assume plugged in


def is_mac_sleeping() -> bool:
    """Check if Mac is in sleep mode.

    Returns:
        True if sleeping, False if awake
    """
    try:
        result = subprocess.run(
            ['pmset', '-g'],
            capture_output=True,
            text=True,
            timeout=5
        )

        output = result.stdout.lower()

        # If we can run this command, Mac is not sleeping
        # pmset shows "sleep" in various states but we can't query while asleep
        # So if this runs successfully, we're awake
        return False

    except Exception as e:
        logger.error(f"Error checking sleep state: {e}")
        return False  # Fail safe: assume awake


def should_run(run_mode: str) -> Tuple[bool, str]:
    """Check if ingestion should run based on conditions.

    Args:
        run_mode: Either "awake-only" or "plugged-in-only"

    Returns:
        Tuple of (should_run, reason)
    """
    if run_mode == "awake-only":
        if is_mac_sleeping():
            return False, "Mac is sleeping"
        return True, "Mac is awake"

    elif run_mode == "plugged-in-only":
        if not is_plugged_in():
            return False, "Running on battery"
        return True, "Plugged into AC power"

    else:
        logger.warning(f"Unknown run mode: {run_mode}, defaulting to run")
        return True, "Unknown mode - running anyway"
