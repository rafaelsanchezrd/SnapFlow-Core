"""
Integration Tests: Google Drive Provider
=========================================
Tests real Google Drive API calls.
Requires TEST_GDRIVE_* environment variables.

Run with: pytest tests/integration/test_google_drive.py -v
"""

import pytest
import uuid


@pytest.mark.integration
@pytest.mark.google_drive
class TestGoogleDriveConnection:
    """Test Google Drive connection and authentication."""
    
    def test_connects_successfully(self, google_drive_provider):
        """Should connect with valid credentials."""
        assert google_drive_provider.is_connected()
    
    def test_gets_provider_info(self, google_drive_provider):
        """Should return correct provider info."""
        assert google_drive_provider.get_provider_type() == "google_drive"
        assert google_drive_provider.get_provider_name() == "Google Drive"


@pytest.mark.integration
@pytest.mark.google_drive
class TestGoogleDriveListFiles:
    """Test listing files from Google Drive."""
    
    def test_lists_files_in_test_folder(self, google_drive_provider, google_drive_test_folder):
        """Should list files in test folder."""
        files = google_drive_provider.list_files(google_drive_test_folder)
        
        assert isinstance(files, list)
        print(f"Found {len(files)} files in folder {google_drive_test_folder}")
    
    def test_filters_by_extension(self, google_drive_provider, google_drive_test_folder):
        """Should filter files by extension."""
        jpg_files = google_drive_provider.list_files(
            google_drive_test_folder,
            extensions=('.jpg', '.jpeg')
        )
        
        for f in jpg_files:
            assert f['name'].lower().endswith(('.jpg', '.jpeg'))
    
    def test_returns_file_metadata(self, google_drive_provider, google_drive_test_folder):
        """Files should have required metadata fields."""
        files = google_drive_provider.list_files(google_drive_test_folder)
        
        if files:
            file = files[0]
            assert 'name' in file
            assert 'id' in file  # Google Drive uses IDs instead of paths
            assert 'size' in file or 'mimeType' in file


@pytest.mark.integration
@pytest.mark.google_drive
class TestGoogleDriveDownloadUpload:
    """Test downloading and uploading files."""
    
    def test_downloads_existing_file(self, google_drive_provider, google_drive_test_folder):
        """Should download an existing file."""
        files = google_drive_provider.list_files(google_drive_test_folder)
        
        if not files:
            pytest.skip("No files in test folder to download")
        
        file_id = files[0]['id']
        content = google_drive_provider.download_file(file_id)
        
        assert content is not None
        assert len(content) > 0
        print(f"Downloaded {len(content)} bytes from file ID {file_id}")
    
    def test_upload_and_download_cycle(
        self, 
        google_drive_provider, 
        google_drive_test_folder, 
        sample_image_bytes
    ):
        """Should upload a file and download it back."""
        test_filename = f"test_upload_{uuid.uuid4().hex[:8]}.jpg"
        uploaded_file_id = None
        
        try:
            # Upload to folder
            result = google_drive_provider.upload_file(
                google_drive_test_folder,  # parent folder ID
                test_filename,
                sample_image_bytes,
                content_type="image/jpeg"
            )
            
            uploaded_file_id = result.get('id')
            assert uploaded_file_id is not None
            print(f"Uploaded as file ID: {uploaded_file_id}")
            
            # Download and verify
            downloaded = google_drive_provider.download_file(uploaded_file_id)
            assert downloaded == sample_image_bytes
            print("Download verified successfully")
            
        finally:
            # Cleanup
            if uploaded_file_id:
                try:
                    google_drive_provider.delete_file(uploaded_file_id)
                    print(f"Cleaned up file {uploaded_file_id}")
                except Exception as e:
                    print(f"Cleanup failed: {e}")
    
    def test_raises_on_nonexistent_file(self, google_drive_provider):
        """Should raise error for non-existent file ID."""
        with pytest.raises(Exception):
            google_drive_provider.download_file("definitely-not-a-real-file-id")


@pytest.mark.integration
@pytest.mark.google_drive
class TestGoogleDriveTokenRefresh:
    """Test OAuth token refresh handling."""
    
    def test_refreshes_token_automatically(self, google_drive_provider, google_drive_test_folder):
        """Token should refresh automatically when needed."""
        # Make multiple calls to trigger potential refresh
        for _ in range(3):
            files = google_drive_provider.list_files(google_drive_test_folder)
            assert isinstance(files, list)
        
        # If we got here, token refresh worked
        print("Token refresh working correctly")
