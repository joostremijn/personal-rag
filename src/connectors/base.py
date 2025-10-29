"""Base connector abstraction for document sources."""

from abc import ABC, abstractmethod
from typing import List, Optional

from src.models import Document, SourceType


class BaseConnector(ABC):
    """Abstract base class for document source connectors."""

    def __init__(self, source_type: SourceType):
        """Initialize the connector.

        Args:
            source_type: Type of source this connector handles
        """
        self.source_type = source_type

    @abstractmethod
    def fetch_documents(self, **kwargs: any) -> List[Document]:
        """Fetch documents from the source.

        Args:
            **kwargs: Source-specific arguments

        Returns:
            List of documents with content and metadata
        """
        pass

    @abstractmethod
    def validate_connection(self) -> bool:
        """Validate that the connector can access the source.

        Returns:
            True if connection is valid, False otherwise
        """
        pass

    def get_source_identifier(self, document_path: str) -> str:
        """Get unique identifier for a document.

        Args:
            document_path: Path or identifier of document

        Returns:
            Unique identifier string
        """
        return f"{self.source_type.value}:{document_path}"
