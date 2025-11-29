"""
SnapFlow Core - Provider Abstractions
=====================================
Storage and Enhancement provider factories with unified interfaces.

Supported Storage Providers:
    - Dropbox (team accounts, chunked uploads)
    - Google Drive (placeholder)

Supported Enhancement Providers:
    - Fotello (presigned URL workflow)
    - AutoHDR (S3 presigned URLs, webhook-based)
"""

from .storage import BaseStorageProvider, StorageFactory, DropboxProvider
from .enhancement import BaseEnhancementProvider, EnhancementFactory, FotelloProvider, AutoHDRProvider

__all__ = [
    # Storage
    "BaseStorageProvider",
    "StorageFactory",
    "DropboxProvider",
    # Enhancement
    "BaseEnhancementProvider",
    "EnhancementFactory",
    "FotelloProvider",
    "AutoHDRProvider",
]
