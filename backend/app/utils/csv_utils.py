from __future__ import annotations

import csv
import io
from typing import Any

REQUIRED_HEADERS = ["关键字", "素材文件名", "素材类型"]

ALLOWED_MATERIAL_TYPES = {"图片", "GIF", "短视频"}
ALLOWED_TRIGGER_RULES = {"首次触发", "每次触发"}
DEFAULT_SIZE_RATIO_PERCENT = 25
MIN_SIZE_RATIO_PERCENT = 5
MAX_SIZE_RATIO_PERCENT = 80


def parse_config_csv_bytes(content: bytes) -> list[dict[str, Any]]:
    """
    Parse config CSV according to the spec.

    Returns a list of dicts using the original Chinese keys:
    - 关键字, 素材文件名, 素材类型, 提示音, 显示时长(秒), 入场偏移(秒), 九宫格位置, 透明度, 是否循环, 触发规则, 素材宽度占比(%)
    """
    # Handle UTF-8 BOM.
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
        keyword = (row.get("关键字") or "").strip()
        material_name = (row.get("素材文件名") or "").strip()
        material_type = (row.get("素材类型") or "").strip()
        cue_sound = (row.get("提示音") or "随机").strip() or "随机"
        if not keyword or not material_name or not material_type:
            continue

        if material_type not in ALLOWED_MATERIAL_TYPES:
            raise ValueError(f"素材类型不合法: {material_type}")

        def _float(name: str) -> float | None:
            v = row.get(name)
            if v is None or str(v).strip() == "":
                return None
            return float(str(v).strip())

        def _int(name: str, default: int) -> int:
            v = row.get(name)
            if v is None or str(v).strip() == "":
                return default
            return int(float(str(v).strip()))

        duration = _float("显示时长(秒)")
        offset = _float("入场偏移(秒)") or 0.0
        grid_pos = _int("九宫格位置", 9)
        opacity = _int("透明度", 100)
        loop = _int("是否循环", 0)
        trigger = (row.get("触发规则") or "每次触发").strip() or "每次触发"
        size_ratio_percent = _float("素材宽度占比(%)")
        if size_ratio_percent is None:
            size_ratio_percent = float(DEFAULT_SIZE_RATIO_PERCENT)

        if grid_pos < 1 or grid_pos > 9:
            raise ValueError(f"九宫格位置必须为 1-9: {grid_pos}")
        if opacity < 0 or opacity > 100:
            raise ValueError(f"透明度必须为 0-100: {opacity}")
        if loop not in (0, 1):
            raise ValueError(f"是否循环必须为 0/1: {loop}")
        if trigger not in ALLOWED_TRIGGER_RULES:
            raise ValueError(f"触发规则不合法: {trigger}")
        if (
            size_ratio_percent < MIN_SIZE_RATIO_PERCENT
            or size_ratio_percent > MAX_SIZE_RATIO_PERCENT
        ):
            raise ValueError(
                f"素材宽度占比(%)必须为 {MIN_SIZE_RATIO_PERCENT}-{MAX_SIZE_RATIO_PERCENT}: {size_ratio_percent}"
            )

        items.append(
            {
                "关键字": keyword,
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
            }
        )

    if not items:
        raise ValueError("CSV 未解析到任何有效配置行")
    return items


def export_config_csv(config: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    fieldnames = [
        "关键字",
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
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for item in config:
        writer.writerow({k: item.get(k, "") for k in fieldnames})
    return output.getvalue()
