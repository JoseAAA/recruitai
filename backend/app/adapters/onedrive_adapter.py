"""
OneDrive Adapter - Secure OAuth 2.0 integration with Microsoft Graph API.
Handles authorization, token management, and file sync for CV ingestion.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

import httpx
from cryptography.fernet import Fernet

from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenEncryption:
    """Handles encryption/decryption of OAuth tokens using Fernet."""
    
    def __init__(self):
        key = settings.TOKEN_ENCRYPTION_KEY
        if not key:
            # Generate a key for development (should be set in production)
            logger.warning("TOKEN_ENCRYPTION_KEY not set, generating temporary key")
            key = Fernet.generate_key().decode()
        self.fernet = Fernet(key.encode() if isinstance(key, str) else key)
    
    def encrypt(self, token: str) -> str:
        """Encrypt a token."""
        return self.fernet.encrypt(token.encode()).decode()
    
    def decrypt(self, encrypted_token: str) -> str:
        """Decrypt a token."""
        return self.fernet.decrypt(encrypted_token.encode()).decode()


class OneDriveAdapter:
    """
    Microsoft Graph API adapter for OneDrive integration.
    Implements OAuth 2.0 authorization code flow.
    """
    
    # Microsoft OAuth 2.0 endpoints
    AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    GRAPH_URL = "https://graph.microsoft.com/v1.0"
    
    # Required scopes for file access
    SCOPES = [
        "Files.Read",
        "Files.Read.All",
        "offline_access",  # For refresh tokens
    ]
    
    def __init__(self):
        self.client_id = settings.ONEDRIVE_CLIENT_ID
        self.client_secret = settings.ONEDRIVE_CLIENT_SECRET
        self.redirect_uri = settings.ONEDRIVE_REDIRECT_URI
        self.encryption = TokenEncryption()
        self._client: Optional[httpx.AsyncClient] = None
    
    @property
    def is_configured(self) -> bool:
        """Check if OneDrive OAuth is configured."""
        return bool(self.client_id and self.client_secret)
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client
    
    def get_authorization_url(self, state: str) -> str:
        """
        Generate the OAuth authorization URL.
        User will be redirected to Microsoft login.
        
        Args:
            state: Random state for CSRF protection
        
        Returns:
            Authorization URL to redirect user to
        """
        if not self.is_configured:
            raise ValueError("OneDrive OAuth not configured")
        
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "scope": " ".join(self.SCOPES),
            "state": state,
            "response_mode": "query",
        }
        return f"{self.AUTH_URL}?{urlencode(params)}"
    
    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchange authorization code for access and refresh tokens.
        
        Args:
            code: Authorization code from OAuth callback
        
        Returns:
            Dict with access_token, refresh_token, expires_in
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "code": code,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        
        response = await self.client.post(self.TOKEN_URL, data=data)
        response.raise_for_status()
        tokens = response.json()
        
        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token"),
            "expires_in": tokens.get("expires_in", 3600),
            "expires_at": datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600)),
        }
    
    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh an expired access token.
        
        Args:
            refresh_token: The refresh token
        
        Returns:
            New tokens dict
        """
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        
        response = await self.client.post(self.TOKEN_URL, data=data)
        response.raise_for_status()
        tokens = response.json()
        
        return {
            "access_token": tokens["access_token"],
            "refresh_token": tokens.get("refresh_token", refresh_token),
            "expires_in": tokens.get("expires_in", 3600),
            "expires_at": datetime.utcnow() + timedelta(seconds=tokens.get("expires_in", 3600)),
        }
    
    async def list_folders(self, access_token: str, path: str = "root") -> List[Dict[str, Any]]:
        """
        List folders in OneDrive.
        
        Args:
            access_token: Valid access token
            path: Folder path or "root"
        
        Returns:
            List of folder items
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        
        if path == "root":
            url = f"{self.GRAPH_URL}/me/drive/root/children"
        else:
            url = f"{self.GRAPH_URL}/me/drive/root:/{path}:/children"
        
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Filter to only return folders
        folders = [
            item for item in data.get("value", [])
            if "folder" in item
        ]
        return folders
    
    async def list_files(
        self, 
        access_token: str, 
        folder_path: str,
        extensions: List[str] = [".pdf", ".docx", ".doc"]
    ) -> List[Dict[str, Any]]:
        """
        List files in a folder, filtered by extensions.
        
        Args:
            access_token: Valid access token
            folder_path: Folder path in OneDrive
            extensions: List of file extensions to include
        
        Returns:
            List of file items with name, id, downloadUrl
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        
        if folder_path == "root":
            url = f"{self.GRAPH_URL}/me/drive/root/children"
        else:
            url = f"{self.GRAPH_URL}/me/drive/root:/{folder_path}:/children"
        
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Filter by extensions and only files
        files = []
        for item in data.get("value", []):
            if "file" in item:
                name = item.get("name", "")
                if any(name.lower().endswith(ext) for ext in extensions):
                    files.append({
                        "id": item["id"],
                        "name": name,
                        "size": item.get("size", 0),
                        "modified": item.get("lastModifiedDateTime"),
                        "download_url": item.get("@microsoft.graph.downloadUrl"),
                    })
        
        return files
    
    async def download_file(self, access_token: str, file_id: str) -> bytes:
        """
        Download a file from OneDrive.
        
        Args:
            access_token: Valid access token
            file_id: OneDrive file ID
        
        Returns:
            File content as bytes
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        url = f"{self.GRAPH_URL}/me/drive/items/{file_id}/content"
        
        response = await self.client.get(url, headers=headers, follow_redirects=True)
        response.raise_for_status()
        
        return response.content
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get current user info to verify connection."""
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await self.client.get(f"{self.GRAPH_URL}/me", headers=headers)
        response.raise_for_status()
        return response.json()


# Singleton instance
onedrive_adapter = OneDriveAdapter()
