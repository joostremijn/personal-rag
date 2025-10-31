"""Unit tests for Pydantic models."""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from src.models import (
    Document,
    DocumentMetadata,
    DocumentChunk,
    ChunkMetadata,
    SourceType,
)


def test_document_requires_content_and_metadata():
    """Document model should enforce required fields."""
    # Missing content should raise ValidationError
    with pytest.raises(ValidationError):
        Document(metadata=DocumentMetadata(source="/test", source_type=SourceType.LOCAL))

    # Missing metadata should raise ValidationError
    with pytest.raises(ValidationError):
        Document(content="test content")


def test_chunk_metadata_to_dict_excludes_none():
    """ChromaDB doesn't accept None values - to_dict should exclude them."""
    metadata = ChunkMetadata(
        source="/test.txt",
        source_type=SourceType.LOCAL,
        chunk_index=0,
        total_chunks=1,
        title=None,  # This should be excluded
        author=None,  # This should be excluded
    )

    dict_data = metadata.to_dict()

    assert "title" not in dict_data
    assert "author" not in dict_data
    assert "source" in dict_data
    assert "source_type" in dict_data


def test_chunk_metadata_datetime_serialization():
    """Datetime objects must serialize to ISO format strings for ChromaDB."""
    now = datetime(2025, 10, 31, 12, 0, 0, tzinfo=timezone.utc)

    metadata = ChunkMetadata(
        source="/test.txt",
        source_type=SourceType.LOCAL,
        chunk_index=0,
        total_chunks=1,
        created_at=now,
        modified_at=now,
        ingested_at=now,
    )

    dict_data = metadata.to_dict()

    # Should be ISO format strings, not datetime objects
    assert isinstance(dict_data["created_at"], str)
    assert isinstance(dict_data["modified_at"], str)
    assert isinstance(dict_data["ingested_at"], str)
    assert dict_data["created_at"] == now.isoformat()


def test_chunk_metadata_from_dict_deserializes_datetime():
    """from_dict should convert ISO strings back to datetime objects."""
    dict_data = {
        "source": "/test.txt",
        "source_type": "local",
        "chunk_index": 0,
        "total_chunks": 1,
        "created_at": "2025-10-31T12:00:00+00:00",
        "modified_at": "2025-10-31T13:00:00+00:00",
        "ingested_at": "2025-10-31T14:00:00+00:00",
    }

    metadata = ChunkMetadata.from_dict(dict_data)

    assert isinstance(metadata.created_at, datetime)
    assert isinstance(metadata.modified_at, datetime)
    assert isinstance(metadata.ingested_at, datetime)


def test_source_type_enum_validation():
    """SourceType should only accept valid enum values."""
    # Valid source type
    metadata = DocumentMetadata(
        source="/test",
        source_type=SourceType.LOCAL
    )
    assert metadata.source_type == SourceType.LOCAL

    # Invalid source type should raise ValidationError
    with pytest.raises(ValidationError):
        DocumentMetadata(
            source="/test",
            source_type="invalid_type"
        )


def test_document_chunk_id_generation():
    """Chunk IDs should be deterministic and unique per source+index."""
    chunk1 = DocumentChunk(
        content="content",
        metadata=ChunkMetadata(
            source="/doc1.txt",
            source_type=SourceType.LOCAL,
            chunk_index=0,
            total_chunks=2,
        )
    )

    chunk2 = DocumentChunk(
        content="content",
        metadata=ChunkMetadata(
            source="/doc1.txt",
            source_type=SourceType.LOCAL,
            chunk_index=1,
            total_chunks=2,
        )
    )

    # Different indices should produce different IDs
    assert chunk1.chunk_id != chunk2.chunk_id

    # Same source and index should produce same ID
    chunk1_copy = DocumentChunk(
        content="different content",  # Content doesn't matter
        metadata=chunk1.metadata,
    )
    assert chunk1.chunk_id == chunk1_copy.chunk_id
