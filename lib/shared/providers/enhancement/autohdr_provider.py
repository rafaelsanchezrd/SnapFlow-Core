"""
AutoHDR Enhancement Provider
============================
Implementation based on AutoHDR External API v2.5.3
API Base: https://quantumreachadvertising.com/external-api

Key differences from Fotello API:
- Uses presigned S3 URLs for uploads (not direct presigned URLs)
- Groups files into "photoshoots" with unique_identifier
- Requires finalize step after all uploads complete
- Returns listing_id (equivalent to enhancement_id)
- Webhook-driven for status updates (not polling)
"""

import uuid
import mimetypes
import requests
import gc
from typing import List, Dict, Any, Optional, Tuple

from .base import BaseEnhancementProvider, EnhancementStatus


class AutoHDRProvider(BaseEnhancementProvider):
    """
    AutoHDR enhancement provider implementation.
    
    Workflow:
    1. Create photoshoot with presigned URLs (create-photoshoot-with-presigned-urls)
    2. Upload files directly to S3 using presigned URLs
    3. Finalize photoshoot (finalize-photoshoot-upload)
    4. AutoHDR processes and sends webhook when complete
    
    Note: AutoHDR is primarily webhook-driven. The check_status method
    provides basic status checking but webhooks are the recommended approach.
    """
    
    API_BASE_URL = "https://quantumreachadvertising.com/external-api"
    
    # AutoHDR-specific status mapping
    STATUS_MAPPING = {
        'pending': EnhancementStatus.PENDING,
        'processing': EnhancementStatus.IN_PROGRESS,
        'in_progress': EnhancementStatus.IN_PROGRESS,
        'completed': EnhancementStatus.COMPLETED,
        'complete': EnhancementStatus.COMPLETED,
        'failed': EnhancementStatus.FAILED,
        'error': EnhancementStatus.FAILED
    }
    
    def __init__(self, api_key: str, email: str = None):
        """
        Initialize AutoHDR provider.
        
        Args:
            api_key: AutoHDR API key (Bearer token)
            email: AutoHDR account email (required for all API calls)
        """
        self.api_key = api_key.strip() if api_key else ""
        self.email = email
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {self.api_key}',
            'Accept': 'application/json'
        })
        self._connected = False
        
        # Track active photoshoots for batch operations
        self._active_photoshoots: Dict[str, Dict] = {}
    
    def get_provider_type(self) -> str:
        """Get provider type identifier."""
        return "autohdr"
    
    def get_provider_name(self) -> str:
        """Get human-readable provider name."""
        return "AutoHDR"
    
    def connect(self, credentials: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate API key with AutoHDR.
        
        Args:
            credentials: Optional override credentials (api_key, email)
            
        Returns:
            True if connection successful
            
        Raises:
            ConnectionError: If API key is invalid
        """
        if credentials:
            if 'api_key' in credentials:
                self.api_key = credentials['api_key'].strip()
                self.session.headers['Authorization'] = f'Bearer {self.api_key}'
            if 'email' in credentials:
                self.email = credentials['email']
        
        print(f"→ Validating AutoHDR API key...")
        
        try:
            response = self.session.get(
                f"{self.API_BASE_URL}/v1/user/profile",
                timeout=10
            )
            
            if response.status_code == 401:
                error_detail = "Invalid or inactive API key"
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', error_detail)
                except:
                    pass
                raise ConnectionError(f"AutoHDR authentication failed: {error_detail}")
            
            elif response.status_code == 404:
                # Profile endpoint may not exist, consider valid
                print("  ⚠️ Profile endpoint not available, will validate on first request")
                self._connected = True
                return True
            
            elif response.status_code not in [200, 201]:
                raise ConnectionError(f"AutoHDR API error: {response.status_code}")
            
            print("✓ AutoHDR API key validated")
            self._connected = True
            return True
            
        except requests.exceptions.Timeout:
            raise ConnectionError("AutoHDR API validation timeout")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"AutoHDR connection error: {e}")
    
    def upload_image(
        self,
        filename: str,
        data: bytes,
        content_type: Optional[str] = None,
    ) -> str:
        """
        Upload a single image to AutoHDR.
        
        Note: AutoHDR works best with batch uploads. For single files,
        this creates a photoshoot with one image.
        
        Args:
            filename: Original filename
            data: Image bytes
            content_type: MIME type (auto-detected if not provided)
            
        Returns:
            Upload ID (listing_id from photoshoot creation)
        """
        if not self.email:
            raise ValueError("AutoHDR email required for uploads. Set email on provider.")
        
        # For single uploads, create a mini photoshoot
        unique_id = str(uuid.uuid4())
        
        result = self.upload_batch(
            images=[(filename, data)],
            unique_identifier=unique_id,
            address=f"Single upload {filename}"
        )
        
        if not result.get('success'):
            raise IOError(f"Upload failed: {result.get('error', 'Unknown error')}")
        
        # Return listing_id as the upload identifier
        return result.get('listing_id', unique_id)
    
    def upload_batch(
        self,
        images: List[Tuple[str, bytes]],
        unique_identifier: str,
        address: str,
        twilight: bool = False,
        upload_callback_url: Optional[str] = None,
        status_callback_url: Optional[str] = None,
        metadata: Optional[Dict] = None,
        auto_finalize: bool = True
    ) -> Dict[str, Any]:
        """
        Upload a batch of images to AutoHDR using presigned S3 URLs.
        
        This is the recommended method for AutoHDR uploads.
        
        Args:
            images: List of (filename, file_bytes) tuples
            unique_identifier: UUID for grouping files into photoshoot
            address: Property address (photoshoot identifier)
            twilight: Enable twilight processing
            upload_callback_url: Webhook for upload notifications
            status_callback_url: Webhook for processing status updates
            metadata: Additional metadata
            auto_finalize: Whether to finalize after upload (default True)
            
        Returns:
            Dict with success status, listing_id, and upload details
        """
        if not self.email:
            return {'success': False, 'error': 'AutoHDR email required for uploads'}
        
        print(f"→ Requesting presigned URLs for {len(images)} files...")
        
        try:
            # Step 1: Request presigned URLs
            file_list = [{"filename": filename} for filename, _ in images]
            
            presigned_request = {
                'email': self.email,
                'unique_identifier': unique_identifier,
                'files': file_list,
                'address': address,
                'twilight': twilight,
                'upload_callback_url': upload_callback_url or 'https://example.com/webhook',
                'status_callback_url': status_callback_url or 'https://example.com/webhook'
            }
            
            response = self.session.post(
                f"{self.API_BASE_URL}/v1/create-photoshoot-with-presigned-urls",
                json=presigned_request,
                timeout=30
            )
            
            if response.status_code not in [200, 201]:
                raise IOError(f"Presigned URL request failed: {response.status_code} - {response.text}")
            
            presigned_data = response.json()
            listing_id = presigned_data.get('id')
            presigned_urls = presigned_data.get('uploaded_files', [])
            
            if len(presigned_urls) != len(images):
                raise IOError(
                    f"URL count mismatch: got {len(presigned_urls)}, expected {len(images)}"
                )
            
            print(f"✓ Received {len(presigned_urls)} presigned URLs (listing_id: {listing_id})")
            
            # Track this photoshoot
            self._active_photoshoots[unique_identifier] = {
                'listing_id': listing_id,
                'address': address,
                'total_files': len(images),
                'uploaded': 0,
                'failed': 0
            }
            
            # Step 2: Upload each file to S3
            print(f"→ Uploading {len(images)} files to S3...")
            
            upload_results = []
            failed_uploads = []
            
            for i, ((filename, file_bytes), presigned_url) in enumerate(zip(images, presigned_urls), 1):
                try:
                    detected_content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
                    
                    s3_response = requests.put(
                        presigned_url,
                        data=file_bytes,
                        headers={'Content-Type': detected_content_type},
                        timeout=300  # 5 minutes per file
                    )
                    
                    if s3_response.status_code in [200, 204]:
                        upload_results.append({
                            'filename': filename,
                            'status': 'success',
                            's3_status': s3_response.status_code
                        })
                        self._active_photoshoots[unique_identifier]['uploaded'] += 1
                    else:
                        failed_uploads.append(filename)
                        upload_results.append({
                            'filename': filename,
                            'status': 'failed',
                            's3_status': s3_response.status_code,
                            'error': s3_response.text[:200]
                        })
                        self._active_photoshoots[unique_identifier]['failed'] += 1
                        
                except Exception as e:
                    failed_uploads.append(filename)
                    upload_results.append({
                        'filename': filename,
                        'status': 'failed',
                        'error': str(e)
                    })
                    self._active_photoshoots[unique_identifier]['failed'] += 1
                
                # Clear file bytes from memory immediately
                file_bytes = None
            
            # Force garbage collection after batch
            gc.collect()
            
            # Step 3: Finalize if requested
            if auto_finalize:
                self.finalize_photoshoot(unique_identifier)
            
            successful_uploads = len([r for r in upload_results if r['status'] == 'success'])
            
            return {
                'success': len(failed_uploads) == 0,
                'listing_id': listing_id,
                'unique_identifier': unique_identifier,
                'total_files': len(images),
                'successful_uploads': successful_uploads,
                'failed_uploads': len(failed_uploads),
                'failed_files': failed_uploads,
                'upload_results': upload_results
            }
            
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'Request timed out'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def finalize_photoshoot(self, unique_identifier: str) -> bool:
        """
        Finalize a photoshoot upload to trigger processing.
        
        Args:
            unique_identifier: The photoshoot's unique identifier
            
        Returns:
            True if finalization successful
        """
        if not self.email:
            print("✗ Cannot finalize: email not set")
            return False
        
        print(f"→ Finalizing photoshoot {unique_identifier}...")
        
        try:
            response = self.session.post(
                f"{self.API_BASE_URL}/v1/finalize-photoshoot-upload",
                json={
                    'email': self.email,
                    'unique_identifier': unique_identifier
                },
                timeout=30
            )
            
            if response.status_code in [200, 201]:
                print(f"✓ Photoshoot finalized successfully")
                return True
            else:
                print(f"⚠️ Finalize returned status {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            print(f"✗ Finalize error: {e}")
            return False
    
    def request_enhancement(
        self,
        upload_ids: List[str],
        listing_id: str,
        **kwargs,
    ) -> str:
        """
        Request enhancement for uploaded images.
        
        Note: For AutoHDR, enhancement is automatically triggered after
        finalize_photoshoot(). This method is provided for API compatibility.
        
        Args:
            upload_ids: List of upload IDs (not used in AutoHDR workflow)
            listing_id: Listing/address identifier
            **kwargs: Additional options (twilight, etc.)
            
        Returns:
            Enhancement ID (same as listing_id for AutoHDR)
        """
        # AutoHDR processes automatically after finalize
        # Return the listing_id as the enhancement reference
        return listing_id
    
    def check_status(self, enhancement_id: str) -> Dict[str, Any]:
        """
        Check enhancement status.
        
        Note: AutoHDR primarily uses webhooks for status updates.
        This method provides basic status checking for compatibility.
        
        Args:
            enhancement_id: The listing_id from upload
            
        Returns:
            Dict with status, enhanced_image_url (if complete), etc.
        """
        # AutoHDR doesn't have a direct status endpoint like Fotello
        # Status comes via webhooks. Return info about this.
        print(f"→ AutoHDR status check for {enhancement_id}")
        print("  Note: AutoHDR uses webhooks for status - check your webhook endpoint")
        
        return {
            'status': 'webhook_based',
            'enhancement_id': enhancement_id,
            'message': 'AutoHDR sends status updates via webhook callbacks',
            'provider': 'autohdr'
        }
    
    def get_result_url(self, enhancement_id: str) -> Optional[str]:
        """
        Get the URL for enhanced image download.
        
        Note: AutoHDR delivers results via webhook callbacks, not polling.
        
        Args:
            enhancement_id: The listing_id
            
        Returns:
            None (results delivered via webhook)
        """
        # AutoHDR doesn't provide a polling endpoint for results
        # Results come via the status_callback_url webhook
        return None
    
    def upload_bracket(
        self,
        bracket_files: List[Dict[str, Any]],
        listing_id: str,
        bracket_index: int,
        address: Optional[str] = None,
        twilight: bool = False,
        callback_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Upload a bracket of images for enhancement.
        
        Convenience method for bracket-based workflows (Fotello compatibility).
        
        Args:
            bracket_files: List of {'name': str, 'bytes': bytes} dicts
            listing_id: Listing identifier
            bracket_index: Bracket number
            address: Property address
            twilight: Enable twilight processing
            callback_url: Webhook for status updates
            
        Returns:
            Dict with listing_id and upload results
        """
        # Convert bracket_files format to images tuple format
        images = [(f['name'], f['bytes']) for f in bracket_files]
        
        # Generate unique identifier for this bracket
        unique_id = f"{listing_id}_bracket_{bracket_index}_{uuid.uuid4().hex[:8]}"
        
        result = self.upload_batch(
            images=images,
            unique_identifier=unique_id,
            address=address or listing_id,
            twilight=twilight,
            status_callback_url=callback_url,
            auto_finalize=True
        )
        
        # Clear bracket file bytes
        for f in bracket_files:
            f['bytes'] = None
        
        return {
            'listing_id': result.get('listing_id'),
            'unique_identifier': unique_id,
            'bracket_index': bracket_index,
            'files_uploaded': result.get('successful_uploads', 0),
            'success': result.get('success', False),
            'error': result.get('error')
        }


def create_autohdr_provider(api_key: str, email: str) -> AutoHDRProvider:
    """
    Factory function to create an AutoHDR provider.
    
    Args:
        api_key: AutoHDR API key
        email: AutoHDR account email
        
    Returns:
        Configured AutoHDRProvider instance
    """
    provider = AutoHDRProvider(api_key, email)
    provider.connect()
    return provider
