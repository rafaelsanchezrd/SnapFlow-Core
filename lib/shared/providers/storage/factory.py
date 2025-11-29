"""
Storage Factory
===============
Factory for creating storage provider instances dynamically.

Supports both legacy credential format (flat fields) and new multi-provider format.
"""

from typing import Dict, Any, Optional

from .base import BaseStorageProvider
from .dropbox_provider import DropboxProvider
from .google_drive_provider import GoogleDriveProvider

from ...config.constants import (
    STORAGE_PROVIDER_DROPBOX,
    STORAGE_PROVIDER_GOOGLE_DRIVE,
)


class StorageFactory:
    """
    Factory for creating storage provider instances.
    
    The factory handles:
    1. Provider type detection (explicit or from credentials)
    2. Credential extraction (legacy or new format)
    3. Provider instantiation and connection
    
    Usage:
        # Explicit provider type
        provider = StorageFactory.create("dropbox", credentials)
        
        # Auto-detect from credentials
        provider = StorageFactory.create_from_credentials(decrypted_data)
    """
    
    # Registered provider classes
    _providers = {
        STORAGE_PROVIDER_DROPBOX: DropboxProvider,
        STORAGE_PROVIDER_GOOGLE_DRIVE: GoogleDriveProvider,
    }
    
    @classmethod
    def create(
        cls,
        provider_type: str,
        credentials: Dict[str, Any],
        auto_connect: bool = True,
    ) -> BaseStorageProvider:
        """
        Create a storage provider instance.
        
        Args:
            provider_type: Provider type ('dropbox', 'google_drive')
            credentials: Provider-specific credentials dictionary
            auto_connect: Whether to automatically connect after creation
            
        Returns:
            Configured storage provider instance
            
        Raises:
            ValueError: If provider type unknown
            ConnectionError: If auto_connect fails
        """
        provider_type = provider_type.lower().strip()
        
        if provider_type not in cls._providers:
            supported = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown storage provider: '{provider_type}'. "
                f"Supported: {supported}"
            )
        
        # Create provider instance
        provider_class = cls._providers[provider_type]
        provider = provider_class()
        
        # Connect if requested
        if auto_connect:
            provider.connect(credentials)
        
        return provider
    
    @classmethod
    def create_from_credentials(
        cls,
        decrypted_data: Dict[str, Any],
        provider_type: Optional[str] = None,
        auto_connect: bool = True,
    ) -> BaseStorageProvider:
        """
        Create storage provider from decrypted credential data.
        
        Handles both legacy and new credential formats:
        
        Legacy format:
            {
                'dropbox_refresh_token': '...',
                'dropbox_app_key': '...',
                'dropbox_app_secret': '...',
            }
            
        New format:
            {
                'storage_provider': 'dropbox',
                'storage_credentials': {
                    'refresh_token': '...',
                    'app_key': '...',
                    'app_secret': '...',
                }
            }
        
        Args:
            decrypted_data: Decrypted credential dictionary
            provider_type: Override provider type (auto-detected if None)
            auto_connect: Whether to automatically connect
            
        Returns:
            Configured storage provider instance
        """
        # Detect format and extract provider type
        if provider_type:
            detected_type = provider_type
        elif 'storage_provider' in decrypted_data:
            # New format
            detected_type = decrypted_data['storage_provider']
        elif 'dropbox_refresh_token' in decrypted_data:
            # Legacy Dropbox format
            detected_type = STORAGE_PROVIDER_DROPBOX
        elif 'google_drive_refresh_token' in decrypted_data:
            # Legacy Google Drive format
            detected_type = STORAGE_PROVIDER_GOOGLE_DRIVE
        else:
            raise ValueError(
                "Cannot determine storage provider type. "
                "Either specify provider_type or include storage credentials."
            )
        
        # Extract credentials based on format
        credentials = cls._extract_credentials(decrypted_data, detected_type)
        
        return cls.create(detected_type, credentials, auto_connect)
    
    @classmethod
    def _extract_credentials(
        cls,
        decrypted_data: Dict[str, Any],
        provider_type: str,
    ) -> Dict[str, Any]:
        """
        Extract provider-specific credentials from decrypted data.
        
        Args:
            decrypted_data: Full decrypted data dictionary
            provider_type: Target provider type
            
        Returns:
            Provider-specific credentials dictionary
        """
        # Check for new format first
        if 'storage_credentials' in decrypted_data:
            return decrypted_data['storage_credentials']
        
        # Legacy format - extract based on provider type
        if provider_type == STORAGE_PROVIDER_DROPBOX:
            return {
                'refresh_token': decrypted_data.get('dropbox_refresh_token'),
                'app_key': decrypted_data.get('dropbox_app_key'),
                'app_secret': decrypted_data.get('dropbox_app_secret'),
                'member_id': decrypted_data.get('dropbox_member_id'),
            }
        
        elif provider_type == STORAGE_PROVIDER_GOOGLE_DRIVE:
            return {
                'client_id': decrypted_data.get('google_drive_client_id'),
                'client_secret': decrypted_data.get('google_drive_client_secret'),
                'refresh_token': decrypted_data.get('google_drive_refresh_token'),
                'shared_drive_id': decrypted_data.get('google_drive_shared_drive_id'),
            }
        
        else:
            raise ValueError(f"Unknown provider type for credential extraction: {provider_type}")
    
    @classmethod
    def get_supported_providers(cls) -> list:
        """Get list of supported provider types."""
        return list(cls._providers.keys())
    
    @classmethod
    def is_provider_supported(cls, provider_type: str) -> bool:
        """Check if a provider type is supported."""
        return provider_type.lower().strip() in cls._providers
    
    @classmethod
    def register_provider(cls, provider_type: str, provider_class: type) -> None:
        """
        Register a new provider class.
        
        Args:
            provider_type: Provider type identifier
            provider_class: Class that implements BaseStorageProvider
        """
        if not issubclass(provider_class, BaseStorageProvider):
            raise TypeError(
                f"Provider class must inherit from BaseStorageProvider"
            )
        cls._providers[provider_type.lower().strip()] = provider_class
