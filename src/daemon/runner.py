"""Ingestion execution wrapper with monitoring."""

import time
import logging
from datetime import datetime
from typing import Optional

from src.daemon.state import RunResult
from src.ingestion import IngestionPipeline
from src.connectors.gdrive import GoogleDriveConnector

logger = logging.getLogger(__name__)


class IngestionRunner:
    """Wraps ingestion pipeline with monitoring and error handling."""

    def __init__(self, max_results: int = 100) -> None:
        """Initialize ingestion runner.

        Args:
            max_results: Maximum documents to fetch from Google Drive
        """
        self.max_results = max_results

    def run_ingestion(self) -> RunResult:
        """Execute ingestion with error handling.

        Returns:
            RunResult with execution details
        """
        start_time = time.time()
        timestamp = datetime.now()

        try:
            logger.info("Starting ingestion run")

            # Initialize components
            pipeline = IngestionPipeline()
            connector = GoogleDriveConnector()

            # Fetch documents
            documents = connector.fetch_documents(
                mode='accessed',
                max_results=self.max_results,
            )

            logger.info(f"Fetched {len(documents)} documents from Google Drive")

            # Run incremental ingestion
            stats = pipeline.ingest_documents_incremental(
                documents,
                skip_unchanged=True
            )

            duration = time.time() - start_time

            logger.info(
                f"Ingestion complete: {stats.total_documents} processed, "
                f"{stats.skipped_documents} skipped, {stats.total_chunks} chunks "
                f"in {duration:.2f}s"
            )

            return RunResult(
                success=True,
                duration=duration,
                processed_docs=stats.total_documents,
                skipped_docs=stats.skipped_documents,
                total_chunks=stats.total_chunks,
                error=None,
                timestamp=timestamp
            )

        except Exception as e:
            duration = time.time() - start_time
            error_msg = str(e)

            logger.exception("Ingestion failed")

            return RunResult(
                success=False,
                duration=duration,
                processed_docs=0,
                skipped_docs=0,
                total_chunks=0,
                error=error_msg,
                timestamp=timestamp
            )
