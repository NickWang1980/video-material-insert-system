from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConfigRule(BaseModel):
    关键字: str
    素材文件名: str
    素材类型: str  # 图片|GIF|短视频
    显示时长_秒: float | None = None
    入场偏移_秒: float = 0.0
    九宫格位置: int = 9
    透明度: int = 100
    是否循环: int = 0
    触发规则: str = "每次触发"  # 首次触发|每次触发

    def to_legacy_dict(self) -> dict[str, Any]:
        return {
            "关键字": self.关键字,
            "素材文件名": self.素材文件名,
            "素材类型": self.素材类型,
            "显示时长(秒)": self.显示时长_秒,
            "入场偏移(秒)": self.入场偏移_秒,
            "九宫格位置": self.九宫格位置,
            "透明度": self.透明度,
            "是否循环": self.是否循环,
            "触发规则": self.触发规则,
        }


class ConfigTemplateCreate(BaseModel):
    template_name: str
    description: str | None = None
    config_content: list[dict[str, Any]]


class ConfigTemplateResponse(BaseModel):
    id: int
    template_name: str
    description: str | None = None
    keywords: list[str] = Field(default_factory=list)
    keyword_preview: str = ""
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
