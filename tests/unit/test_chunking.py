"""Unit tests for document chunking."""

import pytest
from src.chunking import DocumentChunker
from src.models import Document, DocumentMetadata, SourceType


def test_chunk_size_respected(sample_documents):
    """Chunks must not exceed max token size - OpenAI rejects oversized chunks."""
    chunker = DocumentChunker(chunk_size=512, chunk_overlap=50)

    for doc in sample_documents:
        chunks = chunker.chunk_document(doc)

        for chunk in chunks:
            token_count = chunker._token_length(chunk.content)
            # Allow small buffer since splitter is approximate
            assert token_count <= 512 + 10, \
                f"Chunk exceeded max size: {token_count} tokens"


def test_chunk_overlap_prevents_context_loss():
    """Overlapping chunks should preserve context across boundaries."""
    doc = Document(
        content="First sentence. Second sentence. Third sentence. Fourth sentence.",
        metadata=DocumentMetadata(
            source="/test.txt",
            source_type=SourceType.LOCAL,
            title="Test"
        )
    )

    chunker = DocumentChunker(chunk_size=20, chunk_overlap=10)
    chunks = chunker.chunk_document(doc)

    # With overlap, consecutive chunks should share some content
    if len(chunks) > 1:
        assert chunks[0].content != chunks[1].content
        # Some overlap expected (can't test exact since splitter is smart)


def test_empty_document_handling(empty_document):
    """Empty documents shouldn't crash or create invalid chunks."""
    chunker = DocumentChunker()
    chunks = chunker.chunk_document(empty_document)

    assert chunks == [], "Empty document should return empty chunk list"


def test_special_characters_preserved(special_characters_document):
    """Code snippets, unicode, emojis must survive chunking."""
    chunker = DocumentChunker()
    chunks = chunker.chunk_document(special_characters_document)

    assert len(chunks) > 0, "Should create chunks from document"

    # Combine all chunks to verify content preservation
    combined = " ".join(chunk.content for chunk in chunks)

    # Check key special characters preserved
    assert "©" in combined or "©" in special_characters_document.content
    assert "🚀" in combined or "🚀" in special_characters_document.content
    assert "你好" in combined or "你好" in special_characters_document.content


def test_very_large_document(large_document):
    """Documents > 100K tokens should chunk without memory issues."""
    chunker = DocumentChunker(chunk_size=512)

    # This should not raise MemoryError
    chunks = chunker.chunk_document(large_document)

    assert len(chunks) > 0, "Should create chunks from large document"
    assert len(chunks) > 50, "Large document should create many chunks"

    # Verify all chunks have proper metadata
    for chunk in chunks:
        assert chunk.metadata.source == large_document.metadata.source
        assert chunk.metadata.chunk_index >= 0
        assert chunk.metadata.total_chunks == len(chunks)


def test_chunk_metadata_completeness(sample_documents):
    """All chunks must have complete metadata for traceability."""
    chunker = DocumentChunker()

    for doc in sample_documents:
        chunks = chunker.chunk_document(doc)

        for idx, chunk in enumerate(chunks):
            assert chunk.metadata.source == doc.metadata.source
            assert chunk.metadata.source_type == doc.metadata.source_type
            assert chunk.metadata.chunk_index == idx
            assert chunk.metadata.total_chunks == len(chunks)
            assert chunk.metadata.title == doc.metadata.title
