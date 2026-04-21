from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MaterialResponse(BaseModel):
    id: int
    file_name: str
    file_type: str
    file_size: int
    file_path: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaterialRenameRequest(BaseModel):
    new_file_name: str
