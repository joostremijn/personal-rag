"""macOS notification system."""

import subprocess
import logging

logger = logging.getLogger(__name__)


def send_notification(title: str, message: str) -> None:
    """Send native macOS notification.

    Args:
        title: Notification title
        message: Notification message
    """
    try:
        # Escape quotes in message
        message = message.replace('"', '\\"')
        title = title.replace('"', '\\"')

        script = f'display notification "{message}" with title "{title}"'

        subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            timeout=5,
            check=False  # Don't raise on non-zero exit
        )

        logger.debug(f"Sent notification: {title}")

    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        # Don't raise - notifications are non-critical
