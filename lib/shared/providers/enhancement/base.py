"""
SnapFlow Core - Base Enhancement Provider
=========================================
Abstract base class for photo enhancement APIs.

All enhancement providers (Fotello, AutoHDR, etc.) must implement
this interface to be usable with the SnapFlow EnhancementFactory.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from enum import Enum


class EnhancementStatus(Enum):
    """Standard enhancement status values across all providers."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class BaseEnhancementProvider(ABC):
    """
    Abstract base class for photo enhancement APIs.
    
    Enhancement providers handle:
    1. Uploading images to the enhancement service
    2. Requesting enhancement processing
    3. Polling for completion status
    4. Retrieving enhanced image URLs
    
    Typical workflow:
        provider = EnhancementFactory.create("fotello", api_key)
        
        # Upload images
        upload_ids = []
        for file_bytes in files:
            upload_id = provider.upload_image(filename, file_bytes)
            upload_ids.append(upload_id)
        
        # Request enhancement
        enhancement_id = provider.request_enhancement(upload_ids, listing_id=listing_id)
        
        # Poll for completion
        while True:
            status = provider.check_status(enhancement_id)
            if status['status'] == 'completed':
                url = status['enhanced_image_url']
                break
            elif status['status'] == 'failed':
                raise Exception(status['error'])
            time.sleep(30)
    """
    
    @abstractmethod
    def upload_image(
        self,
        filename: str,
        data: bytes,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload an image to the enhancement service.
        
        Args:
            filename: Original filename (used for content-type detection)
            data: Image data as bytes
            content_type: Optional MIME type override
            
        Returns:
            Upload ID for use in enhancement request
            
        Raises:
            IOError: If upload fails
            ValueError: If image data invalid
        """
        pass
    
    @abstractmethod
    def request_enhancement(
        self,
        upload_ids: List[str],
        listing_id: str,
        **kwargs,
    ) -> str:
        """
        Request enhancement processing for uploaded images.
        
        This is typically used for bracket processing where multiple
        images are merged/enhanced together.
        
        Args:
            upload_ids: List of upload IDs from upload_image()
            listing_id: Listing/job identifier for tracking
            **kwargs: Provider-specific options (e.g., shot_type)
            
        Returns:
            Enhancement ID for status tracking
            
        Raises:
            IOError: If request fails
            ValueError: If upload_ids invalid
        """
        pass
    
    @abstractmethod
    def check_status(self, enhancement_id: str) -> Dict[str, Any]:
        """
        Check the status of an enhancement request.
        
        Args:
            enhancement_id: Enhancement ID from request_enhancement()
            
        Returns:
            Status dictionary:
            {
                'status': 'pending' | 'in_progress' | 'completed' | 'failed',
                'enhanced_image_url': str (when completed),
                'enhanced_image_url_expires': str (ISO timestamp),
                'error': str (when failed),
                'progress': int (0-100, if available),
            }
            
        Raises:
            IOError: If status check fails
        """
        pass
    
    @abstractmethod
    def get_provider_type(self) -> str:
        """
        Get provider type identifier.
        
        Returns:
            Provider type string (e.g., 'fotello', 'autohdr')
        """
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        """
        Get human-readable provider name.
        
        Returns:
            Provider name (e.g., 'Fotello', 'AutoHDR')
        """
        pass
    
    def get_result_url(self, enhancement_id: str) -> Optional[str]:
        """
        Get download URL for enhanced image.
        
        Convenience method that checks status and extracts URL.
        Default implementation uses check_status().
        
        Args:
            enhancement_id: Enhancement ID
            
        Returns:
            Download URL if completed, None otherwise
        """
        status = self.check_status(enhancement_id)
        if status.get('status') == 'completed':
            return status.get('enhanced_image_url')
        return None
    
    def download_result(self, enhancement_id: str) -> Optional[bytes]:
        """
        Download enhanced image.
        
        Convenience method that gets URL and downloads content.
        Default implementation uses get_result_url().
        
        Args:
            enhancement_id: Enhancement ID
            
        Returns:
            Image bytes if available, None otherwise
        """
        import requests
        
        url = self.get_result_url(enhancement_id)
        if not url:
            return None
        
        try:
            response = requests.get(url, timeout=300)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Failed to download enhanced image: {e}")
            return None
    
    def is_status_final(self, status: str) -> bool:
        """
        Check if a status value indicates processing is complete.
        
        Args:
            status: Status string from check_status()
            
        Returns:
            True if no more polling needed
        """
        final_statuses = {'completed', 'failed', 'error', 'cancelled'}
        return status.lower() in final_statuses
    
    def normalize_status(self, raw_status: str) -> EnhancementStatus:
        """
        Normalize provider-specific status to standard enum.
        
        Args:
            raw_status: Raw status from provider API
            
        Returns:
            Normalized EnhancementStatus
        """
        status_lower = raw_status.lower()
        
        if status_lower in ('completed', 'done', 'success', 'finished'):
            return EnhancementStatus.COMPLETED
        elif status_lower in ('failed', 'error', 'cancelled'):
            return EnhancementStatus.FAILED
        elif status_lower in ('in_progress', 'processing', 'running'):
            return EnhancementStatus.IN_PROGRESS
        elif status_lower in ('pending', 'queued', 'waiting'):
            return EnhancementStatus.PENDING
        else:
            return EnhancementStatus.UNKNOWN
