"""Tests for ingestion runner."""

from unittest.mock import patch, MagicMock
from src.daemon.runner import IngestionRunner
from src.models import IngestionStats


@patch('src.daemon.runner.GoogleDriveConnector')
@patch('src.daemon.runner.IngestionPipeline')
def test_run_ingestion_success(mock_pipeline, mock_connector):
    """Test successful ingestion run."""
    # Mock connector
    mock_connector_instance = MagicMock()
    mock_connector.return_value = mock_connector_instance
    mock_connector_instance.fetch_documents.return_value = [MagicMock()]

    # Mock pipeline
    mock_pipeline_instance = MagicMock()
    mock_pipeline.return_value = mock_pipeline_instance
    mock_stats = IngestionStats(
        total_documents=5,
        total_chunks=10,
        skipped_documents=95,
        failed_documents=0,
        processing_time=2.5
    )
    mock_pipeline_instance.ingest_documents_incremental.return_value = mock_stats

    runner = IngestionRunner(max_results=100)
    result = runner.run_ingestion()

    assert result.success is True
    assert result.processed_docs == 5
    assert result.skipped_docs == 95
    assert result.total_chunks == 10
    assert result.error is None


@patch('src.daemon.runner.GoogleDriveConnector')
def test_run_ingestion_failure(mock_connector):
    """Test ingestion run with error."""
    # Mock connector to raise exception
    mock_connector.return_value.fetch_documents.side_effect = Exception("Network error")

    runner = IngestionRunner(max_results=100)
    result = runner.run_ingestion()

    assert result.success is False
    assert result.error is not None
    assert "Network error" in result.error
