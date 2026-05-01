from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuditLogItem(BaseModel):
    id: int
    method: str
    path: str
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    status_code: int
    ip_address: str | None = None
    user_agent: str | None = None
    operator: str | None = None
    source: str = "user"
    duration_ms: int | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    items: list[AuditLogItem] = Field(default_factory=list)
    total: int = 0
