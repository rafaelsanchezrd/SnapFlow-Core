"""
SnapFlow Core - Constants and Configuration
============================================
Shared constants, file type configurations, and default values
for the multi-provider photo enhancement pipeline.
"""

from typing import Dict, Any, Tuple

# Version identifier for SnapFlow Core
SHARED_VERSION = "1.2.0"
PACKAGE_NAME = "snapflow-core"

# =============================================================================
# FILE TYPE CONFIGURATION
# =============================================================================

FILE_TYPE_CONFIG: Dict[str, Dict[str, Any]] = {
    'RAW': {
        'extensions': ['.dng', '.raw', '.cr2', '.nef', '.arw', '.orf', '.rw2'],
        'max_size_mb': 250,
        'timeout_multiplier': 3.0,
        'description': 'Camera RAW files'
    },
    'CR3': {
        'extensions': ['.cr3'],
        'max_size_mb': 250,
        'timeout_multiplier': 3.0,
        'description': 'Canon CR3 RAW files (MP4 container)'
    },
    'TIFF': {
        'extensions': ['.tiff', '.tif'],
        'max_size_mb': 300,
        'timeout_multiplier': 2.5,
        'description': 'Uncompressed TIFF files'
    },
    'JPEG': {
        'extensions': ['.jpg', '.jpeg'],
        'max_size_mb': 50,
        'timeout_multiplier': 1.0,
        'description': 'JPEG compressed photos'
    },
    'PNG': {
        'extensions': ['.png'],
        'max_size_mb': 100,
        'timeout_multiplier': 1.5,
        'description': 'PNG lossless files'
    },
    'OTHER': {
        'extensions': ['.heic', '.webp', '.bmp', '.gif'],
        'max_size_mb': 75,
        'timeout_multiplier': 1.2,
        'description': 'Other image formats'
    }
}

# RAW file extensions (for EXIF partial download optimization)
RAW_EXTENSIONS: Tuple[str, ...] = (
    '.arw', '.nef', '.cr2', '.cr3', '.dng', '.raw', '.orf', '.rw2'
)

# All supported image extensions
SUPPORTED_EXTENSIONS: Tuple[str, ...] = (
    '.jpg', '.jpeg',
    '.dng', '.raw', '.cr2', '.cr3', '.nef', '.arw', '.orf', '.rw2',
    '.tiff', '.tif',
    '.png',
    '.heic', '.webp', '.bmp', '.gif'
)

# Header size for partial RAW file downloads (EXIF extraction)
RAW_HEADER_SIZE: int = 64 * 1024  # 64KB

# =============================================================================
# BRACKETING CONFIGURATION
# =============================================================================

# Default time delta for bracket grouping (seconds)
DEFAULT_TIME_DELTA_SECONDS: float = 2.0

# DJI drone time delta override (seconds)
DJI_TIME_DELTA_SECONDS: float = 10.0

# Merge window for intelligent bracketing (seconds)
DEFAULT_MERGE_WINDOW_SECONDS: float = 30.0

# Minimum bracket size for merging consideration
DEFAULT_MIN_BRACKET_SIZE: int = 2

# =============================================================================
# CONTENT TYPE MAPPING
# =============================================================================

CONTENT_TYPE_MAPPING: Dict[str, str] = {
    # RAW formats
    'nef': 'image/x-nikon-nef',
    'dng': 'image/x-adobe-dng',
    'cr2': 'image/x-canon-cr2',
    'cr3': 'image/x-canon-cr3',
    'arw': 'image/x-sony-arw',
    'orf': 'image/x-olympus-orf',
    'rw2': 'image/x-panasonic-rw2',
    'raw': 'image/x-raw',
    # Standard formats
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'tiff': 'image/tiff',
    'tif': 'image/tiff',
    'png': 'image/png',
    # Other formats
    'heic': 'image/heic',
    'webp': 'image/webp',
    'bmp': 'image/bmp',
    'gif': 'image/gif',
}

# =============================================================================
# RETRY CONFIGURATION
# =============================================================================

# Maximum retry attempts for API calls
MAX_RETRIES: int = 3

# Delay between retries (seconds)
RETRY_DELAY_SECONDS: int = 2

# Delay between finalize retry attempts (seconds)
FINALIZE_RETRY_DELAY_SECONDS: int = 180  # 3 minutes

# =============================================================================
# UPLOAD CONFIGURATION
# =============================================================================

# Base timeout for uploads (seconds)
BASE_UPLOAD_TIMEOUT: int = 120

# Maximum upload timeout (seconds)
MAX_UPLOAD_TIMEOUT: int = 900

# Chunk size for large file uploads (bytes)
UPLOAD_CHUNK_SIZE: int = 8 * 1024 * 1024  # 8MB

# =============================================================================
# PROVIDER IDENTIFIERS
# =============================================================================

# Storage provider types
STORAGE_PROVIDER_DROPBOX: str = "dropbox"
STORAGE_PROVIDER_GOOGLE_DRIVE: str = "google_drive"

# Enhancement provider types
ENHANCEMENT_PROVIDER_FOTELLO: str = "fotello"
ENHANCEMENT_PROVIDER_AUTOHDR: str = "autohdr"

# =============================================================================
# API ENDPOINTS
# =============================================================================

# Fotello API endpoints
FOTELLO_BASE_URL: str = "https://us-central1-real-estate-firebase-4109e.cloudfunctions.net"
FOTELLO_UPLOAD_ENDPOINT: str = f"{FOTELLO_BASE_URL}/createUpload"
FOTELLO_ENHANCE_ENDPOINT: str = f"{FOTELLO_BASE_URL}/createEnhance"
FOTELLO_GET_ENHANCE_ENDPOINT: str = f"{FOTELLO_BASE_URL}/getEnhance"

# Dropbox API endpoints
DROPBOX_TOKEN_URL: str = "https://api.dropboxapi.com/oauth2/token"
DROPBOX_CONTENT_URL: str = "https://content.dropboxapi.com/2/files/download"

# AutoHDR API endpoints
AUTOHDR_BASE_URL: str = "https://quantumreachadvertising.com/external-api"
AUTOHDR_CREATE_PHOTOSHOOT_ENDPOINT: str = f"{AUTOHDR_BASE_URL}/v1/create-photoshoot-with-presigned-urls"
AUTOHDR_FINALIZE_ENDPOINT: str = f"{AUTOHDR_BASE_URL}/v1/finalize-photoshoot-upload"
AUTOHDR_PROFILE_ENDPOINT: str = f"{AUTOHDR_BASE_URL}/v1/user/profile"
