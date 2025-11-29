"""
SnapFlow Finalize Function
==========================
Polls enhancement status, downloads results, uploads to storage destination.

Version: 1.0.0-snapflow
"""

import json
import os
import requests
import uuid
import time
from typing import Dict, Any, List

# Import from SnapFlow Core shared library
from shared import (
    # Factories
    StorageFactory,
    EnhancementFactory,
    # Config
    SHARED_VERSION,
    # Notifications
    WebhookNotifier,
    NotificationLevel,
    # Utils
    sanitize_filename_prefix,
)

# Function version
VERSION = f"1.0.0-finalize-snapflow-{SHARED_VERSION}"

# Retry Configuration
RETRY_DELAY_SECONDS = 180  # Wait 3 minutes between retries
MAX_RETRIES = 3


def _parse_notification_level(level_str: str) -> NotificationLevel:
    """Convert string to NotificationLevel enum"""
    mapping = {
        'errors_only': NotificationLevel.ERRORS_ONLY,
        'minimal': NotificationLevel.MINIMAL,
        'standard': NotificationLevel.STANDARD,
        'verbose': NotificationLevel.VERBOSE,
    }
    return mapping.get(level_str, NotificationLevel.MINIMAL)


def _download_file_from_url(url: str) -> bytes:
    """Downloads a file from a given URL and returns its content as bytes"""
    try:
        print(f"Downloading enhanced file from URL")
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        
        content_length = response.headers.get('content-length')
        if content_length:
            size_mb = int(content_length) / (1024 * 1024)
            print(f"Enhanced file size: {size_mb:.2f} MB")
            
        print("Enhanced file downloaded successfully")
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Failed to download file from URL: {e}")
        raise


def _create_standardized_job_result(
    job_id: str,
    listing_id: str,
    total_brackets: int,
    processed_brackets: int,
    completed_enhancements: List[Dict],
    retry_count: int,
    correlation_id: str = None
) -> Dict:
    """Create standardized job result structure"""
    
    # Separate successful and failed enhancements
    successful_uploads = [r for r in completed_enhancements if r.get('status') == 'uploaded']
    failed_results = [r for r in completed_enhancements if r.get('status') != 'uploaded']
    
    # Determine overall job status
    if successful_uploads and not failed_results:
        job_status = 'job_completed'
    elif successful_uploads and failed_results:
        job_status = 'job_partial_success'
    else:
        job_status = 'job_failed'
    
    # Build enhanced_images array
    enhanced_images = []
    for r in successful_uploads:
        if 'storage_path' in r and 'file_size_mb' in r:
            enhanced_images.append({
                'bracket_index': r['bracket_index'],
                'storage_path': r['storage_path'],
                'file_size_mb': r['file_size_mb']
            })
    
    # Build failed_brackets array
    failed_brackets = []
    for r in failed_results:
        failed_brackets.append({
            'bracket_index': r.get('bracket_index'),
            'error': r.get('error', 'Unknown error')
        })
    
    return {
        'status': job_status,
        'job_id': job_id,
        'listing_id': listing_id,
        'total_brackets': total_brackets,
        'processed_brackets': processed_brackets,
        'successful_enhancements': len(successful_uploads),
        'failed_enhancements': len(failed_results),
        'enhanced_images': enhanced_images,
        'failed_brackets': failed_brackets,
        'timestamp': time.time(),
        'source': 'finalize_function',
        'version': VERSION,
        'retry_attempts': retry_count,
        'correlation_id': correlation_id
    }


def _process_enhancement(
    enhancement_info: Dict,
    enhancement_provider,
    storage_provider,
    listing_id: str,
    destination_folder: str,
    notifier: WebhookNotifier,
    current_num: int = None,
    total_num: int = None,
    filename_prefix: str = None
) -> Dict:
    """Process a single enhancement - check status and download/upload if completed"""
    
    enhancement_id = enhancement_info['enhancement_id']
    bracket_index = enhancement_info['bracket_index']
    
    # Progress info
    progress_info = {}
    if current_num is not None and total_num is not None:
        progress_info = {
            'enhancement_progress': f"{current_num} of {total_num}",
            'current_enhancement': current_num,
            'total_enhancements': total_num
        }
    
    try:
        # Check enhancement status using provider
        status_result = enhancement_provider.get_enhancement_status(enhancement_id)
        status = status_result.get('status', 'unknown')
        
        print(f"Enhancement {enhancement_id} status: {status}")
        
        if status == 'completed':
            enhanced_image_url = status_result.get('enhanced_image_url')
            
            if enhanced_image_url:
                progress_msg = f" ({progress_info.get('enhancement_progress', f'bracket {bracket_index + 1}')})"
                print(f"Enhancement completed{progress_msg}")
                
                try:
                    # Download enhanced image
                    enhanced_bytes = _download_file_from_url(enhanced_image_url)
                    
                    # Build destination filename
                    if filename_prefix and filename_prefix.strip():
                        sanitized_prefix = sanitize_filename_prefix(filename_prefix)
                        prefix_to_use = sanitized_prefix if sanitized_prefix else listing_id
                    else:
                        prefix_to_use = listing_id
                    
                    enhanced_filename = f"{bracket_index + 1}_{prefix_to_use}.jpg"
                    
                    # Upload to storage
                    # Handle different path formats for Dropbox vs Google Drive
                    if hasattr(storage_provider, 'provider_name') and storage_provider.provider_name == 'google_drive':
                        # Google Drive: folder_id/filename
                        dest_path = f"{destination_folder}/{enhanced_filename}"
                    else:
                        # Dropbox: /path/to/folder/filename
                        dest_path = f"{destination_folder}/{enhanced_filename}"
                        if not dest_path.startswith('/'):
                            dest_path = '/' + dest_path
                    
                    upload_result = storage_provider.upload_file(dest_path, enhanced_bytes, overwrite=True)
                    
                    print(f"Uploaded to: {dest_path}")
                    
                    notifier.send_debug('bracket_completed', {
                        'bracket_index': bracket_index,
                        'storage_path': dest_path,
                        'enhancement_id': enhancement_id,
                        **progress_info
                    })
                    
                    return {
                        'enhancement_id': enhancement_id,
                        'bracket_index': bracket_index,
                        'status': 'uploaded',
                        'storage_path': dest_path,
                        'file_size_mb': round(len(enhanced_bytes) / (1024 * 1024), 2)
                    }
                    
                except Exception as e:
                    print(f"Failed to download/upload enhanced image: {e}")
                    notifier.send_error('download_upload_error', str(e), {
                        'bracket_index': bracket_index
                    })
                    return {
                        'enhancement_id': enhancement_id,
                        'bracket_index': bracket_index,
                        'status': 'download_failed',
                        'error': str(e)
                    }
            else:
                return {
                    'enhancement_id': enhancement_id,
                    'bracket_index': bracket_index,
                    'status': 'completed_no_url',
                    'error': 'No enhanced_image_url in response'
                }
        
        elif status == 'in_progress' or status == 'processing':
            return {
                'enhancement_id': enhancement_id,
                'bracket_index': bracket_index,
                'status': 'in_progress',
                'retry_needed': True
            }
        
        elif status == 'failed':
            return {
                'enhancement_id': enhancement_id,
                'bracket_index': bracket_index,
                'status': 'failed',
                'error': status_result.get('error', 'Enhancement failed')
            }
        
        else:
            return {
                'enhancement_id': enhancement_id,
                'bracket_index': bracket_index,
                'status': 'unknown_status',
                'error': f'Unknown status: {status}'
            }
            
    except Exception as e:
        print(f"Error checking enhancement: {e}")
        notifier.send_error('api_error', str(e), {
            'enhancement_id': enhancement_id,
            'bracket_index': bracket_index
        })
        return {
            'enhancement_id': enhancement_id,
            'bracket_index': bracket_index,
            'status': 'api_error',
            'error': str(e)
        }


def main(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    SnapFlow Finalize Function
    
    Polls enhancement status, downloads completed results, and uploads
    to the storage destination.
    
    Can be called:
    1. From process function (normal flow)
    2. Directly from Make.com (delayed retrieval with skip_finalize)
    
    Supports:
    - Storage: Dropbox, Google Drive
    - Enhancement: Fotello, AutoHDR
    """
    # Setup correlation ID
    correlation_id = event.get('correlation_id', str(uuid.uuid4()))
    print(f"=== SNAPFLOW FINALIZE v{VERSION} === [ID: {correlation_id}]")
    
    notifier = None
    
    try:
        # Parse event data
        if 'body' in event and event['body']:
            if isinstance(event['body'], str):
                try:
                    event_data = json.loads(event['body'])
                except json.JSONDecodeError:
                    event_data = event
            else:
                event_data = event['body']
        else:
            event_data = event
        
        # If top-level doesn't have job_id, check if event itself does
        if not event_data.get('job_id') and event.get('job_id'):
            event_data = event

        # Extract required fields
        job_id = event_data.get('job_id', str(uuid.uuid4()))
        client_id = event_data.get('client_id')
        listing_id = event_data.get('listing_id')
        enhancement_ids = event_data.get('enhancement_ids', [])
        callback_webhook = event_data.get('callback_webhook')
        total_brackets = event_data.get('total_brackets', 0)
        processed_brackets = event_data.get('processed_brackets', 0)
        notification_level = _parse_notification_level(event_data.get('notification_level', 'minimal'))
        filename_prefix = event_data.get('filename_prefix')
        
        # Provider detection
        storage_provider_name = event_data.get('storage_provider', 'dropbox')
        enhancement_provider_name = event_data.get('enhancement_provider', 'fotello')
        
        print(f"Job: {job_id}, Listing: {listing_id}")
        print(f"Enhancement IDs: {len(enhancement_ids)}")
        print(f"Providers - Storage: {storage_provider_name}, Enhancement: {enhancement_provider_name}")
        
        # Create notifier
        notifier = WebhookNotifier(
            callback_webhook=callback_webhook,
            job_id=job_id,
            listing_id=listing_id,
            client_id=client_id,
            correlation_id=correlation_id,
            notification_level=notification_level,
            function_name='finalize',
            version=VERSION
        )
        
        # Send start notification
        notifier.send_debug('finalize_processing_started', {
            'enhancement_count': len(enhancement_ids)
        })
        
        # Send job_started business notification
        notifier.send_job_result(
            status='job_started',
            total_brackets=total_brackets,
            processed_brackets=processed_brackets,
            successful_enhancements=0,
            failed_enhancements=0,
            enhanced_images=[],
            failed_brackets=[],
            retry_attempts=0
        )
        
        # Validate enhancement_ids structure
        if enhancement_ids and isinstance(enhancement_ids, list) and len(enhancement_ids) > 0:
            sample = enhancement_ids[0]
            if not isinstance(sample, dict) or 'enhancement_id' not in sample:
                # Convert flat list to proper format
                if isinstance(sample, str):
                    enhancement_ids = [
                        {'enhancement_id': eid, 'bracket_index': i}
                        for i, eid in enumerate(enhancement_ids)
                    ]
                    print(f"Converted flat list to enhancement objects: {len(enhancement_ids)} items")
        
        # Validate required fields
        required = ['listing_id', 'enhancement_ids', 'callback_webhook']
        missing = [f for f in required if not event_data.get(f)]
        
        if missing:
            error_msg = f"Missing required fields: {', '.join(missing)}"
            failed_result = _create_standardized_job_result(
                job_id, listing_id or 'unknown', total_brackets, 0, [], 0, correlation_id
            )
            failed_result['status'] = 'job_failed'
            failed_result['failed_brackets'] = [{'bracket_index': -1, 'error': error_msg}]
            notifier.send_business('job_completed', failed_result)
            
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': error_msg,
                    'job_id': job_id,
                    'correlation_id': correlation_id
                })
            }

        # =====================================================================
        # CREATE STORAGE PROVIDER
        # =====================================================================
        try:
            if storage_provider_name == 'dropbox':
                # Get destination folder
                destination_folder = event_data.get('dropbox_destination_folder', '/enhanced')
                
                storage_credentials = {
                    'refresh_token': event_data.get('dropbox_refresh_token'),
                    'app_key': event_data.get('dropbox_app_key'),
                    'app_secret': event_data.get('dropbox_app_secret'),
                    'member_id': event_data.get('dropbox_team_member_id'),
                }
                
            elif storage_provider_name == 'google_drive':
                # Get destination folder ID
                destination_folder = event_data.get('google_drive_destination_folder_id')
                
                storage_credentials = {
                    'client_id': event_data.get('google_drive_client_id'),
                    'client_secret': event_data.get('google_drive_client_secret'),
                    'refresh_token': event_data.get('google_drive_refresh_token'),
                }
            else:
                raise ValueError(f"Unknown storage provider: {storage_provider_name}")
            
            storage = StorageFactory.create(storage_provider_name, storage_credentials)
            print(f"Storage provider connected: {storage_provider_name}")
            
        except Exception as e:
            error_msg = f"Storage connection failed: {str(e)}"
            notifier.send_error('storage_connection_failed', error_msg)
            
            failed_result = _create_standardized_job_result(
                job_id, listing_id, total_brackets, 0, [], 0, correlation_id
            )
            failed_result['status'] = 'job_failed'
            failed_result['failed_brackets'] = [{'bracket_index': -1, 'error': error_msg}]
            notifier.send_business('job_completed', failed_result)
            
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': error_msg,
                    'job_id': job_id,
                    'correlation_id': correlation_id
                })
            }

        # =====================================================================
        # CREATE ENHANCEMENT PROVIDER
        # =====================================================================
        try:
            if enhancement_provider_name == 'fotello':
                enhancement = EnhancementFactory.create(
                    'fotello',
                    event_data.get('fotello_api_key')
                )
            elif enhancement_provider_name == 'autohdr':
                enhancement = EnhancementFactory.create(
                    'autohdr',
                    event_data.get('autohdr_api_key'),
                    email=event_data.get('autohdr_email')
                )
            else:
                raise ValueError(f"Unknown enhancement provider: {enhancement_provider_name}")
            
            print(f"Enhancement provider connected: {enhancement_provider_name}")
            
        except Exception as e:
            error_msg = f"Enhancement provider connection failed: {str(e)}"
            notifier.send_error('enhancement_connection_failed', error_msg)
            
            failed_result = _create_standardized_job_result(
                job_id, listing_id, total_brackets, 0, [], 0, correlation_id
            )
            failed_result['status'] = 'job_failed'
            failed_result['failed_brackets'] = [{'bracket_index': -1, 'error': error_msg}]
            notifier.send_business('job_completed', failed_result)
            
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': error_msg,
                    'job_id': job_id,
                    'correlation_id': correlation_id
                })
            }

        # =====================================================================
        # PROCESS ENHANCEMENTS WITH RETRY LOGIC
        # =====================================================================
        completed_enhancements = []
        pending_retries = enhancement_ids.copy()
        retry_count = 0
        total_enhancements_count = len(enhancement_ids)
        
        while pending_retries and retry_count <= MAX_RETRIES:
            print(f"Processing attempt #{retry_count + 1} for {len(pending_retries)} enhancements")
            
            if retry_count > 0:
                notifier.send_debug('retry_attempt', {
                    'retry_count': retry_count,
                    'pending_count': len(pending_retries),
                    'total_enhancements': total_enhancements_count
                })
                print(f"Waiting {RETRY_DELAY_SECONDS} seconds before retry...")
                time.sleep(RETRY_DELAY_SECONDS)
            
            still_pending = []
            
            for idx, enhancement_info in enumerate(pending_retries):
                current_num = idx + 1
                total_pending = len(pending_retries)
                
                print(f"Checking enhancement {current_num}/{total_pending} (bracket {enhancement_info['bracket_index'] + 1})")
                
                result = _process_enhancement(
                    enhancement_info=enhancement_info,
                    enhancement_provider=enhancement,
                    storage_provider=storage,
                    listing_id=listing_id,
                    destination_folder=destination_folder,
                    notifier=notifier,
                    current_num=current_num,
                    total_num=total_pending,
                    filename_prefix=filename_prefix
                )
                
                if result.get('retry_needed'):
                    still_pending.append(enhancement_info)
                    print(f"Enhancement {enhancement_info['enhancement_id']} still in progress, will retry")
                else:
                    completed_enhancements.append(result)
                    print(f"Enhancement {enhancement_info['enhancement_id']} finished: {result['status']}")
            
            pending_retries = still_pending
            retry_count += 1
        
        # Handle any remaining in-progress as timeouts
        for enhancement_info in pending_retries:
            completed_enhancements.append({
                'enhancement_id': enhancement_info['enhancement_id'],
                'bracket_index': enhancement_info['bracket_index'],
                'status': 'timeout',
                'error': f'Enhancement still in progress after {MAX_RETRIES} retry attempts'
            })
        
        # =====================================================================
        # SEND FINAL RESULT
        # =====================================================================
        job_result = _create_standardized_job_result(
            job_id, listing_id, total_brackets,
            processed_brackets, completed_enhancements, retry_count, correlation_id
        )
        
        notifier.send_business('job_completed', job_result)
        
        print(f"Job completed with status: {job_result['status']}")
        print(f"Successful: {job_result['successful_enhancements']}, Failed: {job_result['failed_enhancements']}")

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'message': 'Processing completed',
                'job_id': job_id,
                'listing_id': listing_id,
                'status': job_result['status'],
                'total_enhancements': len(enhancement_ids),
                'successful_uploads': job_result['successful_enhancements'],
                'failed_uploads': job_result['failed_enhancements'],
                'enhanced_images': [img['storage_path'] for img in job_result['enhanced_images']],
                'version': VERSION,
                'retry_attempts': retry_count,
                'correlation_id': correlation_id
            })
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"Finalize function error: {error_msg}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        # Send failure notification
        if notifier:
            try:
                failed_result = _create_standardized_job_result(
                    event_data.get('job_id', 'unknown'),
                    event_data.get('listing_id', 'unknown'),
                    event_data.get('total_brackets', 0),
                    0, [], 0, correlation_id
                )
                failed_result['status'] = 'job_failed'
                failed_result['failed_brackets'] = [{'bracket_index': -1, 'error': f'Function error: {error_msg}'}]
                notifier.send_business('job_completed', failed_result)
            except:
                pass
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': error_msg,
                'error_type': type(e).__name__,
                'job_id': event_data.get('job_id', 'unknown') if 'event_data' in dir() else 'unknown',
                'version': VERSION,
                'correlation_id': correlation_id
            })
        }
