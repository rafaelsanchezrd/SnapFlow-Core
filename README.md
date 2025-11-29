# SnapFlow Core

Multi-provider photo enhancement pipeline for DigitalOcean Functions.

## Features

- **Multi-Storage Support**: Dropbox, Google Drive
- **Multi-Enhancement Support**: Fotello, AutoHDR
- **Unified Interface**: Factory pattern for easy provider switching
- **Secure**: Fernet encryption for all credentials
- **Tested**: Unit, integration, and E2E tests

## Project Structure

```
snapflow-core/
├── .github/workflows/       # CI/CD pipelines
│   ├── test.yml            # Run tests on PR/push
│   └── deploy.yml          # Deploy to QA/Production
│
├── lib/shared/             # Shared library (SnapFlow Core)
│   ├── config/             # Credentials, constants
│   ├── providers/          # Storage & enhancement providers
│   ├── notifications/      # Webhook notifications
│   └── utils/              # File utilities
│
├── packages/snapflow/      # DO Functions
│   ├── gateway/            # Entry point, validation
│   ├── process/            # Download, upload, enhance
│   ├── finalize/           # Poll, download results, transfer
│   └── discovery/          # List files, EXIF, bracketing
│
├── tests/                  # Test suite
│   ├── unit/              # Fast, no external calls
│   ├── integration/       # Real API tests
│   └── e2e/               # Full pipeline tests
│
├── project.yml            # DO Functions config
└── .env.example           # Credential template
```

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
pip install pytest python-dotenv
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

## Configuration

### Environment Variables

Add to `project.yml` or DO dashboard:

```yaml
CLIENT_001_ENCRYPTION_KEY: "fernet-key-here"
CLIENT_002_ENCRYPTION_KEY: "fernet-key-here"
```

### Generate New Client Key

```python
from cryptography.fernet import Fernet
print(Fernet.generate_key().decode())
```

## Endpoints

| Function | Purpose |
|----------|---------|
| `gateway` | Entry point, validates & dispatches |
| `process` | Downloads from storage, uploads to enhancement |
| `finalize` | Polls for results, uploads back to storage |
| `discovery` | Lists files, extracts EXIF, creates brackets |

## GitHub Secrets Required

### For Tests
- `TEST_DROPBOX_APP_KEY`, `TEST_DROPBOX_APP_SECRET`, `TEST_DROPBOX_REFRESH_TOKEN`
- `TEST_GDRIVE_CLIENT_ID`, `TEST_GDRIVE_CLIENT_SECRET`, `TEST_GDRIVE_REFRESH_TOKEN`
- `TEST_FOTELLO_API_KEY`
- `TEST_AUTOHDR_API_KEY`, `TEST_AUTOHDR_EMAIL`
- `TEST_ENCRYPTION_KEY`

### For Deployment
- `DIGITALOCEAN_ACCESS_TOKEN`
- `DO_QA_NAMESPACE_ID`
- `DO_PROD_NAMESPACE_ID`

## Branch Strategy

| Branch | Environment | Trigger |
|--------|-------------|---------|
| `main` | Production | Auto-deploy on push |
| `develop` | QA | Auto-deploy on push |
| Feature branches | - | Tests only |

## License

Proprietary - All rights reserved
