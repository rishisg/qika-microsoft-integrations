"""
Outlook Agent — FastAPI entry point.

Usage:
  1. Copy env.example to .env and fill in OUTLOOK_* vars.
  2. pip install -r agents/outlook_agent/requirements.txt
  3. Run: uvicorn agents.outlook_agent.app:app --reload --port 8010
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

# Prefer .env.local over .env if present
for fname in [".env.local", ".env"]:
    env_path = BASE_DIR / fname
    if env_path.exists():
        load_dotenv(env_path, override=True)

from agents.outlook_agent.src.main import create_app  # noqa: E402
from agents.outlook_agent.src.config import settings  # noqa: E402


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    val = os.environ.get(name)
    return val if val else default


tenant_id = _env("OUTLOOK_TENANT_ID_LOCAL", "tenant_local")
app = create_app(default_tenant_id=tenant_id)


if __name__ == "__main__":
    uvicorn.run(
        "agents.outlook_agent.app:app",
        host=_env("HOST", "0.0.0.0"),
        port=int(_env("PORT", "8010")),
        reload=True,
    )
