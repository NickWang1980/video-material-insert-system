from __future__ import annotations

from pathlib import Path

from backend.app.services.rough_cut_service import build_timeline


def _format_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    milliseconds = int(round((seconds - int(seconds)) * 1000))
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def _write_srt(path: Path, start: float, end: float, text: str) -> None:
    path.write_text(
        "1\n"
        f"{_format_srt_time(start)} --> {_format_srt_time(end)}\n"
        f"{text}\n",
        encoding="utf-8",
    )


def test_build_timeline_does_not_use_earlier_asr_segment_after_later_match(tmp_path):
    script_text = "角色A取材"
    early_srt = tmp_path / "early.srt"
    late_srt = tmp_path / "late.srt"
    _write_srt(early_srt, 10.9, 15.8, "角色A")
    _write_srt(late_srt, 15.8, 19.0, script_text)

    assets = [
        {
            "id": "asset-late",
            "roleId": "A",
            "filePath": "late.mp4",
            "duration": 30.0,
            "asrSrtPath": late_srt.as_posix(),
        },
        {
            "id": "asset-early",
            "roleId": "A",
            "filePath": "early.mp4",
            "duration": 30.0,
            "asrSrtPath": early_srt.as_posix(),
        },
    ]
    sentences = [
        {"id": "s1", "roleId": "A", "text": script_text, "estimatedDuration": 3.2},
        {"id": "s2", "roleId": "A", "text": script_text, "estimatedDuration": 3.2},
    ]

    _, timeline = build_timeline(sentences, assets, recalculate_durations=True)

    assert timeline[0]["sourceStart"] == 15.8
    assert timeline[0]["sourceEnd"] == 19.0
    assert timeline[1]["sourceStart"] >= 15.8
    assert timeline[1]["sourceStart"] != 10.9
