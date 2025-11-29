"""
SnapFlow Gateway Function
=========================
Entry point for all photo enhancement requests.
Validates credentials, dispatches to process function.

Version: 1.0.0-snapflow
"""

import json
import os
import requests
import uuid
import threading
import time
from datetime import datetime
from typing import Dict, Any

# Import from SnapFlow Core shared library
from shared import (
    decrypt_credentials,
    mask_credentials,
    sanitize_filename_prefix,
    WebhookNotifier,
    NotificationLevel,
    SHARED_VERSION,
)

# Function version
VERSION = f"1.0.0-gateway-snapflow-{SHARED_VERSION}"


def _dispatch_async(
    process_url: str,
    payload: dict,
    callback_webhook: str,
    job_id: str,
    listing_id: str,
    client_id: str,
    correlation_id: str
):
    """
    Dispatch to process function in background thread.
    Runs after gateway has already returned to Make.com.
    """
    try:
        print(f"[ASYNC] Starting dispatch for job {job_id} (client: {client_id}) [ID: {correlation_id}]")
        
        payload['correlation_id'] = correlation_id

        response = requests.post(
            process_url,
            json=payload,
            timeout=60,
            headers={'Content-Type': 'application/json'}
        )

        print(f"[ASYNC] Dispatch response: {response.status_code}")

        if response.status_code >= 400:
            print(f"[ASYNC] Dispatch failed: {response.text}")
            _send_dispatch_error(callback_webhook, job_id, listing_id, client_id, 
                               f'Process function returned {response.status_code}', correlation_id)
        else:
            print(f"[ASYNC] Dispatch successful for job {job_id}")

    except Exception as e:
        print(f"[ASYNC] Dispatch error: {e}")
        _send_dispatch_error(callback_webhook, job_id, listing_id, client_id, 
                           f'Async dispatch failed: {str(e)}', correlation_id)
    finally:
        # Clear sensitive data from memory
        _clear_credentials_from_payload(payload)


def _send_dispatch_error(callback_webhook: str, job_id: str, listing_id: str, 
                        client_id: str, error: str, correlation_id: str):
    """Send dispatch error notification to callback webhook"""
    if not callback_webhook:
        return
    
    try:
        error_notification = {
            'status': 'dispatch_failed',
            'function_name': 'gateway',
            'log_level': 'ERROR',
            'job_id': job_id,
            'listing_id': listing_id,
            'client_id': client_id,
            'error': error,
            'timestamp': time.time(),
            'correlation_id': correlation_id,
            'version': VERSION
        }
        requests.post(callback_webhook, json=error_notification, timeout=10)
    except:
        pass


def _clear_credentials_from_payload(payload: dict):
    """Clear sensitive credentials from payload dict"""
    sensitive_fields = [
        'dropbox_app_key', 'dropbox_app_secret', 'dropbox_refresh_token',
        'fotello_api_key', 'autohdr_api_key',
        'google_drive_client_id', 'google_drive_client_secret', 'google_drive_refresh_token'
    ]
    for field in sensitive_fields:
        payload.pop(field, None)
    print(f"[ASYNC] Cleared credentials from payload")


def _parse_event_data(event: Dict[str, Any]) -> Dict[str, Any]:
    """Parse and extract data from various event formats"""
    
    # List of fields we expect
    expected_fields = [
        # Identity
        'client_id', 'listing_id',
        
        # Provider selection (new format)
        'storage_provider', 'enhancement_provider',
        
        # Dropbox credentials (legacy)
        'dropbox_refresh_token_encrypted', 'dropbox_app_key_encrypted', 
        'dropbox_app_secret_encrypted', 'dropbox_team_member_id', 'access_mode',
        
        # Google Drive credentials (legacy)
        'google_drive_client_id_encrypted', 'google_drive_client_secret_encrypted',
        'google_drive_refresh_token_encrypted',
        
        # Enhancement credentials (legacy)
        'fotello_api_key_encrypted',
        'autohdr_api_key_encrypted', 'autohdr_email',
        
        # Job configuration
        'callback_webhook', 'brackets_data', 
        'dropbox_folder', 'dropbox_destination_folder',
        'google_drive_folder_id', 'google_drive_destination_folder_id',
        'notification_level', 'filename_prefix',
        
        # Optional flags
        'skip_finalize',
    ]
    
    # HTTP request format (from web trigger)
    if '__ow_method' in event and '__ow_headers' in event:
        print("HTTP request detected")
        return {field: event.get(field) for field in expected_fields if field in event}
    
    # Body wrapper format
    if 'body' in event:
        body = event.get('body')
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                pass
        elif isinstance(body, dict):
            return body
    
    # Direct format (fields at top level)
    if 'listing_id' in event or 'client_id' in event:
        return event
    
    return None


def _validate_required_fields(data: Dict[str, Any]) -> list:
    """Validate required fields are present"""
    required = ['client_id', 'listing_id', 'callback_webhook', 'brackets_data']
    
    # Need either Dropbox or Google Drive credentials
    has_dropbox = data.get('dropbox_refresh_token_encrypted')
    has_google_drive = data.get('google_drive_refresh_token_encrypted')
    
    # Need either Fotello or AutoHDR credentials
    has_fotello = data.get('fotello_api_key_encrypted')
    has_autohdr = data.get('autohdr_api_key_encrypted')
    
    missing = [f for f in required if not data.get(f)]
    
    if not has_dropbox and not has_google_drive:
        missing.append('storage_credentials (dropbox or google_drive)')
    
    if not has_fotello and not has_autohdr:
        missing.append('enhancement_credentials (fotello or autohdr)')
    
    # Need destination folder
    if not data.get('dropbox_destination_folder') and not data.get('google_drive_destination_folder_id'):
        missing.append('destination_folder')
    
    return missing


def _detect_providers(data: Dict[str, Any]) -> tuple:
    """Detect storage and enhancement providers from credentials"""
    
    # Storage provider
    if data.get('storage_provider'):
        storage_provider = data['storage_provider']
    elif data.get('dropbox_refresh_token_encrypted'):
        storage_provider = 'dropbox'
    elif data.get('google_drive_refresh_token_encrypted'):
        storage_provider = 'google_drive'
    else:
        storage_provider = None
    
    # Enhancement provider
    if data.get('enhancement_provider'):
        enhancement_provider = data['enhancement_provider']
    elif data.get('fotello_api_key_encrypted'):
        enhancement_provider = 'fotello'
    elif data.get('autohdr_api_key_encrypted'):
        enhancement_provider = 'autohdr'
    else:
        enhancement_provider = None
    
    return storage_provider, enhancement_provider


def _build_process_payload(data: Dict[str, Any], decrypted: Dict[str, Any], 
                          job_id: str, storage_provider: str, 
                          enhancement_provider: str) -> Dict[str, Any]:
    """Build the payload for the process function"""
    
    payload = {
        # Job identity
        'job_id': job_id,
        'client_id': data.get('client_id'),
        'listing_id': data.get('listing_id'),
        
        # Providers
        'storage_provider': storage_provider,
        'enhancement_provider': enhancement_provider,
        
        # Job data
        'brackets_data': data.get('brackets_data', []),
        'callback_webhook': data.get('callback_webhook'),
        'notification_level': data.get('notification_level', 'minimal'),
        'filename_prefix': sanitize_filename_prefix(data.get('filename_prefix', '')),
        
        # Flags
        'skip_finalize': data.get('skip_finalize', False),
        
        # Version info
        'version': VERSION,
    }
    
    # Add storage credentials based on provider
    if storage_provider == 'dropbox':
        payload.update({
            'dropbox_refresh_token': decrypted.get('dropbox_refresh_token'),
            'dropbox_app_key': decrypted.get('dropbox_app_key'),
            'dropbox_app_secret': decrypted.get('dropbox_app_secret'),
            'dropbox_destination_folder': data.get('dropbox_destination_folder'),
            'dropbox_folder': data.get('dropbox_folder'),
            'dropbox_team_member_id': data.get('dropbox_team_member_id'),
            'access_mode': data.get('access_mode', 'member'),
        })
    elif storage_provider == 'google_drive':
        payload.update({
            'google_drive_client_id': decrypted.get('google_drive_client_id'),
            'google_drive_client_secret': decrypted.get('google_drive_client_secret'),
            'google_drive_refresh_token': decrypted.get('google_drive_refresh_token'),
            'google_drive_folder_id': data.get('google_drive_folder_id'),
            'google_drive_destination_folder_id': data.get('google_drive_destination_folder_id'),
        })
    
    # Add enhancement credentials based on provider
    if enhancement_provider == 'fotello':
        payload['fotello_api_key'] = decrypted.get('fotello_api_key')
    elif enhancement_provider == 'autohdr':
        payload['autohdr_api_key'] = decrypted.get('autohdr_api_key')
        payload['autohdr_email'] = data.get('autohdr_email')  # Not encrypted
    
    return payload


def main(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    SnapFlow Gateway - Entry point for photo enhancement requests.
    
    Accepts requests from Make.com, validates credentials, and dispatches
    to the process function asynchronously.
    
    Supports:
    - Storage: Dropbox, Google Drive
    - Enhancement: Fotello, AutoHDR
    """
    # Generate correlation ID for request tracking
    correlation_id = str(uuid.uuid4())
    
    try:
        print(f"=== SNAPFLOW GATEWAY v{VERSION} === [ID: {correlation_id}]")

        # Parse event data
        data = _parse_event_data(event)
        
        if not data or not isinstance(data, dict):
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'Invalid data format',
                    'correlation_id': correlation_id,
                    'version': VERSION
                })
            }

        # Extract client_id early for error reporting
        client_id = data.get('client_id')
        if not client_id:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'client_id is required',
                    'correlation_id': correlation_id,
                    'version': VERSION
                })
            }

        print(f"Request received for client: {client_id}")

        # Validate required fields
        missing_fields = _validate_required_fields(data)
        if missing_fields:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': f'Missing required fields: {", ".join(missing_fields)}',
                    'correlation_id': correlation_id,
                    'version': VERSION
                })
            }

        # Detect providers
        storage_provider, enhancement_provider = _detect_providers(data)
        print(f"Providers detected - Storage: {storage_provider}, Enhancement: {enhancement_provider}")

        # Decrypt credentials using SnapFlow Core
        try:
            decrypted_data = decrypt_credentials(data, client_id)
            print(f"Successfully decrypted credentials for client: {client_id}")
        except Exception as e:
            print(f"Decryption failed for client {client_id}: {e}")
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': f'Credential decryption failed: {str(e)}',
                    'correlation_id': correlation_id,
                    'version': VERSION
                })
            }

        # Validate decrypted credentials based on provider
        if storage_provider == 'dropbox':
            if not decrypted_data.get('dropbox_app_key') or len(decrypted_data.get('dropbox_app_key', '').strip()) < 10:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'error': 'Invalid decrypted dropbox_app_key format',
                        'correlation_id': correlation_id,
                        'version': VERSION
                    })
                }

        # Generate job ID
        job_id = str(uuid.uuid4())
        listing_id = data.get('listing_id')
        callback_webhook = data.get('callback_webhook')
        
        # Get process function URL
        process_url = os.getenv("PROCESS_FUNCTION_URL")
        if not process_url:
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'error': 'PROCESS_FUNCTION_URL not configured',
                    'correlation_id': correlation_id,
                    'version': VERSION
                })
            }

        # Build process payload
        process_payload = _build_process_payload(
            data, decrypted_data, job_id, storage_provider, enhancement_provider
        )

        # Calculate totals for response
        brackets_data = data.get('brackets_data', [])
        total_brackets = len(brackets_data)
        total_files = sum(len(bracket) for bracket in brackets_data)

        # Start async dispatch to process function
        print(f"Starting async dispatch for job {job_id}")
        dispatch_thread = threading.Thread(
            target=_dispatch_async,
            args=(
                process_url, 
                process_payload.copy(), 
                callback_webhook,
                job_id, 
                listing_id, 
                client_id, 
                correlation_id
            )
        )
        dispatch_thread.daemon = True
        dispatch_thread.start()

        # Clear sensitive data before logging
        for field in ['dropbox_app_key', 'dropbox_app_secret', 'dropbox_refresh_token',
                      'fotello_api_key', 'autohdr_api_key', 'google_drive_client_secret',
                      'google_drive_refresh_token']:
            decrypted_data.pop(field, None)
            process_payload.pop(field, None)

        # Immediate response to Make.com
        success_response = {
            'status': 'dispatched',
            'job_id': job_id,
            'client_id': client_id,
            'listing_id': listing_id,
            'storage_provider': storage_provider,
            'enhancement_provider': enhancement_provider,
            'total_brackets': total_brackets,
            'total_files': total_files,
            'skip_finalize': data.get('skip_finalize', False),
            'received_at': datetime.utcnow().isoformat() + "Z",
            'version': VERSION,
            'correlation_id': correlation_id
        }

        print(f"Gateway returning immediately for job {job_id}")

        return {
            'statusCode': 202,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(success_response)
        }

    except Exception as e:
        error_msg = str(e)
        print(f"Gateway error: {error_msg}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")

        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': error_msg,
                'version': VERSION,
                'correlation_id': correlation_id
            })
        }
