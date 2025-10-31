"""Shared pytest fixtures for test suite."""

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from unittest.mock import Mock, MagicMock

import pytest
import chromadb
from chromadb.config import Settings as ChromaSettings

from src.models import Document, DocumentMetadata, DocumentChunk, ChunkMetadata, SourceType


@pytest.fixture(scope="session")
def test_fixtures_dir() -> Path:
    """Get path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def test_chroma_collection():
    """Create isolated ChromaDB collection for tests with automatic cleanup.

    Yields:
        Tuple of (client, collection_name) for test use
    """
    collection_name = f"test_{uuid.uuid4().hex[:8]}"
    client = chromadb.Client(Settings=ChromaSettings(anonymized_telemetry=False))
    collection = client.create_collection(name=collection_name)

    yield client, collection_name

    # Cleanup
    try:
        client.delete_collection(name=collection_name)
    except Exception:
        pass  # Collection might already be deleted


@pytest.fixture
def mock_openai_embeddings():
    """Mock OpenAI embeddings API - returns deterministic fake vectors.

    Returns:
        Mock object with embed_query and embed_documents methods
    """
    mock = MagicMock()

    # embed_query returns single 1536-dim vector
    def fake_embed_query(text: str) -> List[float]:
        # Deterministic vector based on text hash for reproducibility
        hash_val = hash(text) % 1000
        return [float(hash_val) / 1000.0] * 1536

    # embed_documents returns list of vectors
    def fake_embed_documents(texts: List[str]) -> List[List[float]]:
        return [fake_embed_query(text) for text in texts]

    mock.embed_query.side_effect = fake_embed_query
    mock.embed_documents.side_effect = fake_embed_documents

    return mock


@pytest.fixture
def mock_openai_chat():
    """Mock OpenAI chat completion API.

    Returns:
        Mock that returns predictable chat responses
    """
    mock = MagicMock()
    mock.invoke.return_value.content = "This is a mocked answer based on the provided context."
    return mock


@pytest.fixture
def mock_gdrive_service():
    """Mock Google Drive API service.

    Returns:
        Mock Drive API service with files().list() support
    """
    mock = MagicMock()

    # Mock files().list() for listing files
    files_list_mock = MagicMock()
    files_list_mock.execute.return_value = {
        "files": [
            {
                "id": "file1",
                "name": "Test Doc 1.txt",
                "mimeType": "text/plain",
                "modifiedTime": "2025-10-30T10:00:00Z",
                "size": "1024",
                "webViewLink": "https://drive.google.com/file/d/file1/view",
            },
            {
                "id": "file2",
                "name": "Test Doc 2.pdf",
                "mimeType": "application/pdf",
                "modifiedTime": "2025-10-29T15:30:00Z",
                "size": "2048",
                "webViewLink": "https://drive.google.com/file/d/file2/view",
            },
        ]
    }

    mock.files.return_value.list.return_value = files_list_mock

    return mock


@pytest.fixture
def sample_documents(test_fixtures_dir: Path) -> List[Document]:
    """Load test fixture documents.

    Returns:
        List of Document objects from test fixtures
    """
    doc1 = Document(
        content="This is a test document about Python programming. "
                "Python is a versatile language used for data science, web development, and automation.",
        metadata=DocumentMetadata(
            source=str(test_fixtures_dir / "test_doc1.txt"),
            source_type=SourceType.LOCAL,
            title="Test Document 1",
            created_at=datetime(2025, 10, 1, tzinfo=timezone.utc),
            modified_at=datetime(2025, 10, 15, tzinfo=timezone.utc),
            file_type=".txt",
            file_size=100,
        )
    )

    doc2 = Document(
        content="Machine learning is a subset of artificial intelligence. "
                "It involves training models on data to make predictions.",
        metadata=DocumentMetadata(
            source=str(test_fixtures_dir / "test_doc2.md"),
            source_type=SourceType.LOCAL,
            title="Test Document 2",
            created_at=datetime(2025, 10, 10, tzinfo=timezone.utc),
            modified_at=datetime(2025, 10, 20, tzinfo=timezone.utc),
            file_type=".md",
            file_size=150,
        )
    )

    return [doc1, doc2]


@pytest.fixture
def sample_chunks(sample_documents: List[Document]) -> List[DocumentChunk]:
    """Pre-chunked test data.

    Returns:
        List of DocumentChunk objects ready for embedding
    """
    chunks = []

    for doc in sample_documents:
        chunk_metadata = ChunkMetadata(
            source=doc.metadata.source,
            source_type=doc.metadata.source_type,
            chunk_index=0,
            total_chunks=1,
            title=doc.metadata.title,
            created_at=doc.metadata.created_at,
            modified_at=doc.metadata.modified_at,
            file_type=doc.metadata.file_type,
        )

        chunk = DocumentChunk(
            content=doc.content,
            metadata=chunk_metadata,
        )
        chunks.append(chunk)

    return chunks


@pytest.fixture
def empty_document() -> Document:
    """Create an empty document for edge case testing."""
    return Document(
        content="",
        metadata=DocumentMetadata(
            source="/path/to/empty.txt",
            source_type=SourceType.LOCAL,
            title="Empty Document",
        )
    )


@pytest.fixture
def large_document() -> Document:
    """Create a very large document (>100K tokens) for memory testing."""
    # Generate ~100K token document (400K characters)
    content = "This is a test sentence. " * 16000

    return Document(
        content=content,
        metadata=DocumentMetadata(
            source="/path/to/large.txt",
            source_type=SourceType.LOCAL,
            title="Large Document",
            file_size=len(content),
        )
    )


@pytest.fixture
def special_characters_document() -> Document:
    """Document with special characters, unicode, code snippets."""
    content = """
# Code Example

```python
def hello(name: str) -> str:
    return f"Hello, {name}!"
```

Special chars: © ® ™ € £ ¥
Unicode: 你好 مرحبا привет
Emoji: 🚀 🎉 ✨
"""

    return Document(
        content=content,
        metadata=DocumentMetadata(
            source="/path/to/special.md",
            source_type=SourceType.LOCAL,
            title="Special Characters",
        )
    )
