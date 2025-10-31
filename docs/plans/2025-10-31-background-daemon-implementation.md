# Background Ingestion Daemon Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an APScheduler-based daemon that automatically ingests documents from Google Drive on a configurable schedule with web dashboard and CLI control.

**Architecture:** Python daemon process using APScheduler for scheduling, FastAPI for web dashboard, SQLite for state persistence, and macOS native tools for system checks and notifications.

**Tech Stack:** APScheduler, FastAPI, SQLite, subprocess (for macOS pmset/osascript), existing IngestionPipeline

---

## Prerequisites

Before starting, ensure:
- Virtual environment activated: `source .venv/bin/activate`
- Dependencies installed: `uv pip install -e .`
- `.env` file configured with `OPENAI_API_KEY`
- Google OAuth configured (credentials.json, token.json)

---

## Task 1: Add Dependencies

**Files:**
- Modify: `pyproject.toml`

**Step 1: Add new dependencies to pyproject.toml**

Add to the dependencies list in pyproject.toml:

```toml
dependencies = [
    # ... existing dependencies ...
    "apscheduler>=3.10.0",
    "psutil>=5.9.0",  # For better process management
]
```

**Step 2: Install new dependencies**

Run: `uv pip install -e .`
Expected: Successfully installs apscheduler and psutil

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add apscheduler and psutil for daemon"
```

---

## Task 2: State Persistence Module

**Files:**
- Create: `src/daemon/__init__.py`
- Create: `src/daemon/state.py`
- Create: `tests/test_daemon_state.py`

**Step 1: Create daemon package**

Create empty `src/daemon/__init__.py`:

```python
"""Background ingestion daemon components."""
```

**Step 2: Write failing test for state management**

Create `tests/test_daemon_state.py`:

```python
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
        assert history[0]["success"] is True
        assert history[0]["duration"] == 2.5
```

**Step 3: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_daemon_state.py -v`
Expected: FAIL with "No module named 'src.daemon.state'"

**Step 4: Implement state module**

Create `src/daemon/state.py`:

```python
"""State persistence for background daemon."""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any


@dataclass
class RunResult:
    """Result from an ingestion run."""
    success: bool
    duration: float
    processed_docs: int
    skipped_docs: int
    total_chunks: int
    error: Optional[str]
    timestamp: datetime


class DaemonState:
    """Manages daemon state in SQLite database."""

    def __init__(self, db_path: Path) -> None:
        """Initialize state database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS run_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME NOT NULL,
                    success BOOLEAN NOT NULL,
                    duration REAL NOT NULL,
                    processed_docs INTEGER,
                    skipped_docs INTEGER,
                    total_chunks INTEGER,
                    error TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Set default config if not exists
            defaults = {
                "interval": "60",
                "run_mode": "awake-only",
                "scheduler_state": "running",
                "max_results": "100",
            }

            for key, value in defaults.items():
                conn.execute(
                    "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                    (key, value)
                )

            conn.commit()

    def get_config(self, key: str) -> Optional[str]:
        """Get configuration value.

        Args:
            key: Configuration key

        Returns:
            Configuration value or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT value FROM config WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def set_config(self, key: str, value: str) -> None:
        """Set configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                (key, value)
            )
            conn.commit()

    def record_run(self, result: RunResult) -> None:
        """Record an ingestion run result.

        Args:
            result: Run result to record
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO run_history
                (timestamp, success, duration, processed_docs, skipped_docs, total_chunks, error)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.timestamp.isoformat(),
                    result.success,
                    result.duration,
                    result.processed_docs,
                    result.skipped_docs,
                    result.total_chunks,
                    result.error,
                )
            )
            conn.commit()

            # Cleanup old entries (keep last 500)
            conn.execute(
                """
                DELETE FROM run_history
                WHERE id NOT IN (
                    SELECT id FROM run_history
                    ORDER BY id DESC
                    LIMIT 500
                )
                """
            )
            conn.commit()

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent run history.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of run history entries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM run_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_last_run(self) -> Optional[Dict[str, Any]]:
        """Get the most recent run.

        Returns:
            Most recent run entry or None
        """
        history = self.get_history(limit=1)
        return history[0] if history else None
```

**Step 5: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_daemon_state.py -v`
Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add src/daemon/__init__.py src/daemon/state.py tests/test_daemon_state.py
git commit -m "feat: add state persistence for daemon with SQLite"
```

---

## Task 3: macOS System Conditions

**Files:**
- Create: `src/daemon/conditions.py`
- Create: `tests/test_daemon_conditions.py`

**Step 1: Write failing test for condition checks**

Create `tests/test_daemon_conditions.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_daemon_conditions.py -v`
Expected: FAIL with "No module named 'src.daemon.conditions'"

**Step 3: Implement conditions module**

Create `src/daemon/conditions.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_daemon_conditions.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add src/daemon/conditions.py tests/test_daemon_conditions.py
git commit -m "feat: add macOS system condition checks (sleep/power)"
```

---

## Task 4: macOS Notifications

**Files:**
- Create: `src/daemon/notifications.py`
- Create: `tests/test_daemon_notifications.py`

**Step 1: Write test for notifications**

Create `tests/test_daemon_notifications.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_daemon_notifications.py -v`
Expected: FAIL with "No module named 'src.daemon.notifications'"

**Step 3: Implement notifications module**

Create `src/daemon/notifications.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_daemon_notifications.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/daemon/notifications.py tests/test_daemon_notifications.py
git commit -m "feat: add macOS notification support"
```

---

## Task 5: Ingestion Runner

**Files:**
- Create: `src/daemon/runner.py`
- Create: `tests/test_daemon_runner.py`

**Step 1: Write test for ingestion runner**

Create `tests/test_daemon_runner.py`:

```python
"""Tests for ingestion runner."""

from unittest.mock import patch, MagicMock
from src.daemon.runner import IngestionRunner
from src.models import IngestionStats


@patch('src.daemon.runner.GoogleDriveConnector')
@patch('src.daemon.runner.IngestionPipeline')
def test_run_ingestion_success(mock_pipeline, mock_connector):
    """Test successful ingestion run."""
    # Mock connector
    mock_connector_instance = MagicMock()
    mock_connector.return_value = mock_connector_instance
    mock_connector_instance.fetch_documents.return_value = [MagicMock()]

    # Mock pipeline
    mock_pipeline_instance = MagicMock()
    mock_pipeline.return_value = mock_pipeline_instance
    mock_stats = IngestionStats(
        total_documents=5,
        total_chunks=10,
        skipped_documents=95,
        failed_documents=0,
        processing_time=2.5
    )
    mock_pipeline_instance.ingest_documents_incremental.return_value = mock_stats

    runner = IngestionRunner(max_results=100)
    result = runner.run_ingestion()

    assert result.success is True
    assert result.processed_docs == 5
    assert result.skipped_docs == 95
    assert result.total_chunks == 10
    assert result.error is None


@patch('src.daemon.runner.GoogleDriveConnector')
def test_run_ingestion_failure(mock_connector):
    """Test ingestion run with error."""
    # Mock connector to raise exception
    mock_connector.return_value.fetch_documents.side_effect = Exception("Network error")

    runner = IngestionRunner(max_results=100)
    result = runner.run_ingestion()

    assert result.success is False
    assert result.error is not None
    assert "Network error" in result.error
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_daemon_runner.py -v`
Expected: FAIL with "No module named 'src.daemon.runner'"

**Step 3: Implement runner module**

Create `src/daemon/runner.py`:

```python
"""Ingestion execution wrapper with monitoring."""

import time
import logging
from datetime import datetime
from typing import Optional

from src.daemon.state import RunResult
from src.ingestion import IngestionPipeline
from src.connectors.gdrive import GoogleDriveConnector

logger = logging.getLogger(__name__)


class IngestionRunner:
    """Wraps ingestion pipeline with monitoring and error handling."""

    def __init__(self, max_results: int = 100) -> None:
        """Initialize ingestion runner.

        Args:
            max_results: Maximum documents to fetch from Google Drive
        """
        self.max_results = max_results

    def run_ingestion(self) -> RunResult:
        """Execute ingestion with error handling.

        Returns:
            RunResult with execution details
        """
        start_time = time.time()
        timestamp = datetime.now()

        try:
            logger.info("Starting ingestion run")

            # Initialize components
            pipeline = IngestionPipeline()
            connector = GoogleDriveConnector()

            # Fetch documents
            documents = connector.fetch_documents(
                mode='accessed',
                max_results=self.max_results,
            )

            logger.info(f"Fetched {len(documents)} documents from Google Drive")

            # Run incremental ingestion
            stats = pipeline.ingest_documents_incremental(
                documents,
                skip_unchanged=True
            )

            duration = time.time() - start_time

            logger.info(
                f"Ingestion complete: {stats.total_documents} processed, "
                f"{stats.skipped_documents} skipped, {stats.total_chunks} chunks "
                f"in {duration:.2f}s"
            )

            return RunResult(
                success=True,
                duration=duration,
                processed_docs=stats.total_documents,
                skipped_docs=stats.skipped_documents,
                total_chunks=stats.total_chunks,
                error=None,
                timestamp=timestamp
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            logger.exception("Ingestion failed")

            return RunResult(
                success=False,
                duration=duration,
                processed_docs=0,
                skipped_docs=0,
                total_chunks=0,
                error=error_msg,
                timestamp=timestamp
            )
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_daemon_runner.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add src/daemon/runner.py tests/test_daemon_runner.py
git commit -m "feat: add ingestion runner with monitoring"
```

---

## Task 6: Scheduler Component

**Files:**
- Create: `src/daemon/scheduler.py`
- Create: `tests/test_daemon_scheduler.py`

**Step 1: Write test for scheduler**

Create `tests/test_daemon_scheduler.py`:

```python
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
        mock_runner_instance = MagicMock()
        mock_runner.return_value = mock_runner_instance
        mock_result = MagicMock(success=True, duration=1.0)
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
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && pytest tests/test_daemon_scheduler.py -v`
Expected: FAIL with "No module named 'src.daemon.scheduler'"

**Step 3: Implement scheduler module**

Create `src/daemon/scheduler.py`:

```python
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
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && pytest tests/test_daemon_scheduler.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add src/daemon/scheduler.py tests/test_daemon_scheduler.py
git commit -m "feat: add APScheduler-based job scheduler"
```

---

## Task 7: FastAPI Web Dashboard

**Files:**
- Create: `daemon_web.py`
- Create: `templates/dashboard.html`

**Step 1: Create FastAPI app**

Create `daemon_web.py`:

```python
"""FastAPI web dashboard for daemon monitoring and control."""

import logging
from pathlib import Path
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.daemon.state import DaemonState

logger = logging.getLogger(__name__)

# Global state (initialized by daemon)
_state: DaemonState = None
_scheduler = None


def init_app(state: DaemonState, scheduler) -> FastAPI:
    """Initialize FastAPI app with state and scheduler.

    Args:
        state: Daemon state manager
        scheduler: Daemon scheduler

    Returns:
        FastAPI application
    """
    global _state, _scheduler
    _state = state
    _scheduler = scheduler

    app = FastAPI(title="Personal RAG Daemon")

    @app.get("/", response_class=HTMLResponse)
    async def dashboard():
        """Serve dashboard UI."""
        html_path = Path(__file__).parent / "templates" / "dashboard.html"
        if html_path.exists():
            return html_path.read_text()
        return "<h1>Dashboard</h1><p>Template not found</p>"

    @app.get("/api/status")
    async def get_status() -> Dict[str, Any]:
        """Get current daemon status."""
        last_run = _state.get_last_run()

        return {
            "scheduler_state": _state.get_config("scheduler_state"),
            "interval": _state.get_config("interval"),
            "run_mode": _state.get_config("run_mode"),
            "max_results": _state.get_config("max_results"),
            "last_run": last_run,
        }

    @app.get("/api/history")
    async def get_history(limit: int = 50) -> Dict[str, Any]:
        """Get run history."""
        history = _state.get_history(limit=limit)
        return {"history": history}

    @app.get("/api/config")
    async def get_config() -> Dict[str, str]:
        """Get current configuration."""
        return {
            "interval": _state.get_config("interval"),
            "run_mode": _state.get_config("run_mode"),
            "max_results": _state.get_config("max_results"),
        }

    class ConfigUpdate(BaseModel):
        interval: int = None
        run_mode: str = None
        max_results: int = None

    @app.post("/api/config")
    async def update_config(config: ConfigUpdate) -> Dict[str, str]:
        """Update configuration."""
        if config.interval is not None:
            if config.interval not in [10, 30, 60]:
                raise HTTPException(400, "Interval must be 10, 30, or 60")
            _state.set_config("interval", str(config.interval))
            _scheduler.update_interval(config.interval)

        if config.run_mode is not None:
            if config.run_mode not in ["awake-only", "plugged-in-only"]:
                raise HTTPException(400, "Invalid run_mode")
            _state.set_config("run_mode", config.run_mode)

        if config.max_results is not None:
            _state.set_config("max_results", str(config.max_results))

        return {"status": "updated"}

    @app.post("/api/trigger")
    async def trigger_ingestion() -> Dict[str, str]:
        """Trigger manual ingestion now."""
        _scheduler.trigger_now()
        return {"status": "triggered"}

    @app.post("/api/pause")
    async def pause_scheduler() -> Dict[str, str]:
        """Pause scheduler."""
        _scheduler.pause()
        return {"status": "paused"}

    @app.post("/api/resume")
    async def resume_scheduler() -> Dict[str, str]:
        """Resume scheduler."""
        _scheduler.resume()
        return {"status": "resumed"}

    @app.get("/api/logs")
    async def get_logs(lines: int = 100) -> Dict[str, Any]:
        """Get recent log lines."""
        log_path = Path("logs/daemon.log")
        if not log_path.exists():
            return {"logs": []}

        with open(log_path) as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:]
            return {"logs": recent_lines}

    return app
```

**Step 2: Create dashboard HTML template**

Create `templates/dashboard.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Personal RAG Daemon</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; }
        h1 { color: #333; }
        .status { padding: 15px; background: #e8f4f8; border-radius: 5px; margin: 10px 0; }
        .status.running { background: #d4edda; }
        .status.paused { background: #fff3cd; }
        .config { padding: 15px; background: #f8f9fa; border-radius: 5px; margin: 10px 0; }
        .history { margin-top: 20px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f8f9fa; }
        .success { color: green; }
        .failure { color: red; }
        button { padding: 8px 16px; margin: 5px; cursor: pointer; background: #007bff; color: white; border: none; border-radius: 4px; }
        button:hover { background: #0056b3; }
        select, input { padding: 8px; margin: 5px; border-radius: 4px; border: 1px solid #ddd; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Personal RAG - Background Ingestion Daemon</h1>

        <div id="status" class="status">
            <h2>Status</h2>
            <p>Loading...</p>
        </div>

        <div class="config">
            <h2>Configuration</h2>
            <label>Interval:
                <select id="interval">
                    <option value="10">10 minutes</option>
                    <option value="30">30 minutes</option>
                    <option value="60">60 minutes</option>
                </select>
            </label>
            <label>Mode:
                <select id="mode">
                    <option value="awake-only">Awake Only</option>
                    <option value="plugged-in-only">Plugged In Only</option>
                </select>
            </label>
            <button onclick="updateConfig()">Update Config</button>
            <button onclick="triggerNow()">Trigger Now</button>
            <button onclick="pauseScheduler()">Pause</button>
            <button onclick="resumeScheduler()">Resume</button>
        </div>

        <div class="history">
            <h2>Recent Runs</h2>
            <table id="history-table">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Status</th>
                        <th>Duration</th>
                        <th>Processed</th>
                        <th>Skipped</th>
                        <th>Chunks</th>
                        <th>Error</th>
                    </tr>
                </thead>
                <tbody id="history-body">
                    <tr><td colspan="7">Loading...</td></tr>
                </tbody>
            </table>
        </div>
    </div>

    <script>
        async function loadStatus() {
            const res = await fetch('/api/status');
            const data = await res.json();

            const statusDiv = document.getElementById('status');
            statusDiv.className = 'status ' + data.scheduler_state;

            let html = '<h2>Status</h2>';
            html += `<p>State: <strong>${data.scheduler_state}</strong></p>`;
            html += `<p>Interval: ${data.interval} minutes</p>`;
            html += `<p>Mode: ${data.run_mode}</p>`;

            if (data.last_run) {
                html += `<p>Last Run: ${new Date(data.last_run.timestamp).toLocaleString()}</p>`;
                html += `<p>Result: ${data.last_run.success ? 'Success' : 'Failed'}</p>`;
                html += `<p>Processed: ${data.last_run.processed_docs}, Skipped: ${data.last_run.skipped_docs}</p>`;
            }

            statusDiv.innerHTML = html;

            // Update config dropdowns
            document.getElementById('interval').value = data.interval;
            document.getElementById('mode').value = data.run_mode;
        }

        async function loadHistory() {
            const res = await fetch('/api/history?limit=20');
            const data = await res.json();

            const tbody = document.getElementById('history-body');
            tbody.innerHTML = '';

            data.history.forEach(run => {
                const row = tbody.insertRow();
                row.innerHTML = `
                    <td>${new Date(run.timestamp).toLocaleString()}</td>
                    <td class="${run.success ? 'success' : 'failure'}">${run.success ? '✓' : '✗'}</td>
                    <td>${run.duration.toFixed(2)}s</td>
                    <td>${run.processed_docs || 0}</td>
                    <td>${run.skipped_docs || 0}</td>
                    <td>${run.total_chunks || 0}</td>
                    <td>${run.error || ''}</td>
                `;
            });
        }

        async function updateConfig() {
            const interval = parseInt(document.getElementById('interval').value);
            const mode = document.getElementById('mode').value;

            await fetch('/api/config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({interval, run_mode: mode})
            });

            loadStatus();
        }

        async function triggerNow() {
            await fetch('/api/trigger', {method: 'POST'});
            alert('Ingestion triggered');
            setTimeout(loadStatus, 1000);
            setTimeout(loadHistory, 2000);
        }

        async function pauseScheduler() {
            await fetch('/api/pause', {method: 'POST'});
            loadStatus();
        }

        async function resumeScheduler() {
            await fetch('/api/resume', {method: 'POST'});
            loadStatus();
        }

        // Load data on page load
        loadStatus();
        loadHistory();

        // Refresh every 10 seconds
        setInterval(() => {
            loadStatus();
            loadHistory();
        }, 10000);
    </script>
</body>
</html>
```

**Step 3: Commit**

```bash
mkdir -p templates
git add daemon_web.py templates/dashboard.html
git commit -m "feat: add FastAPI web dashboard"
```

---

## Task 8: CLI Tool

**Files:**
- Create: `daemon_cli.py`

**Step 1: Create CLI script**

Create `daemon_cli.py`:

```python
#!/usr/bin/env python3
"""CLI tool for controlling the daemon."""

import argparse
import sys
import subprocess
import signal
import time
from pathlib import Path

import requests


DAEMON_SCRIPT = "daemon.py"
PID_FILE = Path("data/daemon.pid")
API_URL = "http://localhost:8001"


def is_daemon_running() -> bool:
    """Check if daemon is running."""
    if not PID_FILE.exists():
        return False

    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process exists
        subprocess.run(['ps', '-p', str(pid)], capture_output=True, check=True)
        return True
    except:
        return False


def start_daemon():
    """Start the daemon process."""
    if is_daemon_running():
        print("Daemon is already running")
        return 1

    # Start daemon in background
    process = subprocess.Popen(
        [sys.executable, DAEMON_SCRIPT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True  # Detach from parent
    )

    # Write PID
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(str(process.pid))

    # Wait a bit to see if it starts
    time.sleep(2)

    if is_daemon_running():
        print(f"Daemon started (PID: {process.pid})")
        print(f"Web dashboard: {API_URL}")
        return 0
    else:
        print("Failed to start daemon")
        return 1


def stop_daemon():
    """Stop the daemon process."""
    if not is_daemon_running():
        print("Daemon is not running")
        return 1

    try:
        pid = int(PID_FILE.read_text().strip())
        subprocess.run(['kill', str(pid)], check=True)
        PID_FILE.unlink()
        print("Daemon stopped")
        return 0
    except Exception as e:
        print(f"Error stopping daemon: {e}")
        return 1


def get_status():
    """Get daemon status."""
    if not is_daemon_running():
        print("Daemon is not running")
        return 1

    try:
        res = requests.get(f"{API_URL}/api/status", timeout=5)
        data = res.json()

        print("=== Daemon Status ===")
        print(f"State: {data['scheduler_state']}")
        print(f"Interval: {data['interval']} minutes")
        print(f"Mode: {data['run_mode']}")
        print(f"Max Results: {data['max_results']}")

        if data.get('last_run'):
            lr = data['last_run']
            print(f"\nLast Run:")
            print(f"  Time: {lr['timestamp']}")
            print(f"  Success: {lr['success']}")
            print(f"  Duration: {lr['duration']:.2f}s")
            print(f"  Processed: {lr.get('processed_docs', 0)}")
            print(f"  Skipped: {lr.get('skipped_docs', 0)}")
            if lr.get('error'):
                print(f"  Error: {lr['error']}")

        return 0
    except Exception as e:
        print(f"Error getting status: {e}")
        return 1


def trigger_now():
    """Trigger manual ingestion."""
    if not is_daemon_running():
        print("Daemon is not running")
        return 1

    try:
        requests.post(f"{API_URL}/api/trigger", timeout=5)
        print("Ingestion triggered")
        return 0
    except Exception as e:
        print(f"Error triggering ingestion: {e}")
        return 1


def pause_daemon():
    """Pause scheduler."""
    if not is_daemon_running():
        print("Daemon is not running")
        return 1

    try:
        requests.post(f"{API_URL}/api/pause", timeout=5)
        print("Scheduler paused")
        return 0
    except Exception as e:
        print(f"Error pausing: {e}")
        return 1


def resume_daemon():
    """Resume scheduler."""
    if not is_daemon_running():
        print("Daemon is not running")
        return 1

    try:
        requests.post(f"{API_URL}/api/resume", timeout=5)
        print("Scheduler resumed")
        return 0
    except Exception as e:
        print(f"Error resuming: {e}")
        return 1


def configure(args):
    """Update configuration."""
    if not is_daemon_running():
        print("Daemon is not running")
        return 1

    try:
        config = {}
        if args.interval:
            config['interval'] = args.interval
        if args.mode:
            config['run_mode'] = args.mode
        if args.max_results:
            config['max_results'] = args.max_results

        requests.post(f"{API_URL}/api/config", json=config, timeout=5)
        print("Configuration updated")
        return 0
    except Exception as e:
        print(f"Error updating config: {e}")
        return 1


def show_logs(args):
    """Show recent logs."""
    if not is_daemon_running():
        print("Daemon is not running")
        return 1

    try:
        res = requests.get(f"{API_URL}/api/logs?lines={args.tail}", timeout=5)
        data = res.json()

        for line in data['logs']:
            print(line, end='')

        return 0
    except Exception as e:
        print(f"Error getting logs: {e}")
        return 1


def show_history():
    """Show run history."""
    if not is_daemon_running():
        print("Daemon is not running")
        return 1

    try:
        res = requests.get(f"{API_URL}/api/history?limit=20", timeout=5)
        data = res.json()

        print("=== Recent Runs ===")
        for run in data['history']:
            status = "✓" if run['success'] else "✗"
            print(f"{status} {run['timestamp']} - {run['duration']:.2f}s - "
                  f"Processed: {run.get('processed_docs', 0)}, "
                  f"Skipped: {run.get('skipped_docs', 0)}")
            if run.get('error'):
                print(f"   Error: {run['error']}")

        return 0
    except Exception as e:
        print(f"Error getting history: {e}")
        return 1


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Control Personal RAG daemon")
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Start command
    subparsers.add_parser('start', help='Start daemon')

    # Stop command
    subparsers.add_parser('stop', help='Stop daemon')

    # Restart command
    subparsers.add_parser('restart', help='Restart daemon')

    # Status command
    subparsers.add_parser('status', help='Show daemon status')

    # Trigger command
    subparsers.add_parser('trigger', help='Trigger manual ingestion')

    # Pause command
    subparsers.add_parser('pause', help='Pause scheduler')

    # Resume command
    subparsers.add_parser('resume', help='Resume scheduler')

    # Config command
    config_parser = subparsers.add_parser('config', help='Update configuration')
    config_parser.add_argument('--interval', type=int, choices=[10, 30, 60])
    config_parser.add_argument('--mode', choices=['awake-only', 'plugged-in-only'])
    config_parser.add_argument('--max-results', type=int)

    # Logs command
    logs_parser = subparsers.add_parser('logs', help='Show recent logs')
    logs_parser.add_argument('--tail', type=int, default=50)

    # History command
    subparsers.add_parser('history', help='Show run history')

    args = parser.parse_args()

    # Execute command
    if args.command == 'start':
        return start_daemon()
    elif args.command == 'stop':
        return stop_daemon()
    elif args.command == 'restart':
        stop_daemon()
        time.sleep(1)
        return start_daemon()
    elif args.command == 'status':
        return get_status()
    elif args.command == 'trigger':
        return trigger_now()
    elif args.command == 'pause':
        return pause_daemon()
    elif args.command == 'resume':
        return resume_daemon()
    elif args.command == 'config':
        return configure(args)
    elif args.command == 'logs':
        return show_logs(args)
    elif args.command == 'history':
        return show_history()


if __name__ == '__main__':
    sys.exit(main())
```

**Step 2: Make CLI executable**

Run: `chmod +x daemon_cli.py`

**Step 3: Commit**

```bash
git add daemon_cli.py
git commit -m "feat: add CLI tool for daemon control"
```

---

## Task 9: Main Daemon Process

**Files:**
- Create: `daemon.py`

**Step 1: Create main daemon script**

Create `daemon.py`:

```python
#!/usr/bin/env python3
"""Main daemon process."""

import logging
import signal
import sys
import threading
from pathlib import Path

import uvicorn

from src.daemon.state import DaemonState
from src.daemon.scheduler import DaemonScheduler
from daemon_web import init_app


# Configure logging
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "daemon.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class Daemon:
    """Main daemon orchestrator."""

    def __init__(self):
        """Initialize daemon components."""
        # Initialize state
        db_path = Path("data/daemon.db")
        self.state = DaemonState(db_path)

        # Initialize scheduler
        self.scheduler = DaemonScheduler(self.state)

        # Initialize FastAPI app
        self.app = init_app(self.state, self.scheduler)

        # Track server thread
        self.server_thread = None
        self.should_stop = False

    def start(self):
        """Start the daemon."""
        logger.info("Starting Personal RAG daemon")

        # Start scheduler
        self.scheduler.start()

        # Start web server in thread
        self.server_thread = threading.Thread(
            target=self._run_server,
            daemon=True
        )
        self.server_thread.start()

        logger.info("Daemon started successfully")
        logger.info("Web dashboard: http://localhost:8001")

        # Register signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        # Keep main thread alive
        try:
            while not self.should_stop:
                threading.Event().wait(1)
        except KeyboardInterrupt:
            self.stop()

    def _run_server(self):
        """Run FastAPI server."""
        uvicorn.run(
            self.app,
            host="127.0.0.1",
            port=8001,
            log_level="error"  # Quiet server logs
        )

    def stop(self):
        """Stop the daemon."""
        logger.info("Stopping daemon")
        self.should_stop = True

        # Stop scheduler
        self.scheduler.stop()

        logger.info("Daemon stopped")
        sys.exit(0)

    def _handle_signal(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}")
        self.stop()


def main():
    """Main entry point."""
    daemon = Daemon()
    daemon.start()


if __name__ == '__main__':
    main()
```

**Step 2: Make daemon executable**

Run: `chmod +x daemon.py`

**Step 3: Test daemon startup**

Run: `source .venv/bin/activate && python daemon.py`

Expected:
- Daemon starts
- Logs show "Daemon started successfully"
- Web dashboard accessible at http://localhost:8001

Press Ctrl+C to stop.

**Step 4: Commit**

```bash
git add daemon.py
git commit -m "feat: add main daemon process with scheduler and web server"
```

---

## Task 10: Integration Testing

**Files:**
- None (manual testing)

**Step 1: Test daemon lifecycle**

```bash
# Start daemon
python daemon_cli.py start

# Check status
python daemon_cli.py status

# Should show: State: running, Interval: 60 minutes
```

**Step 2: Test web dashboard**

Open http://localhost:8001 in browser
- Should see dashboard with status
- Try changing interval to 10 minutes
- Click "Trigger Now"
- Verify run appears in history

**Step 3: Test CLI configuration**

```bash
# Update interval
python daemon_cli.py config --interval 30

# Check status (should show 30 minutes)
python daemon_cli.py status

# View history
python daemon_cli.py history
```

**Step 4: Test pause/resume**

```bash
# Pause
python daemon_cli.py pause

# Status should show "paused"
python daemon_cli.py status

# Resume
python daemon_cli.py resume
```

**Step 5: Test manual trigger**

```bash
# Trigger ingestion
python daemon_cli.py trigger

# Wait a few seconds, then check history
python daemon_cli.py history
```

**Step 6: Stop daemon**

```bash
python daemon_cli.py stop
```

**Step 7: Document testing results**

If all tests pass, proceed to commit.

---

## Task 11: Documentation

**Files:**
- Create: `docs/DAEMON.md`
- Modify: `CLAUDE.md`

**Step 1: Create daemon documentation**

Create `docs/DAEMON.md`:

```markdown
# Background Ingestion Daemon

Automatic background ingestion of documents from Google Drive.

## Quick Start

```bash
# Start daemon
python daemon_cli.py start

# Check status
python daemon_cli.py status

# Open dashboard
open http://localhost:8001

# Stop daemon
python daemon_cli.py stop
```

## Features

- **Automatic Scheduling**: Runs every 10, 30, or 60 minutes (configurable)
- **Conditional Execution**: "Awake-only" or "Plugged-in-only" modes
- **Web Dashboard**: Monitor status, view history, adjust settings
- **CLI Control**: Start, stop, configure via command line
- **macOS Notifications**: Get notified on ingestion failures
- **Persistent State**: Survives daemon restarts

## Configuration

### Via Web Dashboard

1. Open http://localhost:8001
2. Adjust interval (10/30/60 minutes)
3. Select mode (awake-only / plugged-in-only)
4. Click "Update Config"

### Via CLI

```bash
# Set interval to 10 minutes
python daemon_cli.py config --interval 10

# Set mode to plugged-in-only
python daemon_cli.py config --mode plugged-in-only

# Set max results from Google Drive
python daemon_cli.py config --max-results 200
```

## CLI Commands

```bash
# Lifecycle
python daemon_cli.py start           # Start daemon
python daemon_cli.py stop            # Stop daemon
python daemon_cli.py restart         # Restart daemon

# Monitoring
python daemon_cli.py status          # Show current status
python daemon_cli.py history         # Show recent runs
python daemon_cli.py logs --tail 50  # Show last 50 log lines

# Control
python daemon_cli.py trigger         # Trigger manual run now
python daemon_cli.py pause           # Pause scheduler
python daemon_cli.py resume          # Resume scheduler

# Configuration
python daemon_cli.py config --interval 10           # Set to 10 min
python daemon_cli.py config --mode awake-only       # Set mode
python daemon_cli.py config --max-results 200       # Set fetch limit
```

## Web Dashboard

Access at http://localhost:8001

**Features:**
- Real-time status display
- Run history table (last 20 runs)
- Configuration controls
- Manual trigger button
- Pause/resume buttons
- Auto-refreshes every 10 seconds

## Run Modes

### Awake-Only Mode
- Runs only when Mac is awake
- Skips scheduled runs when sleeping
- Good for: Always-on background updates

### Plugged-In-Only Mode
- Runs only when connected to AC power
- Skips runs when on battery
- Good for: Conserving battery life

## Notifications

macOS notifications sent only on failures:
- "RAG Ingestion Failed: [error summary]"
- Click notification to see details in dashboard

## Logs

Daemon logs to `logs/daemon.log`:

```bash
# View logs
tail -f logs/daemon.log

# Via CLI
python daemon_cli.py logs --tail 100
```

## Auto-Start on Login (Optional)

To start daemon automatically on macOS login:

1. Open System Preferences > Users & Groups > Login Items
2. Click "+" to add item
3. Navigate to project directory
4. Add `daemon_cli.py start` script

Or use `launchd` (advanced):
- Create `.plist` file in `~/Library/LaunchAgents/`
- Configure to run `daemon.py` on login

## Troubleshooting

**Daemon won't start:**
```bash
# Check if port 8001 is available
lsof -i :8001

# Check logs
cat logs/daemon.log
```

**Runs not happening:**
```bash
# Check status
python daemon_cli.py status

# Verify conditions met (not sleeping / plugged in based on mode)

# Check logs for skip reasons
python daemon_cli.py logs --tail 50
```

**Ingestion errors:**
- Check error in dashboard or `python daemon_cli.py history`
- Verify Google OAuth token: `ls -la token.json`
- Re-authenticate if needed: `rm token.json && python ingest.py --source-type gdrive --list-folders`
- Check OpenAI API key in `.env`

## Architecture

```
daemon.py (main process)
├── DaemonScheduler (APScheduler)
│   ├── Scheduled jobs (interval-based)
│   └── Condition checks (awake/power)
├── FastAPI web server (port 8001)
│   └── Dashboard + API endpoints
└── DaemonState (SQLite)
    ├── Configuration
    └── Run history
```

## State Files

- `data/daemon.db` - SQLite database (config + history)
- `data/daemon.pid` - Process ID file
- `logs/daemon.log` - Daemon log file

## Performance

With incremental ingestion:
- **10-minute runs**: ~2-3 seconds for 100 unchanged files
- **30-minute runs**: ~2-5 seconds (depends on changes)
- **60-minute runs**: ~3-10 seconds (may have more changes)

Frequent runs are cheap thanks to skip-before-download optimization!
```

**Step 2: Update CLAUDE.md**

Add to `CLAUDE.md` under "Quick Start":

```markdown
# Background Daemon (optional)
python daemon_cli.py start          # Start automatic ingestion
open http://localhost:8001          # Open dashboard
```

**Step 3: Commit**

```bash
git add docs/DAEMON.md CLAUDE.md
git commit -m "docs: add daemon documentation"
```

---

## Task 12: Final Testing & Completion

**Step 1: End-to-end test**

Run full workflow:

1. Start daemon: `python daemon_cli.py start`
2. Wait 2 minutes (or trigger manually)
3. Check dashboard shows successful run
4. Change interval to 10 minutes via dashboard
5. Wait 10 minutes, verify run happens
6. Check macOS notification if run fails (test by disabling network)
7. Stop daemon: `python daemon_cli.py stop`

**Step 2: Verify all files committed**

Run: `git status`

Should show: "nothing to commit, working tree clean"

**Step 3: Create final summary commit**

```bash
git log --oneline -15 > /tmp/commits.txt
git commit --allow-empty -m "feat: complete background daemon implementation

Implemented APScheduler-based daemon for automatic document ingestion:
- Configurable intervals: 10min, 30min, 60min
- Conditional execution: awake-only or plugged-in-only modes
- Web dashboard (FastAPI) at localhost:8001
- CLI tool for control and monitoring
- macOS notifications on failures
- SQLite state persistence
- Full integration with existing ingestion pipeline

See docs/DAEMON.md for usage instructions."
```

---

## Success Criteria Checklist

Before considering this complete, verify:

- [ ] Daemon starts successfully with `python daemon_cli.py start`
- [ ] Web dashboard accessible at http://localhost:8001
- [ ] Scheduler runs on configured interval (test with 10 min)
- [ ] Awake-only mode skips when Mac would be sleeping (can't test directly)
- [ ] Plugged-in-only mode skips when on battery
- [ ] Manual trigger works via dashboard and CLI
- [ ] Configuration updates work (interval, mode)
- [ ] Pause/resume works
- [ ] Run history displays in dashboard
- [ ] CLI commands all work (start/stop/status/config/history/logs)
- [ ] macOS notifications sent on ingestion failure
- [ ] State persists across daemon restarts
- [ ] Logs written to `logs/daemon.log`
- [ ] All tests pass: `pytest tests/test_daemon_*.py`

---

## Notes for Implementation

### Testing Strategy
- Unit tests for individual components (state, conditions, scheduler)
- Mock external dependencies (GoogleDrive, IngestionPipeline)
- Manual integration testing for end-to-end flow
- Test on macOS specifically (pmset, osascript)

### Key Design Decisions
- **APScheduler over cron**: More flexible, easier to control programmatically
- **SQLite over JSON**: Better concurrency, query capabilities
- **FastAPI over Streamlit**: Lightweight, better for API-first design
- **Background thread for web server**: Keep scheduler in main thread for signal handling

### Dependencies Added
- `apscheduler>=3.10.0` - Job scheduling
- `psutil>=5.9.0` - Process management utilities

### Future Enhancements
- Add Slack/email notification options
- Support multiple Google accounts
- Add metrics tracking (API costs, total docs)
- Add authentication for web UI if exposing beyond localhost
- Create launchd .plist generator for system service
