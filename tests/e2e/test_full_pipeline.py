"""
End-to-End Tests: Full Pipeline
================================
Tests complete workflows from storage to enhancement.

WARNING: These tests are slow and consume API credits!

Run with: pytest tests/e2e/test_full_pipeline.py -v
"""

import pytest
import time
import uuid


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.dropbox
@pytest.mark.fotello
class TestDropboxFotelloPipeline:
    """Test complete Dropbox → Fotello → Dropbox pipeline."""
    
    def test_download_upload_enhance(
        self,
        dropbox_provider,
        fotello_provider,
        dropbox_test_folder
    ):
        """
        Full pipeline test:
        1. List files from Dropbox test folder
        2. Download first image
        3. Upload to Fotello
        4. Request enhancement
        5. Verify enhancement ID returned
        """
        # 1. List files
        files = dropbox_provider.list_files(
            dropbox_test_folder,
            extensions=('.jpg', '.jpeg')
        )
        
        if not files:
            pytest.skip("No JPEG files in Dropbox test folder")
        
        print(f"Found {len(files)} files, using: {files[0]['name']}")
        
        # 2. Download
        file_path = files[0]['path_lower']
        content = dropbox_provider.download_file(file_path)
        
        assert len(content) > 0
        print(f"Downloaded {len(content)} bytes")
        
        # 3. Upload to Fotello
        upload_id = fotello_provider.upload_image(
            files[0]['name'],
            content
        )
        
        assert upload_id is not None
        print(f"Uploaded to Fotello: {upload_id}")
        
        # 4. Request enhancement
        enhancement_id = fotello_provider.request_enhancement(
            upload_ids=[upload_id],
            listing_id=f"e2e-test-{uuid.uuid4().hex[:8]}"
        )
        
        assert enhancement_id is not None
        print(f"Enhancement requested: {enhancement_id}")
        
        # 5. Verify status is accessible
        status = fotello_provider.check_status(enhancement_id)
        
        assert 'status' in status
        print(f"Enhancement status: {status['status']}")
    
    @pytest.mark.skip(reason="Full cycle takes 2+ minutes and costs credits")
    def test_full_cycle_with_result_upload(
        self,
        dropbox_provider,
        fotello_provider,
        dropbox_test_folder
    ):
        """
        Complete cycle including waiting for result and uploading back.
        
        This test:
        1. Downloads from Dropbox
        2. Uploads to Fotello
        3. Waits for enhancement
        4. Downloads enhanced image
        5. Uploads back to Dropbox
        """
        # Get test image
        files = dropbox_provider.list_files(
            dropbox_test_folder,
            extensions=('.jpg', '.jpeg')
        )
        
        if not files:
            pytest.skip("No test files available")
        
        content = dropbox_provider.download_file(files[0]['path_lower'])
        
        # Upload and enhance
        upload_id = fotello_provider.upload_image(files[0]['name'], content)
        enhancement_id = fotello_provider.request_enhancement(
            upload_ids=[upload_id],
            listing_id=f"e2e-full-{uuid.uuid4().hex[:8]}"
        )
        
        # Wait for completion (max 3 minutes)
        enhanced_url = None
        for attempt in range(18):
            status = fotello_provider.check_status(enhancement_id)
            
            if status['status'] == 'completed':
                enhanced_url = status.get('enhanced_image_url')
                break
            elif status['status'] == 'failed':
                pytest.fail(f"Enhancement failed: {status}")
            
            print(f"Waiting... status: {status['status']}")
            time.sleep(10)
        
        if not enhanced_url:
            pytest.fail("Enhancement did not complete in time")
        
        # Download enhanced image
        import requests
        response = requests.get(enhanced_url, timeout=60)
        response.raise_for_status()
        enhanced_content = response.content
        
        print(f"Downloaded enhanced image: {len(enhanced_content)} bytes")
        
        # Upload back to Dropbox
        result_path = f"{dropbox_test_folder}/enhanced/{files[0]['name']}"
        dropbox_provider.upload_file(result_path, enhanced_content)
        
        print(f"Uploaded result to: {result_path}")


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.google_drive
@pytest.mark.fotello
class TestGoogleDriveFotelloPipeline:
    """Test complete Google Drive → Fotello → Google Drive pipeline."""
    
    def test_download_upload_enhance(
        self,
        google_drive_provider,
        fotello_provider,
        google_drive_test_folder
    ):
        """
        Full pipeline test with Google Drive as storage.
        """
        # 1. List files
        files = google_drive_provider.list_files(
            google_drive_test_folder,
            extensions=('.jpg', '.jpeg')
        )
        
        if not files:
            pytest.skip("No JPEG files in Google Drive test folder")
        
        print(f"Found {len(files)} files, using: {files[0]['name']}")
        
        # 2. Download
        content = google_drive_provider.download_file(files[0]['id'])
        
        assert len(content) > 0
        print(f"Downloaded {len(content)} bytes")
        
        # 3. Upload to Fotello
        upload_id = fotello_provider.upload_image(
            files[0]['name'],
            content
        )
        
        assert upload_id is not None
        print(f"Uploaded to Fotello: {upload_id}")
        
        # 4. Request enhancement
        enhancement_id = fotello_provider.request_enhancement(
            upload_ids=[upload_id],
            listing_id=f"gdrive-e2e-{uuid.uuid4().hex[:8]}"
        )
        
        assert enhancement_id is not None
        print(f"Enhancement requested: {enhancement_id}")


@pytest.mark.e2e
@pytest.mark.slow
@pytest.mark.dropbox
@pytest.mark.autohdr
class TestDropboxAutoHDRPipeline:
    """Test Dropbox → AutoHDR pipeline."""
    
    def test_download_upload_to_autohdr(
        self,
        dropbox_provider,
        autohdr_provider,
        dropbox_test_folder
    ):
        """
        Pipeline test with AutoHDR enhancement.
        Note: AutoHDR uses webhooks, so we can only verify upload success.
        """
        # Get test images
        files = dropbox_provider.list_files(
            dropbox_test_folder,
            extensions=('.jpg', '.jpeg')
        )
        
        if len(files) < 2:
            pytest.skip("Need at least 2 JPEG files for AutoHDR bracket")
        
        # Download multiple files for bracket
        images = []
        for file in files[:3]:  # Use up to 3 files
            content = dropbox_provider.download_file(file['path_lower'])
            images.append((file['name'], content))
        
        print(f"Downloaded {len(images)} images for bracket")
        
        # Upload batch to AutoHDR
        result = autohdr_provider.upload_batch(
            images=images,
            unique_identifier=str(uuid.uuid4()),
            address="E2E Test Property",
            auto_finalize=True
        )
        
        assert result.get('successful_uploads', 0) > 0
        print(f"AutoHDR upload result: {result.get('successful_uploads')} files uploaded")


@pytest.mark.e2e
class TestCredentialDecryptionPipeline:
    """Test credential decryption in pipeline context."""
    
    def test_decrypts_and_creates_providers(self, mock_env, encryption_key):
        """Should decrypt credentials and create providers."""
        from shared import decrypt_credentials, StorageFactory
        from cryptography.fernet import Fernet
        import os
        
        # Setup encrypted credentials
        fernet = Fernet(encryption_key.encode())
        
        mock_env({
            "CLIENT_E2E_ENCRYPTION_KEY": encryption_key,
            "TEST_DROPBOX_APP_KEY": os.getenv("TEST_DROPBOX_APP_KEY", "skip"),
            "TEST_DROPBOX_APP_SECRET": os.getenv("TEST_DROPBOX_APP_SECRET", "skip"),
            "TEST_DROPBOX_REFRESH_TOKEN": os.getenv("TEST_DROPBOX_REFRESH_TOKEN", "skip"),
        })
        
        # Skip if real credentials not available
        if os.getenv("TEST_DROPBOX_APP_KEY") == "skip":
            pytest.skip("Dropbox credentials not configured")
        
        # Create encrypted payload (like Make.com would send)
        encrypted_payload = {
            "client_id": "E2E",
            "dropbox_app_key_encrypted": fernet.encrypt(
                os.getenv("TEST_DROPBOX_APP_KEY").encode()
            ).decode(),
            "dropbox_app_secret_encrypted": fernet.encrypt(
                os.getenv("TEST_DROPBOX_APP_SECRET").encode()
            ).decode(),
            "dropbox_refresh_token_encrypted": fernet.encrypt(
                os.getenv("TEST_DROPBOX_REFRESH_TOKEN").encode()
            ).decode(),
        }
        
        # Decrypt (like gateway function does)
        decrypted = decrypt_credentials(encrypted_payload, "E2E")
        
        # Verify decryption worked
        assert decrypted["dropbox_app_key"] == os.getenv("TEST_DROPBOX_APP_KEY")
        
        # Create provider with decrypted credentials
        provider = StorageFactory.create("dropbox", {
            "app_key": decrypted["dropbox_app_key"],
            "app_secret": decrypted["dropbox_app_secret"],
            "refresh_token": decrypted["dropbox_refresh_token"],
        })
        
        assert provider.is_connected()
        print("Full credential decryption → provider creation pipeline works!")
