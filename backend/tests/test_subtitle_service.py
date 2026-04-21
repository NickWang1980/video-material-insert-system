from __future__ import annotations

from pathlib import Path

from backend.app.services.subtitle_service import parse_srt


def test_parse_srt_with_offset(tmp_path: Path):
    p = tmp_path / "a.srt"
    p.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\n家人们\n\n",
        encoding="utf-8",
    )
    subs = parse_srt(str(p), encoding="utf-8", time_offset_seconds=1.0)
    assert len(subs) == 1
    assert abs(subs[0]["start_seconds"] - 2.0) < 1e-6
    assert abs(subs[0]["end_seconds"] - 3.0) < 1e-6

