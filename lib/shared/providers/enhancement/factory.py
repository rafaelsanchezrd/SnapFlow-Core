"""
Enhancement Factory
===================
Factory for creating enhancement provider instances dynamically.

Supports both legacy credential format (flat fields) and new multi-provider format.
"""

from typing import Dict, Any, Optional

from .base import BaseEnhancementProvider
from .fotello_provider import FotelloProvider
from .autohdr_provider import AutoHDRProvider

from ...config.constants import (
    ENHANCEMENT_PROVIDER_FOTELLO,
    ENHANCEMENT_PROVIDER_AUTOHDR,
)


class EnhancementFactory:
    """
    Factory for creating enhancement provider instances.
    
    The factory handles:
    1. Provider type detection (explicit or from credentials)
    2. API key extraction (legacy or new format)
    3. Provider instantiation with provider-specific requirements
    
    Usage:
        # Explicit provider type
        provider = EnhancementFactory.create("fotello", api_key)
        
        # AutoHDR requires email
        provider = EnhancementFactory.create("autohdr", api_key, email="user@example.com")
        
        # Auto-detect from credentials
        provider = EnhancementFactory.create_from_credentials(decrypted_data)
    """
    
    # Registered provider classes
    _providers = {
        ENHANCEMENT_PROVIDER_FOTELLO: FotelloProvider,
        ENHANCEMENT_PROVIDER_AUTOHDR: AutoHDRProvider,
    }
    
    @classmethod
    def create(
        cls,
        provider_type: str,
        api_key: str,
        email: Optional[str] = None,
        **kwargs
    ) -> BaseEnhancementProvider:
        """
        Create an enhancement provider instance.
        
        Args:
            provider_type: Provider type ('fotello', 'autohdr')
            api_key: API key for the provider
            email: Email address (required for AutoHDR)
            **kwargs: Additional provider-specific arguments
            
        Returns:
            Configured enhancement provider instance
            
        Raises:
            ValueError: If provider type unknown or required args missing
        """
        provider_type = provider_type.lower().strip()
        
        if provider_type not in cls._providers:
            supported = ", ".join(cls._providers.keys())
            raise ValueError(
                f"Unknown enhancement provider: '{provider_type}'. "
                f"Supported: {supported}"
            )
        
        if not api_key:
            raise ValueError(f"API key required for {provider_type} provider")
        
        # Provider-specific instantiation
        provider_class = cls._providers[provider_type]
        
        if provider_type == ENHANCEMENT_PROVIDER_AUTOHDR:
            # AutoHDR requires email for API calls
            if not email:
                raise ValueError("AutoHDR provider requires 'email' parameter")
            return provider_class(api_key, email)
        else:
            # Standard provider (Fotello)
            return provider_class(api_key)
    
    @classmethod
    def create_from_credentials(
        cls,
        decrypted_data: Dict[str, Any],
        provider_type: Optional[str] = None,
    ) -> BaseEnhancementProvider:
        """
        Create enhancement provider from decrypted credential data.
        
        Handles both legacy and new credential formats:
        
        Legacy Fotello format:
            {
                'fotello_api_key': '...',
            }
            
        Legacy AutoHDR format:
            {
                'autohdr_api_key': '...',
                'autohdr_email': '...',
            }
            
        New format:
            {
                'enhancement_provider': 'fotello',
                'enhancement_credentials': {
                    'api_key': '...',
                    'email': '...',  # For AutoHDR
                }
            }
        
        Args:
            decrypted_data: Decrypted credential dictionary
            provider_type: Override provider type (auto-detected if None)
            
        Returns:
            Configured enhancement provider instance
        """
        # Detect format and extract provider type
        if provider_type:
            detected_type = provider_type
        elif 'enhancement_provider' in decrypted_data:
            # New format
            detected_type = decrypted_data['enhancement_provider']
        elif 'fotello_api_key' in decrypted_data:
            # Legacy Fotello format
            detected_type = ENHANCEMENT_PROVIDER_FOTELLO
        elif 'autohdr_api_key' in decrypted_data:
            # Legacy AutoHDR format
            detected_type = ENHANCEMENT_PROVIDER_AUTOHDR
        else:
            # Default to Fotello for backward compatibility
            detected_type = ENHANCEMENT_PROVIDER_FOTELLO
        
        # Extract credentials based on format
        api_key = cls._extract_api_key(decrypted_data, detected_type)
        email = cls._extract_email(decrypted_data, detected_type)
        
        return cls.create(detected_type, api_key, email=email)
    
    @classmethod
    def _extract_api_key(
        cls,
        decrypted_data: Dict[str, Any],
        provider_type: str,
    ) -> str:
        """
        Extract API key from decrypted data.
        
        Args:
            decrypted_data: Full decrypted data dictionary
            provider_type: Target provider type
            
        Returns:
            API key string
        """
        # Check for new format first
        if 'enhancement_credentials' in decrypted_data:
            creds = decrypted_data['enhancement_credentials']
            return creds.get('api_key', '')
        
        # Legacy format - extract based on provider type
        if provider_type == ENHANCEMENT_PROVIDER_FOTELLO:
            return decrypted_data.get('fotello_api_key', '')
        
        elif provider_type == ENHANCEMENT_PROVIDER_AUTOHDR:
            return decrypted_data.get('autohdr_api_key', '')
        
        else:
            raise ValueError(f"Unknown provider type for API key extraction: {provider_type}")
    
    @classmethod
    def _extract_email(
        cls,
        decrypted_data: Dict[str, Any],
        provider_type: str,
    ) -> Optional[str]:
        """
        Extract email from decrypted data (for AutoHDR).
        
        Args:
            decrypted_data: Full decrypted data dictionary
            provider_type: Target provider type
            
        Returns:
            Email string or None
        """
        # Check for new format first
        if 'enhancement_credentials' in decrypted_data:
            creds = decrypted_data['enhancement_credentials']
            return creds.get('email')
        
        # Legacy format - only AutoHDR uses email
        if provider_type == ENHANCEMENT_PROVIDER_AUTOHDR:
            return decrypted_data.get('autohdr_email')
        
        return None
    
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
            provider_class: Class that implements BaseEnhancementProvider
        """
        if not issubclass(provider_class, BaseEnhancementProvider):
            raise TypeError(
                f"Provider class must inherit from BaseEnhancementProvider"
            )
        cls._providers[provider_type.lower().strip()] = provider_class
