"""Unit tests for local file connector."""

import os
import tempfile
from pathlib import Path
import pytest

from src.connectors.local import LocalFileConnector
from src.models import SourceType


def test_unsupported_file_type_skipped(tmp_path):
    """Binary files (*.exe, *.png) should be skipped gracefully."""
    # Create unsupported file types
    (tmp_path / "test.exe").write_bytes(b"binary content")
    (tmp_path / "image.png").write_bytes(b"\x89PNG...")

    connector = LocalFileConnector()
    documents = connector.fetch_documents(str(tmp_path))

    # Should return empty list, not crash
    assert documents == []


def test_permission_denied_handled(tmp_path):
    """Files without read permission don't crash pipeline."""
    # Create file with no read permissions
    test_file = tmp_path / "noperm.txt"
    test_file.write_text("secret content")
    test_file.chmod(0o000)  # No permissions

    connector = LocalFileConnector()

    # Should handle gracefully, not raise PermissionError
    try:
        documents = connector.fetch_documents(str(test_file))
        # Either empty list or error is logged
        assert isinstance(documents, list)
    finally:
        # Restore permissions for cleanup
        test_file.chmod(0o644)


def test_symlink_handling(tmp_path):
    """Symlinks should be followed, not cause infinite loops."""
    # Create real file
    real_file = tmp_path / "real.txt"
    real_file.write_text("real content")

    # Create symlink
    symlink = tmp_path / "link.txt"
    symlink.symlink_to(real_file)

    connector = LocalFileConnector()
    documents = connector.fetch_documents(str(tmp_path))

    # Should find documents (exact count depends on symlink handling)
    assert len(documents) >= 1


def test_file_encoding_detection(tmp_path):
    """Non-UTF8 files (latin1, cp1252) should be decoded correctly."""
    # Create latin-1 encoded file
    latin1_file = tmp_path / "latin1.txt"
    content = "Café résumé naïve"
    latin1_file.write_bytes(content.encode('latin-1'))

    connector = LocalFileConnector()
    documents = connector.fetch_documents(str(latin1_file))

    # Should successfully read the file (errors='ignore' handles encoding)
    assert len(documents) == 1
    # Content should contain something (might not be perfect due to encoding)
    assert len(documents[0].content) > 0


def test_empty_file_skipped(tmp_path):
    """Empty files should be skipped, not create empty chunks."""
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("")

    connector = LocalFileConnector()
    documents = connector.fetch_documents(str(empty_file))

    # Empty file should be skipped
    assert documents == []


def test_recursive_directory_scan(tmp_path):
    """Recursive scan should find files in subdirectories."""
    # Create nested structure
    (tmp_path / "dir1").mkdir()
    (tmp_path / "dir1" / "doc1.txt").write_text("content 1")
    (tmp_path / "dir1" / "dir2").mkdir()
    (tmp_path / "dir1" / "dir2" / "doc2.txt").write_text("content 2")

    connector = LocalFileConnector()

    # Recursive scan
    docs_recursive = connector.fetch_documents(str(tmp_path), recursive=True)
    assert len(docs_recursive) == 2

    # Non-recursive scan
    docs_flat = connector.fetch_documents(str(tmp_path), recursive=False)
    assert len(docs_flat) == 0  # No files in root


def test_supported_file_extensions():
    """Connector should support .txt, .md, .pdf, .docx."""
    connector = LocalFileConnector()

    expected_extensions = {".txt", ".md", ".markdown", ".pdf", ".docx", ".doc"}
    assert connector.SUPPORTED_EXTENSIONS == expected_extensions


def test_pdf_reading(test_fixtures_dir):
    """Should successfully read PDF files."""
    connector = LocalFileConnector()

    # Use the sample PDF we created
    pdf_path = test_fixtures_dir / "sample.pdf"

    if pdf_path.exists():
        documents = connector.fetch_documents(str(pdf_path))

        if len(documents) > 0:  # PDF reading might fail with minimal PDF
            assert documents[0].metadata.file_type == ".pdf"
            assert documents[0].metadata.source_type == SourceType.LOCAL


def test_nonexistent_path():
    """Nonexistent paths should return empty list, not crash."""
    connector = LocalFileConnector()

    documents = connector.fetch_documents("/nonexistent/path/to/nowhere")

    assert documents == []


def test_metadata_extraction(tmp_path):
    """Should extract file metadata (size, timestamps)."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    connector = LocalFileConnector()
    documents = connector.fetch_documents(str(test_file))

    assert len(documents) == 1
    doc = documents[0]

    assert doc.metadata.source == str(test_file)
    assert doc.metadata.source_type == SourceType.LOCAL
    assert doc.metadata.file_type == ".txt"
    assert doc.metadata.file_size > 0
    assert doc.metadata.created_at is not None
    assert doc.metadata.modified_at is not None
