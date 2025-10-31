"""Unit tests for ingestion pipeline."""

from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import hashlib
import pytest

from src.ingestion import IngestionPipeline
from src.models import Document, DocumentMetadata, SourceType


def test_duplicate_document_generates_same_id(sample_documents):
    """Same document must produce same deterministic ID - prevents duplicates."""
    pipeline = IngestionPipeline()

    # Create chunks from same document twice
    from src.chunking import DocumentChunker
    chunker = DocumentChunker()

    chunks1 = chunker.chunk_document(sample_documents[0])
    chunks2 = chunker.chunk_document(sample_documents[0])

    # IDs should be identical
    id1 = pipeline._generate_chunk_id(chunks1[0])
    id2 = pipeline._generate_chunk_id(chunks2[0])

    assert id1 == id2, "Same document should generate same chunk ID"


def test_generate_chunk_id_format():
    """Chunk IDs should follow format: {source_hash}_{chunk_index}."""
    pipeline = IngestionPipeline()

    from src.models import DocumentChunk, ChunkMetadata
    source = "/path/to/doc.txt"
    chunk = DocumentChunk(
        content="test",
        metadata=ChunkMetadata(
            source=source,
            source_type=SourceType.LOCAL,
            chunk_index=5,
            total_chunks=10,
        )
    )

    chunk_id = pipeline._generate_chunk_id(chunk)

    # Should be {hash}_5
    expected_hash = hashlib.md5(source.encode()).hexdigest()[:8]
    expected_id = f"{expected_hash}_5"

    assert chunk_id == expected_id


def test_metadata_completeness_in_stored_chunks():
    """All required metadata fields must be present for filtering/display."""
    from src.models import ChunkMetadata

    metadata = ChunkMetadata(
        source="/test.txt",
        source_type=SourceType.LOCAL,
        chunk_index=0,
        total_chunks=1,
        title="Test",
    )

    dict_data = metadata.to_dict()

    # Required fields for UI/filtering
    assert "source" in dict_data
    assert "source_type" in dict_data
    assert "chunk_index" in dict_data
    assert "total_chunks" in dict_data
    assert dict_data["source_type"] == "local"


def test_batch_ingestion_partial_failure(sample_documents, empty_document, monkeypatch):
    """One bad file shouldn't kill entire batch."""
    # Create a document that will fail chunking
    bad_doc = Document(
        content="x" * 1000000,  # Very large
        metadata=DocumentMetadata(
            source="/bad.txt",
            source_type=SourceType.LOCAL,
        )
    )

    documents = sample_documents + [bad_doc]

    pipeline = IngestionPipeline()

    # Mock chunker to fail on bad_doc
    original_chunk = pipeline.chunker.chunk_document

    def mock_chunk_document(doc):
        if doc.metadata.source == "/bad.txt":
            raise Exception("Simulated chunking failure")
        return original_chunk(doc)

    monkeypatch.setattr(pipeline.chunker, "chunk_document", mock_chunk_document)

    # Should not raise, should continue processing
    stats = pipeline.ingest_documents(documents)

    # Some documents should succeed
    assert stats.total_documents >= 1
    assert stats.failed_documents >= 1
    assert "/bad.txt" in stats.failed_files


def test_chunking_preserves_source_info(sample_documents):
    """Every chunk must trace back to original document."""
    from src.chunking import DocumentChunker
    chunker = DocumentChunker()

    for doc in sample_documents:
        chunks = chunker.chunk_document(doc)

        for chunk in chunks:
            assert chunk.metadata.source == doc.metadata.source
            assert chunk.metadata.source_type == doc.metadata.source_type
            assert chunk.metadata.title == doc.metadata.title


def test_collection_stats():
    """get_collection_stats should return accurate statistics."""
    pipeline = IngestionPipeline()

    stats = pipeline.get_collection_stats()

    assert "collection_name" in stats
    assert "total_chunks" in stats
    assert "source_types" in stats
    assert "persist_path" in stats
    assert isinstance(stats["total_chunks"], int)
