from __future__ import annotations

import csv
import io
from typing import Any

REQUIRED_HEADERS = ["关键词", "素材文件名", "素材类型"]

ALLOWED_MATERIAL_TYPES = {"图片", "GIF", "短视频"}
ALLOWED_TRIGGER_RULES = {"首次触发", "每次触发"}
ALLOWED_LIBRARY_SCOPES = {"定量素材", "未归档", "产品分类素材"}
DEFAULT_SIZE_RATIO_PERCENT = 25
DEFAULT_VIDEO_SIZE_RATIO_PERCENT = 70
MIN_SIZE_RATIO_PERCENT = 5
MAX_SIZE_RATIO_PERCENT = 100
DEFAULT_VIDEO_START_SECONDS = 0.0


def parse_config_csv_bytes(content: bytes) -> list[dict[str, Any]]:
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV 为空或缺少表头")

    headers = [h.strip() for h in reader.fieldnames if h is not None]
    for required in REQUIRED_HEADERS:
        if required not in headers:
            raise ValueError(f"CSV 缺少必填字段: {required}")

    items: list[dict[str, Any]] = []
    for row in reader:
        keyword = (row.get("关键词") or "").strip()
        material_name = (row.get("素材文件名") or "").strip()
        material_type = (row.get("素材类型") or "").strip()
        cue_sound = (row.get("提示音") or "随机").strip() or "随机"
        library_scope = (row.get("素材库分类") or "定量素材").strip() or "定量素材"
        product_name = (row.get("产品目录") or "").strip()
        script_folder = (row.get("脚本子文件夹") or "").strip()

        if not keyword or not material_name or not material_type:
            continue

        if material_type not in ALLOWED_MATERIAL_TYPES:
            raise ValueError(f"素材类型不合法: {material_type}")
        if library_scope not in ALLOWED_LIBRARY_SCOPES:
            raise ValueError(f"素材库分类不合法: {library_scope}")
        if library_scope == "产品分类素材" and (not product_name or not script_folder):
            raise ValueError("产品分类素材必须填写产品目录和脚本子文件夹")

        def _float(name: str) -> float | None:
            value = row.get(name)
            if value is None or str(value).strip() == "":
                return None
            return float(str(value).strip())

        def _int(name: str, default: int) -> int:
            value = row.get(name)
            if value is None or str(value).strip() == "":
                return default
            return int(float(str(value).strip()))

        duration = _float("显示时长(秒)")
        if duration is None and material_type in {"图片", "GIF"}:
            duration = 2.0

        offset = _float("入场偏移(秒)") or 0.0
        grid_default = 1 if material_type in {"图片", "GIF"} else 9
        grid_pos = _int("九宫格位置", grid_default)
        opacity = _int("透明度", 100)
        loop = _int("是否循环", 0)
        trigger = (row.get("触发规则") or "每次触发").strip() or "每次触发"
        size_ratio_percent = _float("素材宽度占比(%)")
        if size_ratio_percent is None:
            size_ratio_percent = (
                float(DEFAULT_VIDEO_SIZE_RATIO_PERCENT)
                if material_type == "短视频"
                else float(DEFAULT_SIZE_RATIO_PERCENT)
            )

        video_start_seconds = _float("视频起始秒(秒)")
        if video_start_seconds is None:
            video_start_seconds = DEFAULT_VIDEO_START_SECONDS
        video_start_seconds = max(0.0, float(video_start_seconds))

        video_duration_seconds = _float("视频持续秒(秒)")
        if video_duration_seconds is not None and video_duration_seconds <= 0:
            raise ValueError(f"视频持续秒(秒)必须大于 0: {video_duration_seconds}")

        if grid_pos < 1 or grid_pos > 9:
            raise ValueError(f"九宫格位置必须为 1-9: {grid_pos}")
        if opacity < 0 or opacity > 100:
            raise ValueError(f"透明度必须为 0-100: {opacity}")
        if loop not in (0, 1):
            raise ValueError(f"是否循环必须为 0/1: {loop}")
        if trigger not in ALLOWED_TRIGGER_RULES:
            raise ValueError(f"触发规则不合法: {trigger}")
        if size_ratio_percent < MIN_SIZE_RATIO_PERCENT or size_ratio_percent > MAX_SIZE_RATIO_PERCENT:
            raise ValueError(
                f"素材宽度占比(%)必须为 {MIN_SIZE_RATIO_PERCENT}-{MAX_SIZE_RATIO_PERCENT}: {size_ratio_percent}"
            )
        if material_type == "短视频" and size_ratio_percent not in (70, 100):
            raise ValueError("短视频素材宽度占比(%)仅支持 70 或 100")

        items.append(
            {
                "关键词": keyword,
                "素材库分类": library_scope,
                "产品目录": product_name,
                "脚本子文件夹": script_folder,
                "素材文件名": material_name,
                "素材类型": material_type,
                "提示音": cue_sound,
                "显示时长(秒)": duration,
                "入场偏移(秒)": offset,
                "九宫格位置": grid_pos,
                "透明度": opacity,
                "是否循环": loop,
                "触发规则": trigger,
                "素材宽度占比(%)": float(size_ratio_percent),
                "视频起始秒(秒)": video_start_seconds,
                "视频持续秒(秒)": video_duration_seconds,
            }
        )

    if not items:
        raise ValueError("CSV 未解析到任何有效配置行")
    return items


def export_config_csv(config: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    fieldnames = [
        "关键词",
        "素材库分类",
        "产品目录",
        "脚本子文件夹",
        "素材文件名",
        "素材类型",
        "提示音",
        "显示时长(秒)",
        "入场偏移(秒)",
        "九宫格位置",
        "透明度",
        "是否循环",
        "触发规则",
        "素材宽度占比(%)",
        "视频起始秒(秒)",
        "视频持续秒(秒)",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for item in config:
        normalized = dict(item)
        if not normalized.get("素材库分类"):
            normalized["素材库分类"] = "定量素材"
        if normalized["素材库分类"] != "产品分类素材":
            normalized["产品目录"] = ""
            normalized["脚本子文件夹"] = ""
        writer.writerow({k: normalized.get(k, "") for k in fieldnames})
    return output.getvalue()
