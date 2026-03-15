from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator, ConfigDict


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProjectCreate(BaseModel):
    name: str


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    owner_id: int
    created_at: datetime


class LinkCreate(BaseModel):
    original_url: str
    custom_alias: Optional[str] = None
    expires_at: Optional[datetime] = None
    project_id: Optional[int] = None

    @field_validator("original_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("URL должен начинаться с http:// или https://")
        return value


class LinkUpdate(BaseModel):
    original_url: str

    @field_validator("original_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not (value.startswith("http://") or value.startswith("https://")):
            raise ValueError("URL должен начинаться с http:// или https://")
        return value


class LinkResponse(BaseModel):
    short_code: str
    short_url: str
    original_url: str
    expires_at: Optional[datetime]
    project_id: Optional[int]


class LinkStatsResponse(BaseModel):
    short_code: str
    original_url: str
    created_at: datetime
    clicks: int
    last_used_at: Optional[datetime]
    expires_at: Optional[datetime]
    project_id: Optional[int]


class SearchResponse(BaseModel):
    found: bool
    short_code: Optional[str] = None
    original_url: Optional[str] = None


class ExpiredLinkHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    short_code: str
    original_url: str
    expired_at: datetime
    clicks: int
    created_at: datetime
    last_used_at: Optional[datetime]
    reason: str


class CleanupConfigRequest(BaseModel):
    days: int
