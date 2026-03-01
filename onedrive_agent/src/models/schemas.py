"""Pydantic schemas for OneDrive agent."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OAuthInitRequest(BaseModel):
    tenant_id: str
    user_id: Optional[str] = None
    redirect_url: Optional[str] = Field(
        default=None,
        description="Leave empty to use config default",
    )
    extra_state: Optional[Dict[str, str]] = None

    model_config = {
        "json_schema_extra": {
            "examples": [{"tenant_id": "tenant_local", "user_id": "me"}]
        }
    }


class OAuthInitResponse(BaseModel):
    auth_url: str
    state: str
    redirect_uri: str


class LinkTokensRequest(BaseModel):
    source_user_id: str
    target_user_id: str


class UploadFileRequest(BaseModel):
    file_name: str = Field(..., description="Name for the file in OneDrive")
    content_base64: str = Field(..., description="Base64-encoded file content")
    folder_path: Optional[str] = Field(
        default=None,
        description="Destination folder path e.g. 'Documents/Reports'. Leave empty for root.",
    )
    mime_type: str = Field(default="application/octet-stream")

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "file_name": "hello.txt",
                "content_base64": "SGVsbG8gZnJvbSBRaWthIQ==",
                "folder_path": None,
                "mime_type": "text/plain",
            }]
        }
    }


class CreateFolderRequest(BaseModel):
    folder_name: str
    parent_path: Optional[str] = Field(
        default=None,
        description="Parent folder path. Leave empty to create in root.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"folder_name": "Qika Reports", "parent_path": None}]
        }
    }


class ShareItemRequest(BaseModel):
    item_id: str
    emails: List[str] = Field(..., description="Email addresses to share with")
    role: str = Field(
        default="read",
        description="Permission role: 'read', 'write', or 'owner'",
    )
    send_invitation: bool = True

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "item_id": "ITEM_ID_HERE",
                "emails": ["friend@gmail.com"],
                "role": "read",
                "send_invitation": True,
            }]
        }
    }
