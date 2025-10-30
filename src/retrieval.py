"""Retrieval system for querying vector database."""

import logging
from typing import List, Optional

import chromadb
from chromadb.config import Settings

from src.config import get_settings
from src.embeddings import EmbeddingService
from src.models import ChunkMetadata, QueryRequest, RetrievalResult, SourceType

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for retrieving relevant documents from vector database."""

    def __init__(self, collection_name: Optional[str] = None) -> None:
        """Initialize retrieval service.

        Args:
            collection_name: Name of ChromaDB collection (default from config)
        """
        self.settings = get_settings()
        self.collection_name = collection_name or self.settings.chroma_collection_name
        self.embedding_service = EmbeddingService()

        # Initialize ChromaDB client
        self.client = chromadb.PersistentClient(
            path=str(self.settings.chroma_persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )

        # Get or create collection
        self.collection = self.client.get_collection(name=self.collection_name)
        logger.info(f"Connected to ChromaDB collection: {self.collection_name}")

    def query(
        self,
        query_text: str,
        top_k: Optional[int] = None,
        source_type_filter: Optional[List[SourceType]] = None,
        min_score: float = 0.0,
    ) -> List[RetrievalResult]:
        """Query the vector database for relevant chunks.

        Args:
            query_text: Natural language query
            top_k: Number of results to return (default from config)
            source_type_filter: Optional list of source types to filter by
            min_score: Minimum similarity score (0-1, higher is more similar)

        Returns:
            List of retrieval results sorted by relevance
        """
        if not query_text or not query_text.strip():
            logger.warning("Empty query text provided")
            return []

        # Use config default if not specified
        if top_k is None:
            top_k = self.settings.top_k

        logger.info(f"Querying for: '{query_text}' (top_k={top_k})")

        try:
            # Generate embedding for query
            query_embedding = self.embedding_service.embed_text(query_text)

            # Build where filter for source types
            where_filter = None
            if source_type_filter:
                source_values = [st.value for st in source_type_filter]
                if len(source_values) == 1:
                    where_filter = {"source_type": source_values[0]}
                else:
                    # ChromaDB "in" operator for multiple values
                    where_filter = {"source_type": {"$in": source_values}}
                logger.debug(f"Applying source type filter: {where_filter}")

            # Query ChromaDB
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_filter,
                include=["documents", "metadatas", "distances"],
            )

            # Parse results
            retrieval_results = []
            if results["ids"] and len(results["ids"][0]) > 0:
                for i in range(len(results["ids"][0])):
                    # ChromaDB returns distances (lower = more similar)
                    # For squared L2 distance, typical range is [0, 4]
                    # Convert to similarity score (higher = more similar)
                    distance = results["distances"][0][i]
                    # Normalize distance to similarity: score = 1 / (1 + distance)
                    # This gives scores in range (0, 1] with higher = more similar
                    score = 1.0 / (1.0 + distance)

                    # Apply minimum score filter
                    if score < min_score:
                        logger.debug(
                            f"Filtering out result with score {score:.3f} < {min_score}"
                        )
                        continue

                    content = results["documents"][0][i]
                    metadata_dict = results["metadatas"][0][i]

                    # Reconstruct ChunkMetadata
                    metadata = ChunkMetadata.from_dict(metadata_dict)

                    retrieval_results.append(
                        RetrievalResult(
                            content=content,
                            metadata=metadata,
                            score=score,
                            distance=distance,
                        )
                    )

                logger.info(
                    f"Retrieved {len(retrieval_results)} results (after min_score filter)"
                )
            else:
                logger.warning("No results found for query")

            return retrieval_results

        except Exception as e:
            logger.error(f"Error during retrieval: {e}", exc_info=True)
            return []

    def query_with_request(self, request: QueryRequest) -> List[RetrievalResult]:
        """Query using a QueryRequest object.

        Args:
            request: QueryRequest with query and filters

        Returns:
            List of retrieval results
        """
        # Note: date_from/date_to filters not implemented yet
        # ChromaDB metadata filtering can be extended here
        return self.query(
            query_text=request.query,
            top_k=request.top_k,
            source_type_filter=request.source_type_filter,
        )

    def get_collection_stats(self) -> dict:
        """Get statistics about the collection.

        Returns:
            Dictionary with collection statistics
        """
        try:
            count = self.collection.count()
            # Get a sample to inspect metadata
            sample = self.collection.peek(limit=1)

            # Count by source type (requires fetching all metadata - expensive!)
            # For now, just return total count
            stats = {
                "collection_name": self.collection_name,
                "total_chunks": count,
                "persist_path": str(self.settings.chroma_persist_dir),
            }

            logger.info(f"Collection stats: {count} chunks")
            return stats

        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            return {
                "collection_name": self.collection_name,
                "total_chunks": 0,
                "error": str(e),
            }

    def get_document_by_source(self, source: str) -> List[RetrievalResult]:
        """Retrieve all chunks from a specific source document.

        Args:
            source: Source identifier (e.g., file path or Drive file ID)

        Returns:
            List of all chunks from that document
        """
        try:
            logger.info(f"Fetching all chunks for source: {source}")

            # Query with source filter
            results = self.collection.get(
                where={"source": source},
                include=["documents", "metadatas"],
            )

            retrieval_results = []
            if results["ids"]:
                for i in range(len(results["ids"])):
                    content = results["documents"][i]
                    metadata_dict = results["metadatas"][i]
                    metadata = ChunkMetadata.from_dict(metadata_dict)

                    retrieval_results.append(
                        RetrievalResult(
                            content=content,
                            metadata=metadata,
                            score=1.0,  # No scoring for direct fetch
                            distance=0.0,
                        )
                    )

                # Sort by chunk_index to preserve order
                retrieval_results.sort(key=lambda r: r.metadata.chunk_index)
                logger.info(f"Found {len(retrieval_results)} chunks for source")

            return retrieval_results

        except Exception as e:
            logger.error(f"Error fetching document by source: {e}")
            return []
