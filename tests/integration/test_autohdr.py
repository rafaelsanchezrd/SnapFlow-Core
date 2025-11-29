"""
Integration Tests: AutoHDR Enhancement Provider
=================================================
Tests real AutoHDR API calls.
Requires TEST_AUTOHDR_* environment variables.

WARNING: These tests may consume API credits!

Run with: pytest tests/integration/test_autohdr.py -v
"""

import pytest
import uuid


@pytest.mark.integration
@pytest.mark.autohdr
class TestAutoHDRConnection:
    """Test AutoHDR connection and authentication."""
    
    def test_connects_successfully(self, autohdr_provider):
        """Should connect with valid credentials."""
        assert autohdr_provider.is_connected()
    
    def test_gets_provider_info(self, autohdr_provider):
        """Should return correct provider info."""
        assert autohdr_provider.get_provider_type() == "autohdr"
        assert autohdr_provider.get_provider_name() == "AutoHDR"


@pytest.mark.integration
@pytest.mark.autohdr
class TestAutoHDRPhotoshoot:
    """Test AutoHDR photoshoot workflow."""
    
    def test_creates_photoshoot_with_presigned_urls(self, autohdr_provider, sample_image_bytes):
        """Should create photoshoot and get presigned S3 URLs."""
        unique_id = str(uuid.uuid4())
        
        result = autohdr_provider.upload_batch(
            images=[("test_image.jpg", sample_image_bytes)],
            unique_identifier=unique_id,
            address="123 Test Street",
            auto_finalize=False  # Don't finalize yet
        )
        
        assert result.get('success') or result.get('listing_id')
        print(f"Photoshoot created: {result}")
    
    def test_uploads_to_s3_presigned_url(self, autohdr_provider, sample_image_bytes):
        """Should upload files to S3 using presigned URLs."""
        unique_id = str(uuid.uuid4())
        
        result = autohdr_provider.upload_batch(
            images=[
                ("test_image_1.jpg", sample_image_bytes),
                ("test_image_2.jpg", sample_image_bytes),
            ],
            unique_identifier=unique_id,
            address="456 Test Avenue",
            auto_finalize=True
        )
        
        assert result.get('successful_uploads', 0) >= 1
        print(f"Uploaded {result.get('successful_uploads')} files")


@pytest.mark.integration
@pytest.mark.autohdr
class TestAutoHDRFinalize:
    """Test AutoHDR photoshoot finalization."""
    
    def test_finalizes_photoshoot(self, autohdr_provider, sample_image_bytes):
        """Should finalize photoshoot to trigger processing."""
        unique_id = str(uuid.uuid4())
        
        # Upload without auto-finalize
        result = autohdr_provider.upload_batch(
            images=[("test_finalize.jpg", sample_image_bytes)],
            unique_identifier=unique_id,
            address="789 Finalize Lane",
            auto_finalize=False
        )
        
        # Manually finalize
        finalized = autohdr_provider.finalize_photoshoot(unique_id)
        
        assert finalized is True
        print(f"Photoshoot {unique_id} finalized successfully")


@pytest.mark.integration
@pytest.mark.autohdr
class TestAutoHDRStatus:
    """Test AutoHDR status checking."""
    
    def test_status_indicates_webhook_based(self, autohdr_provider):
        """AutoHDR status should indicate webhook-based delivery."""
        # AutoHDR doesn't have polling - results come via webhook
        status = autohdr_provider.check_status("test-enhancement-id")
        
        assert status.get('status') == 'webhook_based'
        assert 'webhook' in status.get('message', '').lower()


@pytest.mark.integration
@pytest.mark.autohdr
class TestAutoHDRBracketUpload:
    """Test bracket-based upload workflow."""
    
    def test_uploads_bracket(self, autohdr_provider, sample_image_bytes):
        """Should upload a bracket of images."""
        bracket_files = [
            {'name': 'bracket_1.jpg', 'bytes': sample_image_bytes},
            {'name': 'bracket_2.jpg', 'bytes': sample_image_bytes},
            {'name': 'bracket_3.jpg', 'bytes': sample_image_bytes},
        ]
        
        result = autohdr_provider.upload_bracket(
            bracket_files=bracket_files,
            listing_id="test-bracket-listing",
            bracket_index=0,
            address="Bracket Test Address"
        )
        
        assert result.get('success') or result.get('files_uploaded', 0) > 0
        print(f"Bracket uploaded: {result.get('files_uploaded')} files")
