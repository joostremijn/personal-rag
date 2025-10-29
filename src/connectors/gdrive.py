"""Google Drive connector for ingesting documents."""

import io
import logging
import os
import pickle
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from pypdf import PdfReader

from src.config import get_settings
from src.connectors.base import BaseConnector
from src.models import Document, DocumentMetadata, SourceType

logger = logging.getLogger(__name__)


class GoogleDriveConnector(BaseConnector):
    """Connector for reading documents from Google Drive."""

    # Google Drive API scopes
    SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

    # Supported MIME types for download
    SUPPORTED_MIME_TYPES = {
        # Google Docs types
        "application/vnd.google-apps.document": {
            "export": "text/plain",
            "ext": ".txt",
        },
        "application/vnd.google-apps.spreadsheet": {
            "export": "text/csv",
            "ext": ".csv",
        },
        # Standard document types
        "text/plain": {"download": True, "ext": ".txt"},
        "application/pdf": {"download": True, "ext": ".pdf"},
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {
            "download": True,
            "ext": ".docx",
        },
        "text/markdown": {"download": True, "ext": ".md"},
    }

    def __init__(self) -> None:
        """Initialize Google Drive connector."""
        super().__init__(SourceType.GDRIVE)
        self.settings = get_settings()
        self.service = None
        self.creds = None

    def validate_connection(self) -> bool:
        """Validate Google Drive API connection.

        Returns:
            True if connection is valid, False otherwise
        """
        try:
            self._authenticate()
            return self.service is not None
        except Exception as e:
            logger.error(f"Failed to validate Google Drive connection: {e}")
            return False

    def _authenticate(self) -> None:
        """Authenticate with Google Drive API using OAuth2."""
        creds = None
        token_file = self.settings.google_token_path

        # Load existing token if available
        if token_file.exists():
            try:
                with open(token_file, "rb") as token:
                    creds = pickle.load(token)
                logger.info("Loaded existing Google Drive credentials")
            except Exception as e:
                logger.warning(f"Could not load token file: {e}")

        # Refresh or create new credentials if needed
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Refreshed Google Drive credentials")
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    creds = None

            if not creds:
                # Start OAuth flow
                credentials_file = self.settings.google_credentials_path
                if not credentials_file.exists():
                    raise FileNotFoundError(
                        f"Google OAuth credentials file not found: {credentials_file}\n"
                        f"Please download from Google Cloud Console and save as {credentials_file}"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_file), self.SCOPES
                )
                creds = flow.run_local_server(port=0)
                logger.info("Completed Google Drive OAuth flow")

            # Save credentials for future use
            with open(token_file, "wb") as token:
                pickle.dump(creds, token)
            logger.info(f"Saved credentials to {token_file}")

        self.creds = creds
        self.service = build("drive", "v3", credentials=creds)

    def fetch_documents(
        self,
        folder_id: Optional[str] = None,
        query: Optional[str] = None,
        max_results: int = 100,
        **kwargs: any,
    ) -> List[Document]:
        """Fetch documents from Google Drive.

        Args:
            folder_id: Specific folder ID to fetch from (None = all accessible files)
            query: Custom Drive API query string
            max_results: Maximum number of files to fetch
            **kwargs: Additional arguments (unused)

        Returns:
            List of documents
        """
        if not self.service:
            self._authenticate()

        try:
            # Build query
            query_parts = []

            if folder_id:
                query_parts.append(f"'{folder_id}' in parents")

            if query:
                query_parts.append(query)
            else:
                # Default: fetch only supported file types, not trashed
                mime_queries = [
                    f"mimeType='{mime}'" for mime in self.SUPPORTED_MIME_TYPES.keys()
                ]
                query_parts.append(f"({' or '.join(mime_queries)})")
                query_parts.append("trashed=false")

            full_query = " and ".join(query_parts)

            logger.info(f"Fetching from Google Drive with query: {full_query}")

            # Fetch file list
            results = (
                self.service.files()
                .list(
                    q=full_query,
                    pageSize=max_results,
                    fields="files(id, name, mimeType, createdTime, modifiedTime, "
                    "owners, size, webViewLink)",
                )
                .execute()
            )

            files = results.get("files", [])
            logger.info(f"Found {len(files)} files in Google Drive")

            # Fetch documents
            documents = []
            for file_info in files:
                doc = self._fetch_file(file_info)
                if doc:
                    documents.append(doc)

            logger.info(f"Successfully loaded {len(documents)} documents from Google Drive")
            return documents

        except HttpError as e:
            logger.error(f"Google Drive API error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error fetching from Google Drive: {e}")
            return []

    def _fetch_file(self, file_info: dict) -> Optional[Document]:
        """Fetch a single file from Google Drive.

        Args:
            file_info: File metadata from Drive API

        Returns:
            Document or None if fetch failed
        """
        file_id = file_info["id"]
        file_name = file_info["name"]
        mime_type = file_info["mimeType"]

        try:
            logger.debug(f"Fetching file: {file_name} ({mime_type})")

            # Get file content
            if mime_type not in self.SUPPORTED_MIME_TYPES:
                logger.warning(f"Unsupported MIME type {mime_type} for {file_name}")
                return None

            mime_config = self.SUPPORTED_MIME_TYPES[mime_type]

            if "export" in mime_config:
                # Google Docs, Sheets, etc. - export as specific format
                request = self.service.files().export_media(
                    fileId=file_id, mimeType=mime_config["export"]
                )
            else:
                # Regular files - download directly
                request = self.service.files().get_media(fileId=file_id)

            # Download content
            file_data = io.BytesIO()
            downloader = MediaIoBaseDownload(file_data, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()

            file_data.seek(0)

            # Parse content based on type
            if mime_type == "application/pdf":
                content = self._parse_pdf_bytes(file_data)
            else:
                # Text-based content
                content = file_data.read().decode("utf-8", errors="ignore")

            if not content or not content.strip():
                logger.warning(f"Empty content for file: {file_name}")
                return None

            # Build metadata
            metadata = DocumentMetadata(
                source=file_id,
                source_type=self.source_type,
                title=file_name,
                author=file_info.get("owners", [{}])[0].get("displayName"),
                created_at=datetime.fromisoformat(
                    file_info["createdTime"].replace("Z", "+00:00")
                ),
                modified_at=datetime.fromisoformat(
                    file_info["modifiedTime"].replace("Z", "+00:00")
                ),
                file_type=mime_config["ext"],
                file_size=file_info.get("size"),
                url=file_info.get("webViewLink"),
            )

            return Document(content=content, metadata=metadata)

        except Exception as e:
            logger.error(f"Error fetching file {file_name}: {e}")
            return None

    def _parse_pdf_bytes(self, file_data: io.BytesIO) -> str:
        """Parse PDF content from bytes.

        Args:
            file_data: PDF file data

        Returns:
            Extracted text
        """
        try:
            reader = PdfReader(file_data)
            text_parts = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            return "\n\n".join(text_parts)

        except Exception as e:
            logger.error(f"Error parsing PDF: {e}")
            return ""

    def list_folders(self, parent_folder_id: Optional[str] = None) -> List[dict]:
        """List folders in Google Drive.

        Args:
            parent_folder_id: Parent folder ID (None = root)

        Returns:
            List of folder info dicts
        """
        if not self.service:
            self._authenticate()

        try:
            query = "mimeType='application/vnd.google-apps.folder' and trashed=false"
            if parent_folder_id:
                query += f" and '{parent_folder_id}' in parents"

            results = (
                self.service.files()
                .list(
                    q=query,
                    pageSize=100,
                    fields="files(id, name, createdTime, modifiedTime)",
                )
                .execute()
            )

            folders = results.get("files", [])
            logger.info(f"Found {len(folders)} folders")
            return folders

        except Exception as e:
            logger.error(f"Error listing folders: {e}")
            return []
