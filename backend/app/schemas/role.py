from __future__ import annotations

import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator

ALL_MODULE_KEYS: List[str] = [
    "console",
    "tasks",
    "configs",
    "materials",
    "source_videos",
    "rough_cut",
    "audit",
    "user_management",
    "settings",
]

ADMIN_MODULE_KEYS: List[str] = ALL_MODULE_KEYS

DEFAULT_USER_MODULE_KEYS: List[str] = [
    "console",
    "tasks",
    "configs",
    "materials",
    "source_videos",
    "rough_cut",
    "settings",
]


class RoleOut(BaseModel):
    id: int
    name: str
    display_name: str
    is_system: bool
    module_keys: List[str]
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("module_keys", mode="before")
    @classmethod
    def parse_module_keys(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v or []


class CreateRoleRequest(BaseModel):
    name: str
    display_name: str
    module_keys: List[str]


class UpdateRoleRequest(BaseModel):
    display_name: Optional[str] = None
    module_keys: Optional[List[str]] = None
