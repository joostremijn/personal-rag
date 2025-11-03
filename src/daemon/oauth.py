"""OAuth management for Google Drive integration."""

import json
import logging
import pickle
from pathlib import Path
from typing import Dict, Any, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/drive.readonly']


class OAuthManager:
    """Manages Google OAuth authentication."""

    def __init__(
        self,
        credentials_path: Path = Path("credentials.json"),
        token_path: Path = Path("token.json")
    ):
        """Initialize OAuth manager.

        Args:
            credentials_path: Path to OAuth client credentials
            token_path: Path to stored user token
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self._creds: Optional[Credentials] = None

    def _load_credentials(self) -> Optional[Credentials]:
        """Load credentials from token file.

        Handles both JSON format (new) and pickle format (legacy).
        Auto-migrates pickle tokens to JSON.

        Returns:
            Credentials object or None if loading fails
        """
        if not self.token_path.exists():
            return None

        # Try JSON format first (new format)
        try:
            return Credentials.from_authorized_user_file(
                str(self.token_path),
                SCOPES
            )
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Try pickle format (legacy format from GoogleDriveConnector)
            try:
                with open(self.token_path, 'rb') as f:
                    creds = pickle.load(f)
                # Convert to JSON format for future use
                if creds:
                    self._save_credentials(creds)
                    logger.info("Migrated pickle token to JSON format")
                return creds
            except Exception as e:
                logger.warning(f"Failed to load pickle token: {e}")
                return None

    def get_status(self) -> Dict[str, Any]:
        """Get current OAuth authentication status.

        Returns:
            Dictionary with authenticated (bool) and email (str or None)
        """
        try:
            creds = self._load_credentials()

            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    # Try to refresh
                    try:
                        creds.refresh(Request())
                        self._save_credentials(creds)
                    except Exception as e:
                        logger.warning(f"Failed to refresh token: {e}")
                        return {"authenticated": False, "email": None}
                else:
                    return {"authenticated": False, "email": None}

            # Get user email
            service = build('drive', 'v3', credentials=creds)
            about = service.about().get(fields='user').execute()
            email = about['user']['emailAddress']

            self._creds = creds
            return {"authenticated": True, "email": email}

        except Exception as e:
            logger.error(f"Error checking OAuth status: {e}")
            return {"authenticated": False, "email": None}

    def _save_credentials(self, creds: Credentials) -> None:
        """Save credentials to token file."""
        with open(self.token_path, 'w') as token:
            token.write(creds.to_json())

    def get_authorization_url(self) -> str:
        """Get OAuth authorization URL.

        Returns:
            Authorization URL for user to visit
        """
        if not self.credentials_path.exists():
            raise FileNotFoundError(
                f"Credentials file not found: {self.credentials_path}"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(self.credentials_path),
            SCOPES,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'
        )

        auth_url, _ = flow.authorization_url(prompt='consent')
        return auth_url

    def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for token.

        Args:
            code: Authorization code from user

        Returns:
            Status dictionary
        """
        try:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path),
                SCOPES,
                redirect_uri='urn:ietf:wg:oauth:2.0:oob'
            )

            flow.fetch_token(code=code)
            creds = flow.credentials
            self._save_credentials(creds)

            return {"success": True, "email": self.get_status()["email"]}
        except Exception as e:
            logger.error(f"Failed to exchange code: {e}")
            return {"success": False, "error": str(e)}

    def disconnect(self) -> None:
        """Remove stored credentials."""
        if self.token_path.exists():
            self.token_path.unlink()
        self._creds = None
