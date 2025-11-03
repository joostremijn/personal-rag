"""Embeddings interface for generating vector embeddings."""

import logging
from typing import List

from langchain_openai import OpenAIEmbeddings
import tiktoken

from src.config import get_settings
from src.models import DocumentChunk

logger = logging.getLogger(__name__)

# OpenAI API limits
MAX_TOKENS_PER_REQUEST = 300000  # Conservative limit (actual is 300k for embeddings)
TOKENS_PER_CHUNK_ESTIMATE = 4  # Rough estimate: 1 token ≈ 4 chars


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

        # Initialize tokenizer for accurate token counting
        try:
            self.tokenizer = tiktoken.encoding_for_model(self.model_name)
        except KeyError:
            # Fallback for unknown models
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

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

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text.

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        return len(self.tokenizer.encode(text))

    def embed_chunks(self, chunks: List[DocumentChunk]) -> List[DocumentChunk]:
        """Generate embeddings for document chunks with automatic batching.

        Batches chunks to stay under OpenAI's 300k token limit per request.

        Args:
            chunks: List of document chunks

        Returns:
            Same chunks with embeddings populated
        """
        if not chunks:
            return []

        try:
            # Count tokens for each chunk
            chunk_tokens = [self._count_tokens(chunk.content) for chunk in chunks]
            total_tokens = sum(chunk_tokens)

            logger.info(f"Embedding {len(chunks)} chunks ({total_tokens:,} tokens total)")

            # If within limit, process all at once
            if total_tokens <= MAX_TOKENS_PER_REQUEST:
                texts = [chunk.content for chunk in chunks]
                embeddings = self.embed_texts(texts)

                for chunk, embedding in zip(chunks, embeddings):
                    chunk.embedding = embedding

                logger.info(f"Embedded {len(chunks)} chunks in single batch")
                return chunks

            # Otherwise, batch to stay under token limit
            batches = []
            current_batch = []
            current_tokens = 0

            for chunk, tokens in zip(chunks, chunk_tokens):
                # If adding this chunk would exceed limit, start new batch
                if current_tokens + tokens > MAX_TOKENS_PER_REQUEST and current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_tokens = 0

                current_batch.append(chunk)
                current_tokens += tokens

            # Add final batch
            if current_batch:
                batches.append(current_batch)

            logger.info(f"Processing {len(chunks)} chunks in {len(batches)} batches")

            # Process each batch
            all_embedded_chunks = []
            for i, batch in enumerate(batches, 1):
                batch_texts = [chunk.content for chunk in batch]
                batch_tokens = sum(self._count_tokens(t) for t in batch_texts)

                logger.info(f"Batch {i}/{len(batches)}: {len(batch)} chunks ({batch_tokens:,} tokens)")

                embeddings = self.embed_texts(batch_texts)

                for chunk, embedding in zip(batch, embeddings):
                    chunk.embedding = embedding

                all_embedded_chunks.extend(batch)

            logger.info(f"Successfully embedded {len(all_embedded_chunks)} chunks in {len(batches)} batches")
            return all_embedded_chunks

        except Exception as e:
            logger.error(f"Error embedding chunks: {e}")
            raise
