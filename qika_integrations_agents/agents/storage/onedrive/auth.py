"""
OAuth helpers for OneDrive agent (alias for auth.oauth for compatibility).
"""

from qika_integrations_agents.agents.storage.onedrive.auth.oauth import (
    is_token_expiring,
    refresh_access_token,
)

__all__ = ["is_token_expiring", "refresh_access_token"]
