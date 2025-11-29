"""
Dropbox Storage Provider
========================
Dropbox implementation for serverless functions.

Features:
- OAuth2 refresh token authentication
- Team account support (admin impersonation)
- Namespace root configuration
- Partial file downloads (for EXIF extraction)
- Chunked uploads for large files
"""

import requests
from typing import List, Dict, Any, Optional

import dropbox
import dropbox.common
from dropbox.exceptions import ApiError, AuthError
from dropbox.files import WriteMode

from .base import BaseStorageProvider
from ...config.constants import (
    DROPBOX_TOKEN_URL,
    DROPBOX_CONTENT_URL,
    UPLOAD_CHUNK_SIZE,
)
from ...utils.file_utils import normalize_dropbox_path, validate_dropbox_path


class DropboxProvider(BaseStorageProvider):
    """
    Dropbox storage provider for serverless functions.
    
    Supports both personal and team (business) accounts.
    Uses OAuth2 refresh tokens for authentication.
    
    Team Account Setup:
    - Requires member_id for admin impersonation
    - Automatically configures namespace root
    - Uses as_admin() for team-wide access
    """
    
    def __init__(self):
        """Initialize Dropbox provider (credentials set via connect())."""
        self.client: Optional[dropbox.Dropbox] = None
        self._connected = False
        self._access_token: Optional[str] = None
        self._user_info: Optional[Dict[str, Any]] = None
    
    def connect(self, credentials: Dict[str, Any]) -> bool:
        """
        Connect to Dropbox using refresh token.
        
        Args:
            credentials: {
                'refresh_token': str (required),
                'app_key': str (required),
                'app_secret': str (required),
                'member_id': str (optional, for team accounts)
            }
            
        Returns:
            True if connection successful
        """
        refresh_token = credentials.get('refresh_token')
        app_key = credentials.get('app_key')
        app_secret = credentials.get('app_secret')
        member_id = credentials.get('member_id')
        
        if not all([refresh_token, app_key, app_secret]):
            raise ValueError("Missing required Dropbox credentials")
        
        try:
            # Exchange refresh token for access token
            access_token = self._get_fresh_token(refresh_token, app_key, app_secret)
            self._access_token = access_token
            
            # Create client
            if member_id:
                # Team account - use admin impersonation
                self.client = self._create_team_client(access_token, member_id)
                print(f"Connected to Dropbox Team as member: {member_id}")
            else:
                # Personal account
                self.client = dropbox.Dropbox(oauth2_access_token=access_token)
                print("Connected to Dropbox (personal account)")
            
            # Verify connection and get user info
            account = self.client.users_get_current_account()
            self._user_info = {
                'display_name': account.name.display_name,
                'email': account.email,
                'account_type': 'team' if member_id else 'personal',
                'namespace_id': account.root_info.root_namespace_id,
            }
            
            print(f"Authenticated as: {self._user_info['display_name']}")
            self._connected = True
            return True
            
        except AuthError as e:
            print(f"Dropbox authentication failed: {e}")
            self._connected = False
            raise ConnectionError(f"Dropbox authentication failed: {e}")
        except Exception as e:
            print(f"Dropbox connection error: {e}")
            self._connected = False
            raise ConnectionError(f"Dropbox connection error: {e}")
    
    def _get_fresh_token(self, refresh_token: str, app_key: str, app_secret: str) -> str:
        """Exchange refresh token for access token."""
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': app_key,
            'client_secret': app_secret,
        }
        
        try:
            print("Refreshing Dropbox token...")
            response = requests.post(DROPBOX_TOKEN_URL, data=data, timeout=30)
            response.raise_for_status()
            token_data = response.json()
            
            access_token = token_data.get('access_token')
            if not access_token:
                raise ValueError("No access token in response")
            
            print("Successfully obtained fresh Dropbox token")
            return access_token
            
        except Exception as e:
            print(f"Failed to refresh Dropbox token: {e}")
            raise
        finally:
            data.clear()  # Clear credentials from memory
    
    def _create_team_client(self, access_token: str, member_id: str) -> dropbox.Dropbox:
        """Create team client with admin impersonation and namespace root."""
        # Create team client
        dbx_team = dropbox.DropboxTeam(oauth2_access_token=access_token)
        
        # Impersonate team member
        client = dbx_team.as_admin(member_id)
        
        # Get and set namespace root
        account = client.users_get_current_account()
        root_ns_id = account.root_info.root_namespace_id
        
        # Configure path root to team namespace
        client = client.with_path_root(dropbox.common.PathRoot.root(root_ns_id))
        
        print(f"Using namespace: {root_ns_id}")
        return client
    
    def list_files(
        self,
        folder: str,
        extensions: Optional[tuple] = None,
        recursive: bool = True,
        max_files: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List files in Dropbox folder."""
        if not self._connected:
            raise ConnectionError("Not connected to Dropbox")
        
        normalized_folder = normalize_dropbox_path(folder)
        print(f"Listing files in folder: {normalized_folder}")
        
        if max_files:
            print(f"File limit applied: {max_files}")
        
        entries = []
        
        try:
            result = self.client.files_list_folder(normalized_folder, recursive=recursive)
            
            while True:
                for entry in result.entries:
                    if isinstance(entry, dropbox.files.FileMetadata):
                        # Check extension filter
                        if extensions:
                            if not entry.name.lower().endswith(extensions):
                                continue
                        
                        # Validate path format
                        if not validate_dropbox_path(entry.path_lower):
                            print(f"Invalid path format: {entry.path_lower}")
                            continue
                        
                        entries.append({
                            'name': entry.name,
                            'path_lower': entry.path_lower,
                            'size': entry.size,
                        })
                        
                        # Check file limit
                        if max_files and len(entries) >= max_files:
                            print(f"Reached file limit: {len(entries)}")
                            return entries
                
                if result.has_more:
                    result = self.client.files_list_folder_continue(result.cursor)
                else:
                    break
            
            print(f"Found {len(entries)} files")
            return entries
            
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_not_found():
                raise FileNotFoundError(f"Folder not found: {normalized_folder}")
            raise IOError(f"Dropbox API error: {e}")
    
    def download_file(self, path: str) -> bytes:
        """Download complete file from Dropbox."""
        if not self._connected:
            raise ConnectionError("Not connected to Dropbox")
        
        normalized_path = normalize_dropbox_path(path)
        
        try:
            _, response = self.client.files_download(normalized_path)
            return response.content
            
        except ApiError as e:
            if e.error.is_path() and e.error.get_path().is_not_found():
                raise FileNotFoundError(f"File not found: {normalized_path}")
            raise IOError(f"Download failed: {e}")
    
    def download_file_partial(self, path: str, start: int = 0, end: int = None) -> bytes:
        """Download partial file (byte range) from Dropbox."""
        if not self._connected:
            raise ConnectionError("Not connected to Dropbox")
        
        normalized_path = normalize_dropbox_path(path)
        
        # Build range header
        if end is None:
            range_header = f"bytes={start}-"
        else:
            range_header = f"bytes={start}-{end-1}"
        
        try:
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "Dropbox-API-Arg": f'{{"path": "{normalized_path}"}}',
                "Range": range_header,
            }
            
            response = requests.post(DROPBOX_CONTENT_URL, headers=headers, timeout=30)
            response.raise_for_status()
            return response.content
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise FileNotFoundError(f"File not found: {normalized_path}")
            raise IOError(f"Partial download failed: {e}")
    
    def upload_file(
        self,
        remote_path: str,
        content: bytes,
        overwrite: bool = True,
    ) -> bool:
        """Upload file to Dropbox."""
        if not self._connected:
            raise ConnectionError("Not connected to Dropbox")
        
        normalized_path = normalize_dropbox_path(remote_path)
        mode = WriteMode('overwrite') if overwrite else WriteMode('add')
        
        try:
            file_size = len(content)
            
            if file_size <= UPLOAD_CHUNK_SIZE:
                # Simple upload for small files
                self.client.files_upload(content, normalized_path, mode=mode)
            else:
                # Chunked upload for large files
                self._chunked_upload(content, normalized_path, mode)
            
            print(f"Uploaded: {normalized_path}")
            return True
            
        except ApiError as e:
            print(f"Upload failed: {e}")
            raise IOError(f"Upload failed: {e}")
    
    def _chunked_upload(self, content: bytes, remote_path: str, mode: WriteMode) -> None:
        """Upload large file using chunked session."""
        file_size = len(content)
        offset = 0
        
        # Start upload session
        session = self.client.files_upload_session_start(content[:UPLOAD_CHUNK_SIZE])
        offset = UPLOAD_CHUNK_SIZE
        
        cursor = dropbox.files.UploadSessionCursor(
            session_id=session.session_id,
            offset=offset
        )
        
        # Upload chunks
        while offset < file_size:
            chunk_end = min(offset + UPLOAD_CHUNK_SIZE, file_size)
            chunk = content[offset:chunk_end]
            
            if chunk_end < file_size:
                # More chunks to come
                self.client.files_upload_session_append_v2(chunk, cursor)
                offset = chunk_end
                cursor.offset = offset
            else:
                # Final chunk
                commit = dropbox.files.CommitInfo(path=remote_path, mode=mode)
                self.client.files_upload_session_finish(chunk, cursor, commit)
                break
    
    def create_folder(self, folder_path: str) -> bool:
        """Create folder in Dropbox."""
        if not self._connected:
            raise ConnectionError("Not connected to Dropbox")
        
        normalized_path = normalize_dropbox_path(folder_path)
        
        try:
            self.client.files_create_folder_v2(normalized_path)
            print(f"Created folder: {normalized_path}")
            return True
        except ApiError as e:
            if "path/conflict/folder" in str(e):
                print(f"Folder already exists: {normalized_path}")
                return True
            raise IOError(f"Failed to create folder: {e}")
    
    def file_exists(self, path: str) -> bool:
        """Check if file exists in Dropbox."""
        if not self._connected:
            return False
        
        normalized_path = normalize_dropbox_path(path)
        
        try:
            self.client.files_get_metadata(normalized_path)
            return True
        except ApiError:
            return False
    
    def get_user_info(self) -> Dict[str, Any]:
        """Get authenticated user info."""
        if not self._user_info:
            return {}
        return self._user_info.copy()
    
    def get_provider_type(self) -> str:
        """Get provider type identifier."""
        return "dropbox"
    
    def get_provider_name(self) -> str:
        """Get human-readable provider name."""
        return "Dropbox"
    
    def is_connected(self) -> bool:
        """Check if connected to Dropbox."""
        return self._connected
    
    def validate_path(self, path: str) -> bool:
        """Validate Dropbox path format."""
        if not path:
            return False
        normalized = normalize_dropbox_path(path)
        return validate_dropbox_path(normalized)
