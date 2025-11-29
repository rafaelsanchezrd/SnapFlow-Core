"""
Unit Tests: File Utilities
==========================
Tests for file path handling, content type detection, and validation.
No external API calls - runs fast.
"""

import pytest


class TestNormalizeDropboxPath:
    """Tests for normalize_dropbox_path function."""
    
    @pytest.mark.unit
    def test_adds_leading_slash(self):
        """Should add leading slash if missing."""
        from shared.utils import normalize_dropbox_path
        
        assert normalize_dropbox_path("Photos/test") == "/photos/test"
    
    @pytest.mark.unit
    def test_converts_to_lowercase(self):
        """Should convert to lowercase."""
        from shared.utils import normalize_dropbox_path
        
        assert normalize_dropbox_path("/Photos/Test.JPG") == "/photos/test.jpg"
    
    @pytest.mark.unit
    def test_converts_backslashes(self):
        """Should convert backslashes to forward slashes."""
        from shared.utils import normalize_dropbox_path
        
        assert normalize_dropbox_path("\\Photos\\Test") == "/photos/test"
    
    @pytest.mark.unit
    def test_handles_empty_input(self):
        """Should handle empty or None input."""
        from shared.utils import normalize_dropbox_path
        
        assert normalize_dropbox_path("") == ""
        assert normalize_dropbox_path(None) is None
    
    @pytest.mark.unit
    def test_already_normalized_path(self):
        """Should not change already normalized paths."""
        from shared.utils import normalize_dropbox_path
        
        assert normalize_dropbox_path("/photos/test.jpg") == "/photos/test.jpg"


class TestSanitizeFilenamePrefix:
    """Tests for sanitize_filename_prefix function."""
    
    @pytest.mark.unit
    def test_removes_unsafe_characters(self):
        """Should remove/replace unsafe characters."""
        from shared.utils import sanitize_filename_prefix
        
        assert sanitize_filename_prefix("test/file:name") == "test_file_name"
        assert sanitize_filename_prefix("file<>name") == "file__name"
    
    @pytest.mark.unit
    def test_preserves_safe_characters(self):
        """Should preserve alphanumeric, hyphens, underscores."""
        from shared.utils import sanitize_filename_prefix
        
        assert sanitize_filename_prefix("test-file_name123") == "test-file_name123"
    
    @pytest.mark.unit
    def test_collapses_multiple_underscores(self):
        """Should collapse multiple underscores/spaces."""
        from shared.utils import sanitize_filename_prefix
        
        assert sanitize_filename_prefix("test___file") == "test_file"
        assert sanitize_filename_prefix("test   file") == "test_file"
    
    @pytest.mark.unit
    def test_trims_leading_trailing_underscores(self):
        """Should trim underscores from start/end."""
        from shared.utils import sanitize_filename_prefix
        
        assert sanitize_filename_prefix("_test_") == "test"
        assert sanitize_filename_prefix("___test___") == "test"
    
    @pytest.mark.unit
    def test_limits_length(self):
        """Should limit to 50 characters."""
        from shared.utils import sanitize_filename_prefix
        
        long_name = "a" * 100
        result = sanitize_filename_prefix(long_name)
        
        assert len(result) <= 50
    
    @pytest.mark.unit
    def test_handles_empty_input(self):
        """Should handle empty or None input."""
        from shared.utils import sanitize_filename_prefix
        
        assert sanitize_filename_prefix("") == ""
        assert sanitize_filename_prefix(None) == ""


class TestGetContentTypeForFile:
    """Tests for get_content_type_for_file function."""
    
    @pytest.mark.unit
    def test_jpeg_content_type(self):
        """Should return correct type for JPEG files."""
        from shared.utils import get_content_type_for_file
        
        assert get_content_type_for_file("photo.jpg") == "image/jpeg"
        assert get_content_type_for_file("photo.jpeg") == "image/jpeg"
        assert get_content_type_for_file("PHOTO.JPG") == "image/jpeg"
    
    @pytest.mark.unit
    def test_raw_content_types(self):
        """Should return correct types for RAW formats."""
        from shared.utils import get_content_type_for_file
        
        assert get_content_type_for_file("photo.dng") == "image/dng"
        assert get_content_type_for_file("photo.nef") == "image/nef"
        assert get_content_type_for_file("photo.cr2") == "image/cr2"
        assert get_content_type_for_file("photo.arw") == "image/arw"
    
    @pytest.mark.unit
    def test_unknown_extension(self):
        """Should return octet-stream for unknown extensions."""
        from shared.utils import get_content_type_for_file
        
        assert get_content_type_for_file("file.xyz") == "application/octet-stream"
        assert get_content_type_for_file("file") == "application/octet-stream"


class TestGetFileTypeInfo:
    """Tests for get_file_type_info function."""
    
    @pytest.mark.unit
    def test_identifies_jpeg(self):
        """Should identify JPEG files."""
        from shared.utils import get_file_type_info
        
        file_type, config = get_file_type_info("photo.jpg")
        
        assert file_type == "JPEG"
        assert config["max_size_mb"] == 50
    
    @pytest.mark.unit
    def test_identifies_raw(self):
        """Should identify RAW files with larger limits."""
        from shared.utils import get_file_type_info
        
        file_type, config = get_file_type_info("photo.dng")
        
        assert file_type == "RAW"
        assert config["max_size_mb"] > 100  # RAW has larger limit
    
    @pytest.mark.unit
    def test_unknown_falls_back_to_other(self):
        """Unknown extensions should use OTHER config."""
        from shared.utils import get_file_type_info
        
        file_type, config = get_file_type_info("file.unknown")
        
        assert file_type == "OTHER"


class TestValidateFileSize:
    """Tests for validate_file_size function."""
    
    @pytest.mark.unit
    def test_accepts_valid_jpeg_size(self):
        """Should accept JPEG under limit."""
        from shared.utils import validate_file_size
        
        # 10MB JPEG (under 50MB limit)
        size_bytes = 10 * 1024 * 1024
        
        assert validate_file_size("photo.jpg", size_bytes) is True
    
    @pytest.mark.unit
    def test_rejects_oversized_jpeg(self):
        """Should reject JPEG over limit."""
        from shared.utils import validate_file_size
        
        # 100MB JPEG (over 50MB limit)
        size_bytes = 100 * 1024 * 1024
        
        assert validate_file_size("photo.jpg", size_bytes) is False
    
    @pytest.mark.unit
    def test_accepts_large_raw(self):
        """Should accept larger RAW files."""
        from shared.utils import validate_file_size
        
        # 200MB RAW (under 250MB limit)
        size_bytes = 200 * 1024 * 1024
        
        assert validate_file_size("photo.dng", size_bytes) is True
