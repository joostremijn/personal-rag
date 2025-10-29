"""Document chunking utilities."""

import logging
from typing import List

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import get_settings
from src.models import Document, DocumentChunk, ChunkMetadata

logger = logging.getLogger(__name__)


class DocumentChunker:
    """Handles chunking of documents into smaller pieces for embedding."""

    def __init__(self, chunk_size: int | None = None, chunk_overlap: int | None = None):
        """Initialize the chunker.

        Args:
            chunk_size: Target size of chunks in tokens (default from config)
            chunk_overlap: Overlap between chunks in tokens (default from config)
        """
        settings = get_settings()
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

        # Initialize tokenizer for accurate token counting
        try:
            self.tokenizer = tiktoken.encoding_for_model(settings.embedding_model)
        except KeyError:
            # Fallback to cl100k_base if model not found
            logger.warning(
                f"Could not find tokenizer for {settings.embedding_model}, using cl100k_base"
            )
            self.tokenizer = tiktoken.get_encoding("cl100k_base")

        # Calculate approximate character length from tokens
        # Rough estimate: 1 token ≈ 4 characters in English
        char_size = self.chunk_size * 4
        char_overlap = self.chunk_overlap * 4

        # Initialize LangChain text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=char_size,
            chunk_overlap=char_overlap,
            length_function=self._token_length,
            separators=["\n\n", "\n", ". ", " ", ""],
            is_separator_regex=False,
        )

    def _token_length(self, text: str) -> int:
        """Calculate token length of text using tiktoken.

        Args:
            text: Text to measure

        Returns:
            Number of tokens in text
        """
        return len(self.tokenizer.encode(text))

    def chunk_document(self, document: Document) -> List[DocumentChunk]:
        """Chunk a document into smaller pieces.

        Args:
            document: Document to chunk

        Returns:
            List of document chunks with metadata
        """
        if not document.content.strip():
            logger.warning(f"Empty document: {document.metadata.source}")
            return []

        try:
            # Split text into chunks
            text_chunks = self.text_splitter.split_text(document.content)

            if not text_chunks:
                logger.warning(f"No chunks created for: {document.metadata.source}")
                return []

            # Create DocumentChunk objects with metadata
            chunks = []
            total_chunks = len(text_chunks)

            for idx, chunk_text in enumerate(text_chunks):
                chunk_metadata = ChunkMetadata(
                    source=document.metadata.source,
                    source_type=document.metadata.source_type,
                    chunk_index=idx,
                    total_chunks=total_chunks,
                    title=document.metadata.title,
                    author=document.metadata.author,
                    created_at=document.metadata.created_at,
                    modified_at=document.metadata.modified_at,
                    file_type=document.metadata.file_type,
                    url=document.metadata.url,
                )

                chunk = DocumentChunk(
                    content=chunk_text.strip(),
                    metadata=chunk_metadata,
                )
                chunks.append(chunk)

            logger.info(
                f"Created {total_chunks} chunks from {document.metadata.source} "
                f"({self._token_length(document.content)} tokens)"
            )

            return chunks

        except Exception as e:
            logger.error(f"Error chunking document {document.metadata.source}: {e}")
            return []

    def chunk_documents(self, documents: List[Document]) -> List[DocumentChunk]:
        """Chunk multiple documents.

        Args:
            documents: List of documents to chunk

        Returns:
            List of all chunks from all documents
        """
        all_chunks = []
        for document in documents:
            chunks = self.chunk_document(document)
            all_chunks.extend(chunks)

        logger.info(
            f"Created {len(all_chunks)} total chunks from {len(documents)} documents"
        )
        return all_chunks
