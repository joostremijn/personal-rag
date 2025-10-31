"""Ingestion pipeline for processing and storing documents."""

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from src.chunking import DocumentChunker
from src.config import get_settings
from src.embeddings import EmbeddingService
from src.models import Document, DocumentChunk, IngestionStats

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Pipeline for ingesting documents into the vector database."""

    def __init__(
        self,
        collection_name: Optional[str] = None,
        reset_collection: bool = False,
    ) -> None:
        """Initialize the ingestion pipeline.

        Args:
            collection_name: Name of ChromaDB collection (default from config)
            reset_collection: If True, delete and recreate collection
        """
        self.settings = get_settings()
        self.collection_name = collection_name or self.settings.chroma_collection_name

        # Initialize components
        self.chunker = DocumentChunker()
        self.embedding_service = EmbeddingService()

        # Initialize ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=str(self.settings.chroma_persist_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # Get or create collection
        if reset_collection:
            try:
                self.chroma_client.delete_collection(name=self.collection_name)
                logger.info(f"Deleted existing collection: {self.collection_name}")
            except Exception:
                pass  # Collection might not exist

        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Personal RAG documents"},
        )

        logger.info(
            f"Initialized ingestion pipeline with collection: {self.collection_name} "
            f"({self.collection.count()} existing documents)"
        )

    def should_skip_document(self, doc: Document) -> bool:
        """Check if document should be skipped based on existing index.

        Args:
            doc: Document to check

        Returns:
            True if document should be skipped, False if it needs (re)indexing
        """
        return self._should_skip(doc.metadata.source, doc.metadata.modified_at, doc.metadata.title)

    def should_skip_by_metadata(self, source: str, modified_at: Optional[datetime], title: str) -> bool:
        """Check if document should be skipped based only on metadata (no content needed).

        This is useful for deciding whether to download content from remote sources.

        Args:
            source: Document source identifier
            modified_at: Document modification timestamp
            title: Document title (for logging)

        Returns:
            True if document should be skipped, False if it needs (re)indexing
        """
        return self._should_skip(source, modified_at, title)

    def _should_skip(self, source: str, modified_at: Optional[datetime], title: str) -> bool:
        """Internal method to check if document should be skipped.

        Args:
            source: Document source identifier
            modified_at: Document modification timestamp
            title: Document title (for logging)

        Returns:
            True if document should be skipped, False if it needs (re)indexing
        """
        # Query for existing chunks from this source
        try:
            source_hash = hashlib.md5(source.encode()).hexdigest()[:8]
            # Query for any chunk from this source (we just need one to check timestamp)
            results = self.collection.get(
                ids=[f"{source_hash}_0"],  # Check first chunk
                include=["metadatas"]
            )

            if not results or not results["ids"]:
                # Document not in index yet
                logger.debug(f"Document not indexed yet: {title}")
                return False

            # Get the ingested_at timestamp
            metadata = results["metadatas"][0]
            if "ingested_at" not in metadata:
                # Old chunk without timestamp, re-index
                logger.debug(f"Document has no timestamp, re-indexing: {title}")
                return False

            ingested_at = datetime.fromisoformat(metadata["ingested_at"])

            # Make ingested_at timezone-aware if it isn't already (for comparison)
            if ingested_at.tzinfo is None:
                ingested_at = ingested_at.replace(tzinfo=timezone.utc)

            # Check if document was modified after last ingestion
            if modified_at:
                # Make modified_at timezone-aware if needed
                if modified_at.tzinfo is None:
                    modified_at = modified_at.replace(tzinfo=timezone.utc)

                if modified_at > ingested_at:
                    logger.info(f"Document modified since last index, will re-index: {title}")
                    return False

            # Document exists and hasn't been modified, skip it
            logger.info(f"Skipping unchanged document: {title}")
            return True

        except Exception as e:
            logger.warning(f"Error checking document status for {source}: {e}")
            # On error, be safe and re-index
            return False

    def ingest_documents_incremental(
        self,
        documents: List[Document],
        skip_unchanged: bool = True,
        batch_size: int = 10,
    ) -> IngestionStats:
        """Ingest documents incrementally with progress reporting.

        Processes documents in batches, shows progress, and optionally skips
        unchanged documents based on modification time.

        Args:
            documents: List of documents to ingest
            skip_unchanged: Skip documents that haven't been modified since last index
            batch_size: Number of documents to process before storing batch

        Returns:
            Ingestion statistics
        """
        start_time = time.time()
        stats = IngestionStats()

        if not documents:
            logger.warning("No documents to ingest")
            return stats

        total_docs = len(documents)
        logger.info(f"Starting incremental ingestion of {total_docs} documents (batch_size={batch_size})")

        batch_chunks: List[DocumentChunk] = []
        processed = 0

        for i, doc in enumerate(documents, 1):
            try:
                # Check if we should skip this document
                if skip_unchanged and self.should_skip_document(doc):
                    stats.skipped_documents += 1
                    continue

                # Show progress
                logger.info(f"Processing {i}/{total_docs}: {doc.metadata.title}")

                # Chunk document
                chunks = self.chunker.chunk_document(doc)
                if chunks:
                    batch_chunks.extend(chunks)
                    stats.total_documents += 1
                    processed += 1
                else:
                    stats.failed_documents += 1
                    stats.failed_files.append(doc.metadata.source)
                    logger.warning(f"No chunks created for: {doc.metadata.title}")

                # Process batch when full or at end
                if len(batch_chunks) >= batch_size * 5 or i == total_docs:  # ~5 chunks per doc avg
                    if batch_chunks:
                        self._process_and_store_batch(batch_chunks, stats)
                        logger.info(f"Progress: {processed} processed, {stats.skipped_documents} skipped, {stats.failed_documents} failed")
                        batch_chunks = []

            except Exception as e:
                logger.error(f"Error processing document {doc.metadata.source}: {e}")
                stats.failed_documents += 1
                stats.failed_files.append(doc.metadata.source)

        # Process any remaining chunks
        if batch_chunks:
            self._process_and_store_batch(batch_chunks, stats)

        stats.processing_time = time.time() - start_time

        logger.info(
            f"Ingestion complete: {stats.total_documents} processed, {stats.skipped_documents} skipped, "
            f"{stats.total_chunks} chunks in {stats.processing_time:.2f}s"
        )

        if stats.failed_documents > 0:
            logger.warning(f"Failed to process {stats.failed_documents} documents")

        return stats

    def _process_and_store_batch(self, chunks: List[DocumentChunk], stats: IngestionStats) -> None:
        """Process and store a batch of chunks.

        Args:
            chunks: List of chunks to process
            stats: Stats object to update
        """
        try:
            # Generate embeddings
            embedded_chunks = self.embedding_service.embed_chunks(chunks)
            # Store in ChromaDB
            self._store_chunks(embedded_chunks)
            stats.total_chunks += len(embedded_chunks)
            logger.debug(f"Stored batch of {len(embedded_chunks)} chunks")
        except Exception as e:
            logger.error(f"Error processing batch: {e}")
            raise

    def ingest_documents(self, documents: List[Document]) -> IngestionStats:
        """Ingest documents into the vector database (legacy batch method).

        Args:
            documents: List of documents to ingest

        Returns:
            Ingestion statistics
        """
        start_time = time.time()
        stats = IngestionStats()

        if not documents:
            logger.warning("No documents to ingest")
            return stats

        logger.info(f"Starting ingestion of {len(documents)} documents")

        # Process documents
        all_chunks: List[DocumentChunk] = []
        for doc in documents:
            try:
                chunks = self.chunker.chunk_document(doc)
                if chunks:
                    all_chunks.extend(chunks)
                    stats.total_documents += 1
                else:
                    stats.failed_documents += 1
                    stats.failed_files.append(doc.metadata.source)
            except Exception as e:
                logger.error(f"Error processing document {doc.metadata.source}: {e}")
                stats.failed_documents += 1
                stats.failed_files.append(doc.metadata.source)

        if not all_chunks:
            logger.warning("No chunks created from documents")
            stats.processing_time = time.time() - start_time
            return stats

        logger.info(f"Created {len(all_chunks)} chunks from {stats.total_documents} documents")

        # Generate embeddings
        try:
            all_chunks = self.embedding_service.embed_chunks(all_chunks)
            stats.total_chunks = len(all_chunks)
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            stats.processing_time = time.time() - start_time
            return stats

        # Store in ChromaDB
        try:
            self._store_chunks(all_chunks)
            logger.info(f"Stored {len(all_chunks)} chunks in ChromaDB")
        except Exception as e:
            logger.error(f"Error storing chunks in ChromaDB: {e}")
            stats.processing_time = time.time() - start_time
            return stats

        stats.processing_time = time.time() - start_time

        logger.info(
            f"Ingestion complete: {stats.total_documents} documents, "
            f"{stats.total_chunks} chunks in {stats.processing_time:.2f}s"
        )

        if stats.failed_documents > 0:
            logger.warning(f"Failed to process {stats.failed_documents} documents")

        return stats

    def _store_chunks(self, chunks: List[DocumentChunk]) -> None:
        """Store chunks in ChromaDB.

        Args:
            chunks: List of chunks with embeddings
        """
        if not chunks:
            return

        # Prepare data for ChromaDB
        ids = [self._generate_chunk_id(chunk) for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        embeddings = [chunk.embedding for chunk in chunks]
        metadatas = [chunk.metadata.to_dict() for chunk in chunks]

        # Upsert to collection in batches (updates existing, adds new)
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch_end = min(i + batch_size, len(chunks))

            self.collection.upsert(
                ids=ids[i:batch_end],
                documents=documents[i:batch_end],
                embeddings=embeddings[i:batch_end],
                metadatas=metadatas[i:batch_end],
            )

            logger.debug(f"Upserted batch {i // batch_size + 1} ({batch_end - i} chunks)")

    def _generate_chunk_id(self, chunk: DocumentChunk) -> str:
        """Generate deterministic ID for a chunk.

        Args:
            chunk: Document chunk

        Returns:
            Deterministic ID string based on source and chunk index
        """
        # Use source + chunk index for deterministic, reproducible IDs
        # This allows upsert to update existing chunks instead of duplicating
        # Use hashlib instead of hash() for deterministic hashing across runs
        source_hash = hashlib.md5(chunk.metadata.source.encode()).hexdigest()[:8]
        return f"{source_hash}_{chunk.metadata.chunk_index}"

    def get_collection_stats(self) -> dict:
        """Get statistics about the collection.

        Returns:
            Dictionary with collection statistics
        """
        count = self.collection.count()

        # Sample some metadata to get source types
        sample_result = self.collection.get(limit=min(100, count), include=["metadatas"])
        source_types = {}

        if sample_result and "metadatas" in sample_result:
            for metadata in sample_result["metadatas"]:
                source_type = metadata.get("source_type", "unknown")
                source_types[source_type] = source_types.get(source_type, 0) + 1

        return {
            "collection_name": self.collection_name,
            "total_chunks": count,
            "source_types": source_types,
            "persist_path": str(self.settings.chroma_persist_path),
        }

    def clear_collection(self) -> None:
        """Clear all documents from the collection."""
        try:
            self.chroma_client.delete_collection(name=self.collection_name)
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"description": "Personal RAG documents"},
            )
            logger.info(f"Cleared collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Error clearing collection: {e}")
