# SnapFlow Integration Guide

Guide for integrating SnapFlow with Make.com workflows.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Tenant Setup](#tenant-setup)
4. [Workflow Options](#workflow-options)
5. [API Reference](#api-reference)
6. [Make.com Scenarios](#makecom-scenarios)
7. [Callback Handling](#callback-handling)
8. [Troubleshooting](#troubleshooting)

---

## Overview

SnapFlow processes real estate photos through these stages:

```
1. BRACKET GENERATION (Optional)
   Dropbox/Drive → bracket-generator → intelligent-bracketing → brackets_data

2. ENHANCEMENT
   brackets_data → gateway → process → finalize → Enhanced Photos
```

---

## Prerequisites

### 1. SnapFlow Functions Deployed

Verify functions are accessible:
```
https://faas-nyc1-2ef2e6cc.doserverless.co/api/v1/web/{namespace}/snapflow/gateway
https://faas-nyc1-2ef2e6cc.doserverless.co/api/v1/web/{namespace}/snapflow/process
https://faas-nyc1-2ef2e6cc.doserverless.co/api/v1/web/{namespace}/snapflow/finalize
https://faas-nyc1-2ef2e6cc.doserverless.co/api/v1/web/{namespace}/snapflow/bracket-generator
https://faas-nyc1-2ef2e6cc.doserverless.co/api/v1/web/{namespace}/snapflow/intelligent-bracketing
```

### 2. Tenant Configured

Either:
- Central webhook returning tenant config, OR
- `CLIENT_XXX_ENCRYPTION_KEY` in DO environment

### 3. Credentials Encrypted

All credentials must be Fernet-encrypted with the tenant's key.

---

## Tenant Setup

### Option A: Central Webhook (Recommended)

#### 1. Create Airtable Base

**Tenants Table:**

| Field | Type | Example |
|-------|------|---------|
| client_id | Text (Primary) | `001` |
| client_name | Text | `InfiniteViews` |
| encryption_key | Text | `NUqnt-OjPHbgK_...` |
| storage_provider | Select | `dropbox` |
| enhancement_provider | Select | `fotello` |
| callback_webhook | URL | `https://hook.us1.make.com/...` |
| active | Checkbox | ✓ |

#### 2. Create Make.com Webhook Scenario

**Trigger:** Custom Webhook

**Modules:**
1. Webhooks → Custom webhook (catch `client_id`)
2. Airtable → Search records (find by `client_id`)
3. Webhooks → Webhook response (return config)

**Response Mapping:**
```json
{
  "client_id": "{{1.client_id}}",
  "client_name": "{{2.client_name}}",
  "encryption_key": "{{2.encryption_key}}",
  "storage_provider": "{{2.storage_provider}}",
  "enhancement_provider": "{{2.enhancement_provider}}",
  "active": "{{2.active}}"
}
```

#### 3. Configure SnapFlow

Add to DO Functions environment:
```
TENANT_CONFIG_WEBHOOK=https://hook.us1.make.com/xxx/tenant-config
TENANT_CONFIG_SECRET=your-secret-here
```

### Option B: Environment Variables

Add per-client keys to `project.yml`:
```yaml
environment:
  CLIENT_001_ENCRYPTION_KEY: "NUqnt-OjPHbgK_qD8ZUrUB37IocufEE78d6-C8mZ_XI="
  CLIENT_002_ENCRYPTION_KEY: "ef88ItkRGVjBKuDcAKupGJnr58t8Sjr7ZSG9WLyrXRA="
```

---

## Workflow Options

### Option 1: Pre-Built Brackets (Simple)

Use when you already have brackets from another source.

```
Make.com Trigger
    ↓
HTTP Module → gateway
    ↓
(Async processing)
    ↓
Callback Webhook ← job_completed
```

### Option 2: Auto-Bracket Generation (Full Pipeline)

Use when you need to discover and bracket photos automatically.

```
Make.com Trigger
    ↓
HTTP → bracket-generator (discovery)
    ↓
Iterator → bracket-generator (process_page) × N pages
    ↓
Array Aggregator
    ↓
HTTP → intelligent-bracketing
    ↓
HTTP → gateway
    ↓
Callback Webhook ← job_completed
```

### Option 3: Simple Brackets (No Optimization)

Skip intelligent-bracketing if optimization not needed.

```
Make.com Trigger
    ↓
HTTP → bracket-generator (discovery)
    ↓
Iterator → bracket-generator (process_page) × N pages
    ↓
HTTP → bracket-generator (make_bracket)
    ↓
HTTP → gateway
    ↓
Callback Webhook ← job_completed
```

---

## API Reference

### Gateway

**Endpoint:** `POST /snapflow/gateway`

**Request:**
```json
{
  "client_id": "001",
  "listing_id": "property-123",
  
  "storage_provider": "dropbox",
  "dropbox_refresh_token_encrypted": "gAAAAA...",
  "dropbox_app_key_encrypted": "gAAAAA...",
  "dropbox_app_secret_encrypted": "gAAAAA...",
  "dropbox_folder": "/Photos/RAW",
  "dropbox_destination_folder": "/Photos/Enhanced",
  
  "enhancement_provider": "fotello",
  "fotello_api_key_encrypted": "gAAAAA...",
  
  "brackets_data": [
    [
      {"name": "IMG_001.jpg", "path_lower": "/photos/raw/img_001.jpg"},
      {"name": "IMG_002.jpg", "path_lower": "/photos/raw/img_002.jpg"},
      {"name": "IMG_003.jpg", "path_lower": "/photos/raw/img_003.jpg"}
    ],
    [
      {"name": "IMG_004.jpg", "path_lower": "/photos/raw/img_004.jpg"},
      {"name": "IMG_005.jpg", "path_lower": "/photos/raw/img_005.jpg"}
    ]
  ],
  
  "callback_webhook": "https://hook.us1.make.com/xxx/callback",
  "notification_level": "minimal",
  "filename_prefix": "123-Main-St"
}
```

**Response (202 Accepted):**
```json
{
  "status": "dispatched",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "client_id": "001",
  "listing_id": "property-123",
  "storage_provider": "dropbox",
  "enhancement_provider": "fotello",
  "total_brackets": 2,
  "total_files": 5,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

---

### Bracket Generator

**Endpoint:** `POST /snapflow/bracket-generator`

#### Mode: Discovery

**Request:**
```json
{
  "mode": "discovery",
  "client_id": "001",
  "storage_provider": "dropbox",
  "dropbox_folder": "/Photos/RAW",
  "dropbox_refresh_token_encrypted": "gAAAAA...",
  "dropbox_app_key_encrypted": "gAAAAA...",
  "dropbox_app_secret_encrypted": "gAAAAA...",
  "files_per_page": 25,
  "max_files": 500
}
```

**Response:**
```json
{
  "status": "discovery_success",
  "storage_provider": "dropbox",
  "total_files": 150,
  "total_pages": 6,
  "files_per_page": 25,
  "session_id": "550e8400-e29b-41d4-a716-446655440002",
  "all_files": [
    {"name": "IMG_001.jpg", "path_lower": "/photos/raw/img_001.jpg", "size": 5242880},
    {"name": "IMG_002.jpg", "path_lower": "/photos/raw/img_002.jpg", "size": 4718592}
  ]
}
```

#### Mode: Process Page

**Request:**
```json
{
  "mode": "process_page",
  "client_id": "001",
  "storage_provider": "dropbox",
  "page_number": 1,
  "files_per_page": 25,
  "session_id": "550e8400-e29b-41d4-a716-446655440002",
  "all_files": [...],
  "dropbox_refresh_token_encrypted": "gAAAAA...",
  "dropbox_app_key_encrypted": "gAAAAA...",
  "dropbox_app_secret_encrypted": "gAAAAA..."
}
```

**Response:**
```json
{
  "status": "page_processed",
  "storage_provider": "dropbox",
  "page_number": 1,
  "session_id": "550e8400-e29b-41d4-a716-446655440002",
  "processed_count": 25,
  "metadata": [
    {
      "name": "IMG_001.jpg",
      "path_lower": "/photos/raw/img_001.jpg",
      "date_taken": "2024-01-15T10:30:00"
    }
  ]
}
```

#### Mode: Make Bracket

**Request:**
```json
{
  "mode": "make_bracket",
  "aggregated_metadata": [...],
  "time_delta_seconds": 2.0
}
```

**Response:**
```json
[
  [
    {"name": "IMG_001.jpg", "path_lower": "/photos/raw/img_001.jpg"},
    {"name": "IMG_002.jpg", "path_lower": "/photos/raw/img_002.jpg"}
  ],
  [
    {"name": "IMG_003.jpg", "path_lower": "/photos/raw/img_003.jpg"}
  ]
]
```

---

### Intelligent Bracketing

**Endpoint:** `POST /snapflow/intelligent-bracketing`

**Request:**
```json
{
  "aggregated_metadata": [
    {"name": "IMG_001.jpg", "path_lower": "...", "date_taken": "2024-01-15T10:30:00"},
    {"name": "IMG_002.jpg", "path_lower": "...", "date_taken": "2024-01-15T10:30:01"}
  ],
  "time_delta_seconds": 2.0,
  "merge_window_seconds": 30.0,
  "min_bracket_size": 2,
  "single_file_handling": "merge"
}
```

**Response:**
```json
{
  "brackets": [
    [
      {"name": "IMG_001.jpg", "path_lower": "..."},
      {"name": "IMG_002.jpg", "path_lower": "..."}
    ]
  ],
  "single_files": [],
  "stats": {
    "total_files": 150,
    "total_brackets": 25,
    "single_files_count": 0,
    "time_delta_used": 2.0,
    "detection_reason": "STANDARD_CAMERA",
    "improvement": {
      "quality_score": 87.3
    }
  },
  "recommendations": [
    "Excellent bracket quality score: 87.3/100"
  ]
}
```

---

## Make.com Scenarios

### Scenario 1: Simple Enhancement (Pre-Built Brackets)

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Trigger (Webhook/Schedule/etc)                                   │
├─────────────────────────────────────────────────────────────────────┤
│ 2. HTTP Request                                                     │
│    URL: https://faas.../snapflow/gateway                           │
│    Method: POST                                                     │
│    Body: { client_id, listing_id, brackets_data, ... }             │
├─────────────────────────────────────────────────────────────────────┤
│ 3. (No wait - gateway returns immediately)                         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ SEPARATE SCENARIO: Callback Handler                                 │
├─────────────────────────────────────────────────────────────────────┤
│ 1. Webhook Trigger (receives job_completed callback)               │
├─────────────────────────────────────────────────────────────────────┤
│ 2. Router                                                          │
│    - job_completed → Success path                                  │
│    - job_failed → Error path                                       │
├─────────────────────────────────────────────────────────────────────┤
│ 3. Update Airtable/Notion/etc with results                        │
└─────────────────────────────────────────────────────────────────────┘
```

### Scenario 2: Full Pipeline (Auto-Bracket)

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Trigger                                                         │
├─────────────────────────────────────────────────────────────────────┤
│ 2. HTTP Request → bracket-generator (discovery)                    │
│    Body: { mode: "discovery", client_id, dropbox_folder, ... }    │
├─────────────────────────────────────────────────────────────────────┤
│ 3. Set Variable: all_files = {{2.all_files}}                      │
│    Set Variable: total_pages = {{2.total_pages}}                  │
├─────────────────────────────────────────────────────────────────────┤
│ 4. Iterator: Generate array [1, 2, 3, ..., total_pages]           │
├─────────────────────────────────────────────────────────────────────┤
│ 5. HTTP Request → bracket-generator (process_page)                 │
│    Body: { mode: "process_page", page_number: {{4.value}}, ... }  │
├─────────────────────────────────────────────────────────────────────┤
│ 6. Array Aggregator: Collect all metadata arrays                   │
├─────────────────────────────────────────────────────────────────────┤
│ 7. HTTP Request → intelligent-bracketing                           │
│    Body: { aggregated_metadata: {{6.array}}, ... }                │
├─────────────────────────────────────────────────────────────────────┤
│ 8. HTTP Request → gateway                                          │
│    Body: { brackets_data: {{7.brackets}}, ... }                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Callback Handling

### Callback Types

| Status | Description | Action |
|--------|-------------|--------|
| `job_started` | Processing begun | Update status |
| `job_completed` | All brackets enhanced | Mark complete |
| `job_partial_success` | Some brackets failed | Review failures |
| `job_failed` | Complete failure | Alert + retry |

### Callback Payload: job_completed

```json
{
  "status": "job_completed",
  "function_name": "finalize",
  "log_level": "INFO",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "listing_id": "property-123",
  "total_brackets": 5,
  "processed_brackets": 5,
  "successful_enhancements": 5,
  "failed_enhancements": 0,
  "enhanced_images": [
    {
      "bracket_index": 0,
      "dropbox_path": "/Photos/Enhanced/1_123-Main-St.jpg",
      "file_size_mb": 2.5
    },
    {
      "bracket_index": 1,
      "dropbox_path": "/Photos/Enhanced/2_123-Main-St.jpg",
      "file_size_mb": 2.3
    }
  ],
  "failed_brackets": [],
  "timestamp": 1705312200.123,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

### Callback Payload: job_failed

```json
{
  "status": "job_failed",
  "function_name": "process",
  "log_level": "ERROR",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "listing_id": "property-123",
  "error": "Dropbox connection failed: Invalid refresh token",
  "files_processed": 0,
  "files_uploaded": 0,
  "brackets_processed": 0,
  "timestamp": 1705312200.123,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

---

## Troubleshooting

### Common Errors

#### "Tenant 'XXX' not found"

**Cause:** Client ID not configured

**Fix:**
- Add to central config (Airtable), OR
- Add `CLIENT_XXX_ENCRYPTION_KEY` to environment

#### "Failed to decrypt"

**Cause:** Wrong encryption key or corrupted data

**Fix:**
- Verify encryption key matches what was used to encrypt
- Re-encrypt credentials with correct key

#### "Dropbox connection failed"

**Cause:** Invalid or expired token

**Fix:**
- Refresh the Dropbox OAuth token
- Re-encrypt and update credentials

#### "Enhancement timeout"

**Cause:** Enhancement API taking too long

**Fix:**
- Check enhancement provider status
- Job may still complete (finalize retries)

### Debug Tips

1. **Enable verbose logging:**
   ```json
   {"notification_level": "verbose"}
   ```

2. **Check correlation ID:**
   - Same ID flows through all functions
   - Use to trace request in logs

3. **Test credentials separately:**
   ```bash
   # Test Dropbox
   curl -X POST https://api.dropboxapi.com/oauth2/token \
     -d "grant_type=refresh_token&refresh_token=XXX&client_id=XXX&client_secret=XXX"
   ```

4. **Verify webhook:**
   ```bash
   curl -X POST https://hook.us1.make.com/xxx/tenant-config \
     -H "Content-Type: application/json" \
     -H "X-Config-Secret: your-secret" \
     -d '{"client_id": "001"}'
   ```

---

## Credential Encryption Helper

Use this Make.com module to encrypt credentials:

```javascript
// Custom JavaScript module in Make.com
const crypto = require('crypto');

// Your Fernet key (32-byte base64)
const key = 'NUqnt-OjPHbgK_qD8ZUrUB37IocufEE78d6-C8mZ_XI=';

// Value to encrypt
const value = 'your-secret-api-key';

// Fernet encryption (simplified - use proper library in production)
// Better: Use Python script or dedicated encryption service

return {
  encrypted: fernetEncrypt(value, key)
};
```

**Better approach:** Create a dedicated Make.com scenario that:
1. Takes plaintext credentials
2. Calls a SnapFlow utility endpoint to encrypt
3. Stores encrypted values in Airtable

---

## Support

- **Logs:** DigitalOcean Functions → Activity
- **Correlation ID:** Include in all support requests
- **Test endpoint:** Use `/snapflow/gateway` with minimal payload to verify connectivity
