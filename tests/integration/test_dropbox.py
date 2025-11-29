"""
Integration Tests: Dropbox Provider
====================================
Tests real Dropbox API calls.
Requires TEST_DROPBOX_* environment variables.

Run with: pytest tests/integration/test_dropbox.py -v
"""

import pytest
import uuid


@pytest.mark.integration
@pytest.mark.dropbox
class TestDropboxConnection:
    """Test Dropbox connection and authentication."""
    
    def test_connects_successfully(self, dropbox_provider):
        """Should connect with valid credentials."""
        assert dropbox_provider.is_connected()
    
    def test_gets_account_info(self, dropbox_provider):
        """Should retrieve account information."""
        # Provider should have account info after connection
        assert dropbox_provider.get_provider_type() == "dropbox"
        assert dropbox_provider.get_provider_name() == "Dropbox"


@pytest.mark.integration
@pytest.mark.dropbox
class TestDropboxListFiles:
    """Test listing files from Dropbox."""
    
    def test_lists_files_in_test_folder(self, dropbox_provider, dropbox_test_folder):
        """Should list files in test folder."""
        files = dropbox_provider.list_files(dropbox_test_folder)
        
        assert isinstance(files, list)
        # Test folder should have at least some files
        print(f"Found {len(files)} files in {dropbox_test_folder}")
    
    def test_filters_by_extension(self, dropbox_provider, dropbox_test_folder):
        """Should filter files by extension."""
        jpg_files = dropbox_provider.list_files(
            dropbox_test_folder, 
            extensions=('.jpg', '.jpeg')
        )
        
        for f in jpg_files:
            assert f['name'].lower().endswith(('.jpg', '.jpeg'))
    
    def test_returns_file_metadata(self, dropbox_provider, dropbox_test_folder):
        """Files should have required metadata fields."""
        files = dropbox_provider.list_files(dropbox_test_folder)
        
        if files:
            file = files[0]
            assert 'name' in file
            assert 'path_lower' in file
            assert 'size' in file


@pytest.mark.integration
@pytest.mark.dropbox
class TestDropboxDownloadUpload:
    """Test downloading and uploading files."""
    
    def test_downloads_existing_file(self, dropbox_provider, dropbox_test_folder):
        """Should download an existing file."""
        files = dropbox_provider.list_files(dropbox_test_folder)
        
        if not files:
            pytest.skip("No files in test folder to download")
        
        file_path = files[0]['path_lower']
        content = dropbox_provider.download_file(file_path)
        
        assert content is not None
        assert len(content) > 0
        print(f"Downloaded {len(content)} bytes from {file_path}")
    
    def test_upload_and_download_cycle(self, dropbox_provider, dropbox_test_folder, sample_image_bytes):
        """Should upload a file and download it back."""
        # Generate unique filename
        test_filename = f"test_upload_{uuid.uuid4().hex[:8]}.jpg"
        test_path = f"{dropbox_test_folder}/{test_filename}"
        
        try:
            # Upload
            dropbox_provider.upload_file(test_path, sample_image_bytes)
            print(f"Uploaded to {test_path}")
            
            # Download and verify
            downloaded = dropbox_provider.download_file(test_path)
            assert downloaded == sample_image_bytes
            print("Download verified successfully")
            
        finally:
            # Cleanup
            try:
                dropbox_provider.delete_file(test_path)
                print(f"Cleaned up {test_path}")
            except Exception as e:
                print(f"Cleanup failed (may not exist): {e}")
    
    def test_raises_on_nonexistent_file(self, dropbox_provider):
        """Should raise error for non-existent file."""
        with pytest.raises(Exception):
            dropbox_provider.download_file("/definitely/does/not/exist.jpg")


@pytest.mark.integration
@pytest.mark.dropbox
class TestDropboxPathHandling:
    """Test path normalization and handling."""
    
    def test_handles_uppercase_paths(self, dropbox_provider, dropbox_test_folder):
        """Should handle paths with mixed case."""
        # Dropbox paths are case-insensitive
        upper_path = dropbox_test_folder.upper()
        
        files = dropbox_provider.list_files(upper_path)
        
        # Should work and return files
        assert isinstance(files, list)
    
    def test_handles_path_without_leading_slash(self, dropbox_provider, dropbox_test_folder):
        """Should handle paths without leading slash."""
        path_without_slash = dropbox_test_folder.lstrip('/')
        
        files = dropbox_provider.list_files(path_without_slash)
        
        assert isinstance(files, list)
