"""
SnapFlow Core - Enhancement Providers
=====================================
Photo enhancement API abstractions for real estate photography.

Supported:
    - Fotello (presigned URL workflow, polling-based)
    - AutoHDR (S3 presigned URLs, webhook-based)
"""

from .base import BaseEnhancementProvider, EnhancementStatus
from .factory import EnhancementFactory
from .fotello_provider import FotelloProvider
from .autohdr_provider import AutoHDRProvider

__all__ = [
    "BaseEnhancementProvider",
    "EnhancementStatus",
    "EnhancementFactory",
    "FotelloProvider",
    "AutoHDRProvider",
]
