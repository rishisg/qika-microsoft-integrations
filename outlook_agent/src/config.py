from functools import lru_cache
from typing import List, Optional, Union

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="allow",
        env_prefix="OUTLOOK_",
        env_nested_delimiter="__",
    )

    client_id: str = ""
    client_secret: str = ""
    # "common" supports both personal (Hotmail) and org (M365) accounts
    tenant_id: str = "common"
    redirect_uri: str = "http://localhost:8010/outlook/oauth/callback"

    # Microsoft Graph OAuth endpoints (built from tenant_id)
    @property
    def authority(self) -> str:
        return f"https://login.microsoftonline.com/{self.tenant_id}"

    @property
    def auth_url(self) -> str:
        return f"{self.authority}/oauth2/v2.0/authorize"

    @property
    def token_url(self) -> str:
        return f"{self.authority}/oauth2/v2.0/token"

    scopes: Union[str, List[str]] = [
        "https://graph.microsoft.com/Mail.Read",
        "https://graph.microsoft.com/Mail.Send",
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/User.Read",
        "offline_access",
    ]

    @field_validator("scopes", mode="before")
    @classmethod
    def parse_scopes(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split() if s.strip()]
        return v

    token_store_path: str = "./local_secrets/default_tenant/outlook_tokens.json"
    encryption_key: Optional[str] = None

    # API prefix
    api_prefix: str = "/outlook"

    # Observability
    log_level: str = "INFO"
    log_format: str = "json"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
