"""Integration tests for ingestion pipeline with real ChromaDB."""

from unittest.mock import patch
import pytest

from src.ingestion import IngestionPipeline
from src.models import Document, DocumentMetadata, SourceType


def test_local_file_ingestion_workflow(sample_documents, mock_openai_embeddings):
    """End-to-end: documents -> chunks -> embeddings -> ChromaDB."""
    import uuid
    collection_name = f"test_workflow_{uuid.uuid4().hex[:8]}"

    with patch("src.embeddings.OpenAIEmbeddings", return_value=mock_openai_embeddings):
        pipeline = IngestionPipeline(collection_name=collection_name, reset_collection=True)

        # Ingest documents
        stats = pipeline.ingest_documents(sample_documents)

        assert stats.total_documents == len(sample_documents)
        assert stats.total_chunks > 0
        assert stats.failed_documents == 0

        # Verify stored in ChromaDB using pipeline's collection
        count = pipeline.collection.count()
        assert count == stats.total_chunks

        # Cleanup
        pipeline.clear_collection()


def test_incremental_ingestion_skips_existing(sample_documents, mock_openai_embeddings):
    """Re-ingesting same documents should skip unchanged files."""
    import uuid
    collection_name = f"test_incremental_{uuid.uuid4().hex[:8]}"

    with patch("src.embeddings.OpenAIEmbeddings", return_value=mock_openai_embeddings):
        pipeline = IngestionPipeline(collection_name=collection_name, reset_collection=True)

        # First ingestion
        stats1 = pipeline.ingest_documents_incremental(sample_documents, skip_unchanged=False)
        assert stats1.total_documents == len(sample_documents)

        # Second ingestion with skip_unchanged=True
        stats2 = pipeline.ingest_documents_incremental(sample_documents, skip_unchanged=True)
        assert stats2.skipped_documents == len(sample_documents)
        assert stats2.total_documents == 0

        # Cleanup
        pipeline.clear_collection()


def test_metadata_queryable_in_chromadb(sample_documents, mock_openai_embeddings):
    """Metadata filters should work in ChromaDB queries."""
    import uuid
    collection_name = f"test_metadata_{uuid.uuid4().hex[:8]}"

    with patch("src.embeddings.OpenAIEmbeddings", return_value=mock_openai_embeddings):
        pipeline = IngestionPipeline(collection_name=collection_name, reset_collection=True)
        pipeline.ingest_documents(sample_documents)

        # Query with metadata filter using pipeline's collection
        results = pipeline.collection.get(
            where={"source_type": "local"},
            limit=10,
        )

        assert len(results["ids"]) > 0

        # All results should have source_type=local
        for metadata in results["metadatas"]:
            assert metadata["source_type"] == "local"

        # Cleanup
        pipeline.clear_collection()


def test_collection_reset_clears_data(sample_documents, mock_openai_embeddings):
    """reset_collection=True should clear existing data."""
    collection_name = "test_reset_collection"

    with patch("src.embeddings.OpenAIEmbeddings", return_value=mock_openai_embeddings):
        # First ingestion
        pipeline1 = IngestionPipeline(collection_name=collection_name)
        stats1 = pipeline1.ingest_documents(sample_documents)
        initial_count = pipeline1.collection.count()

        # Reset and re-ingest
        pipeline2 = IngestionPipeline(collection_name=collection_name, reset_collection=True)
        assert pipeline2.collection.count() == 0, "Collection should be empty after reset"

        # Clean up
        pipeline2.clear_collection()


def test_batch_processing(sample_documents, mock_openai_embeddings):
    """Large batches should be processed in chunks."""
    import uuid
    collection_name = f"test_batch_{uuid.uuid4().hex[:8]}"

    # Create distinct documents to avoid duplicate IDs
    import copy
    from datetime import datetime, timezone
    distinct_docs = []
    for i in range(10):
        doc = copy.deepcopy(sample_documents[0])
        doc.metadata.source = f"/test_doc_{i}.txt"  # Unique source for unique ID
        distinct_docs.append(doc)

    with patch("src.embeddings.OpenAIEmbeddings", return_value=mock_openai_embeddings):
        pipeline = IngestionPipeline(collection_name=collection_name, reset_collection=True)

        stats = pipeline.ingest_documents_incremental(distinct_docs, batch_size=3)

        # Should process all documents
        assert stats.total_documents == len(distinct_docs)
        assert stats.total_chunks > 0

        # Cleanup
        pipeline.clear_collection()
