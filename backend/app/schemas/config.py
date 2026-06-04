from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConfigRule(BaseModel):
    关键词: str
    素材库分类: str = "定量素材"
    产品目录: str = ""
    脚本子文件夹: str = ""
    素材文件名: str
    素材类型: str  # 图片|GIF|短视频
    提示音: str = "随机"
    显示时长_秒: float | None = None
    入场偏移_秒: float = 0.0
    九宫格位置: int = 9
    透明度: int = 100
    是否循环: int = 0
    触发规则: str = "每次触发"  # 首次触发|每次触发
    素材宽度占比: float = 25.0
    视频起始秒_秒: float = 0.0
    视频持续秒_秒: float | None = None
    # 画中画类型 "普通"|"圆角"|"手机边框"。圆角时半径/描边生效；手机边框时 手机边框文件 生效。
    圆角类型: str = "普通"
    圆角半径_px: int = 24
    描边颜色: str = "#FFFFFF"
    描边粗细_px: int = 0
    手机边框文件: str = ""

    def to_legacy_dict(self) -> dict[str, Any]:
        return {
            "关键词": self.关键词,
            "素材库分类": self.素材库分类,
            "产品目录": self.产品目录,
            "脚本子文件夹": self.脚本子文件夹,
            "素材文件名": self.素材文件名,
            "素材类型": self.素材类型,
            "提示音": self.提示音,
            "显示时长(秒)": self.显示时长_秒,
            "入场偏移(秒)": self.入场偏移_秒,
            "九宫格位置": self.九宫格位置,
            "透明度": self.透明度,
            "是否循环": self.是否循环,
            "触发规则": self.触发规则,
            "素材宽度占比(%)": self.素材宽度占比,
            "视频起始秒(秒)": self.视频起始秒_秒,
            "视频持续秒(秒)": self.视频持续秒_秒,
            "圆角类型": self.圆角类型,
            "圆角半径(px)": self.圆角半径_px,
            "描边颜色": self.描边颜色,
            "描边粗细(px)": self.描边粗细_px,
            "手机边框文件": self.手机边框文件,
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
