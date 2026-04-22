from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..models.material_folder_binding import MaterialFolderBinding
from ..models.material import Material
from ..models.material_product import MaterialProduct
from ..models.material_script_folder import MaterialScriptFolder
from ..utils.csv_utils import (
    DEFAULT_SIZE_RATIO_PERCENT,
    DEFAULT_VIDEO_SIZE_RATIO_PERCENT,
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
    video_start_seconds: float = 0.0
    video_duration_seconds: float | None = None
    layer_rank: int | None = None


def _build_subtitle_layer_rank_map(
    subtitles: list[dict[str, Any]],
    config: list[dict[str, Any]],
    collision_priority_by_subtitle: dict[int, list[str]] | None = None,
) -> dict[int, dict[str, int]]:
    keyword_default_order: dict[str, int] = {}
    for order, rule in enumerate(config):
        if not isinstance(rule, dict):
            continue
        keyword_raw = rule.get("关键词", rule.get("关键字"))
        keyword = keyword_raw if isinstance(keyword_raw, str) else str(keyword_raw or "")
        keyword = keyword.strip()
        if keyword:
            keyword_default_order.setdefault(keyword, order)

    subtitle_layer_rank_map: dict[int, dict[str, int]] = {}
    for subtitle in subtitles:
        subtitle_index = int(subtitle.get("index", 0))
        subtitle_text = str(subtitle.get("text", "") or "")
        matched_keywords = [
            keyword for keyword in keyword_default_order.keys() if keyword in subtitle_text
        ]
        if len(matched_keywords) <= 1:
            continue

        default_ordered = sorted(
            matched_keywords,
            key=lambda item: (-len(item), keyword_default_order.get(item, 10**9)),
        )
        ordered_keywords = list(default_ordered)

        if collision_priority_by_subtitle:
            override_order = collision_priority_by_subtitle.get(subtitle_index, [])
            if override_order:
                normalized_override = [
                    str(keyword).strip()
                    for keyword in override_order
                    if str(keyword).strip()
                ]
                matched_set = set(matched_keywords)
                override_hits = [
                    keyword for keyword in normalized_override if keyword in matched_set
                ]
                if override_hits:
                    ordered_keywords = override_hits + [
                        keyword
                        for keyword in default_ordered
                        if keyword not in set(override_hits)
                    ]

        subtitle_layer_rank_map[subtitle_index] = {
            keyword: idx for idx, keyword in enumerate(ordered_keywords)
        }
    return subtitle_layer_rank_map


def _default_grid_position(material_type: str) -> int:
    if material_type in {"图片", "GIF"}:
        return 1
    return 9


def _default_duration(material_type: str) -> float | None:
    if material_type in {"图片", "GIF"}:
        return 2.0
    return None


def _default_size_ratio(material_type: str) -> float:
    if material_type == "短视频":
        return float(DEFAULT_VIDEO_SIZE_RATIO_PERCENT)
    return float(DEFAULT_SIZE_RATIO_PERCENT)


def _find_material_by_scope(
    db: Session,
    *,
    file_name: str,
    library_scope: str,
    product_name: str,
    script_folder_name: str,
) -> tuple[Material | None, str | None]:
    if library_scope == "产品分类素材":
        if not product_name or not script_folder_name:
            return None, "产品分类素材缺少产品目录或脚本子文件夹"

        product = db.query(MaterialProduct).filter(MaterialProduct.name == product_name).first()
        if product is None:
            return None, f"产品目录不存在: {product_name}"

        script_folder = (
            db.query(MaterialScriptFolder)
            .filter(
                MaterialScriptFolder.product_id == product.id,
                MaterialScriptFolder.name == script_folder_name,
            )
            .first()
        )
        if script_folder is None:
            return None, f"脚本子文件夹不存在: {product_name}/{script_folder_name}"

        material = (
            db.query(Material)
            .join(
                MaterialFolderBinding,
                MaterialFolderBinding.material_id == Material.id,
            )
            .filter(
                MaterialFolderBinding.script_folder_id == script_folder.id,
                Material.file_name == file_name,
            )
            .first()
        )
        if material is None:
            return None, "当前产品脚本目录下素材不存在"
        return material, None

    if library_scope == "未归档":
        material = (
            db.query(Material)
            .filter(
                Material.library_kind == "unfiled",
                Material.file_name == file_name,
            )
            .first()
        )
        if material is None:
            return None, "未归档素材库中素材不存在"
        return material, None

    material = (
        db.query(Material)
        .filter(
            Material.library_kind == "general",
            Material.file_name == file_name,
        )
        .first()
    )
    if material is None:
        return None, "定量素材库中素材不存在"
    return material, None


def build_match_events(
    db: Session,
    subtitles: list[dict[str, Any]],
    config: list[dict[str, Any]],
    collision_priority_by_subtitle: dict[int, list[str]] | None = None,
) -> list[MatchEvent]:
    events: list[MatchEvent] = []
    subtitle_layer_rank_map = _build_subtitle_layer_rank_map(
        subtitles,
        config,
        collision_priority_by_subtitle=collision_priority_by_subtitle,
    )

    for item in config:
        keyword = str(item.get("关键词", item.get("关键字", ""))).strip()
        material_file_raw = str(item.get("素材文件名", "")).strip()
        material_file = Path(material_file_raw.replace("\\", "/")).name
        material_type = str(item.get("素材类型", "")).strip()
        if not keyword or not material_file or not material_type:
            continue

        library_scope = str(item.get("素材库分类", "定量素材") or "定量素材").strip() or "定量素材"
        product_name = str(item.get("产品目录", "") or "").strip()
        script_folder_name = str(item.get("脚本子文件夹", "") or "").strip()

        position = int(
            item.get("九宫格位置", _default_grid_position(material_type))
            or _default_grid_position(material_type)
        )
        duration = item.get("显示时长(秒)", _default_duration(material_type))
        if duration in ("", None):
            duration = _default_duration(material_type)
        offset = float(item.get("入场偏移(秒)", 0) or 0)
        opacity = int(item.get("透明度", 100) or 100)
        loop = int(item.get("是否循环", 0) or 0)
        trigger_rule = str(item.get("触发规则", "每次触发") or "每次触发").strip()
        cue_sound_config = str(item.get("提示音", "随机") or "随机").strip() or "随机"
        size_ratio_percent = float(
            item.get("素材宽度占比(%)", _default_size_ratio(material_type))
            or _default_size_ratio(material_type)
        )
        if material_type == "短视频" and size_ratio_percent not in (70.0, 100.0):
            size_ratio_percent = float(DEFAULT_VIDEO_SIZE_RATIO_PERCENT)
        size_ratio_percent = max(
            float(MIN_SIZE_RATIO_PERCENT),
            min(float(MAX_SIZE_RATIO_PERCENT), size_ratio_percent),
        )

        video_start_seconds = float(item.get("视频起始秒(秒)", 0) or 0)
        video_start_seconds = max(0.0, video_start_seconds)
        video_duration_value = item.get("视频持续秒(秒)", None)
        video_duration_seconds = (
            float(video_duration_value) if video_duration_value not in (None, "") else None
        )
        if video_duration_seconds is not None and video_duration_seconds <= 0:
            video_duration_seconds = None

        material, lookup_error = _find_material_by_scope(
            db,
            file_name=material_file,
            library_scope=library_scope,
            product_name=product_name,
            script_folder_name=script_folder_name,
        )
        material_path = None
        material_fail_reason = lookup_error
        if material is not None:
            material_path = material.file_path
            if not os.path.exists(material_path):
                material_fail_reason = "素材文件不存在"

        matched = False
        for sub in subtitles:
            if keyword not in (sub.get("text") or ""):
                continue

            matched = True
            subtitle_index = int(sub.get("index", 0))
            layer_rank = None
            rank_map = subtitle_layer_rank_map.get(subtitle_index)
            if rank_map and keyword in rank_map:
                layer_rank = int(rank_map[keyword])

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
                    subtitle_index=subtitle_index,
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
                    video_start_seconds=video_start_seconds,
                    video_duration_seconds=video_duration_seconds,
                    layer_rank=layer_rank,
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
                    reason="未在字幕中匹配到关键词",
                    material_path=material_path,
                    cue_sound_config=cue_sound_config,
                    sound_effect_status="未播放",
                    video_start_seconds=video_start_seconds,
                    video_duration_seconds=video_duration_seconds,
                    layer_rank=None,
                )
            )

    return events
