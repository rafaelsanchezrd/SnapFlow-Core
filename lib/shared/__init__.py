"""
Configuration module - Credentials and constants management.
"""

from .credentials import (
    get_client_encryption_key,
    decrypt_credential,
    decrypt_credentials,
    mask_credentials,
    generate_fernet_key,
)

from .constants import (
    SHARED_VERSION,
    FILE_TYPE_CONFIG,
    SUPPORTED_EXTENSIONS,
    RAW_EXTENSIONS,
    RAW_HEADER_SIZE,
    DEFAULT_TIME_DELTA_SECONDS,
    DJI_TIME_DELTA_SECONDS,
    # Provider identifiers
    STORAGE_PROVIDER_DROPBOX,
    STORAGE_PROVIDER_GOOGLE_DRIVE,
    ENHANCEMENT_PROVIDER_FOTELLO,
    ENHANCEMENT_PROVIDER_AUTOHDR,
    # API endpoints
    FOTELLO_BASE_URL,
    AUTOHDR_BASE_URL,
)

__all__ = [
    # Credentials
    "get_client_encryption_key",
    "decrypt_credential",
    "decrypt_credentials",
    "mask_credentials",
    "generate_fernet_key",
    # Constants
    "SHARED_VERSION",
    "FILE_TYPE_CONFIG",
    "SUPPORTED_EXTENSIONS",
    "RAW_EXTENSIONS",
    "RAW_HEADER_SIZE",
    "DEFAULT_TIME_DELTA_SECONDS",
    "DJI_TIME_DELTA_SECONDS",
    # Provider identifiers
    "STORAGE_PROVIDER_DROPBOX",
    "STORAGE_PROVIDER_GOOGLE_DRIVE",
    "ENHANCEMENT_PROVIDER_FOTELLO",
    "ENHANCEMENT_PROVIDER_AUTOHDR",
    # API endpoints
    "FOTELLO_BASE_URL",
    "AUTOHDR_BASE_URL",
]
