"""Ingestion pipeline for processing and storing documents."""

import logging
import time
import uuid
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

    def ingest_documents(self, documents: List[Document]) -> IngestionStats:
        """Ingest documents into the vector database.

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

        # Add to collection in batches
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch_end = min(i + batch_size, len(chunks))

            self.collection.add(
                ids=ids[i:batch_end],
                documents=documents[i:batch_end],
                embeddings=embeddings[i:batch_end],
                metadatas=metadatas[i:batch_end],
            )

            logger.debug(f"Stored batch {i // batch_size + 1} ({batch_end - i} chunks)")

    def _generate_chunk_id(self, chunk: DocumentChunk) -> str:
        """Generate unique ID for a chunk.

        Args:
            chunk: Document chunk

        Returns:
            Unique ID string
        """
        # Use source + chunk index for reproducibility
        source_hash = str(hash(chunk.metadata.source))[-8:]
        return f"{source_hash}_{chunk.metadata.chunk_index}_{uuid.uuid4().hex[:8]}"

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
