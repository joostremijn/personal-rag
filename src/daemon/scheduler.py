"""APScheduler-based job scheduler."""

import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from src.daemon.state import DaemonState
from src.daemon.runner import IngestionRunner
from src.daemon.conditions import should_run
from src.daemon.notifications import send_notification

logger = logging.getLogger(__name__)


class DaemonScheduler:
    """Manages scheduled ingestion jobs."""

    def __init__(self, state: DaemonState) -> None:
        """Initialize scheduler.

        Args:
            state: Daemon state manager
        """
        self.state = state
        self.scheduler = BackgroundScheduler()
        self.job_id = "ingestion_job"

    def start(self) -> None:
        """Start the scheduler."""
        # Get interval from state
        interval_minutes = int(self.state.get_config("interval") or "60")

        # Add job
        self.scheduler.add_job(
            func=self._run_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=self.job_id,
            replace_existing=True
        )

        # Start scheduler
        self.scheduler.start()
        logger.info(f"Scheduler started with {interval_minutes} minute interval")

    def stop(self) -> None:
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")

    def pause(self) -> None:
        """Pause scheduling."""
        self.scheduler.pause()
        self.state.set_config("scheduler_state", "paused")
        logger.info("Scheduler paused")

    def resume(self) -> None:
        """Resume scheduling."""
        self.scheduler.resume()
        self.state.set_config("scheduler_state", "running")
        logger.info("Scheduler resumed")

    def update_interval(self, minutes: int) -> None:
        """Update scheduling interval.

        Args:
            minutes: New interval in minutes
        """
        # Update state
        self.state.set_config("interval", str(minutes))

        # Reschedule job
        self.scheduler.reschedule_job(
            job_id=self.job_id,
            trigger=IntervalTrigger(minutes=minutes)
        )

        logger.info(f"Updated interval to {minutes} minutes")

    def trigger_now(self) -> None:
        """Trigger ingestion immediately (ignoring schedule)."""
        logger.info("Manual trigger requested")
        self._run_job()

    def _run_job(self) -> None:
        """Execute scheduled job (with condition checks)."""
        # Check if paused
        if self.state.get_config("scheduler_state") == "paused":
            logger.info("Scheduler is paused, skipping run")
            return

        # Check run conditions
        run_mode = self.state.get_config("run_mode") or "awake-only"
        should_run_now, reason = should_run(run_mode)

        if not should_run_now:
            logger.info(f"Skipping run: {reason}")
            return

        logger.info(f"Conditions met: {reason}")
        self._execute_ingestion()

    def _execute_ingestion(self) -> None:
        """Execute the ingestion run."""
        max_results = int(self.state.get_config("max_results") or "100")

        runner = IngestionRunner(max_results=max_results)
        result = runner.run_ingestion()

        # Record result
        self.state.record_run(result)

        # Handle result
        if result.success:
            logger.info(
                f"Ingestion successful: {result.processed_docs} processed, "
                f"{result.skipped_docs} skipped in {result.duration:.2f}s"
            )
        else:
            logger.error(f"Ingestion failed: {result.error}")
            # Send notification on failure
            send_notification(
                "RAG Ingestion Failed",
                f"Error: {result.error[:100]}"  # Truncate long errors
            )
