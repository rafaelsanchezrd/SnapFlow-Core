"""
Integration Tests: Fotello Enhancement Provider
=================================================
Tests real Fotello API calls.
Requires TEST_FOTELLO_API_KEY environment variable.

WARNING: These tests may consume API credits!

Run with: pytest tests/integration/test_fotello.py -v
"""

import pytest
import time


@pytest.mark.integration
@pytest.mark.fotello
class TestFotelloConnection:
    """Test Fotello connection and authentication."""
    
    def test_connects_successfully(self, fotello_provider):
        """Should connect with valid API key."""
        assert fotello_provider.is_connected()
    
    def test_gets_provider_info(self, fotello_provider):
        """Should return correct provider info."""
        assert fotello_provider.get_provider_type() == "fotello"
        assert fotello_provider.get_provider_name() == "Fotello"


@pytest.mark.integration
@pytest.mark.fotello
class TestFotelloUpload:
    """Test uploading images to Fotello."""
    
    def test_gets_presigned_url(self, fotello_provider):
        """Should get presigned URL for upload."""
        # This tests the createUpload endpoint
        result = fotello_provider._get_presigned_url("test_image.jpg")
        
        assert 'url' in result
        assert 'id' in result
        print(f"Got presigned URL with ID: {result['id']}")
    
    def test_uploads_image(self, fotello_provider, sample_image_bytes):
        """Should upload an image successfully."""
        upload_id = fotello_provider.upload_image(
            "test_integration.jpg",
            sample_image_bytes
        )
        
        assert upload_id is not None
        assert len(upload_id) > 0
        print(f"Uploaded image with ID: {upload_id}")


@pytest.mark.integration
@pytest.mark.fotello
@pytest.mark.slow
class TestFotelloEnhancement:
    """Test enhancement workflow.
    
    WARNING: This consumes API credits!
    """
    
    def test_requests_enhancement(self, fotello_provider, sample_image_bytes):
        """Should request enhancement for uploaded image."""
        # Upload first
        upload_id = fotello_provider.upload_image(
            "test_enhance.jpg",
            sample_image_bytes
        )
        
        # Request enhancement
        enhancement_id = fotello_provider.request_enhancement(
            upload_ids=[upload_id],
            listing_id="test-integration-listing"
        )
        
        assert enhancement_id is not None
        print(f"Enhancement requested with ID: {enhancement_id}")
    
    def test_checks_enhancement_status(self, fotello_provider, sample_image_bytes):
        """Should check status of enhancement request."""
        # Upload and request enhancement
        upload_id = fotello_provider.upload_image(
            "test_status.jpg",
            sample_image_bytes
        )
        
        enhancement_id = fotello_provider.request_enhancement(
            upload_ids=[upload_id],
            listing_id="test-status-listing"
        )
        
        # Check status immediately (will be pending or in_progress)
        status = fotello_provider.check_status(enhancement_id)
        
        assert 'status' in status
        assert status['status'] in ['pending', 'in_progress', 'completed', 'failed']
        print(f"Enhancement status: {status['status']}")
    
    @pytest.mark.skip(reason="Full enhancement takes 1-2 minutes and costs credits")
    def test_full_enhancement_cycle(self, fotello_provider, sample_image_bytes):
        """Full enhancement cycle - upload, enhance, poll until complete."""
        # Upload
        upload_id = fotello_provider.upload_image(
            "test_full_cycle.jpg",
            sample_image_bytes
        )
        
        # Request enhancement
        enhancement_id = fotello_provider.request_enhancement(
            upload_ids=[upload_id],
            listing_id="test-full-cycle"
        )
        
        # Poll for completion (max 3 minutes)
        max_attempts = 18  # 18 * 10 seconds = 3 minutes
        for attempt in range(max_attempts):
            status = fotello_provider.check_status(enhancement_id)
            
            if status['status'] == 'completed':
                assert 'enhanced_image_url' in status
                print(f"Enhancement completed after {attempt * 10} seconds")
                print(f"Result URL: {status['enhanced_image_url'][:50]}...")
                return
            
            elif status['status'] == 'failed':
                pytest.fail(f"Enhancement failed: {status.get('error', 'Unknown error')}")
            
            print(f"Attempt {attempt + 1}: status = {status['status']}")
            time.sleep(10)
        
        pytest.fail("Enhancement did not complete within 3 minutes")
