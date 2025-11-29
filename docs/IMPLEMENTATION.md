# SnapFlow Implementation Guide

Technical documentation for developers working on SnapFlow Core.

## Table of Contents

1. [Architecture](#architecture)
2. [Function Details](#function-details)
3. [Shared Library](#shared-library)
4. [Provider System](#provider-system)
5. [Tenant Configuration](#tenant-configuration)
6. [Security](#security)
7. [Error Handling](#error-handling)
8. [Adding New Providers](#adding-new-providers)

---

## Architecture

### High-Level Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Make.com  │────▶│   Gateway   │────▶│   Process   │
│  (Trigger)  │     │ (Validate)  │     │ (Enhance)   │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Make.com  │◀────│  Finalize   │◀────│  Fotello/   │
│ (Callback)  │     │ (Deliver)   │     │  AutoHDR    │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Request Flow

1. **Gateway** receives request with encrypted credentials
2. **Gateway** fetches tenant config (webhook or env)
3. **Gateway** decrypts credentials using tenant's Fernet key
4. **Gateway** dispatches to **Process** asynchronously
5. **Process** downloads files from storage provider
6. **Process** uploads to enhancement provider
7. **Process** calls **Finalize** with enhancement IDs
8. **Finalize** polls enhancement provider for completion
9. **Finalize** downloads enhanced images
10. **Finalize** uploads to storage destination folder
11. **Finalize** sends callback to Make.com

### Async Pattern

Gateway returns immediately (202 Accepted) while processing continues:

```python
# Gateway dispatches in background thread
dispatch_thread = threading.Thread(
    target=_dispatch_async,
    args=(process_url, payload, ...)
)
dispatch_thread.daemon = True
dispatch_thread.start()

# Return immediately
return {'statusCode': 202, ...}
```

---

## Function Details

### Gateway (`packages/snapflow/gateway/`)

**Purpose:** Entry point, validation, credential decryption, dispatch

**Input:**
```json
{
  "client_id": "001",
  "listing_id": "property-123",
  "storage_provider": "dropbox",
  "enhancement_provider": "fotello",
  "dropbox_refresh_token_encrypted": "gAAA...",
  "dropbox_app_key_encrypted": "gAAA...",
  "dropbox_app_secret_encrypted": "gAAA...",
  "fotello_api_key_encrypted": "gAAA...",
  "dropbox_folder": "/Photos/RAW",
  "dropbox_destination_folder": "/Photos/Enhanced",
  "brackets_data": [[{"name": "IMG_001.jpg", "path_lower": "/photos/raw/img_001.jpg"}]],
  "callback_webhook": "https://hook.us1.make.com/xxx"
}
```

**Output (202 Accepted):**
```json
{
  "status": "dispatched",
  "job_id": "uuid-here",
  "client_id": "001",
  "listing_id": "property-123",
  "total_brackets": 5,
  "total_files": 25,
  "correlation_id": "uuid-here"
}
```

**Key Features:**
- Tenant config lookup (webhook → env fallback)
- Fernet decryption of all credentials
- Provider auto-detection from credentials
- Async dispatch to Process

---

### Process (`packages/snapflow/process/`)

**Purpose:** Download from storage, upload to enhancement API

**Flow:**
1. Initialize storage provider (Dropbox/Google Drive)
2. For each bracket:
   - Download files to memory
   - Upload to enhancement provider
   - Get enhancement ID
3. Call Finalize with enhancement IDs

**Key Features:**
- Multi-threaded downloads
- Memory management for large files
- Progress notifications to callback
- RAW file support (CR2, CR3, NEF, ARW, DNG, etc.)

---

### Finalize (`packages/snapflow/finalize/`)

**Purpose:** Poll for results, download enhanced, upload to storage

**Flow:**
1. For each enhancement ID:
   - Poll enhancement API for completion
   - Retry with backoff (3 min intervals, 3 max retries)
2. Download enhanced images
3. Upload to storage destination folder
4. Send final callback to Make.com

**Retry Logic:**
```python
RETRY_DELAY_SECONDS = 180  # 3 minutes
MAX_RETRIES = 3

while pending_retries and retry_count <= MAX_RETRIES:
    # Check status
    # Move completed to results
    # Keep in-progress for retry
    time.sleep(RETRY_DELAY_SECONDS)
```

---

### Bracket Generator (`packages/snapflow/bracket-generator/`)

**Purpose:** Provider-agnostic bracket creation from photos

**Modes:**

1. **discovery** - List files, return pagination info
```json
{
  "mode": "discovery",
  "client_id": "001",
  "storage_provider": "dropbox",
  "dropbox_folder": "/Photos/RAW",
  "dropbox_refresh_token_encrypted": "...",
  "max_files": 500
}
```

2. **process_page** - Extract EXIF from page of files
```json
{
  "mode": "process_page",
  "client_id": "001",
  "page_number": 1,
  "files_per_page": 25,
  "all_files": [...]
}
```

3. **make_bracket** - Create brackets from metadata
```json
{
  "mode": "make_bracket",
  "aggregated_metadata": [...],
  "time_delta_seconds": 2.0
}
```

**EXIF Extraction:**
- Supports: JPEG, RAW (NEF, CR2, CR3, ARW, DNG, ORF, RW2)
- CR3 special handling (MP4 container with CMT boxes)
- DJI detection (auto-adjusts time delta to 10s)
- Multi-threaded extraction (3 workers)

---

### Intelligent Bracketing (`packages/snapflow/intelligent-bracketing/`)

**Purpose:** Optimize brackets for real estate workflows

**Input:**
```json
{
  "aggregated_metadata": [...],
  "time_delta_seconds": 2.0,
  "merge_window_seconds": 30.0,
  "min_bracket_size": 2,
  "single_file_handling": "merge"
}
```

**Single File Handling Strategies:**

| Strategy | Description | Use Case |
|----------|-------------|----------|
| `merge` | Merge with nearby brackets | Real estate (recommended) |
| `keep` | Keep as individual brackets | When single shots matter |
| `separate` | Return in separate array | Hero shot processing |
| `skip` | Exclude from results | Not recommended |

**Output:**
```json
{
  "brackets": [[...], [...], ...],
  "single_files": [],
  "stats": {
    "total_files": 150,
    "total_brackets": 25,
    "quality_score": 87.3,
    "time_delta_used": 2.0,
    "detection_reason": "STANDARD_CAMERA"
  },
  "recommendations": [
    "Excellent bracket quality score: 87.3/100"
  ]
}
```

---

## Shared Library

### Location: `lib/shared/`

The shared library is symlinked into each function during deployment.

### Modules

**config/credentials.py**
```python
# Key functions
decrypt_credentials(data, client_id)  # Decrypt all encrypted fields
decrypt_credential(encrypted_value, encryption_key)  # Single field
mask_credentials(data)  # For safe logging
generate_fernet_key()  # Create new key
```

**providers/storage/**
```python
# Factory pattern
provider = get_storage_provider(
    provider_type='dropbox',
    credentials={...}
)

# Unified interface
files = provider.list_files(folder_path)
content = provider.download_file(file_path)
provider.upload_file(dest_path, content)
```

**providers/enhancement/**
```python
# Factory pattern
provider = get_enhancement_provider(
    provider_type='fotello',
    api_key='...'
)

# Unified interface
upload_id = provider.upload_image(filename, content)
enhance_id = provider.request_enhancement(upload_ids, listing_id)
status = provider.check_status(enhance_id)
url = provider.get_result_url(enhance_id)
```

---

## Provider System

### Storage Provider Interface

```python
class StorageProvider(ABC):
    @abstractmethod
    def connect(self) -> bool:
        """Establish connection, return success."""
        pass
    
    @abstractmethod
    def list_files(self, folder_path: str) -> List[Dict]:
        """List files in folder."""
        pass
    
    @abstractmethod
    def download_file(self, file_path: str) -> bytes:
        """Download file content."""
        pass
    
    @abstractmethod
    def upload_file(self, dest_path: str, content: bytes) -> str:
        """Upload file, return path/URL."""
        pass
```

### Enhancement Provider Interface

```python
class EnhancementProvider(ABC):
    @abstractmethod
    def upload_image(self, filename: str, content: bytes) -> str:
        """Upload image, return upload_id."""
        pass
    
    @abstractmethod
    def request_enhancement(self, upload_ids: List[str], listing_id: str) -> str:
        """Request enhancement, return enhancement_id."""
        pass
    
    @abstractmethod
    def check_status(self, enhancement_id: str) -> Dict:
        """Check enhancement status."""
        pass
    
    @abstractmethod
    def get_result_url(self, enhancement_id: str) -> Optional[str]:
        """Get URL to download enhanced image."""
        pass
```

---

## Tenant Configuration

### Webhook Flow

```
┌──────────┐     ┌──────────────┐     ┌──────────────┐
│ Gateway  │────▶│   Make.com   │────▶│   Airtable   │
│          │     │   Webhook    │     │  (Tenants)   │
└──────────┘     └──────────────┘     └──────────────┘
      │
      │ Returns: encryption_key, client_name, active
      ▼
  Decrypt credentials
```

### Webhook Request

```json
POST https://hook.us1.make.com/xxx/tenant-config
Headers:
  Content-Type: application/json
  X-Config-Secret: your-secret-here

Body:
{
  "client_id": "001"
}
```

### Webhook Response

```json
{
  "client_id": "001",
  "client_name": "InfiniteViews",
  "encryption_key": "NUqnt-OjPHbgK_qD8ZUrUB37IocufEE78d6-C8mZ_XI=",
  "storage_provider": "dropbox",
  "enhancement_provider": "fotello",
  "active": true
}
```

### Caching

Tenant configs are cached for 5 minutes to reduce webhook calls:

```python
_tenant_config_cache: Dict[str, tuple] = {}
_cache_ttl_seconds = 300
```

---

## Security

### Credential Encryption

All credentials are encrypted with Fernet (symmetric encryption):

```python
from cryptography.fernet import Fernet

# Encrypt
key = Fernet.generate_key()
fernet = Fernet(key)
encrypted = fernet.encrypt(b"my-secret").decode()

# Decrypt
decrypted = fernet.decrypt(encrypted.encode()).decode()
```

### Credential Flow

1. Make.com stores encrypted credentials
2. Gateway receives encrypted credentials
3. Gateway fetches tenant's Fernet key (webhook/env)
4. Gateway decrypts credentials
5. Credentials cleared from memory after use

### Sensitive Fields

```python
sensitive_fields = [
    'dropbox_app_key', 'dropbox_app_secret', 'dropbox_refresh_token',
    'google_drive_client_id', 'google_drive_client_secret', 'google_drive_refresh_token',
    'fotello_api_key', 'autohdr_api_key'
]
```

---

## Error Handling

### Notification Levels

```python
notification_level = 'minimal'  # Default

# Levels:
# - 'errors_only': Only critical errors
# - 'minimal': Major milestones + errors
# - 'standard': Progress updates
# - 'verbose': Full debugging
```

### Error Response Format

```json
{
  "status": "job_failed",
  "function_name": "process",
  "log_level": "ERROR",
  "job_id": "uuid",
  "listing_id": "property-123",
  "error": "Dropbox connection failed: Invalid token",
  "correlation_id": "uuid",
  "version": "1.0.0-snapflow"
}
```

### Correlation IDs

Every request gets a correlation ID for tracing:

```python
correlation_id = str(uuid.uuid4())
# Passed through: Gateway → Process → Finalize → Callbacks
```

---

## Adding New Providers

### New Storage Provider

1. Create `lib/shared/providers/storage/new_provider.py`:

```python
from .base import StorageProvider

class NewStorageProvider(StorageProvider):
    def __init__(self, api_key: str, **kwargs):
        self.api_key = api_key
        self._client = None
    
    def connect(self) -> bool:
        # Initialize client
        return True
    
    def list_files(self, folder_path: str) -> List[Dict]:
        # Return [{'name': '...', 'path_lower': '...', 'size': ...}]
        pass
    
    def download_file(self, file_path: str) -> bytes:
        # Return file content
        pass
    
    def upload_file(self, dest_path: str, content: bytes) -> str:
        # Return uploaded file path
        pass
```

2. Register in `lib/shared/providers/storage/factory.py`:

```python
from .new_provider import NewStorageProvider

STORAGE_PROVIDERS = {
    'dropbox': DropboxProvider,
    'google_drive': GoogleDriveProvider,
    'new_provider': NewStorageProvider,  # Add here
}
```

3. Update `lib/shared/providers/storage/__init__.py`

### New Enhancement Provider

Same pattern in `lib/shared/providers/enhancement/`.

---

## Testing

### Run Tests

```bash
# Unit tests (no credentials)
pytest tests/unit -v

# Integration tests (requires .env.test)
pytest tests/integration -v

# Specific provider
pytest tests/integration/test_dropbox.py -v

# Skip slow tests
pytest -m "not slow"
```

### Test Markers

```python
@pytest.mark.unit          # Fast, no external calls
@pytest.mark.integration   # Real API calls
@pytest.mark.e2e           # Full pipeline
@pytest.mark.slow          # Takes > 30 seconds
@pytest.mark.dropbox       # Requires Dropbox credentials
@pytest.mark.google_drive  # Requires Google Drive credentials
@pytest.mark.fotello       # Requires Fotello API key
@pytest.mark.autohdr       # Requires AutoHDR API key
```

---

## Deployment

### Manual Deploy

```bash
# Connect to QA
doctl serverless connect fn-cc8fc781-2529-45ec-abaa-69810a7992a3

# Deploy
doctl serverless deploy . --remote-build

# Check functions
doctl serverless functions list
```

### CI/CD Deploy

Push to `develop` → Auto-deploy to QA
Push to `main` → Auto-deploy to Production

### Function URLs

```
Base: https://faas-nyc1-2ef2e6cc.doserverless.co/api/v1/web/{namespace}/snapflow/

Functions:
- gateway
- process
- finalize
- discovery
- bracket-generator
- intelligent-bracketing
```
