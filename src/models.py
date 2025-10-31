"""Pydantic models for data structures."""

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    """Supported document source types."""

    LOCAL = "local"
    GDRIVE = "gdrive"
    EMAIL = "email"
    SLACK = "slack"


class DocumentMetadata(BaseModel):
    """Metadata for a document."""

    source: str = Field(..., description="Original source path or identifier")
    source_type: SourceType = Field(..., description="Type of source")
    title: Optional[str] = Field(None, description="Document title")
    author: Optional[str] = Field(None, description="Document author")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    modified_at: Optional[datetime] = Field(None, description="Last modification timestamp")
    file_type: Optional[str] = Field(None, description="File type/extension")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    url: Optional[str] = Field(None, description="URL if applicable (e.g., Google Drive link)")
    additional: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class Document(BaseModel):
    """A document with content and metadata."""

    content: str = Field(..., description="Document content")
    metadata: DocumentMetadata = Field(..., description="Document metadata")

    @property
    def source_identifier(self) -> str:
        """Get unique identifier for this document."""
        return f"{self.metadata.source_type}:{self.metadata.source}"


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""

    source: str = Field(..., description="Original source path or identifier")
    source_type: SourceType = Field(..., description="Type of source")
    chunk_index: int = Field(..., description="Index of chunk in original document")
    total_chunks: int = Field(..., description="Total number of chunks in document")
    title: Optional[str] = Field(None, description="Document title")
    author: Optional[str] = Field(None, description="Document author")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    modified_at: Optional[datetime] = Field(None, description="Last modification timestamp")
    file_type: Optional[str] = Field(None, description="File type/extension")
    url: Optional[str] = Field(None, description="URL if applicable")
    ingested_at: datetime = Field(
        default_factory=datetime.now, description="When chunk was ingested"
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for ChromaDB storage."""
        data = self.model_dump()
        # Convert datetime objects to ISO format strings
        for key, value in list(data.items()):
            if value is None:
                # ChromaDB doesn't accept None values
                del data[key]
            elif isinstance(value, datetime):
                data[key] = value.isoformat()
        # Convert enum to string
        data["source_type"] = str(self.source_type.value)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChunkMetadata":
        """Create from dictionary retrieved from ChromaDB."""
        # Convert ISO format strings back to datetime
        for key in ["created_at", "modified_at", "ingested_at"]:
            if key in data and data[key]:
                if isinstance(data[key], str):
                    data[key] = datetime.fromisoformat(data[key])
        # Convert string to enum
        if "source_type" in data and isinstance(data["source_type"], str):
            data["source_type"] = SourceType(data["source_type"])
        return cls(**data)


class DocumentChunk(BaseModel):
    """A chunk of a document with embeddings."""

    content: str = Field(..., description="Chunk content")
    metadata: ChunkMetadata = Field(..., description="Chunk metadata")
    embedding: Optional[List[float]] = Field(None, description="Vector embedding")

    @property
    def chunk_id(self) -> str:
        """Generate unique ID for this chunk."""
        return f"{self.metadata.source}:chunk_{self.metadata.chunk_index}"


class RetrievalResult(BaseModel):
    """Result from vector search retrieval."""

    content: str = Field(..., description="Retrieved chunk content")
    metadata: ChunkMetadata = Field(..., description="Chunk metadata")
    score: float = Field(..., description="Similarity score")
    distance: Optional[float] = Field(None, description="Distance metric (if available)")


class QueryRequest(BaseModel):
    """Request for querying the RAG system."""

    query: str = Field(..., description="User query")
    top_k: Optional[int] = Field(None, description="Number of results to retrieve")
    source_type_filter: Optional[List[SourceType]] = Field(
        None, description="Filter by source types"
    )
    date_from: Optional[datetime] = Field(None, description="Filter documents from this date")
    date_to: Optional[datetime] = Field(None, description="Filter documents until this date")


class QueryResponse(BaseModel):
    """Response from RAG query."""

    query: str = Field(..., description="Original query")
    answer: str = Field(..., description="Generated answer")
    sources: List[RetrievalResult] = Field(..., description="Retrieved source chunks")
    processing_time: float = Field(..., description="Processing time in seconds")


class IngestionStats(BaseModel):
    """Statistics from ingestion process."""

    total_documents: int = Field(default=0, description="Total documents processed")
    total_chunks: int = Field(default=0, description="Total chunks created")
    skipped_documents: int = Field(default=0, description="Documents skipped (unchanged)")
    failed_documents: int = Field(default=0, description="Number of failed documents")
    processing_time: float = Field(default=0.0, description="Total processing time in seconds")
    failed_files: List[str] = Field(default_factory=list, description="List of failed file paths")
