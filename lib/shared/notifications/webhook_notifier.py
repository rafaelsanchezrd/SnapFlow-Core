"""
Webhook Notifier
================
Centralized webhook notification management with configurable verbosity levels.
"""

import time
import requests
from enum import Enum
from typing import Dict, Any, Optional, List


class NotificationLevel(Enum):
    """Notification verbosity levels."""
    ERRORS_ONLY = "errors_only"  # Only errors and critical failures
    MINIMAL = "minimal"          # Major milestones only
    STANDARD = "standard"        # Progress updates, skip verbose debug
    VERBOSE = "verbose"          # Everything including debug details


class WebhookNotifier:
    """
    Centralized notification manager for Fotello functions.
    
    Handles both debug notifications (for monitoring) and business notifications
    (for workflow orchestration in Make.com).
    
    Usage:
        notifier = WebhookNotifier(
            callback_webhook="https://...",
            job_id="abc123",
            listing_id="listing456",
            notification_level="minimal"
        )
        
        notifier.send_debug("process_started", {"files": 10})
        notifier.send_business("job_completed", {...})
    """
    
    # Critical notifications always sent regardless of level
    CRITICAL_NOTIFICATIONS = frozenset([
        'job_failed', 'job_completed', 'job_partial_success', 'job_started',
        'dispatch_failed', 'process_completed_success', 'finalize_processing_started',
        'dropbox_connection_failed', 'enhancement_request_success',
        'google_drive_connection_failed',  # Future
    ])
    
    # Minimal level allowed notifications
    MINIMAL_ALLOWED = frozenset([
        'process_started_detailed', 'dropbox_connected_success',
        'google_drive_connected_success',  # Future
        'bracket_processing_started', 'process_completed_success',
    ])
    
    # Verbose-only notifications (skip in standard mode)
    VERBOSE_ONLY = frozenset([
        'status_checked', 'upload_attempt_details', 'upload_result_details',
        'dropbox_token_refresh_attempt', 'finalize_call_attempt', 'retry_attempt',
    ])
    
    def __init__(
        self,
        callback_webhook: str,
        job_id: str = None,
        listing_id: str = None,
        correlation_id: str = None,
        notification_level: str = "minimal",
        function_name: str = "unknown",
        version: str = "unknown",
    ):
        """
        Initialize webhook notifier.
        
        Args:
            callback_webhook: URL to send notifications to
            job_id: Job identifier
            listing_id: Listing identifier
            correlation_id: Request correlation ID for tracing
            notification_level: One of 'errors_only', 'minimal', 'standard', 'verbose'
            function_name: Name of the calling function
            version: Version string for tracking
        """
        self.callback_webhook = callback_webhook
        self.job_id = job_id
        self.listing_id = listing_id
        self.correlation_id = correlation_id
        self.function_name = function_name
        self.version = version
        
        # Parse notification level
        try:
            self.notification_level = NotificationLevel(notification_level.lower())
        except (ValueError, AttributeError):
            self.notification_level = NotificationLevel.MINIMAL
    
    def _should_send(self, status: str, log_level: str) -> bool:
        """
        Determine if notification should be sent based on level and type.
        
        Args:
            status: Notification status/type
            log_level: Log level (INFO, ERROR, WARNING, DEBUG)
            
        Returns:
            True if notification should be sent
        """
        # Always send ERROR level
        if log_level == "ERROR":
            return True
        
        # Always send critical notifications
        if status in self.CRITICAL_NOTIFICATIONS:
            return True
        
        # Check based on notification level
        if self.notification_level == NotificationLevel.ERRORS_ONLY:
            return False
        
        if self.notification_level == NotificationLevel.MINIMAL:
            return status in self.MINIMAL_ALLOWED
        
        if self.notification_level == NotificationLevel.STANDARD:
            return status not in self.VERBOSE_ONLY
        
        # VERBOSE: send everything
        return True
    
    def send_debug(
        self,
        status: str,
        extra_data: Dict[str, Any] = None,
        log_level: str = "INFO",
    ) -> bool:
        """
        Send debug notification to webhook.
        
        Args:
            status: Status identifier (e.g., 'process_started_detailed')
            extra_data: Additional data to include
            log_level: Log level (INFO, ERROR, WARNING, DEBUG)
            
        Returns:
            True if notification was sent successfully
        """
        if not self.callback_webhook:
            return False
        
        if not self._should_send(status, log_level):
            return False
        
        try:
            payload = {
                'debug_status': status,
                'function_name': self.function_name,
                'log_level': log_level,
                'job_id': self.job_id,
                'listing_id': self.listing_id,
                'timestamp': time.time(),
                'version': self.version,
                'correlation_id': self.correlation_id,
            }
            
            if extra_data:
                payload.update(extra_data)
            
            response = requests.post(
                self.callback_webhook,
                json=payload,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            print(f"Debug notification sent: {status} [{log_level}]")
            return response.status_code < 400
            
        except Exception as e:
            print(f"Failed to send debug notification '{status}': {e}")
            return False
    
    def send_business(
        self,
        notification_type: str,
        job_data: Dict[str, Any],
    ) -> bool:
        """
        Send business notification to webhook.
        
        Business notifications are always sent (not filtered by level)
        as they're required for workflow orchestration.
        
        Args:
            notification_type: Type of notification (e.g., 'job_completed')
            job_data: Job result data
            
        Returns:
            True if notification was sent successfully
        """
        if not self.callback_webhook:
            return False
        
        try:
            # Add standard fields
            job_data['function_name'] = self.function_name
            job_data['log_level'] = 'INFO'
            job_data['correlation_id'] = self.correlation_id
            job_data['version'] = self.version
            
            response = requests.post(
                self.callback_webhook,
                json=job_data,
                timeout=10,
                headers={'Content-Type': 'application/json'}
            )
            
            print(f"Business notification sent: {notification_type}")
            return response.status_code < 400
            
        except Exception as e:
            print(f"Failed to send business notification '{notification_type}': {e}")
            return False
    
    def send_error(
        self,
        error_status: str,
        error_message: str,
        extra_data: Dict[str, Any] = None,
    ) -> bool:
        """
        Send error notification (always sent regardless of level).
        
        Args:
            error_status: Error status identifier
            error_message: Human-readable error message
            extra_data: Additional context data
            
        Returns:
            True if notification was sent successfully
        """
        data = {'error': error_message}
        if extra_data:
            data.update(extra_data)
        
        return self.send_debug(error_status, data, log_level="ERROR")
    
    def send_job_result(
        self,
        status: str,
        total_brackets: int,
        processed_brackets: int,
        successful_enhancements: int,
        failed_enhancements: int,
        enhanced_images: List[Dict[str, Any]],
        failed_brackets: List[Dict[str, Any]],
        retry_attempts: int = 0,
    ) -> bool:
        """
        Send standardized job result notification.
        
        Args:
            status: Job status ('job_completed', 'job_partial_success', 'job_failed')
            total_brackets: Total number of brackets
            processed_brackets: Number of brackets processed
            successful_enhancements: Number of successful enhancements
            failed_enhancements: Number of failed enhancements
            enhanced_images: List of enhanced image details
            failed_brackets: List of failed bracket details
            retry_attempts: Number of retry attempts made
            
        Returns:
            True if notification was sent successfully
        """
        job_data = {
            'status': status,
            'job_id': self.job_id,
            'listing_id': self.listing_id,
            'total_brackets': total_brackets,
            'processed_brackets': processed_brackets,
            'successful_enhancements': successful_enhancements,
            'failed_enhancements': failed_enhancements,
            'enhanced_images': enhanced_images,
            'failed_brackets': failed_brackets,
            'timestamp': time.time(),
            'source': f'{self.function_name}_function',
            'retry_attempts': retry_attempts,
        }
        
        return self.send_business(status, job_data)


def create_notifier_from_event(
    event_data: Dict[str, Any],
    function_name: str,
    version: str,
) -> WebhookNotifier:
    """
    Factory function to create WebhookNotifier from event data.
    
    Args:
        event_data: Event/request data containing webhook and IDs
        function_name: Name of the calling function
        version: Version string
        
    Returns:
        Configured WebhookNotifier instance
    """
    return WebhookNotifier(
        callback_webhook=event_data.get('callback_webhook'),
        job_id=event_data.get('job_id'),
        listing_id=event_data.get('listing_id'),
        correlation_id=event_data.get('correlation_id'),
        notification_level=event_data.get('notification_level', 'minimal'),
        function_name=function_name,
        version=version,
    )
