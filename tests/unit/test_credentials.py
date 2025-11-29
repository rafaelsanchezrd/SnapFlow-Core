"""
Unit Tests: Credentials Module
==============================
Tests encryption, decryption, and key management.
No external API calls - runs fast.
"""

import pytest
from cryptography.fernet import Fernet


class TestGenerateFernetKey:
    """Tests for generate_fernet_key function."""
    
    @pytest.mark.unit
    def test_generates_valid_key(self):
        """Generated key should be valid Fernet format."""
        from shared.config import generate_fernet_key
        
        key = generate_fernet_key()
        
        # Should be base64-encoded, 44 chars
        assert len(key) == 44
        assert key.endswith('=')
        
        # Should be usable as Fernet key
        fernet = Fernet(key.encode())
        assert fernet is not None
    
    @pytest.mark.unit
    def test_generates_unique_keys(self):
        """Each call should generate a different key."""
        from shared.config import generate_fernet_key
        
        keys = [generate_fernet_key() for _ in range(10)]
        
        # All keys should be unique
        assert len(set(keys)) == 10


class TestDecryptCredential:
    """Tests for decrypt_credential function."""
    
    @pytest.mark.unit
    def test_decrypts_valid_credential(self, encryption_key):
        """Should decrypt a properly encrypted value."""
        from shared.config import decrypt_credential
        
        # Encrypt a test value
        fernet = Fernet(encryption_key.encode())
        original = "my-secret-api-key"
        encrypted = fernet.encrypt(original.encode()).decode()
        
        # Decrypt it
        result = decrypt_credential(encrypted, encryption_key)
        
        assert result == original
    
    @pytest.mark.unit
    def test_raises_on_invalid_key(self):
        """Should raise ValueError with wrong key."""
        from shared.config import decrypt_credential
        
        # Encrypt with one key
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()
        
        fernet = Fernet(key1.encode())
        encrypted = fernet.encrypt(b"secret").decode()
        
        # Try to decrypt with different key
        with pytest.raises(ValueError, match="Failed to decrypt"):
            decrypt_credential(encrypted, key2)
    
    @pytest.mark.unit
    def test_raises_on_invalid_encrypted_value(self, encryption_key):
        """Should raise ValueError with garbage input."""
        from shared.config import decrypt_credential
        
        with pytest.raises(ValueError, match="Failed to decrypt"):
            decrypt_credential("not-valid-encrypted-data", encryption_key)


class TestDecryptCredentials:
    """Tests for decrypt_credentials function."""
    
    @pytest.mark.unit
    def test_decrypts_legacy_format(self, mock_env, encryption_key):
        """Should decrypt legacy flat format."""
        from shared.config import decrypt_credentials
        
        # Setup environment with encryption key
        mock_env({"CLIENT_TEST_ENCRYPTION_KEY": encryption_key})
        
        # Encrypt test values
        fernet = Fernet(encryption_key.encode())
        
        data = {
            "client_id": "TEST",
            "dropbox_app_key_encrypted": fernet.encrypt(b"app-key-123").decode(),
            "dropbox_app_secret_encrypted": fernet.encrypt(b"app-secret-456").decode(),
            "dropbox_refresh_token_encrypted": fernet.encrypt(b"refresh-token-789").decode(),
            "fotello_api_key_encrypted": fernet.encrypt(b"fotello-key-abc").decode(),
            "other_field": "not-encrypted",
        }
        
        # Decrypt
        result = decrypt_credentials(data, "TEST")
        
        # Check decrypted values
        assert result["dropbox_app_key"] == "app-key-123"
        assert result["dropbox_app_secret"] == "app-secret-456"
        assert result["dropbox_refresh_token"] == "refresh-token-789"
        assert result["fotello_api_key"] == "fotello-key-abc"
        
        # Non-encrypted fields should pass through
        assert result["other_field"] == "not-encrypted"
        
        # Encrypted fields should be removed
        assert "dropbox_app_key_encrypted" not in result
    
    @pytest.mark.unit
    def test_decrypts_google_drive_credentials(self, mock_env, encryption_key):
        """Should decrypt Google Drive credentials."""
        from shared.config import decrypt_credentials
        
        mock_env({"CLIENT_TEST_ENCRYPTION_KEY": encryption_key})
        
        fernet = Fernet(encryption_key.encode())
        
        data = {
            "google_drive_client_id_encrypted": fernet.encrypt(b"gdrive-client-id").decode(),
            "google_drive_client_secret_encrypted": fernet.encrypt(b"gdrive-secret").decode(),
            "google_drive_refresh_token_encrypted": fernet.encrypt(b"gdrive-refresh").decode(),
        }
        
        result = decrypt_credentials(data, "TEST")
        
        assert result["google_drive_client_id"] == "gdrive-client-id"
        assert result["google_drive_client_secret"] == "gdrive-secret"
        assert result["google_drive_refresh_token"] == "gdrive-refresh"
    
    @pytest.mark.unit
    def test_decrypts_autohdr_credentials(self, mock_env, encryption_key):
        """Should decrypt AutoHDR credentials (api_key only, email is plain)."""
        from shared.config import decrypt_credentials
        
        mock_env({"CLIENT_TEST_ENCRYPTION_KEY": encryption_key})
        
        fernet = Fernet(encryption_key.encode())
        
        data = {
            "autohdr_api_key_encrypted": fernet.encrypt(b"autohdr-key").decode(),
            "autohdr_email": "test@example.com",  # NOT encrypted
        }
        
        result = decrypt_credentials(data, "TEST")
        
        assert result["autohdr_api_key"] == "autohdr-key"
        assert result["autohdr_email"] == "test@example.com"
    
    @pytest.mark.unit
    def test_raises_on_missing_client_key(self):
        """Should raise ValueError if client key not in environment."""
        from shared.config import decrypt_credentials
        
        with pytest.raises(ValueError, match="No encryption key found"):
            decrypt_credentials({"some": "data"}, "UNKNOWN_CLIENT")
    
    @pytest.mark.unit
    def test_raises_on_empty_client_id(self):
        """Should raise ValueError if client_id is empty."""
        from shared.config import decrypt_credentials
        
        with pytest.raises(ValueError, match="client_id is required"):
            decrypt_credentials({"some": "data"}, "")
        
        with pytest.raises(ValueError, match="client_id is required"):
            decrypt_credentials({"some": "data"}, None)


class TestMaskCredentials:
    """Tests for mask_credentials function."""
    
    @pytest.mark.unit
    def test_masks_sensitive_fields(self):
        """Should mask known sensitive fields."""
        from shared.config import mask_credentials
        
        data = {
            "dropbox_app_key": "abcdefghijklmnop",
            "dropbox_app_secret": "1234567890abcdef",
            "fotello_api_key": "very-secret-key-here",
            "listing_id": "not-sensitive",
        }
        
        masked = mask_credentials(data)
        
        # Sensitive fields should be masked
        assert masked["dropbox_app_key"] == "abcd...mnop"
        assert masked["dropbox_app_secret"] == "1234...cdef"
        assert masked["fotello_api_key"] == "very...here"
        
        # Non-sensitive fields unchanged
        assert masked["listing_id"] == "not-sensitive"
    
    @pytest.mark.unit
    def test_masks_short_values(self):
        """Short values should be fully masked."""
        from shared.config import mask_credentials
        
        data = {"api_key": "short"}
        
        masked = mask_credentials(data)
        
        assert masked["api_key"] == "***"
    
    @pytest.mark.unit
    def test_handles_nested_credentials(self):
        """Should mask nested credential dictionaries."""
        from shared.config import mask_credentials
        
        data = {
            "storage_credentials": {
                "refresh_token": "very-long-refresh-token-value",
            },
            "enhancement_credentials": {
                "api_key": "enhancement-api-key-value",
            },
        }
        
        masked = mask_credentials(data)
        
        assert masked["storage_credentials"]["refresh_token"] == "very...alue"
        assert masked["enhancement_credentials"]["api_key"] == "enha...alue"
    
    @pytest.mark.unit
    def test_handles_non_dict_input(self):
        """Should return non-dict input unchanged."""
        from shared.config import mask_credentials
        
        assert mask_credentials("string") == "string"
        assert mask_credentials(123) == 123
        assert mask_credentials(None) is None


class TestGetClientEncryptionKey:
    """Tests for get_client_encryption_key function."""
    
    @pytest.mark.unit
    def test_gets_key_from_environment(self, mock_env):
        """Should retrieve key from environment variable."""
        from shared.config import get_client_encryption_key
        
        mock_env({"CLIENT_MYTEST_ENCRYPTION_KEY": "test-key-value"})
        
        key = get_client_encryption_key("MYTEST")
        
        assert key == "test-key-value"
    
    @pytest.mark.unit
    def test_case_insensitive_client_id(self, mock_env):
        """Client ID should be case-insensitive."""
        from shared.config import get_client_encryption_key
        
        mock_env({"CLIENT_ABC_ENCRYPTION_KEY": "the-key"})
        
        assert get_client_encryption_key("abc") == "the-key"
        assert get_client_encryption_key("ABC") == "the-key"
        assert get_client_encryption_key("Abc") == "the-key"
    
    @pytest.mark.unit
    def test_lists_available_clients_on_error(self, mock_env):
        """Error message should list available clients."""
        from shared.config import get_client_encryption_key
        
        mock_env({
            "CLIENT_001_ENCRYPTION_KEY": "key1",
            "CLIENT_002_ENCRYPTION_KEY": "key2",
        })
        
        with pytest.raises(ValueError) as exc_info:
            get_client_encryption_key("UNKNOWN")
        
        error_msg = str(exc_info.value)
        assert "001" in error_msg
        assert "002" in error_msg
