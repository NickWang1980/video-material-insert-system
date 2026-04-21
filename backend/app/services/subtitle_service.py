from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pysrt


@dataclass(frozen=True)
class SubtitleLine:
    index: int
    start: str
    end: str
    text: str
    start_seconds: float
    end_seconds: float
    duration: float


def parse_srt(subtitle_path: str, encoding: str = "utf-8", time_offset_seconds: float = 0.0) -> list[dict[str, Any]]:
    subs = pysrt.open(subtitle_path, encoding=encoding)
    result: list[dict[str, Any]] = []
    for sub in subs:
        start_seconds = sub.start.ordinal / 1000.0 + time_offset_seconds
        end_seconds = sub.end.ordinal / 1000.0 + time_offset_seconds
        if end_seconds < 0:
            continue
        if start_seconds < 0:
            start_seconds = 0.0
        result.append(
            {
                "index": sub.index,
                "start": sub.start.to_time().strftime("%H:%M:%S,%f")[:-3],
                "end": sub.end.to_time().strftime("%H:%M:%S,%f")[:-3],
                "text": sub.text,
                "start_seconds": start_seconds,
                "end_seconds": end_seconds,
                "duration": max(0.0, end_seconds - start_seconds),
            }
        )
    return result

