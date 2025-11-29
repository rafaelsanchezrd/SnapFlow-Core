# SnapFlow Core

Multi-provider photo enhancement pipeline for DigitalOcean Functions.

## Features

- **Multi-Storage Support**: Dropbox, Google Drive (extensible)
- **Multi-Enhancement Support**: Fotello, AutoHDR (extensible)
- **Provider-Agnostic Bracketing**: EXIF-based bracket creation for any storage
- **Intelligent Optimization**: Smart single-file merging for real estate workflows
- **Central Tenant Config**: Webhook-based configuration (no redeploys for new clients)
- **Secure**: Fernet encryption for all credentials
- **Tested**: Unit, integration, and E2E tests with CI/CD

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            Make.com Workflow                            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         BRACKET GENERATION PHASE                        │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────────┐  │
│  │bracket-generator│───▶│ bracket-generator│───▶│    intelligent-   │  │
│  │   (discovery)    │    │  (process_page)  │    │     bracketing    │  │
│  └──────────────────┘    └──────────────────┘    └───────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ brackets_data
┌─────────────────────────────────────────────────────────────────────────┐
│                          ENHANCEMENT PHASE                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐               │
│  │  gateway    │───▶│   process    │───▶│   finalize   │               │
│  │ (validation) │    │  (enhance)   │    │  (delivery)  │               │
│  └──────────────┘    └──────────────┘    └──────────────┘               │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Enhanced Photos in Storage Provider                  │
└─────────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
snapflow-core/
├── .github/workflows/           # CI/CD pipelines
│   ├── test.yml                # Run tests on PR/push
│   └── deploy.yml              # Deploy to QA/Production
│
├── lib/shared/                 # Shared library (SnapFlow Core)
│   ├── config/                 # Credentials, constants
│   │   ├── credentials.py      # Encryption/decryption
│   │   └── constants.py        # File types, limits
│   ├── providers/              # Storage & enhancement providers
│   │   ├── storage/            # Dropbox, Google Drive
│   │   └── enhancement/        # Fotello, AutoHDR
│   ├── notifications/          # Webhook notifications
│   └── utils/                  # File utilities
│
├── packages/snapflow/          # DO Functions (6 total)
│   ├── gateway/                # Entry point, validation, dispatch
│   ├── process/                # Download, upload to enhancement API
│   ├── finalize/               # Poll results, upload back to storage
│   ├── discovery/              # Simple file listing
│   ├── bracket-generator/      # EXIF extraction, bracket creation
│   └── intelligent-bracketing/ # Bracket optimization
│
├── tests/                      # Test suite
│   ├── unit/                   # Fast, no external calls
│   ├── integration/            # Real API tests
│   └── e2e/                    # Full pipeline tests
│
├── docs/                       # Documentation
│   ├── IMPLEMENTATION.md       # Technical implementation details
│   └── INTEGRATION.md          # Make.com integration guide
│
├── project.yml                 # DO Functions config
└── .env.example                # Credential template
```

## Functions Overview

| Function | Purpose | Memory | Timeout |
|----------|---------|--------|---------|
| `gateway` | Entry point, credential decryption, async dispatch | 512 MB | 1 min |
| `process` | Download from storage, upload to enhancement API | 1024 MB | 15 min |
| `finalize` | Poll for results, download enhanced, upload to storage | 1024 MB | 15 min |
| `discovery` | Simple file listing (legacy) | 1024 MB | 5 min |
| `bracket-generator` | EXIF extraction, bracket creation (any provider) | 1024 MB | 5 min |
| `intelligent-bracketing` | Optimize brackets, merge single-files | 512 MB | 1 min |

## Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/YOUR_ORG/snapflow-core.git
cd snapflow-core

# Copy and fill in credentials
cp .env.example .env.test
```

### 2. Run Tests

```bash
# Install dependencies
pip install pytest python-dotenv responses
pip install -r lib/shared/requirements.txt

# Unit tests (fast, no credentials needed)
pytest tests/unit -v

# Integration tests (requires credentials)
pytest tests/integration -v

# All tests
pytest -v
```

### 3. Deploy

```bash
# Connect to namespace
doctl serverless connect <namespace-id>

# Deploy
doctl serverless deploy . --remote-build
```

## Tenant Configuration

### Option 1: Central Webhook (Recommended)

Fetch tenant config dynamically from Make.com/Airtable:

```yaml
# project.yml
environment:
  TENANT_CONFIG_WEBHOOK: "https://hook.us1.make.com/xxx/tenant-config"
  TENANT_CONFIG_SECRET: "your-secret-here"
```

**Benefits:**
- Add clients instantly (no redeploy)
- Rotate keys easily
- Centralized management
- Audit trail

### Option 2: Environment Variables (Fallback)

```yaml
# project.yml
environment:
  CLIENT_001_ENCRYPTION_KEY: "fernet-key-here"
  CLIENT_002_ENCRYPTION_KEY: "fernet-key-here"
```

### Generate New Client Key

```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

## Provider Support

### Storage Providers

| Provider | Status | Notes |
|----------|--------|-------|
| Dropbox | ✅ Ready | Personal & Team accounts |
| Google Drive | ✅ Ready | OAuth 2.0 |
| OneDrive | 🔮 Planned | Easy to add |
| S3 | 🔮 Planned | Easy to add |

### Enhancement Providers

| Provider | Status | Notes |
|----------|--------|-------|
| Fotello | ✅ Ready | Real estate HDR |
| AutoHDR | ✅ Ready | Bracket merging |
| Custom | 🔮 Planned | Implement `EnhancementProvider` base class |

## GitHub Secrets Required

### For Deployment
```
DIGITALOCEAN_ACCESS_TOKEN
DO_QA_NAMESPACE_ID
DO_PROD_NAMESPACE_ID
TENANT_CONFIG_WEBHOOK (optional)
TENANT_CONFIG_SECRET (optional)
```

### For Tests
```
TEST_DROPBOX_APP_KEY
TEST_DROPBOX_APP_SECRET
TEST_DROPBOX_REFRESH_TOKEN
TEST_DROPBOX_TEST_FOLDER

TEST_GDRIVE_CLIENT_ID
TEST_GDRIVE_CLIENT_SECRET
TEST_GDRIVE_REFRESH_TOKEN
TEST_GDRIVE_TEST_FOLDER_ID

TEST_FOTELLO_API_KEY

TEST_AUTOHDR_API_KEY
TEST_AUTOHDR_EMAIL

TEST_ENCRYPTION_KEY
```

## Branch Strategy

| Branch | Environment | Trigger |
|--------|-------------|---------|
| `main` | Production | Auto-deploy on push |
| `develop` | QA | Auto-deploy on push |
| Feature branches | - | Tests only |

## Documentation

- [Implementation Guide](docs/IMPLEMENTATION.md) - Technical details, architecture
- [Integration Guide](docs/INTEGRATION.md) - Make.com setup, API reference

## License

Proprietary - All rights reserved
