"""Token store for OneDrive — identical to Outlook token store."""
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any


class FileTokenStore:
    def __init__(self, path: str, encryption_key: Optional[str] = None):
        self.base_path = Path(path).parent
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.encryption_key = encryption_key

    def _token_path(self, tenant_id: str, user_id: Optional[str]) -> Path:
        uid = user_id or "default"
        tenant_dir = self.base_path / tenant_id
        tenant_dir.mkdir(parents=True, exist_ok=True)
        return tenant_dir / f"onedrive_{uid}.json"

    async def get(self, tenant_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        path = self._token_path(tenant_id, user_id)
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    async def set(self, tenant_id: str, user_id: Optional[str], data: Dict[str, Any]) -> None:
        path = self._token_path(tenant_id, user_id)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    async def delete(self, tenant_id: str, user_id: Optional[str] = None) -> None:
        path = self._token_path(tenant_id, user_id)
        if path.exists():
            os.remove(path)

    async def link_user_tokens(self, tenant_id: str, source_user_id: str, target_user_id: str) -> None:
        source_data = await self.get(tenant_id, source_user_id)
        if source_data is None:
            raise ValueError(f"No tokens found for source_user_id={source_user_id}")
        await self.set(tenant_id, target_user_id, source_data)


def encode_state(data: Dict[str, str]) -> str:
    import base64
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


def decode_state(state: str) -> Dict[str, str]:
    import base64
    try:
        return json.loads(base64.urlsafe_b64decode(state.encode()).decode())
    except Exception:
        return {}
