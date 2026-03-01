# Qika Microsoft Integrations

Microsoft Graph API integrations for Qika — Outlook and OneDrive agents.
Mirrors the existing Google integrations (Gmail, Google Drive) in structure and pattern.

## Agents

| Agent | Port | Description |
|---|---|---|
| `outlook_agent` | 8010 | Outlook email — send, read, reply, move, delete |
| `onedrive_agent` | 8011 | OneDrive files — upload, download, list, create folder, share |

## Setup

```bash
# 1. Copy env and fill in your Azure App credentials
cp agents/outlook_agent/env.example agents/outlook_agent/.env
cp agents/onedrive_agent/env.example agents/onedrive_agent/.env

# 2. Install dependencies
pip install -r agents/outlook_agent/requirements.txt
pip install -r agents/onedrive_agent/requirements.txt

# 3. Run servers
uvicorn agents.outlook_agent.app:app --reload --port 8010
uvicorn agents.onedrive_agent.app:app --reload --port 8011
```

## Auth
Both agents use Microsoft Graph OAuth 2.0. Use the same Azure App (client_id / client_secret).
Open `http://localhost:8010/docs` or `http://localhost:8011/docs` and use `POST /*/oauth/init` to authenticate.

## Status
- ✅ Outlook Agent — fully built and tested (13 unit tests)
- ✅ OneDrive Agent — fully built and tested (6 unit tests)
- ⏳ SharePoint Agent — pending Microsoft 365 account
- ⏳ Teams Agent — pending Microsoft 365 account
