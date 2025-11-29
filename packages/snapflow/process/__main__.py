"""
SnapFlow Process Function
=========================
Downloads photos from storage, uploads to enhancement API, requests processing.

Version: 1.0.0-snapflow
"""

import json
import os
import requests
import uuid
import time
import gc
from typing import Dict, Any, List

# Import from SnapFlow Core shared library
from shared import (
    # Factories
    StorageFactory,
    EnhancementFactory,
    # Config
    decrypt_credentials,
    SHARED_VERSION,
    # Notifications
    WebhookNotifier,
    NotificationLevel,
    # Utils
    validate_file_size,
    get_file_type_info,
    get_memory_info,
    force_garbage_collection,
)

# Function version
VERSION = f"1.0.0-process-snapflow-{SHARED_VERSION}"


def _parse_notification_level(level_str: str) -> NotificationLevel:
    """Convert string to NotificationLevel enum"""
    mapping = {
        'errors_only': NotificationLevel.ERRORS_ONLY,
        'minimal': NotificationLevel.MINIMAL,
        'standard': NotificationLevel.STANDARD,
        'verbose': NotificationLevel.VERBOSE,
    }
    return mapping.get(level_str, NotificationLevel.MINIMAL)


def main(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    SnapFlow Process Function
    
    Downloads photos from storage provider, uploads to enhancement provider,
    and requests enhancement processing.
    
    Supports:
    - Storage: Dropbox, Google Drive
    - Enhancement: Fotello, AutoHDR
    - skip_finalize: For delayed retrieval workflows
    """
    # Setup correlation ID
    correlation_id = event.get('correlation_id', str(uuid.uuid4()))
    print(f"=== SNAPFLOW PROCESS v{VERSION} === [ID: {correlation_id}]")
    
    # Initialize tracking variables
    job_id = None
    callback_webhook = None
    listing_id = None
    notifier = None
    files_processed = 0
    files_uploaded = 0
    brackets_processed = 0
    
    try:
        # Parse event data
        if 'job_id' in event or 'listing_id' in event:
            event_data = event
        elif 'body' in event and event['body']:
            body = event.get('body')
            if isinstance(body, str):
                event_data = json.loads(body)
            else:
                event_data = body
        else:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'job_failed',
                    'error': 'No valid data found in event',
                    'correlation_id': correlation_id
                })
            }

        # Extract common fields
        job_id = event_data.get('job_id', str(uuid.uuid4()))
        client_id = event_data.get('client_id')
        listing_id = event_data.get('listing_id')
        callback_webhook = event_data.get('callback_webhook')
        brackets_data = event_data.get('brackets_data', [])
        notification_level = _parse_notification_level(event_data.get('notification_level', 'minimal'))
        filename_prefix = event_data.get('filename_prefix')
        skip_finalize = event_data.get('skip_finalize', False)
        
        # Detect providers
        storage_provider = event_data.get('storage_provider', 'dropbox')
        enhancement_provider = event_data.get('enhancement_provider', 'fotello')
        
        print(f"Job: {job_id}, Listing: {listing_id}")
        print(f"Providers - Storage: {storage_provider}, Enhancement: {enhancement_provider}")
        print(f"skip_finalize: {skip_finalize}")
        
        # Create notifier
        notifier = WebhookNotifier(
            callback_webhook=callback_webhook,
            job_id=job_id,
            listing_id=listing_id,
            client_id=client_id,
            correlation_id=correlation_id,
            notification_level=notification_level,
            function_name='process',
            version=VERSION
        )
        
        # Send process started notification
        notifier.send_debug('process_started', {
            'storage_provider': storage_provider,
            'enhancement_provider': enhancement_provider,
            'brackets_count': len(brackets_data),
            'skip_finalize': skip_finalize
        })

        # Validate required fields
        required_fields = ['listing_id', 'callback_webhook']
        missing = [f for f in required_fields if not event_data.get(f)]
        if missing:
            error_msg = f"Missing required fields: {', '.join(missing)}"
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'job_failed',
                    'error': error_msg,
                    'correlation_id': correlation_id
                })
            }

        if not brackets_data:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'job_failed',
                    'error': 'No brackets_data found in payload',
                    'correlation_id': correlation_id
                })
            }

        # =====================================================================
        # CREATE STORAGE PROVIDER
        # =====================================================================
        notifier.send_debug('storage_connecting', {'provider': storage_provider})
        
        try:
            if storage_provider == 'dropbox':
                storage_credentials = {
                    'refresh_token': event_data.get('dropbox_refresh_token'),
                    'app_key': event_data.get('dropbox_app_key'),
                    'app_secret': event_data.get('dropbox_app_secret'),
                    'member_id': event_data.get('dropbox_team_member_id'),
                }
            elif storage_provider == 'google_drive':
                storage_credentials = {
                    'client_id': event_data.get('google_drive_client_id'),
                    'client_secret': event_data.get('google_drive_client_secret'),
                    'refresh_token': event_data.get('google_drive_refresh_token'),
                }
            else:
                raise ValueError(f"Unknown storage provider: {storage_provider}")
            
            storage = StorageFactory.create(storage_provider, storage_credentials)
            user_info = storage.get_user_info()
            
            notifier.send_debug('storage_connected', {
                'provider': storage_provider,
                'user': user_info.get('display_name') or user_info.get('email')
            })
            
        except Exception as e:
            error_msg = f"Storage connection failed: {str(e)}"
            notifier.send_error('storage_connection_failed', error_msg)
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'job_failed',
                    'error': error_msg,
                    'correlation_id': correlation_id
                })
            }

        # =====================================================================
        # CREATE ENHANCEMENT PROVIDER
        # =====================================================================
        notifier.send_debug('enhancement_connecting', {'provider': enhancement_provider})
        
        try:
            if enhancement_provider == 'fotello':
                enhancement = EnhancementFactory.create(
                    'fotello', 
                    event_data.get('fotello_api_key')
                )
            elif enhancement_provider == 'autohdr':
                enhancement = EnhancementFactory.create(
                    'autohdr',
                    event_data.get('autohdr_api_key'),
                    email=event_data.get('autohdr_email')
                )
            else:
                raise ValueError(f"Unknown enhancement provider: {enhancement_provider}")
            
            notifier.send_debug('enhancement_connected', {'provider': enhancement_provider})
            
        except Exception as e:
            error_msg = f"Enhancement provider connection failed: {str(e)}"
            notifier.send_error('enhancement_connection_failed', error_msg)
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'job_failed',
                    'error': error_msg,
                    'correlation_id': correlation_id
                })
            }

        # =====================================================================
        # PROCESS BRACKETS
        # =====================================================================
        notifier.send_debug('bracket_processing_started', {'total_brackets': len(brackets_data)})
        
        enhancement_ids = []
        total_brackets_count = len(brackets_data)
        
        for bracket_idx, bracket in enumerate(brackets_data):
            current_bracket_num = bracket_idx + 1
            
            # Log memory and progress
            memory_info = get_memory_info()
            notifier.send_debug('processing_bracket_started', {
                'bracket_index': bracket_idx,
                'bracket_progress': f"{current_bracket_num} of {total_brackets_count}",
                'file_count': len(bracket),
                **memory_info
            })
            
            print(f"Processing bracket {current_bracket_num}/{total_brackets_count} ({len(bracket)} files)")
            
            # Download and prepare files for this bracket
            bracket_files = []
            for file_info in bracket:
                # Support both Dropbox (path_lower) and Google Drive (id) formats
                file_path = file_info.get('path_lower') or file_info.get('id') or file_info.get('path_id')
                original_filename = file_info.get('name')
                
                if not file_path or not original_filename:
                    print(f"Skipping file due to missing path or name: {file_info}")
                    continue

                try:
                    # Download file from storage
                    file_bytes = storage.download_file(file_path)
                    
                    # Validate file size
                    is_valid, error_msg = validate_file_size(original_filename, len(file_bytes))
                    if not is_valid:
                        print(f"File {original_filename} failed validation: {error_msg}")
                        continue

                    bracket_files.append({
                        'name': original_filename,
                        'bytes': file_bytes,
                        'file_type': get_file_type_info(original_filename)[0]
                    })
                    
                    files_processed += 1
                    
                except Exception as e:
                    print(f"Failed to download {original_filename}: {e}")
                    continue
            
            if not bracket_files:
                print(f"No valid files in bracket {current_bracket_num}, skipping")
                notifier.send_debug('bracket_skipped_no_files', {
                    'bracket_index': bracket_idx,
                    'reason': 'no_valid_files'
                })
                continue
            
            # Upload bracket to enhancement provider
            try:
                print(f"Uploading bracket {current_bracket_num} ({len(bracket_files)} files)")
                
                # Upload each file and collect upload IDs
                upload_ids = []
                for file_info in bracket_files:
                    try:
                        upload_id = enhancement.upload_image(
                            file_info['name'],
                            file_info['bytes']
                        )
                        upload_ids.append(upload_id)
                        files_uploaded += 1
                        
                        # Clear file bytes immediately
                        file_info['bytes'] = None
                        
                    except Exception as e:
                        print(f"Failed to upload {file_info['name']}: {e}")
                        file_info['bytes'] = None
                        continue
                
                # Force garbage collection after large uploads
                bracket_files.clear()
                force_garbage_collection()
                
                if not upload_ids:
                    print(f"No files uploaded for bracket {current_bracket_num}")
                    notifier.send_debug('bracket_upload_failed', {
                        'bracket_index': bracket_idx,
                        'reason': 'no_successful_uploads'
                    })
                    continue
                
                # Request enhancement
                enhancement_id = enhancement.request_enhancement(
                    upload_ids=upload_ids,
                    listing_id=listing_id
                )
                
                enhancement_ids.append({
                    'enhancement_id': enhancement_id,
                    'bracket_index': bracket_idx,
                    'file_count': len(upload_ids)
                })
                
                brackets_processed += 1
                
                notifier.send_debug('enhancement_request_success', {
                    'bracket_index': bracket_idx,
                    'bracket_progress': f"{current_bracket_num} of {total_brackets_count}",
                    'enhancement_id': enhancement_id,
                    'files_uploaded': len(upload_ids)
                })
                
                print(f"Bracket {current_bracket_num} enhancement requested: {enhancement_id}")
                
            except Exception as e:
                print(f"Failed to process bracket {current_bracket_num}: {e}")
                notifier.send_error('bracket_processing_error', str(e), {
                    'bracket_index': bracket_idx
                })
                continue

        # =====================================================================
        # CHECK RESULTS
        # =====================================================================
        if not enhancement_ids:
            raise Exception("No brackets were successfully processed")

        # =====================================================================
        # HANDLE FINALIZE (or skip)
        # =====================================================================
        if skip_finalize:
            # Return enhancement IDs for later retrieval
            print(f"skip_finalize=True: Returning {len(enhancement_ids)} enhancement IDs")
            
            notifier.send_debug('finalize_skipped', {
                'enhancement_ids_count': len(enhancement_ids),
                'reason': 'skip_finalize=true'
            })
            
            # Send completion callback with enhancement IDs for storage
            notifier.send_job_result(
                status='enhancement_requested',
                total_brackets=len(brackets_data),
                processed_brackets=brackets_processed,
                successful_enhancements=len(enhancement_ids),
                failed_enhancements=len(brackets_data) - brackets_processed,
                enhanced_images=[],  # Not available yet
                failed_brackets=[],
                retry_attempts=0
            )
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'status': 'enhancement_requested',
                    'job_id': job_id,
                    'listing_id': listing_id,
                    'skip_finalize': True,
                    'enhancement_ids': enhancement_ids,
                    'files_processed': files_processed,
                    'files_uploaded': files_uploaded,
                    'brackets_processed': brackets_processed,
                    'message': f'Enhancement requested for {brackets_processed} brackets. Call finalize later with enhancement_ids.',
                    'version': VERSION,
                    'correlation_id': correlation_id
                })
            }
        
        # Call finalize function
        notifier.send_debug('finalize_call_attempt', {
            'enhancement_ids_count': len(enhancement_ids)
        })
        
        finalize_url = os.getenv("FINALIZE_FUNCTION_URL")
        if not finalize_url:
            print("FINALIZE_FUNCTION_URL not set, skipping finalize call")
            notifier.send_debug('finalize_url_missing', {})
        else:
            # Build finalize payload
            finalize_payload = {
                'job_id': job_id,
                'listing_id': listing_id,
                'filename_prefix': filename_prefix,
                'enhancement_ids': enhancement_ids,
                'callback_webhook': callback_webhook,
                'notification_level': event_data.get('notification_level', 'minimal'),
                'total_brackets': len(brackets_data),
                'processed_brackets': brackets_processed,
                'version': VERSION,
                'correlation_id': correlation_id,
                
                # Pass through storage credentials for finalize to upload results
                'storage_provider': storage_provider,
            }
            
            # Add storage credentials based on provider
            if storage_provider == 'dropbox':
                finalize_payload.update({
                    'dropbox_refresh_token': event_data.get('dropbox_refresh_token'),
                    'dropbox_app_key': event_data.get('dropbox_app_key'),
                    'dropbox_app_secret': event_data.get('dropbox_app_secret'),
                    'dropbox_destination_folder': event_data.get('dropbox_destination_folder'),
                    'dropbox_team_member_id': event_data.get('dropbox_team_member_id'),
                    'access_mode': event_data.get('access_mode', 'member'),
                })
            elif storage_provider == 'google_drive':
                finalize_payload.update({
                    'google_drive_client_id': event_data.get('google_drive_client_id'),
                    'google_drive_client_secret': event_data.get('google_drive_client_secret'),
                    'google_drive_refresh_token': event_data.get('google_drive_refresh_token'),
                    'google_drive_destination_folder_id': event_data.get('google_drive_destination_folder_id'),
                })
            
            # Add enhancement credentials
            if enhancement_provider == 'fotello':
                finalize_payload['fotello_api_key'] = event_data.get('fotello_api_key')
            elif enhancement_provider == 'autohdr':
                finalize_payload['autohdr_api_key'] = event_data.get('autohdr_api_key')
                finalize_payload['autohdr_email'] = event_data.get('autohdr_email')
            
            finalize_payload['enhancement_provider'] = enhancement_provider
            
            try:
                print("Calling finalize function...")
                finalize_response = requests.post(
                    finalize_url,
                    json=finalize_payload,
                    timeout=90,
                    headers={'Content-Type': 'application/json'}
                )
                print(f"Finalize response: {finalize_response.status_code}")
                
                if finalize_response.status_code >= 400:
                    notifier.send_error('finalize_call_failed', finalize_response.text)
                else:
                    notifier.send_debug('finalize_called_successfully', {
                        'status_code': finalize_response.status_code
                    })
                    
            except Exception as e:
                print(f"Failed to call finalize: {e}")
                notifier.send_error('finalize_call_exception', str(e))

        # Process completed
        notifier.send_debug('process_completed_success', {
            'brackets_processed': brackets_processed,
            'enhancement_requests': len(enhancement_ids),
            'files_processed': files_processed,
            'files_uploaded': files_uploaded
        })

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'enhancement_requested',
                'job_id': job_id,
                'listing_id': listing_id,
                'files_processed': files_processed,
                'files_uploaded': files_uploaded,
                'brackets_processed': brackets_processed,
                'enhancement_requests': len(enhancement_ids),
                'message': f'Successfully processed {brackets_processed} brackets. Finalize monitoring started.',
                'version': VERSION,
                'correlation_id': correlation_id
            })
        }

    except Exception as e:
        error_msg = str(e)
        print(f"Process function failed: {error_msg}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        
        # Send error notification
        if notifier:
            notifier.send_error('job_failed', error_msg)

        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'status': 'job_failed',
                'job_id': job_id,
                'listing_id': listing_id,
                'error': error_msg,
                'files_processed': files_processed,
                'files_uploaded': files_uploaded,
                'brackets_processed': brackets_processed,
                'version': VERSION,
                'correlation_id': correlation_id
            })
        }
