"""Main daemon process for Personal RAG background ingestion."""

import argparse
import logging
import signal
import sys
from pathlib import Path
from typing import Optional

import uvicorn

from daemon_web import init_app
from src.daemon.scheduler import DaemonScheduler
from src.daemon.state import DaemonState

# Ensure logs directory exists
Path("logs").mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/daemon.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def migrate_to_multi_source(state: DaemonState) -> None:
    """Migrate existing single-source config to multi-source.

    Args:
        state: Daemon state
    """
    # Check if migration needed (no sources exist, but config does)
    sources = state.get_sources()

    if len(sources) == 0:
        max_results = state.get_config("max_results")

        if max_results:  # Existing user
            logger.info("Migrating existing config to multi-source")

            # Create default Google Drive source
            state.create_source({
                "name": "Google Drive (auto-migrated)",
                "source_type": "gdrive",
                "enabled": True,
                "folder_id": None,
                "ingestion_mode": "accessed",
                "days_back": 730
            })

            logger.info("Migration complete: created default Google Drive source")


class PersonalRAGDaemon:
    """Main daemon orchestrator."""

    def __init__(self, db_path: Path, port: int = 8001) -> None:
        """Initialize daemon.

        Args:
            db_path: Path to SQLite database
            port: Port for web server
        """
        self.db_path = db_path
        self.port = port

        # Initialize components
        logger.info("Initializing daemon components")
        self.state = DaemonState(db_path)

        # Run migration
        migrate_to_multi_source(self.state)

        self.scheduler = DaemonScheduler(self.state)
        self.app = init_app(self.state, self.scheduler)

        # Set initial state
        if not self.state.get_config("scheduler_state"):
            self.state.set_config("scheduler_state", "running")
        if not self.state.get_config("interval"):
            self.state.set_config("interval", "60")
        if not self.state.get_config("run_mode"):
            self.state.set_config("run_mode", "awake-only")
        if not self.state.get_config("max_results"):
            self.state.set_config("max_results", "100")

        logger.info(f"Daemon initialized (db={db_path}, port={port})")

    def start(self) -> None:
        """Start daemon (scheduler + web server)."""
        logger.info("Starting Personal RAG Daemon")

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        # Start scheduler
        self.scheduler.start()
        logger.info("Scheduler started")

        # Start web server
        logger.info(f"Starting web server on port {self.port}")
        logger.info(f"Dashboard: http://localhost:{self.port}")

        uvicorn.run(
            self.app,
            host="0.0.0.0",
            port=self.port,
            log_level="info"
        )

    def stop(self) -> None:
        """Stop daemon."""
        logger.info("Stopping daemon")
        self.scheduler.stop()
        logger.info("Daemon stopped")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down")
        self.stop()
        sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Personal RAG Background Daemon")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=Path("data/daemon.db"),
        help="Path to SQLite database (default: data/daemon.db)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Web server port (default: 8001)"
    )

    args = parser.parse_args()

    # Ensure parent directory exists
    args.db_path.parent.mkdir(parents=True, exist_ok=True)

    daemon = PersonalRAGDaemon(db_path=args.db_path, port=args.port)
    daemon.start()


if __name__ == "__main__":
    main()
