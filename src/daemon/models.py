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
