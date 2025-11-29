"""
File Utilities
==============
Path normalization, file type detection, and validation functions.
"""

import os
import re
from typing import Dict, Any, Tuple, Optional

from ..config.constants import (
    FILE_TYPE_CONFIG,
    CONTENT_TYPE_MAPPING,
)


def normalize_dropbox_path(path: str) -> str:
    """
    Normalize path to Dropbox path_lower format.
    
    - Converts backslashes to forward slashes
    - Ensures leading slash
    - Removes duplicate slashes
    - Removes trailing slash (unless root)
    - Converts to lowercase
    
    Args:
        path: Raw path string
        
    Returns:
        Normalized path string
    """
    if not path:
        return path
    
    # Replace backslashes with forward slashes
    normalized = path.replace('\\', '/')
    
    # Ensure leading slash
    if not normalized.startswith('/'):
        normalized = '/' + normalized
    
    # Remove duplicate slashes
    while '//' in normalized:
        normalized = normalized.replace('//', '/')
    
    # Remove trailing slash unless it's the root
    if len(normalized) > 1 and normalized.endswith('/'):
        normalized = normalized[:-1]
    
    # Convert to lowercase for path_lower compatibility
    normalized = normalized.lower()
    
    return normalized


def validate_dropbox_path(path: str) -> bool:
    """
    Validate that path follows Dropbox path_lower format.
    
    Args:
        path: Path to validate
        
    Returns:
        True if valid, False otherwise
    """
    if not path or not isinstance(path, str):
        return False
    
    return (
        path.startswith('/') and 
        '\\' not in path and 
        path == path.lower()
    )


def sanitize_filename_prefix(prefix: str) -> str:
    """
    Sanitize filename prefix to be filesystem-safe.
    
    - Removes/replaces unsafe characters
    - Collapses multiple spaces/underscores
    - Limits length to 50 characters
    
    Args:
        prefix: Raw prefix string
        
    Returns:
        Sanitized prefix string (empty if invalid)
    """
    if not prefix or not isinstance(prefix, str):
        return ""
    
    # Keep alphanumeric, hyphens, underscores, and spaces
    sanitized = re.sub(r'[^\w\-\s]', '_', prefix)
    
    # Replace multiple spaces/underscores with single underscore
    sanitized = re.sub(r'[\s_]+', '_', sanitized)
    
    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')
    
    # Limit length to reasonable size
    sanitized = sanitized[:50]
    
    return sanitized


def get_file_extension(filename: str) -> str:
    """
    Get lowercase file extension from filename.
    
    Args:
        filename: Filename or path
        
    Returns:
        Lowercase extension including dot (e.g., '.jpg')
    """
    if not filename:
        return ''
    
    _, ext = os.path.splitext(filename)
    return ext.lower()


def get_file_type_info(filename: str) -> Tuple[str, Dict[str, Any]]:
    """
    Determine file type and get configuration for the given filename.
    
    Args:
        filename: Filename to analyze
        
    Returns:
        Tuple of (file_type, config_dict)
        file_type is one of: 'RAW', 'CR3', 'TIFF', 'JPEG', 'PNG', 'OTHER'
    """
    file_ext = get_file_extension(filename)
    
    for file_type, config in FILE_TYPE_CONFIG.items():
        if file_ext in config['extensions']:
            return file_type, config
    
    return 'OTHER', FILE_TYPE_CONFIG['OTHER']


def get_content_type_for_file(filename: str) -> str:
    """
    Get correct MIME type based on file extension.
    
    Args:
        filename: Filename to analyze
        
    Returns:
        MIME type string (e.g., 'image/jpeg')
    """
    file_ext = get_file_extension(filename)
    
    # Remove leading dot for lookup
    ext_key = file_ext.lstrip('.')
    
    content_type = CONTENT_TYPE_MAPPING.get(ext_key, 'application/octet-stream')
    
    return content_type


def validate_file_size(filename: str, file_size_bytes: int) -> Tuple[bool, Optional[str]]:
    """
    Validate if file size is acceptable based on file type.
    
    Args:
        filename: Filename for type detection
        file_size_bytes: File size in bytes
        
    Returns:
        Tuple of (is_valid, error_message)
        error_message is None if valid
    """
    file_type, config = get_file_type_info(filename)
    file_size_mb = file_size_bytes / (1024 * 1024)
    max_size_mb = config['max_size_mb']
    
    if file_size_mb > max_size_mb:
        error_msg = (
            f"File too large: {filename} "
            f"({file_size_mb:.1f}MB > {max_size_mb}MB limit for {file_type})"
        )
        return False, error_msg
    
    return True, None


def calculate_upload_timeout(filename: str, file_size_bytes: int, base_timeout: int = 120) -> int:
    """
    Calculate appropriate upload timeout based on file type and size.
    
    Args:
        filename: Filename for type detection
        file_size_bytes: File size in bytes
        base_timeout: Base timeout in seconds
        
    Returns:
        Calculated timeout in seconds (capped at 900)
    """
    file_type, config = get_file_type_info(filename)
    file_size_mb = file_size_bytes / (1024 * 1024)
    
    timeout = int(base_timeout * config['timeout_multiplier'])
    
    # Scale up for very large files
    if file_size_mb > 50:
        timeout = int(timeout * (file_size_mb / 50))
    
    # Cap at 15 minutes
    return min(timeout, 900)


def is_dji_file(filename: str) -> bool:
    """
    Detect if file is from a DJI drone based on filename pattern.
    
    DJI files typically follow pattern: DJI_NNNN.dng
    
    Args:
        filename: Filename to check
        
    Returns:
        True if DJI file pattern detected
    """
    if not filename:
        return False
    
    name_upper = filename.upper()
    name_lower = filename.lower()
    
    return name_upper.startswith('DJI_') and name_lower.endswith('.dng')


def is_cr3_file(filename: str) -> bool:
    """
    Check if file is a Canon CR3 (MP4 container) format.
    
    Args:
        filename: Filename to check
        
    Returns:
        True if CR3 file
    """
    return get_file_extension(filename) == '.cr3'


def is_raw_file(filename: str) -> bool:
    """
    Check if file is a RAW format (requires special EXIF handling).
    
    Args:
        filename: Filename to check
        
    Returns:
        True if traditional RAW file (not CR3)
    """
    from ..config.constants import RAW_EXTENSIONS
    
    ext = get_file_extension(filename)
    
    # Exclude CR3 as it needs full download for MP4 container parsing
    if ext == '.cr3':
        return False
    
    return ext in RAW_EXTENSIONS
