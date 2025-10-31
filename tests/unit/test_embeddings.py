"""Unit tests for embeddings service."""

from unittest.mock import patch, MagicMock
import pytest

from src.embeddings import EmbeddingService
from src.models import DocumentChunk, ChunkMetadata, SourceType


def test_embedding_dimension_consistency(mock_openai_embeddings, sample_chunks):
    """All embeddings must have same dimensions (1536 for text-embedding-3-small)."""
    with patch("src.embeddings.OpenAIEmbeddings", return_value=mock_openai_embeddings):
        service = EmbeddingService()
        embedded_chunks = service.embed_chunks(sample_chunks)

        # All embeddings should be 1536 dimensions
        for chunk in embedded_chunks:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == 1536, \
                f"Expected 1536 dimensions, got {len(chunk.embedding)}"


def test_batch_embedding_handles_empty_list(mock_openai_embeddings):
    """Empty chunk list should return empty list without API call."""
    with patch("src.embeddings.OpenAIEmbeddings", return_value=mock_openai_embeddings):
        service = EmbeddingService()
        result = service.embed_chunks([])

        assert result == []
        # Verify no API call was made
        mock_openai_embeddings.embed_documents.assert_not_called()


def test_empty_text_embedding(mock_openai_embeddings):
    """Empty strings should be handled gracefully."""
    empty_chunk = DocumentChunk(
        content="",
        metadata=ChunkMetadata(
            source="/test.txt",
            source_type=SourceType.LOCAL,
            chunk_index=0,
            total_chunks=1,
        )
    )

    with patch("src.embeddings.OpenAIEmbeddings", return_value=mock_openai_embeddings):
        service = EmbeddingService()

        # Should handle empty content without crashing
        result = service.embed_chunks([empty_chunk])
        assert len(result) == 1
        assert result[0].embedding is not None


def test_embed_texts_returns_correct_count(mock_openai_embeddings):
    """embed_texts should return same number of embeddings as inputs."""
    texts = ["text 1", "text 2", "text 3"]

    with patch("src.embeddings.OpenAIEmbeddings", return_value=mock_openai_embeddings):
        service = EmbeddingService()
        embeddings = service.embed_texts(texts)

        assert len(embeddings) == len(texts)
        for embedding in embeddings:
            assert len(embedding) == 1536


def test_embed_query_single_text(mock_openai_embeddings):
    """embed_query should return single embedding vector."""
    text = "What is machine learning?"

    with patch("src.embeddings.OpenAIEmbeddings", return_value=mock_openai_embeddings):
        service = EmbeddingService()
        embedding = service.embed_text(text)

        assert isinstance(embedding, list)
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)


def test_embeddings_are_deterministic(mock_openai_embeddings):
    """Same text should produce same embedding (with our mock)."""
    text = "consistent text"
    chunk = DocumentChunk(
        content=text,
        metadata=ChunkMetadata(
            source="/test.txt",
            source_type=SourceType.LOCAL,
            chunk_index=0,
            total_chunks=1,
        )
    )

    with patch("src.embeddings.OpenAIEmbeddings", return_value=mock_openai_embeddings):
        service = EmbeddingService()

        result1 = service.embed_chunks([chunk])
        result2 = service.embed_chunks([chunk])

        assert result1[0].embedding == result2[0].embedding, \
            "Same text should produce same embedding"
