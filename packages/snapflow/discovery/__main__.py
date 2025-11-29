"""
SnapFlow Discovery Function
===========================
Lists files from storage, extracts EXIF metadata, creates brackets.

Modes:
- discovery: List all files, return pagination info
- process_page: Extract EXIF from a page of files
- make_bracket: Create brackets from aggregated metadata

Version: 1.0.0-snapflow
"""

import json
import os
import uuid
import math
import time
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List, Optional, Tuple
from io import BytesIO

# Import from SnapFlow Core shared library
from shared import (
    # Factories
    StorageFactory,
    # Config
    decrypt_credentials,
    SHARED_VERSION,
)

# Third-party imports for EXIF
try:
    import exifread
    EXIFREAD_AVAILABLE = True
except ImportError:
    EXIFREAD_AVAILABLE = False
    print("WARNING: exifread not available, EXIF extraction disabled")

# Function version
VERSION = f"1.0.0-discovery-snapflow-{SHARED_VERSION}"

# Configuration
DEFAULT_TIME_DELTA_SECONDS = 2
DEFAULT_FILES_PER_PAGE = 25
MAX_THREADS = 3
MAX_RETRIES = 3
RETRY_DELAY = 2
RAW_HEADER_SIZE = 64 * 1024

# Supported file extensions
RAW_EXTENSIONS = ('.arw', '.nef', '.cr2', '.cr3', '.dng', '.raw', '.orf', '.rw2')
SUPPORTED_EXTENSIONS = ('.jpg', '.jpeg') + RAW_EXTENSIONS


def _detect_dji_file(filename: str) -> bool:
    """Detect DJI drone files by filename pattern"""
    return filename.upper().startswith('DJI_') and filename.lower().endswith('.dng')


def _get_time_delta_with_dji_override(
    time_delta_seconds: Optional[float],
    metadata_files: List[Dict]
) -> timedelta:
    """Get time delta with automatic DJI override"""
    
    # Default if not provided
    if time_delta_seconds is None:
        requested_seconds = DEFAULT_TIME_DELTA_SECONDS
    else:
        try:
            requested_seconds = float(time_delta_seconds)
        except (ValueError, TypeError):
            print(f"Invalid time_delta_seconds: {time_delta_seconds}, using default")
            requested_seconds = DEFAULT_TIME_DELTA_SECONDS
    
    # Count DJI files
    dji_count = sum(1 for f in metadata_files if _detect_dji_file(f.get('name', '')))
    total_files = len(metadata_files)
    dji_ratio = dji_count / total_files if total_files > 0 else 0
    
    if dji_ratio > 0.5:
        # Majority DJI - use longer time delta
        actual_seconds = 10
        print(f"DJI detected ({dji_count}/{total_files}): time_delta={actual_seconds}s")
    else:
        actual_seconds = requested_seconds
        print(f"Standard cameras: time_delta={actual_seconds}s")
    
    return timedelta(seconds=actual_seconds)


def _extract_exif_datetime(file_bytes: bytes, filename: str) -> Optional[str]:
    """Extract datetime from EXIF data"""
    if not EXIFREAD_AVAILABLE:
        return None
    
    try:
        with BytesIO(file_bytes) as stream:
            tags = exifread.process_file(stream, details=True)
        
        if not tags:
            return None
        
        # DJI-specific tag priority
        if _detect_dji_file(filename):
            datetime_tags = ['Image DateTime', 'EXIF DateTime', 'DateTime']
        else:
            datetime_tags = ['EXIF DateTimeOriginal', 'Image DateTime', 'EXIF DateTime', 'DateTime']
        
        for tag_name in datetime_tags:
            if tag_name in tags:
                try:
                    dt = datetime.strptime(str(tags[tag_name]), '%Y:%m:%d %H:%M:%S')
                    return dt.isoformat()
                except ValueError:
                    continue
        
        return None
        
    except Exception as e:
        print(f"EXIF extraction failed for {filename}: {e}")
        return None


def _download_and_extract_exif(
    storage_provider,
    file_info: Dict[str, Any],
    attempt: int = 1
) -> Optional[Dict[str, Any]]:
    """Download file and extract EXIF metadata"""
    
    file_path = file_info.get('path_lower') or file_info.get('id') or file_info.get('path_id')
    file_name = file_info.get('name', '')
    
    if not file_path:
        print(f"No path for file: {file_name}")
        return None
    
    try:
        # For RAW files, try partial download first (header only)
        is_raw = file_name.lower().endswith(RAW_EXTENSIONS)
        is_cr3 = file_name.lower().endswith('.cr3')
        
        if is_raw and not is_cr3:
            # Partial download for most RAW files
            try:
                file_bytes = storage_provider.download_file_partial(file_path, 0, RAW_HEADER_SIZE)
            except (NotImplementedError, AttributeError):
                # Fallback to full download
                file_bytes = storage_provider.download_file(file_path)
        else:
            # Full download for JPEG and CR3 (CR3 needs full file)
            file_bytes = storage_provider.download_file(file_path)
        
        # Extract EXIF
        date_taken = _extract_exif_datetime(file_bytes, file_name)
        
        if date_taken:
            result = {
                'name': file_name,
                'path_lower': file_path,
                'date_taken': date_taken
            }
            
            # Add DJI marker
            if _detect_dji_file(file_name):
                result['manufacturer'] = 'dji'
            
            return result
        else:
            print(f"No datetime found for: {file_name}")
            return None
            
    except Exception as e:
        if attempt < MAX_RETRIES:
            print(f"Download failed for {file_name}: {e}, retrying...")
            time.sleep(RETRY_DELAY)
            return _download_and_extract_exif(storage_provider, file_info, attempt + 1)
        else:
            print(f"Download failed after {MAX_RETRIES} attempts: {file_name}")
            return None


def _group_files_by_bracket(
    files: List[Dict[str, Any]],
    time_delta: timedelta
) -> List[List[Dict[str, Any]]]:
    """Group files into brackets based on time delta"""
    if not files:
        return []
    
    print(f"Creating brackets from {len(files)} files, time_delta={time_delta.total_seconds()}s")
    
    # Sort by timestamp
    sorted_files = sorted(files, key=lambda f: f['date_taken'])
    
    brackets = []
    current_bracket = []
    
    for file in sorted_files:
        current_time = datetime.fromisoformat(file['date_taken'])
        
        if not current_bracket:
            current_bracket.append(file)
        else:
            last_time = datetime.fromisoformat(current_bracket[-1]['date_taken'])
            time_gap = current_time - last_time
            
            if time_gap <= time_delta:
                current_bracket.append(file)
            else:
                # Finish current bracket
                bracket_output = [{'name': f['name'], 'path_lower': f['path_lower']} for f in current_bracket]
                brackets.append(bracket_output)
                current_bracket = [file]
    
    # Add final bracket
    if current_bracket:
        bracket_output = [{'name': f['name'], 'path_lower': f['path_lower']} for f in current_bracket]
        brackets.append(bracket_output)
    
    print(f"Created {len(brackets)} brackets")
    return brackets


def _sort_brackets_chronologically(
    brackets: List[List[Dict]],
    all_metadata: List[Dict]
) -> List[List[Dict]]:
    """Sort brackets by earliest timestamp in each bracket"""
    if not brackets or not all_metadata:
        return brackets
    
    # Create lookup
    metadata_lookup = {f['name']: f['date_taken'] for f in all_metadata}
    
    def get_earliest_time(bracket):
        times = [metadata_lookup.get(f['name'], '9999-12-31') for f in bracket]
        return min(times) if times else '9999-12-31'
    
    return sorted(brackets, key=get_earliest_time)


# =============================================================================
# MODE HANDLERS
# =============================================================================

def _handle_discovery_mode(
    storage_provider,
    folder_path: str,
    files_per_page: int,
    max_files: Optional[int] = None
) -> Dict[str, Any]:
    """Discovery mode: List all files and return pagination info"""
    print(f"Discovery mode: listing files in {folder_path}")
    
    # List files from storage
    all_files = storage_provider.list_files(
        folder=folder_path,
        extensions=SUPPORTED_EXTENSIONS,
        recursive=True,
        max_files=max_files
    )
    
    total_files = len(all_files)
    total_pages = math.ceil(total_files / files_per_page) if total_files > 0 else 0
    session_id = str(uuid.uuid4())
    
    print(f"Discovery complete: {total_files} files, {total_pages} pages")
    
    return {
        'status': 'discovery_success',
        'total_files': total_files,
        'total_pages': total_pages,
        'files_per_page': files_per_page,
        'session_id': session_id,
        'all_files': all_files,
        'file_limit_active': max_files is not None,
        'max_files_applied': max_files
    }


def _handle_process_page_mode(
    storage_provider,
    page_number: int,
    files_per_page: int,
    all_files: List[Dict],
    session_id: str
) -> Dict[str, Any]:
    """Process page mode: Extract EXIF from a page of files"""
    print(f"Process page mode: page {page_number}")
    
    # Get files for this page
    start_idx = (page_number - 1) * files_per_page
    end_idx = start_idx + files_per_page
    page_files = all_files[start_idx:end_idx]
    
    print(f"Processing files {start_idx + 1}-{min(end_idx, len(all_files))} of {len(all_files)}")
    
    # Process with threading
    extracted_metadata = []
    
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        future_to_file = {
            executor.submit(_download_and_extract_exif, storage_provider, f): f
            for f in page_files
        }
        
        for future in as_completed(future_to_file):
            result = future.result()
            if result:
                extracted_metadata.append(result)
    
    print(f"Page {page_number} complete: {len(extracted_metadata)} files processed")
    
    return {
        'status': 'page_processed',
        'page_number': page_number,
        'session_id': session_id,
        'processed_count': len(extracted_metadata),
        'metadata': extracted_metadata
    }


def _handle_make_bracket_mode(
    aggregated_metadata: List,
    time_delta_seconds: Optional[float]
) -> List[List[Dict]]:
    """Make bracket mode: Create brackets from aggregated metadata"""
    print("Make bracket mode")
    
    # Flatten nested arrays if needed
    all_metadata = []
    
    if len(aggregated_metadata) == 1 and isinstance(aggregated_metadata[0], list):
        # Double-nested: [[{...}]]
        all_metadata = aggregated_metadata[0]
    else:
        # Normal case: [{...}] or [[{...}], [{...}]]
        for item in aggregated_metadata:
            if isinstance(item, list):
                all_metadata.extend(item)
            else:
                all_metadata.append(item)
    
    print(f"Flattened to {len(all_metadata)} files")
    
    if not all_metadata:
        raise ValueError("No metadata found after flattening")
    
    # Validate format
    if 'date_taken' not in all_metadata[0]:
        raise ValueError("Invalid format: 'date_taken' field missing")
    
    # Get time delta
    time_delta = _get_time_delta_with_dji_override(time_delta_seconds, all_metadata)
    
    # Create brackets
    brackets = _group_files_by_bracket(all_metadata, time_delta)
    
    # Sort chronologically
    sorted_brackets = _sort_brackets_chronologically(brackets, all_metadata)
    
    print(f"Created {len(sorted_brackets)} brackets from {len(all_metadata)} files")
    
    return sorted_brackets


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    SnapFlow Discovery Function
    
    Modes:
    - discovery: List files, return pagination info
    - process_page: Extract EXIF from a page of files
    - make_bracket: Create brackets from aggregated metadata
    """
    correlation_id = data.get('correlation_id', str(uuid.uuid4()))
    print(f"=== SNAPFLOW DISCOVERY v{VERSION} === [ID: {correlation_id}]")
    
    try:
        mode = data.get('mode')
        
        if mode not in ['discovery', 'process_page', 'make_bracket']:
            raise ValueError(f"Invalid mode: {mode}. Must be 'discovery', 'process_page', or 'make_bracket'")
        
        print(f"Mode: {mode}")
        
        # =====================================================================
        # MAKE_BRACKET MODE (no storage connection needed)
        # =====================================================================
        if mode == 'make_bracket':
            aggregated_metadata = data.get('aggregated_metadata')
            time_delta_seconds = data.get('time_delta_seconds')
            
            if not aggregated_metadata:
                raise ValueError("Missing 'aggregated_metadata' for make_bracket mode")
            
            brackets = _handle_make_bracket_mode(aggregated_metadata, time_delta_seconds)
            
            return {
                'statusCode': 200,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps(brackets)
            }
        
        # =====================================================================
        # DISCOVERY & PROCESS_PAGE MODES (need storage connection)
        # =====================================================================
        client_id = data.get('client_id')
        if not client_id:
            raise ValueError("Missing 'client_id'")
        
        # Detect storage provider
        storage_provider_name = data.get('storage_provider')
        if not storage_provider_name:
            # Auto-detect from credentials
            if data.get('dropbox_refresh_token_encrypted') or data.get('dropbox_refresh_token'):
                storage_provider_name = 'dropbox'
            elif data.get('google_drive_refresh_token_encrypted') or data.get('google_drive_refresh_token'):
                storage_provider_name = 'google_drive'
            else:
                raise ValueError("Cannot detect storage provider from credentials")
        
        print(f"Storage provider: {storage_provider_name}")
        
        # Decrypt credentials if encrypted
        if data.get('dropbox_refresh_token_encrypted') or data.get('google_drive_refresh_token_encrypted'):
            decrypted_data = decrypt_credentials(data, client_id)
        else:
            decrypted_data = data
        
        # Create storage provider
        if storage_provider_name == 'dropbox':
            storage_credentials = {
                'refresh_token': decrypted_data.get('dropbox_refresh_token'),
                'app_key': decrypted_data.get('dropbox_app_key'),
                'app_secret': decrypted_data.get('dropbox_app_secret'),
                'member_id': decrypted_data.get('dropbox_team_member_id'),
            }
        elif storage_provider_name == 'google_drive':
            storage_credentials = {
                'client_id': decrypted_data.get('google_drive_client_id'),
                'client_secret': decrypted_data.get('google_drive_client_secret'),
                'refresh_token': decrypted_data.get('google_drive_refresh_token'),
            }
        else:
            raise ValueError(f"Unknown storage provider: {storage_provider_name}")
        
        storage = StorageFactory.create(storage_provider_name, storage_credentials)
        print("Storage connected")
        
        # Handle mode
        if mode == 'discovery':
            folder_path = data.get('dropbox_folder') or data.get('google_drive_folder_id')
            if not folder_path:
                raise ValueError("Missing folder path for discovery")
            
            files_per_page = data.get('files_per_page', DEFAULT_FILES_PER_PAGE)
            max_files = data.get('max_files')
            
            if max_files:
                try:
                    max_files = int(max_files)
                    if max_files <= 0:
                        max_files = None
                except (ValueError, TypeError):
                    max_files = None
            
            result = _handle_discovery_mode(storage, folder_path, files_per_page, max_files)
            
        elif mode == 'process_page':
            page_number = data.get('page_number')
            all_files = data.get('all_files')
            session_id = data.get('session_id', str(uuid.uuid4()))
            files_per_page = data.get('files_per_page', DEFAULT_FILES_PER_PAGE)
            
            if not page_number or not all_files:
                raise ValueError("Missing 'page_number' or 'all_files' for process_page")
            
            result = _handle_process_page_mode(storage, page_number, files_per_page, all_files, session_id)
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(result)
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"Discovery error: {error_msg}")
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
