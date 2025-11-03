# Multi-Source Daemon Configuration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable users to configure multiple named sources (Google Drive folders, local directories) with integrated OAuth, smart batch processing, and user-friendly web UI.

**Architecture:** Hybrid approach with simple database schema (sources table) + smart two-phase runner (250 metadata fetch, 10 download/process batches). ChromaDB-based deduplication eliminates max_results cap. Global OAuth for all Drive sources.

**Tech Stack:** SQLite (sources table), FastAPI (OAuth + API endpoints), APScheduler (existing), ChromaDB (existing), Google Drive API, Jinja2 (dashboard templates)

---

## Phase 1: Database & State Foundation

### Task 1.1: Create Sources Table Schema

**Files:**
- Modify: `src/daemon/state.py:35-73`
- Test: `tests/unit/daemon/test_daemon_state.py`

**Step 1: Write test for sources table creation**

Add to `tests/unit/daemon/test_daemon_state.py`:

```python
def test_sources_table_exists(tmp_path):
    """Test that sources table is created on init."""
    db_path = tmp_path / "test.db"
    state = DaemonState(db_path)

    import sqlite3
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sources'"
        )
        assert cursor.fetchone() is not None
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/daemon/test_daemon_state.py::test_sources_table_exists -v
```

Expected: FAIL (table doesn't exist)

**Step 3: Add sources table to schema**

In `src/daemon/state.py`, modify `_init_db` method to add after `run_history` table:

```python
def _init_db(self) -> None:
    """Initialize database schema."""
    with sqlite3.connect(self.db_path) as conn:
        # ... existing config table ...

        # ... existing run_history table ...

        # Sources table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                source_type TEXT NOT NULL,
                enabled BOOLEAN DEFAULT 1,

                folder_id TEXT,
                ingestion_mode TEXT DEFAULT 'accessed',
                days_back INTEGER DEFAULT 730,

                local_path TEXT,
                recursive BOOLEAN DEFAULT 1,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # ... existing defaults ...

        conn.commit()
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/daemon/test_daemon_state.py::test_sources_table_exists -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/daemon/state.py tests/unit/daemon/test_daemon_state.py
git commit -m "feat: add sources table schema to daemon state"
```

---

### Task 1.2: Add Source CRUD Methods

**Files:**
- Modify: `src/daemon/state.py` (add new methods after existing methods)
- Test: `tests/unit/daemon/test_daemon_state.py`

**Step 1: Write test for create_source**

Add to `tests/unit/daemon/test_daemon_state.py`:

```python
def test_create_source(tmp_path):
    """Test creating a new source."""
    db_path = tmp_path / "test.db"
    state = DaemonState(db_path)

    source_data = {
        "name": "Test Drive",
        "source_type": "gdrive",
        "enabled": True,
        "folder_id": None,
        "ingestion_mode": "accessed",
        "days_back": 730
    }

    source_id = state.create_source(source_data)
    assert source_id is not None
    assert source_id > 0
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/daemon/test_daemon_state.py::test_create_source -v
```

Expected: FAIL (method doesn't exist)

**Step 3: Implement create_source method**

Add to `src/daemon/state.py` after `get_last_run`:

```python
def create_source(self, data: Dict[str, Any]) -> int:
    """Create a new source.

    Args:
        data: Source configuration

    Returns:
        ID of created source
    """
    with sqlite3.connect(self.db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO sources
            (name, source_type, enabled, folder_id, ingestion_mode, days_back, local_path, recursive)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["name"],
                data["source_type"],
                data.get("enabled", True),
                data.get("folder_id"),
                data.get("ingestion_mode", "accessed"),
                data.get("days_back", 730),
                data.get("local_path"),
                data.get("recursive", True),
            )
        )
        conn.commit()
        return cursor.lastrowid
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/daemon/test_daemon_state.py::test_create_source -v
```

Expected: PASS

**Step 5: Write tests for remaining CRUD operations**

Add to `tests/unit/daemon/test_daemon_state.py`:

```python
def test_get_sources(tmp_path):
    """Test listing all sources."""
    db_path = tmp_path / "test.db"
    state = DaemonState(db_path)

    # Create two sources
    state.create_source({"name": "Source 1", "source_type": "gdrive"})
    state.create_source({"name": "Source 2", "source_type": "local", "local_path": "/test"})

    sources = state.get_sources()
    assert len(sources) == 2
    assert sources[0]["name"] == "Source 1"
    assert sources[1]["name"] == "Source 2"


def test_get_enabled_sources(tmp_path):
    """Test listing only enabled sources."""
    db_path = tmp_path / "test.db"
    state = DaemonState(db_path)

    state.create_source({"name": "Enabled", "source_type": "gdrive", "enabled": True})
    state.create_source({"name": "Disabled", "source_type": "gdrive", "enabled": False})

    sources = state.get_sources(enabled_only=True)
    assert len(sources) == 1
    assert sources[0]["name"] == "Enabled"


def test_update_source(tmp_path):
    """Test updating a source."""
    db_path = tmp_path / "test.db"
    state = DaemonState(db_path)

    source_id = state.create_source({"name": "Test", "source_type": "gdrive"})
    state.update_source(source_id, {"name": "Updated", "days_back": 365})

    sources = state.get_sources()
    assert sources[0]["name"] == "Updated"
    assert sources[0]["days_back"] == 365


def test_delete_source(tmp_path):
    """Test deleting a source."""
    db_path = tmp_path / "test.db"
    state = DaemonState(db_path)

    source_id = state.create_source({"name": "Test", "source_type": "gdrive"})
    state.delete_source(source_id)

    sources = state.get_sources()
    assert len(sources) == 0
```

**Step 6: Run tests to verify they fail**

```bash
pytest tests/unit/daemon/test_daemon_state.py -k "get_sources or update_source or delete_source" -v
```

Expected: FAIL (methods don't exist)

**Step 7: Implement remaining CRUD methods**

Add to `src/daemon/state.py`:

```python
def get_sources(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
    """Get all sources.

    Args:
        enabled_only: If True, return only enabled sources

    Returns:
        List of source dictionaries
    """
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row
        query = "SELECT * FROM sources"
        if enabled_only:
            query += " WHERE enabled = 1"
        query += " ORDER BY created_at DESC"

        cursor = conn.execute(query)
        return [dict(row) for row in cursor.fetchall()]


def get_source(self, source_id: int) -> Optional[Dict[str, Any]]:
    """Get a single source by ID.

    Args:
        source_id: Source ID

    Returns:
        Source dictionary or None
    """
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM sources WHERE id = ?",
            (source_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def update_source(self, source_id: int, data: Dict[str, Any]) -> None:
    """Update a source.

    Args:
        source_id: Source ID
        data: Fields to update
    """
    fields = []
    values = []

    for key, value in data.items():
        if key != "id":
            fields.append(f"{key} = ?")
            values.append(value)

    if not fields:
        return

    values.append(source_id)

    with sqlite3.connect(self.db_path) as conn:
        conn.execute(
            f"UPDATE sources SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            values
        )
        conn.commit()


def delete_source(self, source_id: int) -> None:
    """Delete a source.

    Args:
        source_id: Source ID
    """
    with sqlite3.connect(self.db_path) as conn:
        conn.execute("DELETE FROM sources WHERE id = ?", (source_id,))
        conn.commit()
```

**Step 8: Run all tests to verify they pass**

```bash
pytest tests/unit/daemon/test_daemon_state.py -v
```

Expected: All PASS

**Step 9: Commit**

```bash
git add src/daemon/state.py tests/unit/daemon/test_daemon_state.py
git commit -m "feat: add source CRUD methods to daemon state"
```

---

### Task 1.3: Add Source Breakdown to Run History

**Files:**
- Modify: `src/daemon/state.py:106-143`
- Test: `tests/unit/daemon/test_daemon_state.py`

**Step 1: Write test for source breakdown in run history**

Add to `tests/unit/daemon/test_daemon_state.py`:

```python
def test_record_run_with_source_breakdown(tmp_path):
    """Test recording run with per-source breakdown."""
    from src.daemon.state import RunResult
    from datetime import datetime

    db_path = tmp_path / "test.db"
    state = DaemonState(db_path)

    result = RunResult(
        success=True,
        duration=120.5,
        processed_docs=45,
        skipped_docs=200,
        total_chunks=150,
        error=None,
        timestamp=datetime.now(),
        source_breakdown={
            "Work Drive": {"processed": 30, "skipped": 150},
            "Personal Notes": {"processed": 15, "skipped": 50}
        }
    )

    state.record_run(result)

    history = state.get_history(limit=1)
    assert len(history) == 1

    import json
    breakdown = json.loads(history[0]["source_breakdown"])
    assert breakdown["Work Drive"]["processed"] == 30
    assert breakdown["Personal Notes"]["skipped"] == 50
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/daemon/test_daemon_state.py::test_record_run_with_source_breakdown -v
```

Expected: FAIL (source_breakdown column doesn't exist)

**Step 3: Add source_breakdown column to run_history**

In `src/daemon/state.py`, modify `_init_db` to add column to run_history table:

```python
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
        source_breakdown TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
```

**Step 4: Update RunResult dataclass**

In `src/daemon/state.py`, update RunResult:

```python
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
    source_breakdown: Optional[Dict[str, Dict[str, int]]] = None
```

**Step 5: Update record_run to handle source_breakdown**

In `src/daemon/state.py`, modify `record_run`:

```python
def record_run(self, result: RunResult) -> None:
    """Record an ingestion run result.

    Args:
        result: Run result to record
    """
    import json

    source_breakdown_json = None
    if result.source_breakdown:
        source_breakdown_json = json.dumps(result.source_breakdown)

    with sqlite3.connect(self.db_path) as conn:
        conn.execute(
            """
            INSERT INTO run_history
            (timestamp, success, duration, processed_docs, skipped_docs, total_chunks, error, source_breakdown)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.timestamp.isoformat(),
                result.success,
                result.duration,
                result.processed_docs,
                result.skipped_docs,
                result.total_chunks,
                result.error,
                source_breakdown_json,
            )
        )
        conn.commit()

        # ... existing cleanup code ...
```

**Step 6: Run test to verify it passes**

```bash
pytest tests/unit/daemon/test_daemon_state.py::test_record_run_with_source_breakdown -v
```

Expected: PASS

**Step 7: Commit**

```bash
git add src/daemon/state.py tests/unit/daemon/test_daemon_state.py
git commit -m "feat: add source breakdown to run history"
```

---

## Phase 2: OAuth Integration

### Task 2.1: Create OAuth Endpoints Module

**Files:**
- Create: `src/daemon/oauth.py`
- Test: `tests/unit/daemon/test_oauth.py`

**Step 1: Write test for OAuth status check**

Create `tests/unit/daemon/test_oauth.py`:

```python
"""Tests for OAuth integration."""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
from src.daemon.oauth import OAuthManager


def test_oauth_status_not_authenticated(tmp_path):
    """Test OAuth status when not authenticated."""
    token_path = tmp_path / "token.json"
    creds_path = tmp_path / "credentials.json"

    manager = OAuthManager(
        credentials_path=creds_path,
        token_path=token_path
    )

    status = manager.get_status()
    assert status["authenticated"] is False
    assert status["email"] is None


def test_oauth_status_authenticated(tmp_path):
    """Test OAuth status when authenticated."""
    token_path = tmp_path / "token.json"
    creds_path = tmp_path / "credentials.json"

    # Create dummy token file
    import json
    token_path.write_text(json.dumps({
        "token": "test_token",
        "refresh_token": "test_refresh",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "test_id",
        "client_secret": "test_secret",
        "scopes": ["https://www.googleapis.com/auth/drive.readonly"]
    }))

    with patch("src.daemon.oauth.Credentials") as mock_creds:
        mock_cred_instance = MagicMock()
        mock_cred_instance.valid = True
        mock_creds.from_authorized_user_file.return_value = mock_cred_instance

        with patch("src.daemon.oauth.build") as mock_build:
            mock_service = MagicMock()
            mock_service.about().get().execute.return_value = {
                "user": {"emailAddress": "test@example.com"}
            }
            mock_build.return_value = mock_service

            manager = OAuthManager(
                credentials_path=creds_path,
                token_path=token_path
            )

            status = manager.get_status()
            assert status["authenticated"] is True
            assert status["email"] == "test@example.com"
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/daemon/test_oauth.py::test_oauth_status_not_authenticated -v
```

Expected: FAIL (module doesn't exist)

**Step 3: Create OAuthManager class**

Create `src/daemon/oauth.py`:

```python
"""OAuth management for Google Drive integration."""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


class OAuthManager:
    """Manages Google OAuth authentication."""

    def __init__(
        self,
        credentials_path: Path = Path("credentials.json"),
        token_path: Path = Path("token.json")
    ):
        """Initialize OAuth manager.

        Args:
            credentials_path: Path to OAuth client credentials
            token_path: Path to stored user token
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._creds: Optional[Credentials] = None

    def get_status(self) -> Dict[str, Any]:
        """Get current OAuth authentication status.

        Returns:
            Dictionary with authenticated (bool) and email (str or None)
        """
        try:
            if not self.token_path.exists():
                return {"authenticated": False, "email": None}

            creds = Credentials.from_authorized_user_file(
                str(self.token_path),
                SCOPES
            )

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    # Try to refresh
                    try:
                        creds.refresh(Request())
                        self._save_credentials(creds)
                    except Exception as e:
                        logger.warning(f"Failed to refresh token: {e}")
                        return {"authenticated": False, "email": None}
                else:
                    return {"authenticated": False, "email": None}

            # Get user email
            service = build('drive', 'v3', credentials=creds)
            about = service.about().get(fields='user').execute()
            email = about['user']['emailAddress']

            self._creds = creds
            return {"authenticated": True, "email": email}

        except Exception as e:
            logger.error(f"Error checking OAuth status: {e}")
            return {"authenticated": False, "email": None}

    def _save_credentials(self, creds: Credentials) -> None:
        """Save credentials to token file."""
        with open(self.token_path, 'w') as token:
            token.write(creds.to_json())

    def get_authorization_url(self) -> str:
        """Get OAuth authorization URL.

        Returns:
            Authorization URL for user to visit
        """
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Credentials file not found: {self.credentials_path}"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_path),
            SCOPES,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'
        )

        auth_url, _ = flow.authorization_url(prompt='consent')
        return auth_url

    def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for token.

        Args:
            code: Authorization code from user

        Returns:
            Status dictionary
        """
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path),
                SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )

            flow.fetch_token(code=code)
            creds = flow.credentials
            self._save_credentials(creds)

            return {"success": True, "email": self.get_status()["email"]}
        except Exception as e:
            logger.error(f"Failed to exchange code: {e}")
            return {"success": False, "error": str(e)}

    def disconnect(self) -> None:
        """Remove stored credentials."""
        if self.token_path.exists():
            self.token_path.unlink()
        self._creds = None
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/daemon/test_oauth.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/daemon/oauth.py tests/unit/daemon/test_oauth.py
git commit -m "feat: add OAuth manager for Google Drive"
```

---

### Task 2.2: Add OAuth API Endpoints

**Files:**
- Modify: `daemon_web.py`
- Test: Manual testing (OAuth flow requires browser)

**Step 1: Add OAuth manager to daemon_web.py**

At the top of `daemon_web.py`, add imports:

```python
from src.daemon.oauth import OAuthManager
from fastapi.responses import RedirectResponse, HTMLResponse
```

**Step 2: Initialize OAuth manager in init_app**

In `daemon_web.py`, modify `init_app` function:

```python
def init_app(state: DaemonState, scheduler: DaemonScheduler) -> FastAPI:
    """Initialize FastAPI app."""
    app = FastAPI(title="Personal RAG Daemon")

    # Initialize OAuth manager
    oauth_manager = OAuthManager()

    # ... existing code ...
```

**Step 3: Add OAuth status endpoint**

Add to `daemon_web.py` after existing endpoints:

```python
@app.get("/api/oauth/status")
async def oauth_status():
    """Get OAuth authentication status."""
    return oauth_manager.get_status()


@app.get("/api/oauth/authorize")
async def oauth_authorize():
    """Start OAuth flow."""
    try:
        auth_url = oauth_manager.get_authorization_url()
        # Return HTML page with instructions
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Google Drive Authorization</title></head>
        <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto;">
            <h2>Authorize Google Drive Access</h2>
            <p>Click the button below to authorize Personal RAG to access your Google Drive:</p>
            <p><a href="{auth_url}" target="_blank" style="display: inline-block; background: #4285f4; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px;">Authorize Google Drive</a></p>
            <p style="margin-top: 30px; color: #666;">After authorizing, copy the code and paste it below:</p>
            <form action="/api/oauth/callback" method="post" style="margin-top: 20px;">
                <input type="text" name="code" placeholder="Paste authorization code here" style="width: 100%; padding: 10px; font-size: 14px;" required>
                <button type="submit" style="margin-top: 10px; background: #34a853; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer;">Complete Authorization</button>
            </form>
        </body>
        </html>
        """
        return HTMLResponse(content=html_content)
    except FileNotFoundError as e:
        return {"error": str(e)}, 404


@app.post("/api/oauth/callback")
async def oauth_callback(code: str = Form(...)):
    """Handle OAuth callback."""
    result = oauth_manager.exchange_code(code)

    if result["success"]:
        # Redirect to dashboard with success message
        return RedirectResponse(url="/?oauth=success", status_code=303)
    else:
        return {"error": result.get("error")}, 400


@app.post("/api/oauth/disconnect")
async def oauth_disconnect():
    """Disconnect Google Drive."""
    oauth_manager.disconnect()
    return {"success": True}
```

**Step 4: Add Form import**

At top of `daemon_web.py`:

```python
from fastapi import Form
```

**Step 5: Test manually**

Start daemon and test OAuth flow:

```bash
python daemon.py
# Visit http://localhost:8001/api/oauth/authorize
```

**Step 6: Commit**

```bash
git add daemon_web.py
git commit -m "feat: add OAuth API endpoints to daemon web"
```

---

## Phase 3: Smart Multi-Source Runner

### Task 3.1: Create Source Model

**Files:**
- Create: `src/daemon/models.py`
- Test: `tests/unit/daemon/test_daemon_models.py`

**Step 1: Write test for Source model**

Create `tests/unit/daemon/test_daemon_models.py`:

```python
"""Tests for daemon models."""

from src.daemon.models import Source, SourceType


def test_source_from_dict_gdrive():
    """Test creating Google Drive source from dict."""
    data = {
        "id": 1,
        "name": "Work Drive",
        "source_type": "gdrive",
        "enabled": 1,
        "folder_id": "abc123",
        "ingestion_mode": "accessed",
        "days_back": 730,
        "local_path": None,
        "recursive": 1
    }

    source = Source.from_dict(data)

    assert source.id == 1
    assert source.name == "Work Drive"
    assert source.source_type == SourceType.GDRIVE
    assert source.enabled is True
    assert source.folder_id == "abc123"
    assert source.ingestion_mode == "accessed"
    assert source.days_back == 730


def test_source_from_dict_local():
    """Test creating local source from dict."""
    data = {
        "id": 2,
        "name": "Personal Notes",
        "source_type": "local",
        "enabled": 1,
        "folder_id": None,
        "ingestion_mode": "accessed",
        "days_back": 730,
        "local_path": "/Users/test/notes",
        "recursive": 1
    }

    source = Source.from_dict(data)

    assert source.id == 2
    assert source.name == "Personal Notes"
    assert source.source_type == SourceType.LOCAL
    assert source.local_path == "/Users/test/notes"
    assert source.recursive is True
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/daemon/test_daemon_models.py -v
```

Expected: FAIL (module doesn't exist)

**Step 3: Create Source model**

Create `src/daemon/models.py`:

```python
"""Data models for daemon."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any


class SourceType(str, Enum):
    """Source type enum."""
    GDRIVE = "gdrive"
    LOCAL = "local"


@dataclass
class Source:
    """Represents a configured ingestion source."""

    id: int
    name: str
    source_type: SourceType
    enabled: bool

    # Google Drive specific
    folder_id: Optional[str] = None
    ingestion_mode: str = "accessed"
    days_back: int = 730

    # Local specific
    local_path: Optional[str] = None
    recursive: bool = True

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Source":
        """Create Source from database dict.

        Args:
            data: Database row as dict

        Returns:
            Source instance
        """
        return cls(
            id=data["id"],
            name=data["name"],
            source_type=SourceType(data["source_type"]),
            enabled=bool(data["enabled"]),
            folder_id=data.get("folder_id"),
            ingestion_mode=data.get("ingestion_mode", "accessed"),
            days_back=data.get("days_back", 730),
            local_path=data.get("local_path"),
            recursive=bool(data.get("recursive", True))
        )
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/unit/daemon/test_daemon_models.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/daemon/models.py tests/unit/daemon/test_daemon_models.py
git commit -m "feat: add Source model for daemon"
```

---

### Task 3.2: Refactor IngestionRunner for Multi-Source

**Files:**
- Modify: `src/daemon/runner.py`
- Test: `tests/unit/daemon/test_daemon_runner.py`

**Step 1: Write test for multi-source ingestion**

Add to `tests/unit/daemon/test_daemon_runner.py`:

```python
def test_run_multi_source_ingestion(tmp_path, monkeypatch):
    """Test running ingestion with multiple sources."""
    from src.daemon.models import Source, SourceType
    from src.daemon.runner import MultiSourceIngestionRunner

    # Mock sources
    sources = [
        Source(
            id=1,
            name="Test Drive",
            source_type=SourceType.GDRIVE,
            enabled=True,
            folder_id=None,
            ingestion_mode="accessed",
            days_back=730
        ),
        Source(
            id=2,
            name="Test Local",
            source_type=SourceType.LOCAL,
            enabled=True,
            local_path=str(tmp_path / "docs"),
            recursive=True
        )
    ]

    # Create test directory
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "test.txt").write_text("Test content")

    # Mock ingestion pipeline
    class MockPipeline:
        def ingest_documents(self, docs):
            return len(docs), 0, len(docs) * 3

    monkeypatch.setattr(
        "src.daemon.runner.IngestionPipeline",
        lambda: MockPipeline()
    )

    runner = MultiSourceIngestionRunner(time_budget=60)
    result = runner.run_ingestion(sources)

    assert result.success is True
    assert result.source_breakdown is not None
    assert "Test Drive" in result.source_breakdown
    assert "Test Local" in result.source_breakdown
```

**Step 2: Run test to verify it fails**

```bash
pytest tests/unit/daemon/test_daemon_runner.py::test_run_multi_source_ingestion -v
```

Expected: FAIL (MultiSourceIngestionRunner doesn't exist)

**Step 3: Create MultiSourceIngestionRunner**

Modify `src/daemon/runner.py`:

```python
"""Multi-source ingestion runner with time limits."""

import logging
import time
from datetime import datetime
from typing import List, Dict, Any

from src.daemon.models import Source, SourceType
from src.daemon.state import RunResult
from src.ingestion import IngestionPipeline
from src.connectors.local import LocalConnector
from src.connectors.gdrive import GoogleDriveConnector
from src.models import Document

logger = logging.getLogger(__name__)

METADATA_BATCH_SIZE = 250  # Fetch 250 file metadata per API call
PROCESSING_BATCH_SIZE = 10  # Download + process 10 at a time


class MultiSourceIngestionRunner:
    """Runs ingestion across multiple sources with time limits."""

    def __init__(self, time_budget: int = 600):
        """Initialize runner.

        Args:
            time_budget: Total time budget in seconds (default: 10 minutes)
        """
        self.time_budget = time_budget

    def run_ingestion(self, sources: List[Source]) -> RunResult:
        """Run ingestion for all enabled sources.

        Args:
            sources: List of sources to process

        Returns:
            RunResult with aggregated stats
        """
        start_time = time.time()

        try:
            # Separate by type (Drive first, then local)
            gdrive_sources = [s for s in sources if s.source_type == SourceType.GDRIVE]
            local_sources = [s for s in sources if s.source_type == SourceType.LOCAL]
            all_sources = gdrive_sources + local_sources

            if not all_sources:
                return RunResult(
                    success=True,
                    duration=0,
                    processed_docs=0,
                    skipped_docs=0,
                    total_chunks=0,
                    error=None,
                    timestamp=datetime.now(),
                    source_breakdown={}
                )

            # Allocate time per source
            per_source_budget = self.time_budget / len(all_sources)

            # Initialize pipeline
            pipeline = IngestionPipeline()

            # Process each source
            total_processed = 0
            total_skipped = 0
            total_chunks = 0
            source_breakdown = {}

            for source in all_sources:
                if time.time() - start_time >= self.time_budget:
                    logger.warning("Time budget exhausted, stopping early")
                    break

                try:
                    stats = self._process_source(
                        source,
                        pipeline,
                        per_source_budget
                    )

                    total_processed += stats["processed"]
                    total_skipped += stats["skipped"]
                    total_chunks += stats["chunks"]
                    source_breakdown[source.name] = {
                        "processed": stats["processed"],
                        "skipped": stats["skipped"]
                    }

                    logger.info(
                        f"Source '{source.name}': {stats['processed']} processed, "
                        f"{stats['skipped']} skipped"
                    )

                except Exception as e:
                    logger.error(f"Error processing source '{source.name}': {e}")
                    source_breakdown[source.name] = {
                        "processed": 0,
                        "skipped": 0,
                        "error": str(e)
                    }

            duration = time.time() - start_time

            return RunResult(
                success=True,
                duration=duration,
                processed_docs=total_processed,
                skipped_docs=total_skipped,
                total_chunks=total_chunks,
                error=None,
                timestamp=datetime.now(),
                source_breakdown=source_breakdown
            )

        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            duration = time.time() - start_time

            return RunResult(
                success=False,
                duration=duration,
                processed_docs=0,
                skipped_docs=0,
                total_chunks=0,
                error=str(e),
                timestamp=datetime.now()
            )

    def _process_source(
        self,
        source: Source,
        pipeline: IngestionPipeline,
        time_budget: float
    ) -> Dict[str, int]:
        """Process a single source.

        Args:
            source: Source to process
            pipeline: Ingestion pipeline
            time_budget: Time budget for this source

        Returns:
            Stats dict with processed, skipped, chunks
        """
        start = time.time()
        processed = 0
        skipped = 0
        total_chunks = 0

        if source.source_type == SourceType.LOCAL:
            # Local source: simple recursive scan
            connector = LocalConnector(str(source.local_path))
            documents = connector.load_documents()

            # Process in batches
            for i in range(0, len(documents), PROCESSING_BATCH_SIZE):
                if time.time() - start >= time_budget:
                    break

                batch = documents[i:i + PROCESSING_BATCH_SIZE]
                proc, skip, chunks = pipeline.ingest_documents(batch)
                processed += proc
                skipped += skip
                total_chunks += chunks

        elif source.source_type == SourceType.GDRIVE:
            # Google Drive: two-phase processing
            connector = GoogleDriveConnector()

            # Phase 1: Fetch metadata in large batches (250 at a time)
            # Phase 2: Download + process in small batches (10 at a time)
            # TODO: Implement two-phase processing in next task

            processed, skipped, total_chunks = 0, 0, 0

        return {
            "processed": processed,
            "skipped": skipped,
            "chunks": total_chunks
        }


# Keep old IngestionRunner for backward compatibility
class IngestionRunner:
    """Legacy single-source runner (deprecated)."""

    def __init__(self, max_results: int = 100):
        self.max_results = max_results

    def run_ingestion(self) -> RunResult:
        """Run legacy ingestion."""
        # Delegate to multi-source runner with synthetic source
        from src.daemon.models import Source, SourceType

        source = Source(
            id=0,
            name="Google Drive (legacy)",
            source_type=SourceType.GDRIVE,
            enabled=True,
            folder_id=None,
            ingestion_mode="accessed",
            days_back=730
        )

        runner = MultiSourceIngestionRunner()
        return runner.run_ingestion([source])
```

**Step 4: Run test to verify it passes**

```bash
pytest tests/unit/daemon/test_daemon_runner.py::test_run_multi_source_ingestion -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add src/daemon/runner.py tests/unit/daemon/test_daemon_runner.py
git commit -m "feat: add multi-source ingestion runner"
```

---

## Phase 4: Web Dashboard UI

### Task 4.1: Add Sources Section to Dashboard

**Files:**
- Modify: `templates/dashboard.html`
- Modify: `daemon_web.py`

**Step 1: Add source management endpoints**

Add to `daemon_web.py` after OAuth endpoints:

```python
@app.get("/api/sources")
async def list_sources():
    """List all sources."""
    sources = state.get_sources()
    return {"sources": sources}


@app.post("/api/sources")
async def create_source(source: Dict[str, Any]):
    """Create a new source."""
    try:
        source_id = state.create_source(source)
        return {"success": True, "id": source_id}
    except Exception as e:
        logger.error(f"Failed to create source: {e}")
        return {"success": False, "error": str(e)}, 400


@app.get("/api/sources/{source_id}")
async def get_source(source_id: int):
    """Get a single source."""
    source = state.get_source(source_id)
    if source:
        return source
    return {"error": "Source not found"}, 404


@app.put("/api/sources/{source_id}")
async def update_source(source_id: int, data: Dict[str, Any]):
    """Update a source."""
    try:
        state.update_source(source_id, data)
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to update source: {e}")
        return {"success": False, "error": str(e)}, 400


@app.delete("/api/sources/{source_id}")
async def delete_source(source_id: int):
    """Delete a source."""
    try:
        state.delete_source(source_id)
        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to delete source: {e}")
        return {"success": False, "error": str(e)}, 400


@app.post("/api/sources/{source_id}/toggle")
async def toggle_source(source_id: int):
    """Toggle source enabled status."""
    source = state.get_source(source_id)
    if not source:
        return {"error": "Source not found"}, 404

    state.update_source(source_id, {"enabled": not source["enabled"]})
    return {"success": True, "enabled": not source["enabled"]}
```

**Step 2: Update dashboard template**

This is a large change. Add sources section to `templates/dashboard.html` after the header and before existing configuration section:

```html
<!-- OAuth Status -->
<div class="section" id="oauth-section">
    <div class="section-header">
        <h2>Google Drive Connection</h2>
    </div>
    <div class="section-content">
        <div id="oauth-status">Loading...</div>
    </div>
</div>

<!-- Sources Section -->
<div class="section" id="sources-section">
    <div class="section-header">
        <h2>Sources</h2>
        <button class="btn btn-primary" onclick="showAddSourceModal()">+ Add Source</button>
    </div>
    <div class="section-content">
        <div id="sources-list">Loading...</div>
    </div>
</div>

<!-- Add Source Modal -->
<div id="source-modal" class="modal">
    <div class="modal-content">
        <div class="modal-header">
            <h3 id="modal-title">Add Source</h3>
            <span class="close" onclick="closeSourceModal()">&times;</span>
        </div>
        <div class="modal-body">
            <form id="source-form">
                <input type="hidden" id="source-id">

                <div class="form-group">
                    <label for="source-name">Name</label>
                    <input type="text" id="source-name" required placeholder="e.g., Work Drive">
                </div>

                <div class="form-group">
                    <label>Type</label>
                    <div>
                        <input type="radio" id="type-gdrive" name="source-type" value="gdrive" checked>
                        <label for="type-gdrive">Google Drive</label>
                        <input type="radio" id="type-local" name="source-type" value="local">
                        <label for="type-local">Local Directory</label>
                    </div>
                </div>

                <div id="gdrive-settings" class="type-settings">
                    <div class="form-group">
                        <label for="folder-id">Folder ID (leave empty for all files)</label>
                        <input type="text" id="folder-id" placeholder="Optional">
                    </div>

                    <div class="form-group">
                        <label for="ingestion-mode">Mode</label>
                        <select id="ingestion-mode">
                            <option value="accessed">Recently Accessed</option>
                            <option value="drive">All Drive Files</option>
                        </select>
                    </div>

                    <div class="form-group">
                        <label for="days-back">Time Range (months)</label>
                        <input type="number" id="days-back" value="24" min="1">
                    </div>
                </div>

                <div id="local-settings" class="type-settings" style="display:none;">
                    <div class="form-group">
                        <label for="local-path">Directory Path</label>
                        <input type="text" id="local-path" placeholder="/Users/name/Documents">
                    </div>

                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="recursive" checked>
                            Scan subdirectories recursively
                        </label>
                    </div>
                </div>

                <div class="form-group">
                    <label>
                        <input type="checkbox" id="enabled" checked>
                        Enabled
                    </label>
                </div>

                <div class="modal-footer">
                    <button type="button" class="btn" onclick="closeSourceModal()">Cancel</button>
                    <button type="submit" class="btn btn-primary">Save</button>
                </div>
            </form>
        </div>
    </div>
</div>
```

**Step 3: Add JavaScript for source management**

Add to `templates/dashboard.html` in the `<script>` section:

```javascript
// OAuth Status
async function loadOAuthStatus() {
    const response = await fetch('/api/oauth/status');
    const data = await response.json();

    const statusDiv = document.getElementById('oauth-status');
    if (data.authenticated) {
        statusDiv.innerHTML = `
            <div style="color: #2d5;">
                ✓ Connected: ${data.email}
                <button class="btn" onclick="disconnectOAuth()" style="margin-left: 10px;">Disconnect</button>
            </div>
        `;
    } else {
        statusDiv.innerHTML = `
            <div style="color: #d52;">
                Not connected
                <a href="/api/oauth/authorize" class="btn btn-primary" style="margin-left: 10px;">Connect Google Drive</a>
            </div>
        `;
    }
}

async function disconnectOAuth() {
    if (confirm('Disconnect Google Drive? You will need to re-authorize.')) {
        await fetch('/api/oauth/disconnect', { method: 'POST' });
        loadOAuthStatus();
        loadSources();
    }
}

// Sources Management
async function loadSources() {
    const response = await fetch('/api/sources');
    const data = await response.json();

    const listDiv = document.getElementById('sources-list');

    if (data.sources.length === 0) {
        listDiv.innerHTML = '<p style="color: #666;">No sources configured. Click "Add Source" to get started.</p>';
        return;
    }

    listDiv.innerHTML = data.sources.map(source => `
        <div class="source-item" style="border: 1px solid #ddd; padding: 15px; margin-bottom: 10px; border-radius: 4px;">
            <div style="display: flex; justify-content: space-between; align-items: start;">
                <div>
                    <h4 style="margin: 0 0 5px 0;">
                        <input type="checkbox" ${source.enabled ? 'checked' : ''}
                               onchange="toggleSource(${source.id})"
                               style="margin-right: 8px;">
                        ${source.name}
                        <span style="color: #666; font-size: 0.9em;">(${source.source_type})</span>
                    </h4>
                    <div style="color: #666; font-size: 0.9em;">
                        ${getSourceSummary(source)}
                    </div>
                </div>
                <div>
                    <button class="btn" onclick="editSource(${source.id})">Edit</button>
                    <button class="btn" onclick="deleteSource(${source.id})" style="background: #d52; color: white;">Delete</button>
                </div>
            </div>
        </div>
    `).join('');
}

function getSourceSummary(source) {
    if (source.source_type === 'gdrive') {
        const mode = source.ingestion_mode === 'accessed' ? 'Recently accessed' : 'All files';
        const months = Math.round(source.days_back / 30);
        return `${mode}, last ${months} months${source.folder_id ? ', folder: ' + source.folder_id : ''}`;
    } else {
        return `${source.local_path}${source.recursive ? ', recursive' : ''}`;
    }
}

async function toggleSource(sourceId) {
    await fetch(`/api/sources/${sourceId}/toggle`, { method: 'POST' });
    loadSources();
}

async function deleteSource(sourceId) {
    if (confirm('Delete this source? This cannot be undone.')) {
        await fetch(`/api/sources/${sourceId}`, { method: 'DELETE' });
        loadSources();
    }
}

function showAddSourceModal() {
    document.getElementById('modal-title').textContent = 'Add Source';
    document.getElementById('source-form').reset();
    document.getElementById('source-id').value = '';
    document.getElementById('source-modal').style.display = 'block';
    updateTypeSettings();
}

async function editSource(sourceId) {
    const response = await fetch(`/api/sources/${sourceId}`);
    const source = await response.json();

    document.getElementById('modal-title').textContent = 'Edit Source';
    document.getElementById('source-id').value = source.id;
    document.getElementById('source-name').value = source.name;
    document.querySelector(`input[name="source-type"][value="${source.source_type}"]`).checked = true;
    document.getElementById('enabled').checked = source.enabled;

    if (source.source_type === 'gdrive') {
        document.getElementById('folder-id').value = source.folder_id || '';
        document.getElementById('ingestion-mode').value = source.ingestion_mode;
        document.getElementById('days-back').value = Math.round(source.days_back / 30);
    } else {
        document.getElementById('local-path').value = source.local_path || '';
        document.getElementById('recursive').checked = source.recursive;
    }

    updateTypeSettings();
    document.getElementById('source-modal').style.display = 'block';
}

function closeSourceModal() {
    document.getElementById('source-modal').style.display = 'none';
}

function updateTypeSettings() {
    const type = document.querySelector('input[name="source-type"]:checked').value;
    document.getElementById('gdrive-settings').style.display = type === 'gdrive' ? 'block' : 'none';
    document.getElementById('local-settings').style.display = type === 'local' ? 'block' : 'none';
}

document.querySelectorAll('input[name="source-type"]').forEach(radio => {
    radio.addEventListener('change', updateTypeSettings);
});

document.getElementById('source-form').addEventListener('submit', async (e) => {
    e.preventDefault();

    const sourceId = document.getElementById('source-id').value;
    const type = document.querySelector('input[name="source-type"]:checked').value;

    const data = {
        name: document.getElementById('source-name').value,
        source_type: type,
        enabled: document.getElementById('enabled').checked
    };

    if (type === 'gdrive') {
        data.folder_id = document.getElementById('folder-id').value || null;
        data.ingestion_mode = document.getElementById('ingestion-mode').value;
        data.days_back = parseInt(document.getElementById('days-back').value) * 30;
    } else {
        data.local_path = document.getElementById('local-path').value;
        data.recursive = document.getElementById('recursive').checked;
    }

    const url = sourceId ? `/api/sources/${sourceId}` : '/api/sources';
    const method = sourceId ? 'PUT' : 'POST';

    const response = await fetch(url, {
        method: method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    });

    if (response.ok) {
        closeSourceModal();
        loadSources();
    } else {
        const error = await response.json();
        alert('Error: ' + (error.error || 'Failed to save source'));
    }
});

// Initialize
loadOAuthStatus();
loadSources();
```

**Step 3: Add modal CSS**

Add to `templates/dashboard.html` in `<style>`:

```css
.modal {
    display: none;
    position: fixed;
    z-index: 1000;
    left: 0;
    top: 0;
    width: 100%;
    height: 100%;
    background-color: rgba(0,0,0,0.5);
}

.modal-content {
    background-color: #fff;
    margin: 50px auto;
    padding: 0;
    border-radius: 8px;
    width: 90%;
    max-width: 600px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
}

.modal-header {
    padding: 20px;
    border-bottom: 1px solid #eee;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-header h3 {
    margin: 0;
}

.modal-body {
    padding: 20px;
}

.modal-footer {
    padding: 15px 20px;
    border-top: 1px solid #eee;
    text-align: right;
}

.close {
    font-size: 28px;
    font-weight: bold;
    color: #aaa;
    cursor: pointer;
}

.close:hover {
    color: #000;
}

.form-group {
    margin-bottom: 15px;
}

.form-group label {
    display: block;
    margin-bottom: 5px;
    font-weight: 500;
}

.form-group input[type="text"],
.form-group input[type="number"],
.form-group select {
    width: 100%;
    padding: 8px;
    border: 1px solid #ddd;
    border-radius: 4px;
}

.type-settings {
    margin-top: 15px;
    padding: 15px;
    background: #f9f9f9;
    border-radius: 4px;
}
```

**Step 4: Test manually**

Start daemon and test source management:

```bash
python daemon.py
# Visit http://localhost:8001
```

**Step 5: Commit**

```bash
git add templates/dashboard.html daemon_web.py
git commit -m "feat: add sources management UI to dashboard"
```

---

## Phase 5: Integration & Migration

### Task 5.1: Update Scheduler to Use Multi-Source Runner

**Files:**
- Modify: `src/daemon/scheduler.py`
- Test: `tests/unit/daemon/test_daemon_scheduler.py`

**Step 1: Update scheduler to load and use sources**

Modify `src/daemon/scheduler.py`:

```python
from src.daemon.runner import MultiSourceIngestionRunner
from src.daemon.models import Source

# ... existing code ...

def _execute_ingestion(self) -> None:
    """Execute the ingestion run."""
    # Load enabled sources
    sources_data = self.state.get_sources(enabled_only=True)
    sources = [Source.from_dict(s) for s in sources_data]

    if not sources:
        logger.warning("No enabled sources configured")
        return

    # Run multi-source ingestion
    runner = MultiSourceIngestionRunner(time_budget=600)  # 10 minutes
    result = runner.run_ingestion(sources)

    # Record result
    self.state.record_run(result)

    # Handle result
    if result.success:
        logger.info(
            f"Ingestion successful: {result.processed_docs} processed, "
            f"{result.skipped_docs} skipped in {result.duration:.2f}s"
        )
        if result.source_breakdown:
            for source_name, stats in result.source_breakdown.items():
                logger.info(f"  {source_name}: {stats['processed']} processed, {stats['skipped']} skipped")
    else:
        logger.error(f"Ingestion failed: {result.error}")
        # Send notification on failure
        send_notification(
            "RAG Ingestion Failed",
            f"Error: {result.error[:100]}"
        )
```

**Step 2: Test manually**

```bash
# Start daemon
python daemon.py

# Add a test source via dashboard
# Trigger manual run
python daemon_cli.py trigger

# Check logs for multi-source execution
tail -f logs/daemon.log
```

**Step 3: Commit**

```bash
git add src/daemon/scheduler.py
git commit -m "feat: update scheduler to use multi-source runner"
```

---

### Task 5.2: Add Auto-Migration for Existing Users

**Files:**
- Modify: `daemon.py`
- Test: Manual testing

**Step 1: Add migration function**

Add to `daemon.py` after imports:

```python
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
```

**Step 2: Call migration in __init__**

Modify `PersonalRAGDaemon.__init__`:

```python
def __init__(self, db_path: Path, port: int = 8001) -> None:
    """Initialize daemon."""
    # ... existing initialization ...

    # Run migration
    migrate_to_multi_source(self.state)

    logger.info(f"Daemon initialized (db={db_path}, port={port})")
```

**Step 3: Test migration**

```bash
# Backup existing daemon.db
cp data/daemon.db data/daemon.db.backup

# Start daemon - should auto-migrate
python daemon.py

# Check that default source was created
python daemon_cli.py status
```

**Step 4: Commit**

```bash
git add daemon.py
git commit -m "feat: add auto-migration for existing daemon users"
```

---

## Phase 6: Documentation & Testing

### Task 6.1: Update Documentation

**Files:**
- Modify: `docs/DAEMON.md`
- Modify: `GETTING-STARTED.md`

**Step 1: Update DAEMON.md with multi-source instructions**

Add section to `docs/DAEMON.md` after Quick Start:

```markdown
## Managing Sources

Sources are configured locations where the daemon will fetch documents.

### Adding a Google Drive Source

1. **Connect Google Drive** (first time only):
   - Open dashboard: `http://localhost:8001`
   - Click "Connect Google Drive"
   - Authorize in browser
   - Copy and paste authorization code

2. **Add Source**:
   - Click "+ Add Source"
   - Enter name (e.g., "Work Documents")
   - Select "Google Drive"
   - Configure:
     - **Folder ID**: Leave empty for all files, or enter specific folder ID
     - **Mode**: Recently Accessed (recommended) or All Files
     - **Time Range**: 24 months (default)
   - Click "Save"

### Adding a Local Directory Source

1. **Add Source**:
   - Click "+ Add Source"
   - Enter name (e.g., "Personal Notes")
   - Select "Local Directory"
   - Configure:
     - **Path**: Absolute path to directory (e.g., `/Users/name/Documents/notes`)
     - **Recursive**: Check to include subdirectories
   - Click "Save"

### Managing Sources

- **Enable/Disable**: Click checkbox next to source name
- **Edit**: Click "Edit" button
- **Delete**: Click "Delete" button (requires confirmation)

### Source Priority

Google Drive sources are processed first, then local sources. Within each type, sources are processed in creation order.
```

**Step 2: Update GETTING-STARTED.md**

Update Step 6 in `GETTING-STARTED.md` to mention multi-source:

```markdown
### 6.4 Configure Sources

The daemon can watch multiple sources:

**Add Google Drive folder:**
1. Open `http://localhost:8001`
2. Connect Google Drive (if not already)
3. Click "+ Add Source"
4. Name it (e.g., "Work Drive")
5. Select Google Drive
6. Configure folder and time range
7. Save

**Add local directory:**
1. Click "+ Add Source"
2. Name it (e.g., "Personal Notes")
3. Select Local Directory
4. Enter path: `/Users/yourname/Documents/notes`
5. Save

The daemon will process all enabled sources each run, prioritizing Google Drive.
```

**Step 3: Commit**

```bash
git add docs/DAEMON.md GETTING-STARTED.md
git commit -m "docs: update for multi-source daemon configuration"
```

---

### Task 6.2: Run Full Test Suite

**Files:**
- All test files

**Step 1: Run all unit and integration tests**

```bash
source .venv/bin/activate
pytest tests/ --ignore=tests/e2e/ -v
```

Expected: All tests pass (67 passed, 1 skipped)

**Step 2: If any tests fail, fix them**

Address any failures related to the multi-source changes.

**Step 3: Run manual E2E test**

```bash
# Start daemon
python daemon.py

# Test full flow:
# 1. Connect OAuth
# 2. Add Google Drive source
# 3. Add local source
# 4. Trigger ingestion
# 5. Check run history shows per-source breakdown
```

**Step 4: Commit any test fixes**

```bash
git add tests/
git commit -m "test: fix tests for multi-source daemon"
```

---

## Final Steps

### Merge Checklist

Before creating PR, verify:

- [ ] All tests pass (`pytest tests/ --ignore=tests/e2e/`)
- [ ] OAuth flow works (manual test)
- [ ] Can add/edit/delete sources via dashboard
- [ ] Can add both Google Drive and local sources
- [ ] Daemon processes multiple sources
- [ ] Run history shows per-source breakdown
- [ ] Migration works for existing users
- [ ] Documentation updated

### Create Pull Request

After all tasks complete:

```bash
# Push branch
git push -u origin feature/multi-source-daemon

# Create PR
gh pr create --title "Multi-Source Daemon Configuration" --body "$(cat <<'EOF'
## Summary

Implements multi-source daemon configuration as designed in docs/plans/2025-11-01-multi-source-daemon-design.md.

### Changes

**Database & State:**
- New `sources` table for managing multiple named sources
- Source CRUD operations in DaemonState
- Per-source breakdown in run history

**OAuth Integration:**
- Global OAuth manager for Google Drive
- OAuth API endpoints (/api/oauth/*)
- Authorization flow in web dashboard

**Multi-Source Processing:**
- MultiSourceIngestionRunner with time-limited execution
- Two-phase batch processing (250 metadata, 10 download/process)
- ChromaDB-based deduplication

**Web Dashboard:**
- OAuth connection status
- Sources management UI with modal
- Add/edit/delete/toggle sources
- Per-source stats in run history

**Migration:**
- Auto-migration for existing users
- Backward compatible

### Testing

- 67 tests passing
- OAuth flow tested manually
- Multi-source ingestion tested manually

### Documentation

- Updated docs/DAEMON.md
- Updated GETTING-STARTED.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

**Plan complete!** This plan provides bite-sized, test-driven tasks for implementing the multi-source daemon configuration feature.
