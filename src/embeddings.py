"""Embeddings interface for generating vector embeddings."""

import logging
from typing import List

from langchain_openai import OpenAIEmbeddings

from src.config import get_settings
from src.models import DocumentChunk

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating embeddings from text."""

    def __init__(self) -> None:
        """Initialize the embedding service."""
        settings = get_settings()

        self.embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_key=settings.openai_api_key,
        )
        self.model_name = settings.embedding_model
        logger.info(f"Initialized embedding service with model: {self.model_name}")

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        try:
            embedding = self.embeddings.embed_query(text)
            return embedding
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        try:
            embeddings = self.embeddings.embed_documents(texts)
            logger.info(f"Generated embeddings for {len(texts)} texts")
            return embeddings
        except Exception as e:
            logger.error(f"Error generating batch embeddings: {e}")
            raise

    def embed_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Generate embeddings for document chunks.

        Args:
            chunks: List of document chunks

        Returns:
            Same chunks with embeddings populated
        """
        if not chunks:
            return []

        try:
            # Extract texts from chunks
            texts = [chunk.content for chunk in chunks]

            # Generate embeddings in batch
            embeddings = self.embed_texts(texts)

            # Attach embeddings to chunks
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding

            logger.info(f"Embedded {len(chunks)} chunks")
            return chunks

        except Exception as e:
            logger.error(f"Error embedding chunks: {e}")
            raise
