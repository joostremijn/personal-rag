# Personal RAG Background Daemon

A background service that automatically ingests documents from Google Drive into your Personal RAG system at regular intervals.

## Features

- **Scheduled Ingestion**: Automatically fetches and processes documents from Google Drive
- **Configurable Intervals**: Run every 10, 30, or 60 minutes
- **Conditional Execution**: Only run when Mac is awake or plugged in
- **Web Dashboard**: Monitor status, view history, and control the daemon via web UI
- **CLI Tool**: Control daemon from the command line
- **macOS Notifications**: Get notified when ingestion fails
- **State Persistence**: Maintains configuration and run history in SQLite

## Quick Start

### 1. Start the Daemon

```bash
python daemon.py
```

The daemon will:
- Start on port 8001 (configurable with `--port`)
- Run every 60 minutes by default (configurable via dashboard/CLI)
- Only run when Mac is awake (configurable to "plugged-in-only")
- Fetch up to 100 documents from Google Drive (configurable)

### 2. Access the Web Dashboard

Open your browser to `http://localhost:8001`

The dashboard provides:
- Current status (running/paused, interval, mode)
- Last run details (time, success, documents processed)
- Configuration controls (change interval and mode)
- Run history table (last 20 runs)
- Manual controls (trigger now, pause, resume)

### 3. Use the CLI

```bash
# Check status
python daemon_cli.py status

# Trigger manual ingestion
python daemon_cli.py trigger

# Change configuration
python daemon_cli.py config --interval 30 --mode plugged-in-only

# View run history
python daemon_cli.py history --limit 10

# Pause/resume scheduler
python daemon_cli.py pause
python daemon_cli.py resume
```

## Configuration

### Intervals

Choose how often the daemon runs:
- **10 minutes**: Frequent updates (high API usage)
- **30 minutes**: Balanced (recommended for active use)
- **60 minutes**: Conservative (default, recommended for background use)

### Run Modes

Control when the daemon can run:
- **awake-only** (default): Run whenever the Mac is awake (not sleeping)
- **plugged-in-only**: Only run when Mac is plugged into AC power (battery-friendly)

### Max Results

Maximum number of documents to fetch from Google Drive per run (default: 100).

## Command Reference

### Daemon Process

```bash
# Start daemon
python daemon.py

# Start on custom port
python daemon.py --port 8080

# Use custom database path
python daemon.py --db-path /path/to/daemon.db
```

### CLI Commands

```bash
# Status
python daemon_cli.py status
python daemon_cli.py --url http://localhost:8080 status  # custom port

# Configuration
python daemon_cli.py config --interval 10
python daemon_cli.py config --mode plugged-in-only
python daemon_cli.py config --max-results 50
python daemon_cli.py config --interval 30 --mode awake-only  # multiple at once

# Manual trigger
python daemon_cli.py trigger

# Control scheduler
python daemon_cli.py pause
python daemon_cli.py resume

# History
python daemon_cli.py history
python daemon_cli.py history --limit 5

# Logs
python daemon_cli.py logs
python daemon_cli.py logs --tail 50
```

## Web Dashboard API

The daemon exposes a REST API:

### Endpoints

```
GET  /                      - Dashboard HTML
GET  /api/status            - Get daemon status
GET  /api/history?limit=20  - Get run history
GET  /api/config            - Get configuration
POST /api/config            - Update configuration
POST /api/trigger           - Trigger manual ingestion
POST /api/pause             - Pause scheduler
POST /api/resume            - Resume scheduler
GET  /api/logs?lines=100    - Get recent log lines
```

### Example: Get Status

```bash
curl http://localhost:8001/api/status
```

Response:
```json
{
  "scheduler_state": "running",
  "interval": "60",
  "run_mode": "awake-only",
  "max_results": "100",
  "last_run": {
    "timestamp": "2025-11-01T09:02:56",
    "success": true,
    "processed_docs": 94,
    "skipped_docs": 5,
    "total_chunks": 341,
    "duration": 253.13
  }
}
```

### Example: Update Configuration

```bash
curl -X POST http://localhost:8001/api/config \
  -H 'Content-Type: application/json' \
  -d '{"interval": 30, "run_mode": "plugged-in-only"}'
```

## Architecture

### Components

1. **daemon.py** - Main orchestrator
   - Initializes all components
   - Manages lifecycle (start/stop)
   - Handles graceful shutdown (SIGINT/SIGTERM)

2. **DaemonState** (`src/daemon/state.py`)
   - SQLite-backed state persistence
   - Stores configuration (interval, mode, max_results)
   - Records run history

3. **DaemonScheduler** (`src/daemon/scheduler.py`)
   - APScheduler-based job scheduling
   - Executes ingestion at intervals
   - Checks run conditions before executing

4. **IngestionRunner** (`src/daemon/runner.py`)
   - Wraps ingestion pipeline with monitoring
   - Handles errors gracefully
   - Returns structured results (RunResult)

5. **Web Dashboard** (`daemon_web.py`)
   - FastAPI application
   - REST API endpoints
   - HTML dashboard UI

6. **CLI Tool** (`daemon_cli.py`)
   - Command-line interface
   - Communicates with daemon via HTTP

### System Conditions

The daemon checks system conditions before running:

**macOS Integration** (`src/daemon/conditions.py`):
- `is_mac_sleeping()` - Checks if Mac is asleep (always returns False if we can check)
- `is_plugged_in()` - Checks AC power status via `pmset`
- `should_run(mode)` - Determines if conditions are met for given mode

**Notifications** (`src/daemon/notifications.py`):
- Sends macOS notifications on ingestion failures
- Uses `osascript` for native notifications

## Data Storage

### Database Location

Default: `data/daemon.db` (SQLite)

### Tables

**config**: Key-value store for daemon configuration
```sql
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

**run_history**: Records of ingestion runs
```sql
CREATE TABLE run_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    success INTEGER NOT NULL,
    duration REAL NOT NULL,
    processed_docs INTEGER DEFAULT 0,
    skipped_docs INTEGER DEFAULT 0,
    total_chunks INTEGER DEFAULT 0,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Logs

Location: `logs/daemon.log`

Log format:
```
2025-11-01 09:02:05,644 - __main__ - INFO - Starting Personal RAG Daemon
2025-11-01 09:02:56,333 - src.daemon.scheduler - INFO - Conditions met: Mac is awake
2025-11-01 09:07:09,465 - src.daemon.scheduler - INFO - Ingestion successful: 94 processed, 5 skipped in 253.13s
```

## Troubleshooting

### Daemon won't start

**Error**: `FileNotFoundError: logs/daemon.log`
**Fix**: The `logs/` directory should be created automatically. Check write permissions.

**Error**: `Port 8001 already in use`
**Fix**: Either stop the existing daemon or use a different port:
```bash
python daemon.py --port 8002
```

### Ingestion not running

**Check status**: `python daemon_cli.py status`

**Common issues**:
1. Scheduler is paused - Resume with `python daemon_cli.py resume`
2. Conditions not met - Check run mode:
   - "plugged-in-only" requires AC power
   - Mac must be awake for any mode
3. Check logs: `python daemon_cli.py logs --tail 50`

### No documents processed

**Symptoms**: Ingestion runs but 0 documents processed, all skipped

**Causes**:
1. **Incremental ingestion**: Documents haven't changed since last run
2. **No access**: Google Drive credentials may have expired
3. **Empty query**: No documents match the access criteria

**Solutions**:
- Force reindex to process all documents: Run `ingest.py --force-reindex`
- Check credentials: Look for Google Drive auth errors in logs
- Verify documents exist: Use `ingest.py --source-type gdrive --dry-run`

### API not responding

**Check if daemon is running**:
```bash
curl http://localhost:8001/api/status
```

**If connection refused**:
- Daemon may not be running - Start with `python daemon.py`
- Wrong port - Check what port daemon was started with
- Firewall blocking - Check macOS firewall settings

### High CPU/memory usage

**During ingestion**: Normal - processing and embedding documents is CPU-intensive

**When idle**: Not normal - Check logs for errors or stuck jobs

**Reduce load**:
- Increase interval: `python daemon_cli.py config --interval 60`
- Reduce max_results: `python daemon_cli.py config --max-results 50`
- Use "plugged-in-only" mode to avoid running on battery

## Production Deployment

### Running as macOS Launch Agent

To run the daemon automatically on login:

1. Create launch agent file: `~/Library/LaunchAgents/com.personal-rag.daemon.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.personal-rag.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USERNAME/src/personal/rag-pipeline/.venv/bin/python</string>
        <string>/Users/YOUR_USERNAME/src/personal/rag-pipeline/daemon.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/src/personal/rag-pipeline</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/src/personal/rag-pipeline/logs/daemon-stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/src/personal/rag-pipeline/logs/daemon-stderr.log</string>
</dict>
</plist>
```

2. Load the launch agent:
```bash
launchctl load ~/Library/LaunchAgents/com.personal-rag.daemon.plist
```

3. Verify it's running:
```bash
launchctl list | grep personal-rag
```

4. Unload (stop):
```bash
launchctl unload ~/Library/LaunchAgents/com.personal-rag.daemon.plist
```

### Recommended Settings

For production use:
- **Interval**: 60 minutes (conservative, low API usage)
- **Mode**: awake-only (runs during work hours automatically)
- **Max Results**: 100 (default, good balance)

For heavy users:
- **Interval**: 30 minutes
- **Mode**: plugged-in-only (battery-friendly)
- **Max Results**: 200

## Performance

### Ingestion Speed

Typical performance for 100 documents:
- Metadata fetch: ~10 seconds
- Document download: ~80 seconds
- Processing & embedding: ~160 seconds
- **Total**: ~250 seconds (4 minutes)

### API Usage

Per ingestion run (100 documents):
- **Google Drive API**: ~101 requests (1 list + 100 downloads)
- **OpenAI API**: ~7 embedding requests (batched, 50 chunks per batch)

Estimated costs per run:
- Embeddings: ~$0.02 (341 chunks × $0.00002/chunk)
- Total per day (24 runs): ~$0.48
- Total per month: ~$14.40

### Resource Usage

- **Memory**: ~200 MB (idle), ~500 MB (during ingestion)
- **Disk**: ~1 MB for database, ~10 MB for logs per month
- **CPU**: <1% (idle), 50-100% (during ingestion, brief spikes)

## Next Steps

- **Monitor**: Check dashboard regularly to ensure ingestion is working
- **Optimize**: Adjust interval and max_results based on your usage patterns
- **Query**: Use `query.py` or `app.py` (Streamlit) to search indexed documents
- **Expand**: Add more document sources (local files, Dropbox, etc.)

## See Also

- [CLAUDE.md](../CLAUDE.md) - Quick reference guide
- [GOOGLE-OAUTH.md](../GOOGLE-OAUTH.md) - Google Drive setup
- [PLAN-REMAINDER.md](../PLAN-REMAINDER.md) - Future enhancements
