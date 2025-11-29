"""
Fotello Enhancement Provider
============================
Fotello API implementation for real estate photo enhancement.

Features:
- Presigned URL upload workflow
- Bracket-based enhancement requests
- Status polling with retry logic
- Content-type detection for RAW files
"""

import requests
from typing import List, Dict, Any, Optional

from .base import BaseEnhancementProvider, EnhancementStatus
from ...config.constants import (
    FOTELLO_UPLOAD_ENDPOINT,
    FOTELLO_ENHANCE_ENDPOINT,
    FOTELLO_GET_ENHANCE_ENDPOINT,
    BASE_UPLOAD_TIMEOUT,
    MAX_UPLOAD_TIMEOUT,
)
from ...utils.file_utils import (
    get_content_type_for_file,
    get_file_type_info,
    calculate_upload_timeout,
)


class FotelloProvider(BaseEnhancementProvider):
    """
    Fotello enhancement API provider.
    
    Fotello uses a presigned URL workflow:
    1. Request presigned URL via createUpload
    2. Upload file directly to presigned URL
    3. Request enhancement via createEnhance with upload IDs
    4. Poll getEnhance for completion status
    
    API Endpoints:
    - createUpload: Get presigned URL for file upload
    - createEnhance: Request bracket enhancement
    - getEnhance: Check enhancement status
    """
    
    def __init__(self, api_key: str):
        """
        Initialize Fotello provider.
        
        Args:
            api_key: Fotello API key for authentication
        """
        self.api_key = api_key
        self._headers = {
            'Content-Type': 'application/json',
            'Authorization': api_key,
        }
    
    def upload_image(
        self,
        filename: str,
        data: bytes,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload an image to Fotello.
        
        Workflow:
        1. Request presigned URL from createUpload
        2. Upload file bytes to presigned URL
        3. Return upload_id for enhancement request
        
        Args:
            filename: Original filename
            data: Image data as bytes
            content_type: Optional MIME type (auto-detected if not provided)
            
        Returns:
            Upload ID string
        """
        file_size = len(data)
        file_size_mb = file_size / (1024 * 1024)
        
        # Get file type info for timeout calculation
        file_type, type_config = get_file_type_info(filename)
        timeout = calculate_upload_timeout(filename, file_size)
        
        print(f"Uploading {filename} ({file_size_mb:.1f}MB, type: {file_type})")
        
        # Step 1: Get presigned URL
        presigned_data = self._get_presigned_url(filename)
        presigned_url = presigned_data.get('url')
        upload_id = presigned_data.get('id')
        
        if not presigned_url or not upload_id:
            raise ValueError(f"Invalid presigned response for {filename}")
        
        print(f"Got presigned URL for {filename}, upload_id: {upload_id}")
        
        # Step 2: Determine content type
        if not content_type:
            content_type = get_content_type_for_file(filename)
        
        print(f"Using Content-Type: {content_type}")
        
        # Step 3: Upload to presigned URL
        # Note: Fotello presigned URLs expect application/octet-stream
        try:
            upload_response = requests.put(
                presigned_url,
                data=data,
                headers={'Content-Type': 'application/octet-stream'},
                timeout=timeout,
            )
            upload_response.raise_for_status()
            
            print(f"Successfully uploaded {filename} ({file_size_mb:.1f}MB)")
            return upload_id
            
        except requests.exceptions.HTTPError as e:
            status_code = getattr(e.response, 'status_code', None)
            response_text = getattr(e.response, 'text', 'No response')
            
            if status_code == 403:
                print(f"403 Forbidden for {filename} - possible Content-Type mismatch")
            
            raise IOError(
                f"Upload failed for {filename}: HTTP {status_code} - {response_text}"
            )
    
    def _get_presigned_url(self, filename: str) -> Dict[str, Any]:
        """
        Request presigned URL from Fotello createUpload endpoint.
        
        Args:
            filename: Filename for the upload
            
        Returns:
            Response dict with 'url' and 'id' fields
        """
        try:
            response = requests.post(
                FOTELLO_UPLOAD_ENDPOINT,
                json={'filename': filename},
                headers=self._headers,
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise IOError(f"Failed to get presigned URL for {filename}: {e}")
    
    def request_enhancement(
        self,
        upload_ids: List[str],
        listing_id: str,
        **kwargs,
    ) -> str:
        """
        Request enhancement for uploaded images.
        
        Args:
            upload_ids: List of upload IDs from upload_image()
            listing_id: Listing identifier for tracking
            **kwargs: Additional options:
                - shot_type: Type of shot ('interior', 'exterior', etc.)
                
        Returns:
            Enhancement ID for status tracking
        """
        shot_type = kwargs.get('shot_type', 'interior')
        
        payload = {
            'upload_ids': upload_ids,
            'listing_id': listing_id,
            'shot_type': shot_type,
        }
        
        try:
            response = requests.post(
                FOTELLO_ENHANCE_ENDPOINT,
                json=payload,
                headers=self._headers,
                timeout=60,
            )
            response.raise_for_status()
            
            response_data = response.json()
            enhancement_id = response_data.get('id')
            
            if not enhancement_id:
                raise ValueError(f"No enhancement ID in response: {response_data}")
            
            print(f"Enhancement requested: {enhancement_id}")
            return enhancement_id
            
        except requests.exceptions.RequestException as e:
            raise IOError(f"Enhancement request failed: {e}")
    
    def check_status(self, enhancement_id: str) -> Dict[str, Any]:
        """
        Check enhancement status.
        
        Args:
            enhancement_id: Enhancement ID from request_enhancement()
            
        Returns:
            Status dictionary with:
            - status: 'pending', 'in_progress', 'completed', 'failed'
            - enhanced_image_url: URL when completed
            - enhanced_image_url_expires: Expiration timestamp
            - error: Error message when failed
        """
        try:
            response = requests.get(
                f"{FOTELLO_GET_ENHANCE_ENDPOINT}?id={enhancement_id}",
                headers={'Authorization': self.api_key},
                timeout=30,
            )
            response.raise_for_status()
            
            result = response.json()
            status = result.get('status', 'unknown')
            
            print(f"Enhancement {enhancement_id} status: {status}")
            
            # Normalize response
            normalized = {
                'status': status,
                'enhancement_id': enhancement_id,
            }
            
            if status == 'completed':
                normalized['enhanced_image_url'] = result.get('enhanced_image_url')
                normalized['enhanced_image_url_expires'] = result.get('enhanced_image_url_expires')
            elif status == 'failed':
                normalized['error'] = result.get('error', 'Enhancement failed')
            
            return normalized
            
        except requests.exceptions.RequestException as e:
            raise IOError(f"Status check failed for {enhancement_id}: {e}")
    
    def get_provider_type(self) -> str:
        """Get provider type identifier."""
        return "fotello"
    
    def get_provider_name(self) -> str:
        """Get human-readable provider name."""
        return "Fotello"
    
    def upload_bracket(
        self,
        bracket_files: List[Dict[str, Any]],
        bracket_index: int,
        listing_id: str,
        callback_webhook: Optional[str] = None,
        job_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Upload and enhance a complete bracket.
        
        Convenience method that handles the full upload + enhancement flow
        for a bracket of images.
        
        Args:
            bracket_files: List of {'name': str, 'bytes': bytes} dicts
            bracket_index: Index of this bracket (for logging)
            listing_id: Listing identifier
            callback_webhook: Optional webhook for notifications
            job_id: Optional job ID for tracking
            correlation_id: Optional correlation ID
            
        Returns:
            Dictionary with:
            - enhancement_id: Enhancement ID
            - upload_ids: List of upload IDs
            - file_count: Number of files uploaded
        """
        import gc
        from ...utils.memory_utils import clear_large_object
        
        upload_ids = []
        
        for file_info in bracket_files:
            filename = file_info['name']
            file_bytes = file_info['bytes']
            
            if not file_bytes:
                print(f"Skipping {filename} - no data")
                continue
            
            try:
                upload_id = self.upload_image(filename, file_bytes)
                upload_ids.append(upload_id)
                
                # Clear memory immediately after upload
                file_info['bytes'] = None
                
                # Force GC for large files
                file_size_mb = len(file_bytes) / (1024 * 1024)
                if file_size_mb > 50:
                    gc.collect()
                    
            except Exception as e:
                print(f"Failed to upload {filename}: {e}")
                file_info['bytes'] = None
                continue
        
        # Clean up
        bracket_files.clear()
        gc.collect()
        
        if not upload_ids:
            raise ValueError(f"No files uploaded successfully for bracket {bracket_index + 1}")
        
        # Request enhancement
        enhancement_id = self.request_enhancement(
            upload_ids=upload_ids,
            listing_id=listing_id,
            shot_type='interior',
        )
        
        return {
            'enhancement_id': enhancement_id,
            'upload_ids': upload_ids,
            'file_count': len(upload_ids),
            'bracket_index': bracket_index,
        }
