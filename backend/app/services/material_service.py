from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from ..models.material import Material
from ..utils.csv_utils import (
    DEFAULT_SIZE_RATIO_PERCENT,
    MAX_SIZE_RATIO_PERCENT,
    MIN_SIZE_RATIO_PERCENT,
)


@dataclass(frozen=True)
class MatchEvent:
    keyword: str
    subtitle_index: int
    subtitle_text: str
    material_file_name: str
    material_type: str
    position: int
    opacity: int
    loop: int
    trigger_rule: str
    size_ratio_percent: float
    start_time: float
    end_time: float
    status: str  # success|failed
    reason: str | None
    material_path: str | None
    cue_sound_config: str = "随机"
    sound_effect_file_name: str | None = None
    sound_effect_status: str | None = None
    sound_effect_reason: str | None = None
    sound_effect_path: str | None = None


def build_match_events(
    db: Session, subtitles: list[dict[str, Any]], config: list[dict[str, Any]]
) -> list[MatchEvent]:
    events: list[MatchEvent] = []

    for item in config:
        keyword = str(item.get("关键字", "")).strip()
        material_file_raw = str(item.get("素材文件名", "")).strip()
        # Allow users to provide full paths in template CSV/editor.
        # Matching is based on material library file name.
        material_file = Path(material_file_raw.replace("\\", "/")).name
        material_type = str(item.get("素材类型", "")).strip()
        if not keyword or not material_file or not material_type:
            continue

        position = int(item.get("九宫格位置", 9) or 9)
        duration = item.get("显示时长(秒)", None)
        offset = float(item.get("入场偏移(秒)", 0) or 0)
        opacity = int(item.get("透明度", 100) or 100)
        loop = int(item.get("是否循环", 0) or 0)
        trigger_rule = str(item.get("触发规则", "每次触发") or "每次触发").strip()
        cue_sound_config = str(item.get("提示音", "随机") or "随机").strip() or "随机"
        size_ratio_percent = float(
            item.get("素材宽度占比(%)", DEFAULT_SIZE_RATIO_PERCENT)
            or DEFAULT_SIZE_RATIO_PERCENT
        )
        size_ratio_percent = max(
            float(MIN_SIZE_RATIO_PERCENT),
            min(float(MAX_SIZE_RATIO_PERCENT), size_ratio_percent),
        )

        material = (
            db.query(Material).filter(Material.file_name == material_file).first()
        )
        material_path = None
        material_fail_reason = None
        if material is None:
            material_fail_reason = "素材不存在"
        else:
            material_path = material.file_path
            if not os.path.exists(material_path):
                material_fail_reason = "素材文件不存在"

        matched = False
        for sub in subtitles:
            if keyword not in (sub.get("text") or ""):
                continue

            matched = True
            start_time = float(sub.get("start_seconds", 0)) + offset
            base_end = float(sub.get("end_seconds", 0)) + offset
            if duration is None or duration == "":
                end_time = base_end
            else:
                end_time = start_time + float(duration)

            status = "success"
            reason = None
            if material_fail_reason:
                status = "failed"
                reason = material_fail_reason
            elif end_time <= start_time:
                status = "failed"
                reason = "时间范围无效"

            events.append(
                MatchEvent(
                    keyword=keyword,
                    subtitle_index=int(sub.get("index", 0)),
                    subtitle_text=str(sub.get("text", "")),
                    material_file_name=material_file,
                    material_type=material_type,
                    position=position,
                    opacity=opacity,
                    loop=loop,
                    trigger_rule=trigger_rule,
                    size_ratio_percent=size_ratio_percent,
                    start_time=max(0.0, start_time),
                    end_time=max(0.0, end_time),
                    status=status,
                    reason=reason,
                    material_path=material_path,
                    cue_sound_config=cue_sound_config,
                    sound_effect_status="未播放",
                )
            )

            if trigger_rule == "首次触发":
                break

        if not matched:
            events.append(
                MatchEvent(
                    keyword=keyword,
                    subtitle_index=0,
                    subtitle_text="",
                    material_file_name=material_file,
                    material_type=material_type,
                    position=position,
                    opacity=opacity,
                    loop=loop,
                    trigger_rule=trigger_rule,
                    size_ratio_percent=size_ratio_percent,
                    start_time=0.0,
                    end_time=0.0,
                    status="failed",
                    reason="未在字幕中匹配到关键字",
                    material_path=material_path,
                    cue_sound_config=cue_sound_config,
                    sound_effect_status="未播放",
                )
            )

    return events
