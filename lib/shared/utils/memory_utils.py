"""
Memory Utilities
================
Memory monitoring and garbage collection helpers for serverless functions.
"""

import gc
from typing import Dict, Any, Optional


def get_memory_info() -> Dict[str, Any]:
    """
    Get current memory usage information.
    
    Returns:
        Dictionary with memory stats, or error info if unavailable
    """
    try:
        import psutil
        memory = psutil.virtual_memory()
        return {
            'memory_percent': round(memory.percent, 1),
            'memory_used_mb': round(memory.used / (1024 * 1024), 1),
            'memory_available_mb': round(memory.available / (1024 * 1024), 1),
            'memory_total_mb': round(memory.total / (1024 * 1024), 1),
        }
    except ImportError:
        return {'memory_status': 'psutil_not_available'}
    except Exception as e:
        return {'memory_error': str(e)}


def force_garbage_collection() -> Dict[str, Any]:
    """
    Force garbage collection and return stats.
    
    Returns:
        Dictionary with GC statistics
    """
    try:
        # Get counts before
        before_counts = gc.get_count()
        
        # Force collection
        collected = gc.collect()
        
        # Get counts after
        after_counts = gc.get_count()
        
        return {
            'objects_collected': collected,
            'before_counts': before_counts,
            'after_counts': after_counts,
        }
    except Exception as e:
        return {'gc_error': str(e)}


def clear_large_object(obj: Any, threshold_mb: float = 50.0) -> bool:
    """
    Clear a large object from memory and trigger GC if above threshold.
    
    This is useful for clearing file bytes after upload to free memory
    in serverless functions with limited RAM.
    
    Args:
        obj: Object to clear (typically bytes or dict with 'bytes' key)
        threshold_mb: Size threshold to trigger GC (MB)
        
    Returns:
        True if GC was triggered, False otherwise
    """
    triggered_gc = False
    
    try:
        # Estimate size
        size_bytes = 0
        
        if isinstance(obj, bytes):
            size_bytes = len(obj)
        elif isinstance(obj, dict) and 'bytes' in obj:
            if isinstance(obj['bytes'], bytes):
                size_bytes = len(obj['bytes'])
            obj['bytes'] = None
        
        size_mb = size_bytes / (1024 * 1024)
        
        # Trigger GC for large objects
        if size_mb > threshold_mb:
            gc.collect()
            triggered_gc = True
    except Exception:
        pass
    
    return triggered_gc


def log_memory_status(logger, context: str = "") -> None:
    """
    Log current memory status for debugging.
    
    Args:
        logger: Logger instance to use
        context: Optional context string for the log message
    """
    memory_info = get_memory_info()
    
    if 'memory_percent' in memory_info:
        prefix = f"[{context}] " if context else ""
        logger.info(
            f"{prefix}Memory: {memory_info['memory_percent']}% used "
            f"({memory_info['memory_used_mb']:.0f}MB / {memory_info['memory_total_mb']:.0f}MB)"
        )
    elif 'memory_status' in memory_info:
        logger.debug(f"Memory status: {memory_info['memory_status']}")
    elif 'memory_error' in memory_info:
        logger.warning(f"Memory check error: {memory_info['memory_error']}")


class MemoryTracker:
    """
    Context manager for tracking memory usage during operations.
    
    Usage:
        with MemoryTracker("Processing bracket") as tracker:
            # ... do work ...
        print(f"Memory delta: {tracker.delta_mb}MB")
    """
    
    def __init__(self, operation_name: str = "Operation"):
        self.operation_name = operation_name
        self.start_memory: Optional[Dict[str, Any]] = None
        self.end_memory: Optional[Dict[str, Any]] = None
        self.delta_mb: float = 0.0
    
    def __enter__(self):
        self.start_memory = get_memory_info()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_memory = get_memory_info()
        
        if (self.start_memory and self.end_memory and 
            'memory_used_mb' in self.start_memory and 
            'memory_used_mb' in self.end_memory):
            
            self.delta_mb = (
                self.end_memory['memory_used_mb'] - 
                self.start_memory['memory_used_mb']
            )
        
        return False  # Don't suppress exceptions
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of memory usage during operation."""
        return {
            'operation': self.operation_name,
            'start_memory_mb': self.start_memory.get('memory_used_mb') if self.start_memory else None,
            'end_memory_mb': self.end_memory.get('memory_used_mb') if self.end_memory else None,
            'delta_mb': round(self.delta_mb, 2),
        }
