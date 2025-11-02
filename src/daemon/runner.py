"""Multi-source ingestion runner with time limits."""

import logging
import time
from datetime import datetime
from typing import List, Dict, Any

from src.daemon.models import Source, SourceType
from src.daemon.state import RunResult
from src.ingestion import IngestionPipeline
from src.connectors.local import LocalFileConnector
from src.connectors.gdrive import GoogleDriveConnector
from src.models import Document

logger = logging.getLogger(__name__)

METADATA_BATCH_SIZE = 250  # Fetch 250 file metadata per API call
PROCESSING_BATCH_SIZE = 10  # Download + process 10 at a time


class MultiSourceIngestionRunner:
    """Runs ingestion across multiple sources with time limits."""

    def __init__(self, time_budget: int = 600):
        """Initialize runner.

        Args:
            time_budget: Total time budget in seconds (default: 10 minutes)
        """
        self.time_budget = time_budget

    def run_ingestion(self, sources: List[Source]) -> RunResult:
        """Run ingestion for all enabled sources.

        Args:
            sources: List of sources to process

        Returns:
            RunResult with aggregated stats
        """
        start_time = time.time()

        try:
            # Separate by type (Drive first, then local)
            gdrive_sources = [s for s in sources if s.source_type == SourceType.GDRIVE]
            local_sources = [s for s in sources if s.source_type == SourceType.LOCAL]
            all_sources = gdrive_sources + local_sources

            if not all_sources:
                return RunResult(
                    success=True,
                    duration=0,
                    processed_docs=0,
                    skipped_docs=0,
                    total_chunks=0,
                    error=None,
                    timestamp=datetime.now(),
                    source_breakdown={}
                )

            # Allocate time per source
            per_source_budget = self.time_budget / len(all_sources)

            # Initialize pipeline
            pipeline = IngestionPipeline()

            # Process each source
            total_processed = 0
            total_skipped = 0
            total_chunks = 0
            source_breakdown = {}

            for source in all_sources:
                if time.time() - start_time >= self.time_budget:
                    logger.warning("Time budget exhausted, stopping early")
                    break

                try:
                    stats = self._process_source(
                        source,
                        pipeline,
                        per_source_budget
                    )

                    total_processed += stats["processed"]
                    total_skipped += stats["skipped"]
                    total_chunks += stats["chunks"]
                    source_breakdown[source.name] = {
                        "processed": stats["processed"],
                        "skipped": stats["skipped"]
                    }

                    logger.info(
                        f"Source '{source.name}': {stats['processed']} processed, "
                        f"{stats['skipped']} skipped"
                    )

                except Exception as e:
                    logger.error(f"Error processing source '{source.name}': {e}")
                    source_breakdown[source.name] = {
                        "processed": 0,
                        "skipped": 0,
                        "error": str(e)
                    }

            duration = time.time() - start_time

            return RunResult(
                success=True,
                duration=duration,
                processed_docs=total_processed,
                skipped_docs=total_skipped,
                total_chunks=total_chunks,
                error=None,
                timestamp=datetime.now(),
                source_breakdown=source_breakdown
            )

        except Exception as e:
            logger.error(f"Ingestion failed: {e}")
            duration = time.time() - start_time

            return RunResult(
                success=False,
                duration=duration,
                processed_docs=0,
                skipped_docs=0,
                total_chunks=0,
                error=str(e),
                timestamp=datetime.now()
            )

    def _process_source(
        self,
        source: Source,
        pipeline: IngestionPipeline,
        time_budget: float
    ) -> Dict[str, int]:
        """Process a single source.

        Args:
            source: Source to process
            pipeline: Ingestion pipeline
            time_budget: Time budget for this source

        Returns:
            Stats dict with processed, skipped, chunks
        """
        start = time.time()
        processed = 0
        skipped = 0
        total_chunks = 0

        if source.source_type == SourceType.LOCAL:
            # Local source: simple recursive scan
            connector = LocalFileConnector(str(source.local_path))
            documents = connector.load_documents()

            # Process in batches
            for i in range(0, len(documents), PROCESSING_BATCH_SIZE):
                if time.time() - start >= time_budget:
                    break

                batch = documents[i:i + PROCESSING_BATCH_SIZE]
                proc, skip, chunks = pipeline.ingest_documents(batch)
                processed += proc
                skipped += skip
                total_chunks += chunks

        elif source.source_type == SourceType.GDRIVE:
            # Google Drive: two-phase processing
            connector = GoogleDriveConnector()

            # Phase 1: Fetch metadata in large batches (250 at a time)
            # Phase 2: Download + process in small batches (10 at a time)
            # TODO: Implement two-phase processing in next task

            processed, skipped, total_chunks = 0, 0, 0

        return {
            "processed": processed,
            "skipped": skipped,
            "chunks": total_chunks
        }


# Keep old IngestionRunner for backward compatibility
class IngestionRunner:
    """Legacy single-source runner (deprecated)."""

    def __init__(self, max_results: int = 100):
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
