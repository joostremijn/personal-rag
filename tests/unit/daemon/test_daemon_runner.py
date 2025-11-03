"""Tests for ingestion runner."""

from unittest.mock import patch, MagicMock
from src.daemon.runner import IngestionRunner
from src.models import IngestionStats
from src.daemon.models import Source, SourceType


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


@patch('src.daemon.runner.GoogleDriveConnector')
@patch('src.daemon.runner.IngestionPipeline')
def test_run_multi_source_ingestion(mock_pipeline, mock_connector, tmp_path):
    """Test running ingestion with multiple sources."""
    from src.daemon.runner import MultiSourceIngestionRunner

    # Mock sources
    sources = [
        Source(
            id=1,
            name="Test Drive",
            source_type=SourceType.GDRIVE,
            enabled=True,
            folder_id=None,
            ingestion_mode="accessed",
            days_back=730
        ),
        Source(
            id=2,
            name="Test Local",
            source_type=SourceType.LOCAL,
            enabled=True,
            local_path=str(tmp_path / "docs"),
            recursive=True
        )
    ]

    # Create test directory
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "test.txt").write_text("Test content")

    # Mock Google Drive connector
    mock_connector_instance = MagicMock()
    mock_connector.return_value = mock_connector_instance
    mock_connector_instance.fetch_documents.return_value = [MagicMock(), MagicMock()]

    # Mock ingestion pipeline
    mock_pipeline_instance = MagicMock()
    mock_pipeline.return_value = mock_pipeline_instance

    # Return different stats for each call
    mock_pipeline_instance.ingest_documents_incremental.return_value = IngestionStats(
        total_documents=2,
        total_chunks=6,
        skipped_documents=0,
        failed_documents=0,
        processing_time=0.1
    )
    mock_pipeline_instance.ingest_documents.return_value = (1, 0, 3)

    runner = MultiSourceIngestionRunner(time_budget=60)
    result = runner.run_ingestion(sources)

    assert result.success is True
    assert result.source_breakdown is not None
    assert "Test Drive" in result.source_breakdown
    assert "Test Local" in result.source_breakdown


@patch('src.daemon.runner.GoogleDriveConnector')
@patch('src.daemon.runner.IngestionPipeline')
def test_multi_source_runner_processes_gdrive_documents(mock_pipeline, mock_connector):
    """Test that MultiSourceIngestionRunner actually fetches and processes Google Drive documents."""
    from src.daemon.runner import MultiSourceIngestionRunner

    # Create Google Drive source
    source = Source(
        id=1,
        name="My Drive",
        source_type=SourceType.GDRIVE,
        enabled=True,
        folder_id=None,
        ingestion_mode="accessed",
        days_back=730
    )

    # Mock connector to return file metadata, then documents
    mock_connector_instance = MagicMock()
    mock_connector.return_value = mock_connector_instance

    # fetch_documents returns file metadata
    mock_files = [
        {"id": "file1", "name": "doc1.txt", "modifiedTime": "2024-01-01T00:00:00Z"},
        {"id": "file2", "name": "doc2.txt", "modifiedTime": "2024-01-01T00:00:00Z"},
        {"id": "file3", "name": "doc3.txt", "modifiedTime": "2024-01-01T00:00:00Z"},
    ]
    mock_connector_instance.fetch_documents.return_value = mock_files

    # download_file_batch returns documents matching the input batch size
    def download_batch_side_effect(files):
        return [MagicMock() for _ in files]
    mock_connector_instance.download_file_batch.side_effect = download_batch_side_effect

    # Mock pipeline to process them
    mock_pipeline_instance = MagicMock()
    mock_pipeline.return_value = mock_pipeline_instance
    mock_stats = IngestionStats(
        total_documents=3,
        total_chunks=9,
        skipped_documents=0,
        failed_documents=0,
        processing_time=1.0
    )
    mock_pipeline_instance.ingest_documents_incremental.return_value = mock_stats

    # Run ingestion
    runner = MultiSourceIngestionRunner(time_budget=60)
    result = runner.run_ingestion([source])

    # Verify fetch_documents was called with correct parameters including skip callback
    call_args = mock_connector_instance.fetch_documents.call_args
    assert call_args[1]['mode'] == 'accessed'
    assert call_args[1]['max_results'] is None  # No limit
    assert call_args[1]['folder_id'] is None
    assert call_args[1]['days_back'] == 730
    assert 'should_skip_callback' in call_args[1]  # Should pass skip callback

    # Verify documents were processed
    mock_pipeline_instance.ingest_documents_incremental.assert_called_once()

    # Verify results
    assert result.success is True
    assert result.processed_docs == 3
    assert result.total_chunks == 9
    assert result.source_breakdown["My Drive"]["processed"] == 3
    assert result.source_breakdown["My Drive"]["chunks"] == 9


@patch('src.daemon.runner.GoogleDriveConnector')
@patch('src.daemon.runner.IngestionPipeline')
def test_multi_source_runner_reports_progress(mock_pipeline, mock_connector):
    """Test that runner reports progress updates to state during ingestion."""
    from src.daemon.runner import MultiSourceIngestionRunner

    # Create mock state
    mock_state = MagicMock()

    # Create Google Drive source
    source = Source(
        id=1,
        name="Work Drive",
        source_type=SourceType.GDRIVE,
        enabled=True,
        folder_id=None,
        ingestion_mode="accessed",
        days_back=730
    )

    # Mock connector
    mock_connector_instance = MagicMock()
    mock_connector.return_value = mock_connector_instance

    # fetch_documents now returns file metadata (dicts), not documents
    mock_files = [{"id": f"file{i}", "name": f"doc{i}.txt", "modifiedTime": "2024-01-01T00:00:00Z"}
                  for i in range(100)]
    mock_connector_instance.fetch_documents.return_value = mock_files

    # download_file_batch returns documents matching the input batch size
    def download_batch_side_effect(files):
        return [MagicMock() for _ in files]
    mock_connector_instance.download_file_batch.side_effect = download_batch_side_effect

    # Mock pipeline - return stats per batch (10 files per batch)
    mock_pipeline_instance = MagicMock()
    mock_pipeline.return_value = mock_pipeline_instance

    # Return stats for each batch call (5 docs per 10-file batch)
    def pipeline_side_effect(docs, skip_unchanged=True):
        num_docs = len(docs)
        return IngestionStats(
            total_documents=num_docs // 2,  # Half processed
            total_chunks=(num_docs // 2) * 3,  # 3 chunks each
            skipped_documents=num_docs // 2,  # Half skipped
            failed_documents=0,
            processing_time=0.1
        )
    mock_pipeline_instance.ingest_documents_incremental.side_effect = pipeline_side_effect

    # Run ingestion with state
    runner = MultiSourceIngestionRunner(time_budget=60, state=mock_state)
    result = runner.run_ingestion([source])

    # Verify progress updates were called
    assert mock_state.set_active_run.call_count >= 3

    # Check that progress messages include expected info
    calls = [call[0][0] for call in mock_state.set_active_run.call_args_list]

    # Should show fetching metadata phase
    assert any("Fetching metadata from Work Drive" in call for call in calls)

    # Should show downloading/processing progress
    assert any("Downloading Work Drive" in call for call in calls) or \
           any("Processing Work Drive" in call for call in calls)

    # Should show completion with stats
    assert any("Completed Work Drive" in call for call in calls)
    assert any("50 processed" in call for call in calls)
