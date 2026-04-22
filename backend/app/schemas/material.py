from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MaterialProductPayload(BaseModel):
    name: str


class MaterialScriptFolderPayload(BaseModel):
    name: str


class MaterialScriptFolderResponse(BaseModel):
    id: int
    product_id: int
    name: str
    created_at: datetime
    updated_at: datetime


class MaterialProductResponse(BaseModel):
    id: int
    name: str
    created_at: datetime
    updated_at: datetime
    scripts: list[MaterialScriptFolderResponse] = Field(default_factory=list)


class MaterialFolderLink(BaseModel):
    product_id: int
    product_name: str
    script_folder_id: int
    script_folder_name: str


class MaterialResponse(BaseModel):
    id: int
    file_name: str
    file_type: str
    file_size: int
    file_path: str
    library_kind: str = "unfiled"
    product_id: int | None = None
    script_folder_id: int | None = None
    product_name: str | None = None
    script_folder: str | None = None
    script_folder_name: str | None = None
    folder_links: list[MaterialFolderLink] = Field(default_factory=list)
    audio_removed: bool | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MaterialRenameRequest(BaseModel):
    new_file_name: str


class MaterialTreeScriptNode(BaseModel):
    id: int
    name: str


class MaterialTreeProductNode(BaseModel):
    id: int
    name: str
    scripts: list[MaterialTreeScriptNode] = Field(default_factory=list)


class MaterialTreeResponse(BaseModel):
    unfiled_label: str = "未归档"
    product_label: str = "产品分类素材"
    products: list[MaterialTreeProductNode]


class MaterialFilePayload(BaseModel):
    target_type: str  # general|unfiled|script
    script_folder_id: int | None = None
