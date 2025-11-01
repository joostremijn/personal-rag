# Background Ingestion Daemon Design

**Date:** 2025-10-31
**Status:** Approved
**Purpose:** Enable automatic background ingestion of documents from Google Drive on macOS

## Requirements

### Functional Requirements
- Run ingestion on configurable schedule (10min, 30min, or 60min intervals)
- Support conditional execution:
  - "Awake-only" mode: Skip runs when Mac is sleeping
  - "Plugged-in-only" mode: Skip runs when on battery power
- Provide web dashboard for monitoring and control
- Provide CLI for programmatic control
- Send macOS notifications on ingestion failures
- Persist daemon state and run history

### Non-Functional Requirements
- Reuse existing ingestion pipeline (no code duplication)
- Survive daemon restarts (persist configuration)
- Low resource usage when idle
- Fast runs with incremental ingestion (2-3s for unchanged documents)

## Architecture Overview

### Components

```
┌─────────────────────────────────────────────────┐
│                  daemon.py                      │
│  ┌──────────────┐  ┌──────────────────────────┐ │
│  │ APScheduler  │  │   FastAPI Web Server     │ │
│  │ (Background  │  │   (port 8001)            │ │
│  │  Scheduler)  │  │                          │ │
│  └──────┬───────┘  └────────┬─────────────────┘ │
│         │                   │                    │
│         v                   v                    │
│  ┌──────────────────────────────────────────┐   │
│  │        IngestionRunner                   │   │
│  │  - Condition checks (awake/power)        │   │
│  │  - Execute existing pipeline             │   │
│  │  - Error handling & notifications        │   │
│  └──────────────┬───────────────────────────┘   │
└─────────────────┼───────────────────────────────┘
                  │
                  v
         ┌────────────────────┐
         │ Existing Pipeline  │
         │ - IngestionPipeline│
         │ - GoogleDrive      │
         │ - ChromaDB         │
         └────────────────────┘
```

### File Structure

```
daemon.py                 # Main daemon entry point
daemon_web.py             # FastAPI web dashboard
daemon_cli.py             # CLI tool for control
src/daemon/
  ├── __init__.py
  ├── scheduler.py        # APScheduler configuration
  ├── conditions.py       # macOS system checks (awake/power)
  ├── runner.py           # Ingestion execution wrapper
  ├── notifications.py    # macOS notification sender
  └── state.py            # State persistence (SQLite)
data/
  └── daemon.db           # SQLite database for state
logs/
  └── daemon.log          # Daemon log file
```

## Component Details

### 1. Scheduler (APScheduler)

**Technology:** APScheduler `BackgroundScheduler`

**Configuration:**
- Interval options: 10, 30, or 60 minutes (default: 60)
- Stored in daemon state DB, dynamically adjustable
- Non-blocking execution (runs in background thread)

**Job execution flow:**
```python
def scheduled_job():
    # 1. Check conditions
    should_run, reason = check_conditions()
    if not should_run:
        log(f"Skipping run: {reason}")
        return

    # 2. Run ingestion
    result = runner.run_ingestion()

    # 3. Handle result
    if result.success:
        log_success(result.stats)
    else:
        log_error(result.error)
        send_notification(result.error)

    # 4. Store result in DB
    store_run_result(result)
```

### 2. Conditional Execution

**Condition Modes:**
- `awake-only`: Run only when Mac is not sleeping
- `plugged-in-only`: Run only when connected to AC power

**macOS System Checks:**

```python
def is_mac_sleeping() -> bool:
    """Check if Mac is in sleep mode."""
    # Use: pmset -g
    # Parse output for "sleep" state
    result = subprocess.run(['pmset', '-g'], capture_output=True, text=True)
    return 'sleep' in result.stdout.lower()

def is_plugged_in() -> bool:
    """Check if Mac is connected to AC power."""
    # Use: pmset -g batt
    # Parse output for "AC Power" or "Battery Power"
    result = subprocess.run(['pmset', '-g', 'batt'], capture_output=True, text=True)
    return 'AC Power' in result.stdout
```

**Implementation notes:**
- Checks run immediately before each scheduled job
- Fast execution (~50ms per check)
- If condition fails: Log reason, skip run, wait for next interval

### 3. Ingestion Runner

**Purpose:** Wrap existing `IngestionPipeline` with monitoring and error handling

```python
@dataclass
class RunResult:
    success: bool
    duration: float
    stats: Optional[IngestionStats]
    error: Optional[str]
    timestamp: datetime

class IngestionRunner:
    def run_ingestion(self) -> RunResult:
        """Execute ingestion with error handling."""
        start_time = time.time()

        try:
            # Initialize existing components
            pipeline = IngestionPipeline()
            connector = GoogleDriveConnector()

            # Fetch documents
            documents = connector.fetch_documents(
                mode='accessed',
                max_results=100,  # configurable in settings
            )

            # Run incremental ingestion
            stats = pipeline.ingest_documents_incremental(
                documents,
                skip_unchanged=True
            )

            return RunResult(
                success=True,
                duration=time.time() - start_time,
                stats=stats,
                error=None,
                timestamp=datetime.now()
            )

        except Exception as e:
            logger.exception("Ingestion failed")
            return RunResult(
                success=False,
                duration=time.time() - start_time,
                stats=None,
                error=str(e),
                timestamp=datetime.now()
            )
```

### 4. Error Handling & Notifications

**Error Handling:**
- Catch all exceptions during ingestion
- Log full traceback to `logs/daemon.log`
- Store error in state DB for dashboard display
- Continue scheduling (don't crash daemon)

**macOS Notifications:**

```python
def send_notification(title: str, message: str):
    """Send native macOS notification."""
    script = f'''
    display notification "{message}" with title "{title}"
    '''
    subprocess.run(['osascript', '-e', script])
```

**Notification Policy:**
- **Success**: No notification (silent operation)
- **Failure**: Send notification with error summary
- Example: "RAG Ingestion Failed: Network timeout connecting to Google Drive"

### 5. State Persistence

**SQLite Database:** `data/daemon.db`

**Schema:**

```sql
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE run_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    success BOOLEAN NOT NULL,
    duration REAL NOT NULL,
    processed_docs INTEGER,
    skipped_docs INTEGER,
    total_chunks INTEGER,
    error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Config keys:
-- - interval: "10", "30", or "60" (minutes)
-- - run_mode: "awake-only" or "plugged-in-only"
-- - scheduler_state: "running" or "paused"
-- - max_results: "100" (Google Drive fetch limit)
```

**State Operations:**
- Load config on daemon start
- Update config via web UI or CLI
- Store each run result
- Query recent history for dashboard
- Retain last 500 runs (auto-cleanup older entries)

### 6. Web Dashboard (FastAPI)

**Server:** FastAPI on port 8001

**Endpoints:**

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Dashboard UI (HTML page) |
| GET | `/api/status` | Current daemon status |
| GET | `/api/history` | Recent run history |
| GET | `/api/config` | Current configuration |
| POST | `/api/trigger` | Trigger manual run now |
| POST | `/api/config` | Update configuration |
| POST | `/api/pause` | Pause scheduler |
| POST | `/api/resume` | Resume scheduler |
| GET | `/api/logs` | Get recent log lines |

**Dashboard UI:**

```
┌─────────────────────────────────────────────────┐
│ Personal RAG - Background Ingestion Daemon      │
├─────────────────────────────────────────────────┤
│ Status: ● Running                               │
│ Next Run: 2:15 PM (in 8 minutes)                │
│ Last Run: 2:07 PM (Success - 2.3s)              │
│   ├─ Processed: 0 documents                     │
│   ├─ Skipped: 97 documents                      │
│   └─ Chunks: 0                                  │
├─────────────────────────────────────────────────┤
│ Configuration                                   │
│   Interval: [10min] [30min] [●60min]           │
│   Mode: [●Awake-only] [Plugged-in-only]        │
│   [Pause] [Trigger Now]                         │
├─────────────────────────────────────────────────┤
│ Recent Runs                                     │
│ ✓ 2:07 PM - 2.3s - 0 processed, 97 skipped     │
│ ✓ 1:07 PM - 2.1s - 1 processed, 96 skipped     │
│ ✗ 12:07 PM - Failed - Network timeout          │
│ ✓ 11:07 AM - 1.8s - 0 processed, 97 skipped    │
│   ... (show last 20)                            │
└─────────────────────────────────────────────────┘
```

### 7. CLI Tool

**Implementation:** Python script that calls FastAPI endpoints

**Commands:**

```bash
# Daemon lifecycle
python daemon_cli.py start          # Start daemon process
python daemon_cli.py stop           # Stop daemon process
python daemon_cli.py restart        # Restart daemon

# Status & monitoring
python daemon_cli.py status         # Show current status
python daemon_cli.py history        # Show recent runs
python daemon_cli.py logs --tail 50 # Show last 50 log lines

# Control
python daemon_cli.py trigger        # Trigger manual run now
python daemon_cli.py pause          # Pause scheduler
python daemon_cli.py resume         # Resume scheduler

# Configuration
python daemon_cli.py config --interval 10           # Set to 10 min
python daemon_cli.py config --mode awake-only       # Set mode
python daemon_cli.py config --max-results 200       # Set fetch limit
```

**Start Behavior:**
- Start daemon as background process
- Create PID file in `data/daemon.pid`
- Detach from terminal (runs independently)
- Can optionally add to macOS login items for auto-start on boot

## Deployment & Operations

### Starting the Daemon

**Manual start:**
```bash
python daemon_cli.py start
```

**Auto-start on login (optional):**
- Add to macOS Login Items via System Preferences
- Or create simple launchd .plist if user wants it to survive reboots

### Monitoring

**Check status:**
```bash
# CLI
python daemon_cli.py status

# Web dashboard
open http://localhost:8001
```

**View logs:**
```bash
# Tail logs
tail -f logs/daemon.log

# Via CLI
python daemon_cli.py logs --tail 100
```

### Configuration Changes

**Via Web UI:**
- Navigate to http://localhost:8001
- Adjust interval/mode dropdowns
- Changes take effect immediately (next scheduled run)

**Via CLI:**
```bash
python daemon_cli.py config --interval 30 --mode plugged-in-only
```

### Troubleshooting

**Daemon won't start:**
- Check if port 8001 is available: `lsof -i :8001`
- Check logs: `cat logs/daemon.log`
- Verify venv activated and dependencies installed

**Runs not happening:**
- Check daemon status: `python daemon_cli.py status`
- Verify conditions are met (awake/plugged-in based on mode)
- Check logs for skip reasons

**Ingestion errors:**
- View error in dashboard or CLI history
- Check if Google OAuth token expired (re-authenticate)
- Verify network connectivity
- Check OpenAI API key valid

## Success Criteria

- [ ] Daemon starts successfully and runs in background
- [ ] Scheduled runs execute on configured interval (10/30/60 min)
- [ ] Conditional execution correctly skips runs based on mode (awake/plugged-in)
- [ ] Web dashboard displays status, history, and allows configuration
- [ ] CLI commands work for all operations (start/stop/status/config)
- [ ] macOS notifications sent on ingestion failures
- [ ] State persists across daemon restarts
- [ ] Incremental ingestion results in fast runs (2-3s for unchanged documents)
- [ ] Daemon survives network errors and continues scheduling

## Future Enhancements

- Add Slack/email notification options
- Support multiple Google accounts
- Add ingestion from other sources (local folders, emails)
- Add metrics tracking (total documents indexed, API costs)
- Add web UI authentication if exposed beyond localhost
- Add launchd .plist generator for true system service
- Add data retention policies (auto-delete old documents)
