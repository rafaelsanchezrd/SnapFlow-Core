"""
SnapFlow Core - Base Storage Provider
=====================================
Abstract base class for all storage providers in serverless context.

Unlike desktop applications, serverless storage providers need to:
- Download files from cloud storage
- Upload processed files back
- Work without UI/progress callbacks
- Handle authentication per-request (no persistent connections)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class BaseStorageProvider(ABC):
    """
    Abstract base class for cloud storage providers.
    
    All storage providers (Dropbox, Google Drive, S3, etc.) must implement
    this interface to be usable with the SnapFlow StorageFactory.
    
    Serverless-specific considerations:
    - Each function invocation may need fresh authentication
    - No persistent connections between invocations
    - Memory constraints require efficient file handling
    - Progress callbacks are logging-only (no UI)
    """
    
    @abstractmethod
    def connect(self, credentials: Dict[str, Any]) -> bool:
        """
        Establish connection with the storage provider.
        
        This method should handle authentication, token refresh, etc.
        May be called multiple times (idempotent).
        
        Args:
            credentials: Provider-specific credentials dictionary
                For Dropbox: {
                    'refresh_token': str,
                    'app_key': str,
                    'app_secret': str,
                    'member_id': str (optional, for team accounts)
                }
                For Google Drive: {
                    'client_id': str,
                    'client_secret': str,
                    'refresh_token': str,
                    'shared_drive_id': str (optional)
                }
        
        Returns:
            True if connection successful, False otherwise
            
        Raises:
            ConnectionError: If authentication fails
        """
        pass
    
    @abstractmethod
    def list_files(
        self,
        folder: str,
        extensions: Optional[tuple] = None,
        recursive: bool = True,
        max_files: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        List files in a folder.
        
        Args:
            folder: Folder path to list
            extensions: Tuple of allowed extensions (e.g., ('.jpg', '.dng'))
                       If None, return all files
            recursive: Whether to search subfolders
            max_files: Maximum number of files to return (None for unlimited)
        
        Returns:
            List of file info dictionaries:
            [
                {
                    'name': 'photo.jpg',
                    'path_lower': '/folder/photo.jpg',
                    'size': 1234567
                },
                ...
            ]
            
        Raises:
            FileNotFoundError: If folder doesn't exist
            PermissionError: If access denied
        """
        pass
    
    @abstractmethod
    def download_file(self, path: str) -> bytes:
        """
        Download complete file content.
        
        Args:
            path: Full path to file in storage
        
        Returns:
            File content as bytes
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If download fails
        """
        pass
    
    @abstractmethod
    def download_file_partial(self, path: str, start: int = 0, end: int = None) -> bytes:
        """
        Download partial file content (byte range).
        
        Useful for extracting EXIF data from large RAW files without
        downloading the entire file.
        
        Args:
            path: Full path to file in storage
            start: Start byte position (default 0)
            end: End byte position (default None = to end)
        
        Returns:
            Requested byte range as bytes
            
        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If download fails
        """
        pass
    
    @abstractmethod
    def upload_file(
        self,
        remote_path: str,
        content: bytes,
        overwrite: bool = True,
    ) -> bool:
        """
        Upload file content to storage.
        
        Args:
            remote_path: Destination path in storage
            content: File content as bytes
            overwrite: Whether to overwrite existing file
        
        Returns:
            True if upload successful
            
        Raises:
            PermissionError: If write access denied
            IOError: If upload fails
        """
        pass
    
    @abstractmethod
    def get_user_info(self) -> Dict[str, Any]:
        """
        Get information about authenticated user/account.
        
        Returns:
            Dictionary with user info:
            {
                'display_name': 'John Doe',
                'email': 'john@example.com',
                'account_type': 'team' or 'personal',
                'namespace_id': '...'  # Provider-specific
            }
        """
        pass
    
    @abstractmethod
    def get_provider_type(self) -> str:
        """
        Get provider type identifier.
        
        Returns:
            Provider type string (e.g., 'dropbox', 'google_drive')
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get human-readable provider name.
        
        Returns:
            Provider name (e.g., 'Dropbox', 'Google Drive')
        """
        pass
    
    def is_connected(self) -> bool:
        """
        Check if provider is currently connected.
        
        Default implementation returns False.
        Subclasses should override to track connection state.
        
        Returns:
            True if connected, False otherwise
        """
        return False
    
    def create_folder(self, folder_path: str) -> bool:
        """
        Create a folder in storage.
        
        Default implementation raises NotImplementedError.
        Subclasses should override if folder creation is supported.
        
        Args:
            folder_path: Path to folder to create
            
        Returns:
            True if created (or already exists)
        """
        raise NotImplementedError("Folder creation not supported by this provider")
    
    def file_exists(self, path: str) -> bool:
        """
        Check if a file exists in storage.
        
        Default implementation tries to get metadata.
        Subclasses may override for more efficient check.
        
        Args:
            path: Path to file
            
        Returns:
            True if file exists
        """
        try:
            # Try to list just that one file
            # This is inefficient; subclasses should override
            return True
        except FileNotFoundError:
            return False
        except Exception:
            return False
    
    def validate_path(self, path: str) -> bool:
        """
        Validate that a path is valid for this provider.
        
        Default implementation accepts any non-empty string.
        Subclasses should override with provider-specific validation.
        
        Args:
            path: Path to validate
            
        Returns:
            True if valid
        """
        return bool(path and isinstance(path, str))
