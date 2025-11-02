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
