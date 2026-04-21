from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from .material_service import MatchEvent


def write_report_xlsx(report_path: str, events: list[MatchEvent]) -> None:
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "执行报告"

    headers = [
        "关键字",
        "字幕索引",
        "字幕文本",
        "出现时间",
        "素材文件名",
        "素材类型",
        "入场时间(秒)",
        "结束时间(秒)",
        "九宫格位置",
        "透明度",
        "是否循环",
        "触发规则",
        "素材宽度占比(%)",
        "植入状态",
        "失败原因",
        "提示音配置",
        "实际提示音文件",
        "提示音状态",
        "提示音原因",
    ]
    ws.append(headers)

    for e in events:
        appear_time = ""
        if e.subtitle_index:
            appear_time = f"{e.start_time:.3f}"
        ws.append(
            [
                e.keyword,
                e.subtitle_index,
                e.subtitle_text,
                appear_time,
                e.material_file_name,
                e.material_type,
                round(e.start_time, 3),
                round(e.end_time, 3),
                e.position,
                e.opacity,
                e.loop,
                e.trigger_rule,
                round(e.size_ratio_percent, 2),
                "成功" if e.status == "success" else "失败",
                e.reason or "",
                e.cue_sound_config or "随机",
                e.sound_effect_file_name or "",
                e.sound_effect_status or "",
                e.sound_effect_reason or "",
            ]
        )

    wb.save(path)
