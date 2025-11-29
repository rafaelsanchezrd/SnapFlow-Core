"""
SnapFlow Core - Google Drive Storage Provider
==============================================
Google Drive storage provider for serverless photo processing.

Based on production-tested autohdr-transfer implementation.
Supports OAuth2 authentication with automatic token refresh.

Features:
- OAuth2 refresh token authentication
- Automatic token refresh with callback support
- Shared Drive support
- Comprehensive RAW file format support
- Download/upload operations
"""

import io
import re
import mimetypes
from typing import List, Dict, Any, Optional, Tuple, Callable

from .base import BaseStorageProvider

# Lazy import Google libraries
_google_imported = False
_Credentials = None
_Request = None
_build = None
_MediaIoBaseDownload = None
_MediaIoBaseUpload = None
_RefreshError = None


def _import_google_libs():
    """Lazy import Google libraries only when needed"""
    global _google_imported, _Credentials, _Request, _build
    global _MediaIoBaseDownload, _MediaIoBaseUpload, _RefreshError
    
    if _google_imported:
        return
    
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
        from google.auth.exceptions import RefreshError
        
        _Credentials = Credentials
        _Request = Request
        _build = build
        _MediaIoBaseDownload = MediaIoBaseDownload
        _MediaIoBaseUpload = MediaIoBaseUpload
        _RefreshError = RefreshError
        _google_imported = True
        
    except ImportError:
        raise ImportError(
            "Google API libraries not installed. "
            "Run: pip install google-auth google-auth-oauthlib google-api-python-client"
        )


# Supported image MIME types for Google Drive
SUPPORTED_MIME_TYPES = [
    # Standard image formats
    'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
    'image/bmp', 'image/webp', 'image/tiff', 'image/svg+xml',
    
    # Apple formats
    'image/heic', 'image/heif',
    
    # Canon RAW formats
    'image/x-canon-cr2', 'image/x-canon-cr3', 'image/x-canon-crw',
    
    # Nikon RAW formats
    'image/x-nikon-nef', 'image/x-nikon-nrw',
    
    # Sony RAW formats
    'image/x-sony-arw', 'image/x-sony-sr2', 'image/x-sony-srf',
    
    # Adobe/Universal RAW
    'image/x-adobe-dng', 'image/dng', 'image/x-dng',
    'application/octet-stream',  # Fallback for unrecognized RAW
    
    # Panasonic RAW formats
    'image/x-panasonic-raw', 'image/x-panasonic-rw2',
    
    # Olympus RAW formats
    'image/x-olympus-orf',
    
    # Fujifilm RAW formats
    'image/x-fuji-raf',
    
    # Pentax RAW formats
    'image/x-pentax-pef', 'image/x-pentax-dng',
    
    # Other RAW formats
    'image/x-phaseone-iiq',
    'image/x-hasselblad-3fr', 'image/x-hasselblad-fff',
    'image/x-leica-rwl', 'image/x-leica-raw',
    'image/x-sigma-x3f',
    'image/x-mamiya-mef',
    'image/x-samsung-srw',
    'image/x-epson-erf',
    'image/x-kodak-dcr', 'image/x-kodak-kdc',
    'image/x-minolta-mrw',
    'image/x-leaf-mos',
]

# Supported file extensions (for fallback filtering)
GDRIVE_SUPPORTED_EXTENSIONS = (
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.svg',
    '.heic', '.heif',
    '.cr2', '.cr3', '.crw',
    '.nef', '.nrw',
    '.arw', '.sr2', '.srf',
    '.dng',
    '.raw', '.rw2',
    '.orf',
    '.raf',
    '.pef',
    '.iiq',
    '.3fr', '.fff',
    '.rwl',
    '.x3f',
    '.mef',
    '.srw',
    '.erf',
    '.dcr', '.kdc',
    '.mrw',
    '.mos'
)


class GoogleDriveProvider(BaseStorageProvider):
    """
    Google Drive storage provider using OAuth2 credentials.
    
    Features:
    - OAuth2 authentication with refresh token
    - Automatic token refresh with callback support
    - Support for shared drives
    - Comprehensive RAW file format support
    - Download/upload operations
    
    Path Format:
    Unlike Dropbox which uses filesystem-style paths (/folder/file.jpg),
    Google Drive uses folder IDs. Files are identified by their file ID.
    
    Credential Requirements:
    - client_id: OAuth2 client ID
    - client_secret: OAuth2 client secret
    - refresh_token: OAuth2 refresh token
    - token (optional): Current access token
    - token_uri (optional): Token endpoint URL
    - scopes (optional): OAuth2 scopes
    """
    
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    SCOPES_WRITE = ['https://www.googleapis.com/auth/drive.file']
    TOKEN_URI = 'https://oauth2.googleapis.com/token'
    
    def __init__(self):
        """Initialize Google Drive provider"""
        self.credentials = None
        self.service = None
        self._connected = False
        self._user_info: Dict[str, Any] = {}
        self._shared_drive_id: Optional[str] = None
        
        # Token refresh tracking
        self._token_refreshed = False
        self._refreshed_token_data: Optional[Dict[str, Any]] = None
        
        # Token refresh callback (optional)
        self._token_refresh_callback: Optional[Callable] = None
    
    def connect(self, credentials: Dict[str, Any]) -> bool:
        """
        Connect to Google Drive using OAuth2 credentials.
        
        Args:
            credentials: Dict containing:
                - client_id: OAuth2 client ID (required)
                - client_secret: OAuth2 client secret (required)
                - refresh_token: OAuth2 refresh token (required)
                - token (optional): Current access token
                - token_uri (optional): Token endpoint
                - scopes (optional): OAuth2 scopes
                - shared_drive_id (optional): For shared drives
                - token_refresh_callback (optional): Callback when token refreshed
                
        Returns:
            bool: True if connection successful
        """
        _import_google_libs()
        
        print("Connecting to Google Drive...")
        
        # Extract credentials
        client_id = credentials.get('client_id')
        client_secret = credentials.get('client_secret')
        refresh_token = credentials.get('refresh_token')
        token = credentials.get('token')  # May be None
        token_uri = credentials.get('token_uri', self.TOKEN_URI)
        scopes = credentials.get('scopes', self.SCOPES)
        shared_drive_id = credentials.get('shared_drive_id')
        
        # Validate required fields
        if not client_id:
            raise ValueError("Missing required credential: client_id")
        if not client_secret:
            raise ValueError("Missing required credential: client_secret")
        if not refresh_token:
            raise ValueError("Missing required credential: refresh_token")
        
        # Store optional settings
        self._shared_drive_id = shared_drive_id
        self._token_refresh_callback = credentials.get('token_refresh_callback')
        
        try:
            # Create credentials object
            self.credentials = _Credentials(
                token=token,
                refresh_token=refresh_token,
                token_uri=token_uri,
                client_id=client_id,
                client_secret=client_secret,
                scopes=scopes
            )
            
            # Check if token needs refresh
            if not self.credentials.valid:
                if self.credentials.expired or self.credentials.token is None:
                    print("Access token expired or missing, refreshing...")
                    self._refresh_token()
            
            # Build Drive service
            self.service = _build('drive', 'v3', credentials=self.credentials)
            
            # Verify connection by getting user info
            about = self.service.about().get(fields='user').execute()
            user = about.get('user', {})
            
            self._user_info = {
                'email': user.get('emailAddress', 'unknown'),
                'display_name': user.get('displayName', 'Unknown User'),
                'photo_link': user.get('photoLink'),
                'account_type': 'shared_drive' if shared_drive_id else 'personal',
            }
            
            self._connected = True
            print(f"Connected to Google Drive as: {self._user_info['email']}")
            return True
            
        except _RefreshError as e:
            self._connected = False
            raise Exception(f"Token refresh failed: {str(e)}. User may need to re-authorize.")
        except Exception as e:
            self._connected = False
            raise Exception(f"Google Drive connection failed: {str(e)}")
    
    def _refresh_token(self) -> None:
        """Refresh the OAuth2 access token"""
        _import_google_libs()
        
        try:
            self.credentials.refresh(_Request())
            print("Token refreshed successfully")
            
            # Mark token as refreshed
            self._token_refreshed = True
            
            # Store refreshed token data
            self._refreshed_token_data = {
                'token': self.credentials.token,
                'refresh_token': self.credentials.refresh_token,
                'token_uri': self.credentials.token_uri,
                'client_id': self.credentials.client_id,
                'client_secret': self.credentials.client_secret,
                'scopes': list(self.credentials.scopes) if self.credentials.scopes else None,
                'expiry': self.credentials.expiry.isoformat() if self.credentials.expiry else None
            }
            
            # Call refresh callback if provided
            if self._token_refresh_callback:
                try:
                    self._token_refresh_callback(self._refreshed_token_data)
                    print("Token refresh callback executed")
                except Exception as e:
                    print(f"Token refresh callback failed: {e}")
                    
        except _RefreshError as e:
            raise Exception(f"Token refresh failed: {str(e)}")
    
    def get_refreshed_token_data(self) -> Optional[Dict[str, Any]]:
        """
        Get refreshed token data if token was refreshed during this session.
        
        Returns:
            Dict with token data if refreshed, None otherwise
        """
        return self._refreshed_token_data if self._token_refreshed else None
    
    def was_token_refreshed(self) -> bool:
        """Check if token was refreshed during this session"""
        return self._token_refreshed
    
    def list_files(
        self,
        folder: str,
        extensions: Optional[Tuple[str, ...]] = None,
        recursive: bool = False,
        max_files: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        List files in a Google Drive folder.
        
        Args:
            folder: Google Drive folder ID
            extensions: Tuple of file extensions to filter (e.g., ('.jpg', '.dng'))
            recursive: If True, list files in subfolders (not implemented for GDrive)
            max_files: Maximum number of files to return
            
        Returns:
            List of file metadata dicts with keys:
                - id: Google Drive file ID
                - name: File name
                - path_lower: Same as name (for compatibility)
                - size: File size in bytes
                - mimeType: MIME type
                - createdTime: Creation timestamp
                - modifiedTime: Modification timestamp
        """
        if not self._connected:
            raise Exception("Not connected to Google Drive. Call connect() first.")
        
        folder_id = folder  # In GDrive, folder is identified by ID
        print(f"Listing files in folder: {folder_id}")
        
        # Build MIME type query
        mime_query = " or ".join([f"mimeType='{mt}'" for mt in SUPPORTED_MIME_TYPES])
        query = f"'{folder_id}' in parents and trashed=false and ({mime_query})"
        
        files = []
        page_token = None
        
        try:
            while True:
                results = self.service.files().list(
                    q=query,
                    spaces='drive',
                    fields='nextPageToken, files(id, name, mimeType, size, createdTime, modifiedTime)',
                    pageToken=page_token,
                    pageSize=100,
                    includeItemsFromAllDrives=True,
                    supportsAllDrives=True,
                    corpora='allDrives'
                ).execute()
                
                items = results.get('files', [])
                
                # Filter by extension if specified, or use default supported extensions
                filter_extensions = extensions if extensions else GDRIVE_SUPPORTED_EXTENSIONS
                
                for item in items:
                    file_name_lower = item['name'].lower()
                    mime_type = item.get('mimeType', '')
                    
                    # Check if file has valid extension
                    has_valid_extension = any(
                        file_name_lower.endswith(ext) for ext in filter_extensions
                    )
                    
                    if has_valid_extension:
                        # Log misidentified files (DNG files often detected as octet-stream)
                        if mime_type == 'application/octet-stream':
                            print(f"  Detected misidentified file: {item['name']} (MIME: {mime_type})")
                        
                        # Normalize to match Dropbox format for compatibility
                        files.append({
                            'id': item['id'],
                            'name': item['name'],
                            'path_lower': item['name'].lower(),  # GDrive doesn't have paths
                            'path_id': item['id'],  # Use ID as path identifier
                            'size': int(item.get('size', 0)),
                            'mimeType': item.get('mimeType', ''),
                            'createdTime': item.get('createdTime'),
                            'modifiedTime': item.get('modifiedTime'),
                        })
                        
                        # Check max_files limit
                        if max_files and len(files) >= max_files:
                            print(f"Reached file limit: {len(files)}/{max_files}")
                            return files
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break
            
            print(f"Found {len(files)} image files in folder")
            return files
            
        except Exception as e:
            raise Exception(f"Error listing files: {str(e)}")
    
    def download_file(self, path: str) -> bytes:
        """
        Download a file from Google Drive.
        
        Args:
            path: Google Drive file ID (not a filesystem path)
            
        Returns:
            File contents as bytes
        """
        _import_google_libs()
        
        if not self._connected:
            raise Exception("Not connected to Google Drive. Call connect() first.")
        
        file_id = path  # In GDrive, path is actually the file ID
        
        try:
            request = self.service.files().get_media(fileId=file_id)
            file_buffer = io.BytesIO()
            downloader = _MediaIoBaseDownload(file_buffer, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_buffer.seek(0)
            content = file_buffer.read()
            print(f"Downloaded file {file_id}: {len(content)} bytes")
            return content
            
        except Exception as e:
            raise Exception(f"Error downloading file {file_id}: {str(e)}")
    
    def download_file_partial(
        self,
        path: str,
        start: int = 0,
        end: int = None
    ) -> bytes:
        """
        Download a partial file from Google Drive.
        
        Note: Google Drive API doesn't support range requests directly
        through the standard SDK, so this downloads the full file and slices it.
        For large files, consider using direct HTTP requests with Range headers.
        
        Args:
            path: Google Drive file ID
            start: Start byte position
            end: End byte position (None = to end of file)
            
        Returns:
            Partial file contents as bytes
        """
        # Download full file and slice
        # TODO: Implement efficient range request using direct HTTP
        full_content = self.download_file(path)
        
        if end is None:
            return full_content[start:]
        return full_content[start:end]
    
    def upload_file(
        self,
        remote_path: str,
        content: bytes,
        overwrite: bool = True
    ) -> Dict[str, Any]:
        """
        Upload a file to Google Drive.
        
        Args:
            remote_path: Destination folder ID + filename (format: "folder_id/filename.jpg")
            content: File contents as bytes
            overwrite: If True, overwrite existing file
            
        Returns:
            Dict with upload result including file ID
        """
        _import_google_libs()
        
        if not self._connected:
            raise Exception("Not connected to Google Drive. Call connect() first.")
        
        # Parse remote_path to get folder ID and filename
        if '/' in remote_path:
            parts = remote_path.rsplit('/', 1)
            folder_id = parts[0]
            filename = parts[1]
        else:
            raise ValueError("remote_path must be in format 'folder_id/filename'")
        
        try:
            # Detect MIME type
            mime_type, _ = mimetypes.guess_type(filename)
            if not mime_type:
                mime_type = 'application/octet-stream'
            
            # Check if file exists (if overwrite=True)
            if overwrite:
                existing = self.service.files().list(
                    q=f"'{folder_id}' in parents and name='{filename}' and trashed=false",
                    spaces='drive',
                    fields='files(id)',
                    supportsAllDrives=True
                ).execute()
                
                existing_files = existing.get('files', [])
                if existing_files:
                    # Update existing file
                    file_id = existing_files[0]['id']
                    media = _MediaIoBaseUpload(
                        io.BytesIO(content),
                        mimetype=mime_type,
                        resumable=True
                    )
                    self.service.files().update(
                        fileId=file_id,
                        media_body=media,
                        supportsAllDrives=True
                    ).execute()
                    
                    print(f"Updated existing file: {filename} (ID: {file_id})")
                    return {
                        'id': file_id,
                        'name': filename,
                        'action': 'updated',
                        'size': len(content)
                    }
            
            # Create new file
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            media = _MediaIoBaseUpload(
                io.BytesIO(content),
                mimetype=mime_type,
                resumable=True
            )
            
            created = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, name',
                supportsAllDrives=True
            ).execute()
            
            print(f"Uploaded new file: {filename} (ID: {created['id']})")
            return {
                'id': created['id'],
                'name': filename,
                'action': 'created',
                'size': len(content)
            }
            
        except Exception as e:
            raise Exception(f"Error uploading file {filename}: {str(e)}")
    
    def create_folder(self, folder_path: str) -> bool:
        """
        Create a folder in Google Drive.
        
        Args:
            folder_path: Parent folder ID + folder name (format: "parent_id/folder_name")
            
        Returns:
            bool: True if created successfully
        """
        if not self._connected:
            raise Exception("Not connected to Google Drive. Call connect() first.")
        
        # Parse folder_path
        if '/' in folder_path:
            parts = folder_path.rsplit('/', 1)
            parent_id = parts[0]
            folder_name = parts[1]
        else:
            parent_id = 'root'
            folder_name = folder_path
        
        try:
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id]
            }
            
            created = self.service.files().create(
                body=file_metadata,
                fields='id',
                supportsAllDrives=True
            ).execute()
            
            print(f"Created folder: {folder_name} (ID: {created['id']})")
            return True
            
        except Exception as e:
            print(f"Error creating folder {folder_name}: {str(e)}")
            return False
    
    def file_exists(self, path: str) -> bool:
        """
        Check if a file exists in Google Drive.
        
        Args:
            path: Google Drive file ID
            
        Returns:
            bool: True if file exists
        """
        if not self._connected:
            raise Exception("Not connected to Google Drive. Call connect() first.")
        
        try:
            self.service.files().get(
                fileId=path,
                fields='id',
                supportsAllDrives=True
            ).execute()
            return True
        except:
            return False
    
    def get_file_by_name(self, folder_id: str, filename: str) -> Optional[Dict[str, Any]]:
        """
        Find a file by name in a specific folder.
        
        Args:
            folder_id: Google Drive folder ID
            filename: Name of file to find
            
        Returns:
            File metadata dict or None if not found
        """
        if not self._connected:
            raise Exception("Not connected to Google Drive. Call connect() first.")
        
        try:
            results = self.service.files().list(
                q=f"'{folder_id}' in parents and name='{filename}' and trashed=false",
                spaces='drive',
                fields='files(id, name, mimeType, size, createdTime, modifiedTime)',
                supportsAllDrives=True,
                includeItemsFromAllDrives=True
            ).execute()
            
            files = results.get('files', [])
            if files:
                return files[0]
            return None
            
        except Exception as e:
            print(f"Error finding file {filename}: {str(e)}")
            return None
    
    def get_user_info(self) -> Dict[str, Any]:
        """Get information about the authenticated user"""
        return self._user_info.copy()
    
    def get_provider_type(self) -> str:
        """Get provider type identifier"""
        return "google_drive"
    
    def get_provider_name(self) -> str:
        """Get human-readable provider name"""
        return "Google Drive"
    
    def is_connected(self) -> bool:
        """Check if connected to Google Drive"""
        return self._connected
    
    def validate_path(self, path: str) -> bool:
        """
        Validate a Google Drive path/ID.
        
        Args:
            path: Google Drive file/folder ID
            
        Returns:
            bool: True if valid format
        """
        # Google Drive IDs are typically 28-44 characters, alphanumeric with dashes/underscores
        if not path or not isinstance(path, str):
            return False
        
        # Basic validation
        return bool(re.match(r'^[a-zA-Z0-9_-]{10,50}$', path))
