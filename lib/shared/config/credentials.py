"""
Credentials Management
======================
Handles client-specific encryption keys and credential decryption.

All tenants use Fernet symmetric encryption (standardized).

To generate a new client key:
    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())
    
Or use: generate_fernet_key() from this module.
"""

import os
from typing import Dict, Any, Optional
from cryptography.fernet import Fernet


def generate_fernet_key() -> str:
    """
    Generate a new Fernet encryption key.
    
    Use this to create keys for new clients.
    Add the generated key to DO environment variables as:
        CLIENT_XXX_ENCRYPTION_KEY="generated-key-here"
    
    Returns:
        Base64-encoded Fernet key string
    """
    return Fernet.generate_key().decode()


def get_client_encryption_key(client_id: str) -> str:
    """
    Get encryption key for specific client from environment variables.
    
    Args:
        client_id: Client identifier (e.g., "001", "002")
        
    Returns:
        Encryption key string
        
    Raises:
        ValueError: If client_id is missing or no key found
    """
    if not client_id:
        raise ValueError("client_id is required for multi-client setup")
    
    key_env_var = f"CLIENT_{client_id.upper()}_ENCRYPTION_KEY"
    encryption_key = os.getenv(key_env_var)
    
    if not encryption_key:
        available_clients = []
        for env_var in os.environ:
            if env_var.endswith('_ENCRYPTION_KEY') and env_var.startswith('CLIENT_'):
                client_name = env_var.replace('CLIENT_', '').replace('_ENCRYPTION_KEY', '')
                available_clients.append(client_name)
        
        raise ValueError(
            f"No encryption key found for client '{client_id}'. "
            f"Available clients: {available_clients}"
        )
    
    return encryption_key


def decrypt_credential(encrypted_value: str, encryption_key: str) -> str:
    """
    Decrypt a single encrypted credential value.
    
    Args:
        encrypted_value: Fernet-encrypted string
        encryption_key: Fernet key string
        
    Returns:
        Decrypted string value
        
    Raises:
        ValueError: If decryption fails
    """
    try:
        fernet = Fernet(encryption_key.encode())
        decrypted = fernet.decrypt(encrypted_value.encode()).decode()
        return decrypted
    except Exception as e:
        raise ValueError(f"Failed to decrypt credential: {e}")


def decrypt_credentials(data: Dict[str, Any], client_id: str) -> Dict[str, Any]:
    """
    Decrypt all encrypted credentials in a data dictionary.
    
    Supports two formats:
    
    1. Legacy format (current):
        {
            "dropbox_app_key_encrypted": "...",
            "dropbox_app_secret_encrypted": "...",
            "dropbox_refresh_token_encrypted": "...",
            "fotello_api_key_encrypted": "..."
        }
        
    2. New multi-provider format (future):
        {
            "storage_provider": "dropbox",
            "storage_credentials": {
                "app_key_encrypted": "...",
                "app_secret_encrypted": "...",
                "refresh_token_encrypted": "..."
            },
            "enhancement_provider": "fotello",
            "enhancement_credentials": {
                "api_key_encrypted": "..."
            }
        }
    
    Args:
        data: Dictionary containing encrypted fields
        client_id: Client identifier for key lookup
        
    Returns:
        Dictionary with decrypted values (encrypted fields replaced)
        
    Raises:
        ValueError: If decryption fails for any field
    """
    encryption_key = get_client_encryption_key(client_id)
    
    try:
        fernet = Fernet(encryption_key.encode())
    except Exception as e:
        raise ValueError(f"Invalid encryption key format for client {client_id}: {e}")
    
    decrypted_data = data.copy()
    
    # Check if new format (has storage_credentials or enhancement_credentials)
    if 'storage_credentials' in data or 'enhancement_credentials' in data:
        decrypted_data = _decrypt_new_format(data, fernet, client_id)
    else:
        decrypted_data = _decrypt_legacy_format(data, fernet, client_id)
    
    return decrypted_data


def _decrypt_legacy_format(data: Dict[str, Any], fernet: Fernet, client_id: str) -> Dict[str, Any]:
    """
    Decrypt legacy format with flat encrypted fields.
    
    Maps:
        dropbox_app_key_encrypted -> dropbox_app_key
        dropbox_app_secret_encrypted -> dropbox_app_secret
        dropbox_refresh_token_encrypted -> dropbox_refresh_token
        fotello_api_key_encrypted -> fotello_api_key
        autohdr_api_key_encrypted -> autohdr_api_key
        google_drive_*_encrypted -> google_drive_*
        
    Note: autohdr_email is NOT encrypted (plain text field)
    """
    decrypted_data = data.copy()
    
    # Storage provider encrypted fields
    storage_encrypted_fields = {
        # Dropbox
        'dropbox_app_key_encrypted': 'dropbox_app_key',
        'dropbox_app_secret_encrypted': 'dropbox_app_secret',
        'dropbox_refresh_token_encrypted': 'dropbox_refresh_token',
        # Google Drive (future)
        'google_drive_client_id_encrypted': 'google_drive_client_id',
        'google_drive_client_secret_encrypted': 'google_drive_client_secret',
        'google_drive_refresh_token_encrypted': 'google_drive_refresh_token',
    }
    
    # Enhancement provider encrypted fields
    enhancement_encrypted_fields = {
        'fotello_api_key_encrypted': 'fotello_api_key',
        'autohdr_api_key_encrypted': 'autohdr_api_key',
    }
    
    # Combine all encrypted fields
    all_encrypted_fields = {**storage_encrypted_fields, **enhancement_encrypted_fields}
    
    for encrypted_field, decrypted_field in all_encrypted_fields.items():
        if encrypted_field in data and data[encrypted_field]:
            try:
                encrypted_value = data[encrypted_field].encode()
                decrypted_value = fernet.decrypt(encrypted_value).decode()
                decrypted_data[decrypted_field] = decrypted_value
                del decrypted_data[encrypted_field]
            except Exception as e:
                raise ValueError(
                    f"Failed to decrypt {encrypted_field} for client {client_id}: {e}"
                )
    
    # Note: autohdr_email is NOT encrypted - it's passed through as-is
    # The field is already in decrypted_data from the copy() above
    
    return decrypted_data


def _decrypt_new_format(data: Dict[str, Any], fernet: Fernet, client_id: str) -> Dict[str, Any]:
    """
    Decrypt new multi-provider format with nested credentials.
    """
    decrypted_data = data.copy()
    
    # Decrypt storage credentials
    if 'storage_credentials' in data and data['storage_credentials']:
        storage_creds = data['storage_credentials'].copy()
        decrypted_storage = {}
        
        for key, value in storage_creds.items():
            if key.endswith('_encrypted') and value:
                try:
                    decrypted_key = key.replace('_encrypted', '')
                    decrypted_storage[decrypted_key] = fernet.decrypt(value.encode()).decode()
                except Exception as e:
                    raise ValueError(
                        f"Failed to decrypt storage credential {key} for client {client_id}: {e}"
                    )
            else:
                decrypted_storage[key] = value
        
        decrypted_data['storage_credentials'] = decrypted_storage
    
    # Decrypt enhancement credentials
    if 'enhancement_credentials' in data and data['enhancement_credentials']:
        enhancement_creds = data['enhancement_credentials'].copy()
        decrypted_enhancement = {}
        
        for key, value in enhancement_creds.items():
            if key.endswith('_encrypted') and value:
                try:
                    decrypted_key = key.replace('_encrypted', '')
                    decrypted_enhancement[decrypted_key] = fernet.decrypt(value.encode()).decode()
                except Exception as e:
                    raise ValueError(
                        f"Failed to decrypt enhancement credential {key} for client {client_id}: {e}"
                    )
            else:
                decrypted_enhancement[key] = value
        
        decrypted_data['enhancement_credentials'] = decrypted_enhancement
    
    return decrypted_data


def mask_credentials(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Create a masked copy of data for safe logging.
    
    Args:
        data: Dictionary potentially containing sensitive values
        
    Returns:
        Dictionary with sensitive values masked
    """
    if not isinstance(data, dict):
        return data
    
    masked = data.copy()
    sensitive_fields = [
        'dropbox_app_key', 'dropbox_app_secret', 'dropbox_refresh_token',
        'fotello_api_key', 'autohdr_api_key',
        'google_drive_client_id', 'google_drive_client_secret', 'google_drive_refresh_token',
        'api_key', 'access_token', 'refresh_token', 'client_secret',
    ]
    
    for field in sensitive_fields:
        if field in masked and masked[field]:
            value = masked[field]
            if isinstance(value, str) and len(value) > 8:
                masked[field] = f"{value[:4]}...{value[-4:]}"
            else:
                masked[field] = "***"
    
    # Handle nested credentials
    for nested_key in ['storage_credentials', 'enhancement_credentials']:
        if nested_key in masked and isinstance(masked[nested_key], dict):
            masked[nested_key] = mask_credentials(masked[nested_key])
    
    return masked
