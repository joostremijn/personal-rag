# Multi-Source Daemon Configuration Design

**Date:** November 1, 2025
**Status:** Approved
**Author:** Design session with user

## Overview

Redesign the Personal RAG daemon to support multiple configurable sources (Google Drive folders, local directories) with user-friendly configuration, OAuth integration, and intelligent batch processing that eliminates arbitrary document limits.

## Goals

1. **Simple configuration**: 1-2 clicks after OAuth to add Google Drive source
2. **Multiple sources**: Users can configure multiple Google Drive folders and local directories with friendly names
3. **Smart processing**: Process all accessed documents (no max_results cap), most recent first
4. **Seamless OAuth**: Integrated Google Drive authentication in web dashboard
5. **Backward compatible**: Existing daemon users continue working without changes

## Non-Goals

- Per-source OAuth (multiple Google accounts)
- Custom schedules per source
- File type filtering per source
- Real-time sync (keep interval-based scheduling)

## Architecture Approach

**Hybrid: Simple Schema + Smart Runner**

- Lightweight database schema (sources table with basic config)
- Smart IngestionRunner uses two-phase processing:
  1. Fetch metadata in large batches (250 docs)
  2. Download + process in small batches (10 docs) for memory safety
- ChromaDB-based deduplication (skip already-indexed documents)
- Time-limited execution (default 10 minutes per run)

**Why this approach:**
- Simple database (no complex state tracking)
- Handles thousands of documents gracefully
- Memory-efficient processing
- Natural resume capability (next run picks up where left off)

## Database Schema

### New `sources` Table

```sql
CREATE TABLE sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,          -- "Work Drive", "Personal Notes"
    source_type TEXT NOT NULL,           -- "gdrive" or "local"
    enabled BOOLEAN DEFAULT 1,           -- On/off toggle

    -- Google Drive specific
    folder_id TEXT,                      -- NULL = root/all Drive
    ingestion_mode TEXT DEFAULT 'accessed',  -- 'accessed', 'drive', 'all'
    days_back INTEGER DEFAULT 730,       -- 24 months default

    -- Local directory specific
    local_path TEXT,                     -- Path to directory
    recursive BOOLEAN DEFAULT 1,         -- Scan subdirectories

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Design Decisions:**
- **Unique names**: Users refer to sources by friendly name ("Work Drive")
- **Type-specific fields**: `folder_id` for Drive, `local_path` for local (NULL for unused)
- **Sensible defaults**: 24 months, accessed mode, enabled by default
- **No state tracking**: Resume handled by smart runner, not database

### Enhanced `run_history` Table

```sql
-- Add new column (backward compatible)
ALTER TABLE run_history ADD COLUMN source_breakdown TEXT;
-- JSON format: {"Work Drive": {"processed": 30, "skipped": 180}}
```

**Existing tables unchanged:**
- `config` table: Keep for global settings (interval, run_mode)
- Existing `run_history` columns: Remain unchanged

## OAuth Integration

### Global OAuth Model

**One Google account for all Drive sources** (simpler than per-source auth).

**Token storage:**
- Keep existing `credentials.json` (project credentials)
- Keep existing `token.json` (user access/refresh tokens)
- Store at project root (current location)

### OAuth Flow in Web Dashboard

**First-time setup (no token.json):**
1. Dashboard shows prominent "Connect Google Drive" button
2. Click → `/api/oauth/authorize` → redirects to Google
3. User grants permissions → Google redirects to `/api/oauth/callback`
4. Backend saves `token.json`, redirects to dashboard with success message
5. Dashboard header shows "Connected: user@gmail.com"

**Adding Drive sources (authenticated):**
1. "Add Source" modal → select "Google Drive"
2. No auth needed - uses existing token
3. Configure folder, mode, time range
4. Save → source ready to use

**Token expiration:**
- Auto-refresh during ingestion using refresh_token
- If refresh fails → dashboard banner: "Reconnect Google Drive"
- Click → restart OAuth flow

### API Endpoints

```python
# OAuth management
GET  /api/oauth/status          # {authenticated: bool, email: str}
GET  /api/oauth/authorize       # Redirect to Google OAuth
GET  /api/oauth/callback        # Handle OAuth callback, save token
POST /api/oauth/disconnect      # Delete token.json
```

## Smart Runner & Processing Logic

### Two-Phase Batch Processing

**Phase 1: Metadata fetch (large batches)**
```python
METADATA_BATCH_SIZE = 250  # Fetch 250 file metadata per API call

# Lightweight API call (~12KB for 250 files)
metadata_batch = drive_api.list_files(
    pageSize=250,
    orderBy='viewedByMeTime desc',  # Most recent first
    fields='files(id, name, mimeType, modifiedTime, viewedByMeTime)'
)
```

**Phase 2: Download + process (small batches)**
```python
PROCESSING_BATCH_SIZE = 10  # Download + process 10 at a time

# Filter to only new documents
to_process = [f for f in metadata_batch if not already_indexed(f.id)]

# Process in batches of 10 for memory safety
for mini_batch in chunks(to_process, size=10):
    documents = [download_document(f) for f in mini_batch]
    process_and_index(documents)  # Chunk, embed, store
```

### Per-Run Execution

**High-level flow:**
```python
def run_ingestion():
    enabled_sources = load_enabled_sources()  # From sources table
    total_budget = 600  # 10 minutes default
    per_source_budget = total_budget / len(enabled_sources)

    results = {}

    # Process Google Drive sources first (primary focus)
    gdrive_sources = [s for s in enabled_sources if s.type == 'gdrive']
    local_sources = [s for s in enabled_sources if s.type == 'local']

    for source in gdrive_sources + local_sources:
        results[source.name] = process_source(source, per_source_budget)

    return results
```

**Per-source processing:**
```python
def process_source(source, time_budget):
    start = time.time()
    processed = 0
    skipped = 0
    page_token = None

    while time.time() - start < time_budget:
        # Phase 1: Fetch 250 metadata
        metadata_batch, page_token = fetch_metadata(source, page_token)
        if not metadata_batch:
            break

        # Filter already-indexed
        to_process = [f for f in metadata_batch if not already_indexed(f.id)]
        skipped += len(metadata_batch) - len(to_process)

        # Caught-up detection
        if len(to_process) == 0:
            logger.info(f"Caught up on {source.name}")
            break

        # Phase 2: Download + process in batches of 10
        for mini_batch in chunks(to_process, size=10):
            if time.time() - start > time_budget:
                break

            download_and_index(mini_batch)
            processed += len(mini_batch)

    return {"processed": processed, "skipped": skipped}
```

### Smart Deduplication

**Document ID generation:**
```python
def generate_doc_id(source_name: str, source_type: str, file_path: str) -> str:
    """Generate deterministic document ID."""
    return hashlib.sha256(
        f"{source_type}:{source_name}:{file_path}".encode()
    ).hexdigest()
```

**Already-indexed check:**
```python
def already_indexed(doc_id: str) -> bool:
    """Check if document already in ChromaDB."""
    results = chroma_collection.get(ids=[doc_id])
    return len(results['ids']) > 0
```

**Benefits:**
- No need to track "last processed" state in database
- Naturally resumes where left off
- Works across runs and daemon restarts
- Eliminates max_results cap (process until caught up or time expires)

### API Efficiency

**Google Drive API limits:**
- 10,000 queries per day per project
- Our usage: 250 files/call

**Example calculations:**
- 60-min interval: 24 runs/day × 4 API calls = 96 calls/day ✅
- 10-min interval: 144 runs/day × 4 API calls = 576 calls/day ✅
- Even with 5 sources: 576 × 5 = 2,880 calls/day ✅

**Memory usage:**
- Metadata for 250 files: ~12KB
- 10 full documents in processing: ~5-10MB (PDFs, docs)
- Total peak memory: <50MB per run

## Web Dashboard UI

### Header Section (New)

```
┌─────────────────────────────────────────────────┐
│ Personal RAG Daemon                              │
│ [Connected: user@gmail.com] [Disconnect]         │  ← OAuth status
└─────────────────────────────────────────────────┘
```

**OAuth states:**
- Not authenticated: Large "Connect Google Drive" button
- Authenticated: Shows email with small disconnect link
- Token expired: "Reconnect Google Drive" banner

### Sources Section (New)

```
┌─────────────────────────────────────────────────┐
│ SOURCES                        [+ Add Source]    │
├─────────────────────────────────────────────────┤
│ ✓ Work Drive (Google Drive)          [Edit] [🗑] │
│   └─ Last 24 months, accessed mode               │
│ ✓ Personal Notes (Local)             [Edit] [🗑] │
│   └─ ~/Documents/notes, recursive                │
│ ☐ Archive Drive (Google Drive)       [Edit] [🗑] │  ← disabled
│   └─ Folder: Archive, all files                  │
└─────────────────────────────────────────────────┘
```

**Features:**
- Checkbox: Enable/disable source (toggle immediately)
- Summary line: Shows key settings at a glance
- Edit: Opens modal with full config
- Delete: Removes source (with confirmation)

### Add/Edit Source Modal

```
┌─────────────────────────────────────────────────┐
│ Add Source                               [X]     │
├─────────────────────────────────────────────────┤
│ Name: [Work Drive________________]              │
│                                                  │
│ Type: (•) Google Drive  ( ) Local Directory     │
│                                                  │
│ ┌─ Google Drive Settings ─────────────────────┐ │
│ │ Folder: ( ) All files                        │ │
│ │         (•) Specific folder [Browse...]      │ │
│ │         Selected: /Work Documents            │ │
│ │                                               │ │
│ │ Mode: (•) Recently accessed                  │ │
│ │       ( ) All files in Drive                 │ │
│ │                                               │ │
│ │ Time range: [24] months                      │ │
│ └──────────────────────────────────────────────┘ │
│                                                  │
│ [Enabled] ☑                                     │
│                                    [Cancel] [Save]│
└─────────────────────────────────────────────────┘
```

**Form behavior:**
- Type radio: Shows/hides Google Drive vs Local settings
- Folder browse: Opens folder picker (uses Drive API)
- Validation: Name required, path required for local
- Google Drive disabled if not authenticated (shows tooltip)

### Enhanced Last Run Section

```
Last Run: 2 minutes ago (✓ Success)
Total: 45 processed, 234 skipped
Duration: 8m 34s

Source breakdown:
  • Work Drive: 30 processed, 180 skipped
  • Personal Notes: 15 processed, 54 skipped
```

**Shows:**
- Per-source stats (helps debug which sources are active)
- Total time (helps tune time budget)
- Success/failure per run (existing)

### First-Time User Experience

**No OAuth + no sources:**
```
┌─────────────────────────────────────────────────┐
│        Welcome to Personal RAG Daemon            │
│                                                  │
│  Get started by connecting your Google Drive     │
│                                                  │
│         [Connect Google Drive]                   │
│                                                  │
│  Or add a local directory:                       │
│         [Add Local Directory]                    │
└─────────────────────────────────────────────────┘
```

**After OAuth:**
```
┌─────────────────────────────────────────────────┐
│  Connected to Google Drive! ✓                    │
│                                                  │
│  Now add your first source:                      │
│         [Add Google Drive Source]                │
└─────────────────────────────────────────────────┘
```

## API Endpoints

### Source Management

```python
GET  /api/sources               # List all sources
POST /api/sources               # Create new source
GET  /api/sources/{id}          # Get source details
PUT  /api/sources/{id}          # Update source
DELETE /api/sources/{id}        # Delete source
POST /api/sources/{id}/toggle   # Enable/disable source
```

**Example payloads:**

```json
// POST /api/sources - Google Drive
{
  "name": "Work Drive",
  "source_type": "gdrive",
  "enabled": true,
  "folder_id": null,
  "ingestion_mode": "accessed",
  "days_back": 730
}

// POST /api/sources - Local
{
  "name": "Personal Notes",
  "source_type": "local",
  "enabled": true,
  "local_path": "/Users/joost/Documents/notes",
  "recursive": true
}
```

### Enhanced Existing Endpoints

```json
// GET /api/status (enhanced)
{
  "scheduler_state": "running",
  "interval": 60,
  "run_mode": "awake-only",
  "oauth_status": {
    "authenticated": true,
    "email": "user@gmail.com"
  },
  "sources": [
    {"id": 1, "name": "Work Drive", "enabled": true, "type": "gdrive"},
    {"id": 2, "name": "Personal Notes", "enabled": true, "type": "local"}
  ],
  "last_run": {
    "timestamp": "2025-11-01T09:02:56",
    "success": true,
    "duration": 514.2,
    "by_source": {
      "Work Drive": {"processed": 30, "skipped": 180},
      "Personal Notes": {"processed": 15, "skipped": 54}
    }
  }
}
```

## Migration & Backward Compatibility

### Auto-Migration on First Startup

```python
def migrate_to_multi_source():
    """Migrate existing single-source config to multi-source."""

    # Create sources table if doesn't exist
    if not table_exists('sources'):
        create_sources_table()

        # Check if user has existing daemon config
        if state.get_config("max_results"):
            # Auto-create default source
            create_source({
                "name": "Google Drive (auto-migrated)",
                "source_type": "gdrive",
                "enabled": True,
                "folder_id": None,
                "ingestion_mode": "accessed",
                "days_back": 730
            })
            logger.info("Migrated existing config to multi-source")
```

### Breaking Changes

**None!**

- All existing API endpoints work unchanged
- CLI commands work unchanged
- Database schema is additive (new table, no modifications)
- Existing `run_history` entries remain valid
- `max_results` config ignored (replaced by time limits)

### Default Behavior

**Existing users:**
- Auto-migrated to default Google Drive source
- Daemon continues running without interruption
- Can add more sources via new UI

**New users:**
- Empty sources list
- "Add your first source" prompt
- OAuth + create source in 2 clicks

## Implementation Phases

### Phase 1: Database & State (Foundation)
- Create `sources` table schema
- Add migration logic for existing users
- Update `DaemonState` with source CRUD methods
- Add tests for source management

### Phase 2: OAuth Integration
- Implement `/api/oauth/*` endpoints
- Add Google OAuth flow (authorize, callback, refresh)
- Update dashboard header with OAuth status
- Handle token expiration gracefully

### Phase 3: Smart Runner
- Refactor `IngestionRunner` for multi-source
- Implement two-phase batch processing (250 metadata, 10 processing)
- Add document ID deduplication via ChromaDB
- Implement time-limited execution per source

### Phase 4: Web Dashboard UI
- Add sources section to dashboard
- Create add/edit source modal
- Add OAuth connect/disconnect UI
- Enhance last run section with per-source stats

### Phase 5: Testing & Polish
- Add unit tests for all new components
- Add integration tests for multi-source ingestion
- Update documentation (DAEMON.md, GETTING-STARTED.md)
- Test migration from existing daemon setup

## Success Metrics

- ✅ New user can add Google Drive source in <3 clicks after OAuth
- ✅ Daemon handles 5+ sources without performance degradation
- ✅ Memory usage stays under 100MB during ingestion
- ✅ API calls stay under 3,000/day even with aggressive scheduling
- ✅ Existing daemon users continue working without manual intervention
- ✅ Caught-up detection works (stops when all sources fully indexed)

## Open Questions

- [ ] Should we show folder browser UI or just text input for folder_id?
- [ ] Default time budget: 10 minutes per run - tune based on real usage?
- [ ] Should we add source priority (process certain sources first)?

## Future Enhancements (Out of Scope)

- Per-source schedules (some sources check hourly, others daily)
- File type filters per source (only index PDFs from certain folders)
- Multi-account OAuth (different Google accounts per source)
- Real-time sync via webhooks (instead of polling)
- Folder tree browser UI for Drive
- Modified date tracking (re-index changed documents)
