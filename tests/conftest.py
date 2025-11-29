"""
Pytest Configuration and Fixtures
==================================
Loads test credentials from environment and provides reusable fixtures.
"""

import os
import sys
import pytest
from pathlib import Path
from dotenv import load_dotenv

# Add lib/shared to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "lib"))

# Load test environment variables
env_file = project_root / ".env.test"
if env_file.exists():
    load_dotenv(env_file)
else:
    # Try loading from CI environment
    load_dotenv()


# =============================================================================
# CREDENTIAL FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def dropbox_credentials():
    """Dropbox API credentials from environment."""
    creds = {
        "app_key": os.getenv("TEST_DROPBOX_APP_KEY"),
        "app_secret": os.getenv("TEST_DROPBOX_APP_SECRET"),
        "refresh_token": os.getenv("TEST_DROPBOX_REFRESH_TOKEN"),
    }
    
    if not all(creds.values()):
        pytest.skip("Dropbox credentials not configured")
    
    return creds


@pytest.fixture(scope="session")
def dropbox_test_folder():
    """Dropbox test folder path."""
    folder = os.getenv("TEST_DROPBOX_TEST_FOLDER", "/SnapFlow-Tests")
    return folder


@pytest.fixture(scope="session")
def google_drive_credentials():
    """Google Drive API credentials from environment."""
    creds = {
        "client_id": os.getenv("TEST_GDRIVE_CLIENT_ID"),
        "client_secret": os.getenv("TEST_GDRIVE_CLIENT_SECRET"),
        "refresh_token": os.getenv("TEST_GDRIVE_REFRESH_TOKEN"),
    }
    
    if not all(creds.values()):
        pytest.skip("Google Drive credentials not configured")
    
    return creds


@pytest.fixture(scope="session")
def google_drive_test_folder():
    """Google Drive test folder ID."""
    folder_id = os.getenv("TEST_GDRIVE_TEST_FOLDER_ID")
    if not folder_id:
        pytest.skip("Google Drive test folder not configured")
    return folder_id


@pytest.fixture(scope="session")
def fotello_credentials():
    """Fotello API credentials from environment."""
    api_key = os.getenv("TEST_FOTELLO_API_KEY")
    
    if not api_key:
        pytest.skip("Fotello credentials not configured")
    
    return {"api_key": api_key}


@pytest.fixture(scope="session")
def autohdr_credentials():
    """AutoHDR API credentials from environment."""
    creds = {
        "api_key": os.getenv("TEST_AUTOHDR_API_KEY"),
        "email": os.getenv("TEST_AUTOHDR_EMAIL"),
    }
    
    if not all(creds.values()):
        pytest.skip("AutoHDR credentials not configured")
    
    return creds


@pytest.fixture(scope="session")
def encryption_key():
    """Fernet encryption key for testing."""
    key = os.getenv("TEST_ENCRYPTION_KEY")
    
    if not key:
        # Generate a temporary key for unit tests
        from cryptography.fernet import Fernet
        key = Fernet.generate_key().decode()
    
    return key


@pytest.fixture(scope="session")
def test_client_id():
    """Test client ID."""
    return os.getenv("TEST_CLIENT_ID", "TEST")


# =============================================================================
# PROVIDER FIXTURES
# =============================================================================

@pytest.fixture
def dropbox_provider(dropbox_credentials):
    """Configured Dropbox storage provider."""
    from shared.providers import StorageFactory
    
    provider = StorageFactory.create("dropbox", dropbox_credentials)
    return provider


@pytest.fixture
def google_drive_provider(google_drive_credentials):
    """Configured Google Drive storage provider."""
    from shared.providers import StorageFactory
    
    provider = StorageFactory.create("google_drive", google_drive_credentials)
    return provider


@pytest.fixture
def fotello_provider(fotello_credentials):
    """Configured Fotello enhancement provider."""
    from shared.providers import EnhancementFactory
    
    provider = EnhancementFactory.create("fotello", fotello_credentials)
    return provider


@pytest.fixture
def autohdr_provider(autohdr_credentials):
    """Configured AutoHDR enhancement provider."""
    from shared.providers import EnhancementFactory
    
    provider = EnhancementFactory.create("autohdr", autohdr_credentials)
    return provider


# =============================================================================
# UTILITY FIXTURES
# =============================================================================

@pytest.fixture
def mock_env(monkeypatch):
    """Helper to mock environment variables."""
    def _mock_env(env_dict):
        for key, value in env_dict.items():
            monkeypatch.setenv(key, value)
    return _mock_env


@pytest.fixture
def sample_image_bytes():
    """Minimal valid JPEG bytes for testing uploads."""
    # Smallest valid JPEG (1x1 pixel, gray)
    return bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
        0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
        0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
        0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
        0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
        0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
        0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
        0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
        0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
        0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
        0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
        0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
        0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD3, 0x20, 0x0A, 0x28, 0xA0, 0x02, 0x80,
        0x0A, 0x28, 0x03, 0xFF, 0xD9
    ])


# =============================================================================
# TEST MARKERS COLLECTION
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Fast tests with no external dependencies")
    config.addinivalue_line("markers", "integration: Tests that call external APIs")
    config.addinivalue_line("markers", "e2e: End-to-end pipeline tests")
    config.addinivalue_line("markers", "dropbox: Tests requiring Dropbox credentials")
    config.addinivalue_line("markers", "google_drive: Tests requiring Google Drive credentials")
    config.addinivalue_line("markers", "fotello: Tests requiring Fotello credentials")
    config.addinivalue_line("markers", "autohdr: Tests requiring AutoHDR credentials")
    config.addinivalue_line("markers", "slow: Tests that take more than 30 seconds")
