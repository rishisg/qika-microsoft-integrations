"""
OneDrive Agent — FastAPI entry point. Runs on port 8011.
Usage:
  1. Copy env.example to .env and fill in ONEDRIVE_* vars
     (same client_id/client_secret as outlook_agent)
  2. pip install -r agents/onedrive_agent/requirements.txt
  3. uvicorn agents.onedrive_agent.app:app --reload --port 8011
"""

import os
import sys
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import uvicorn

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parents[1]
sys.path.append(str(REPO_ROOT))

for fname in [".env.local", ".env"]:
    env_path = BASE_DIR / fname
    if env_path.exists():
        load_dotenv(env_path, override=True)

from agents.onedrive_agent.src.main import create_app  # noqa: E402


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.environ.get(name)
    return val if val else default


tenant_id = _env("ONEDRIVE_TENANT_ID_LOCAL", "tenant_local")
app = create_app(default_tenant_id=tenant_id)

if __name__ == "__main__":
    uvicorn.run(
        "agents.onedrive_agent.app:app",
        host=_env("HOST", "0.0.0.0"),
        port=int(_env("PORT", "8011")),
        reload=True,
    )
