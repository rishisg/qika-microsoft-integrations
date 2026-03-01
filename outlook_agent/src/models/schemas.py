"""Pydantic schemas for Outlook agent API request/response models."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── OAuth ──────────────────────────────────────────────────

class OAuthInitRequest(BaseModel):
    tenant_id: str
    user_id: Optional[str] = None
    redirect_url: Optional[str] = Field(
        default=None,
        description="Leave empty to use the default redirect URI from config",
    )
    extra_state: Optional[Dict[str, str]] = None

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tenant_id": "tenant_local",
                    "user_id": "me",
                }
            ]
        }
    }


class OAuthInitResponse(BaseModel):
    auth_url: str
    state: str
    redirect_uri: str


class LinkTokensRequest(BaseModel):
    source_user_id: str
    target_user_id: str


# ── Email ──────────────────────────────────────────────────

class SendEmailRequest(BaseModel):
    to: List[str] = Field(..., description="List of recipient email addresses")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body text")
    cc: Optional[List[str]] = Field(default=None)
    bcc: Optional[List[str]] = Field(default=None)
    body_type: str = Field(default="Text", description="'Text' or 'HTML'")


class SendEmailResponse(BaseModel):
    success: bool
    status: str
    subject: str
    to: List[str]


class ReplyEmailRequest(BaseModel):
    message_id: str
    body: str
    body_type: str = "Text"


class ListMessagesRequest(BaseModel):
    folder: str = Field(default="inbox")
    search: Optional[str] = None
    max_results: int = Field(default=20, ge=1, le=100)
    skip: int = Field(default=0, ge=0)


class MoveMessageRequest(BaseModel):
    message_id: str
    destination_folder_id: str


class MarkReadRequest(BaseModel):
    message_id: str
    is_read: bool = True
