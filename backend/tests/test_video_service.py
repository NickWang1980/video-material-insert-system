from __future__ import annotations

from backend.app.services.material_service import MatchEvent
from backend.app.services.video_service import (
    VideoProbe,
    _apply_collision_layer_order,
    build_ffmpeg_command,
    grid_xy_expr,
)


def test_grid_xy_expr():
    x, y = grid_xy_expr(1)
    assert "main_w" in x and "overlay_w" in x
    assert "main_h" in y and "overlay_h" in y


class _Settings:
    ffmpeg_bin = "ffmpeg"
    ffprobe_bin = "ffprobe"


def _event(
    sound_effect_path: str | None = None,
    material_type: str = "图片",
    video_start_seconds: float = 0.0,
    video_duration_seconds: float | None = None,
) -> MatchEvent:
    return MatchEvent(
        keyword="家人们",
        subtitle_index=1,
        subtitle_text="家人们",
        material_file_name="hello.png",
        material_type=material_type,
        position=9,
        opacity=100,
        loop=0,
        trigger_rule="首次触发",
        size_ratio_percent=30.0,
        start_time=1.0,
        end_time=3.0,
        status="success",
        reason=None,
        material_path="C:/tmp/hello.png",
        sound_effect_file_name="ding.mp3" if sound_effect_path else None,
        sound_effect_status="已添加" if sound_effect_path else "未播放",
        sound_effect_reason=None if sound_effect_path else "音效池为空",
        sound_effect_path=sound_effect_path,
        video_start_seconds=video_start_seconds,
        video_duration_seconds=video_duration_seconds,
    )


def test_build_ffmpeg_command_with_sound_effect(monkeypatch):
    def _probe(_settings, _video_path):
        return VideoProbe(width=1080, height=1920, duration=60.0, has_audio=True)

    monkeypatch.setattr("backend.app.services.video_service.probe_video", _probe)
    cmd = build_ffmpeg_command(
        _Settings(),
        video_path="C:/tmp/in.mp4",
        subtitle_path="C:/tmp/in.srt",
        subtitle_encoding="utf-8",
        events=[_event("C:/tmp/ding.mp3")],
        output_path="C:/tmp/out.mp4",
        output_format="MP4",
        resolution="1080P",
        video_bitrate_kbps=1500,
    )
    cmd_str = " ".join(cmd)
    assert "force_original_aspect_ratio=decrease" in cmd_str
    assert "amix=inputs=2" in cmd_str
    assert "-map [aout]" in cmd_str
    assert "-c:a aac" in cmd_str


def test_build_ffmpeg_command_without_sound_effect(monkeypatch):
    def _probe(_settings, _video_path):
        return VideoProbe(width=1080, height=1920, duration=60.0, has_audio=True)

    monkeypatch.setattr("backend.app.services.video_service.probe_video", _probe)
    cmd = build_ffmpeg_command(
        _Settings(),
        video_path="C:/tmp/in.mp4",
        subtitle_path="C:/tmp/in.srt",
        subtitle_encoding="utf-8",
        events=[_event(None)],
        output_path="C:/tmp/out.mp4",
        output_format="MP4",
        resolution="1080P",
        video_bitrate_kbps=1500,
    )
    cmd_str = " ".join(cmd)
    assert "-map 0:a?" in cmd_str
    assert "-c:a copy" in cmd_str


def test_build_ffmpeg_command_short_video_clip_params(monkeypatch):
    def _probe(_settings, _video_path):
        return VideoProbe(width=1080, height=1920, duration=60.0, has_audio=False)

    monkeypatch.setattr("backend.app.services.video_service.probe_video", _probe)
    cmd = build_ffmpeg_command(
        _Settings(),
        video_path="C:/tmp/in.mp4",
        subtitle_path="C:/tmp/in.srt",
        subtitle_encoding="utf-8",
        events=[_event(None, material_type="短视频", video_start_seconds=2.0, video_duration_seconds=4.0)],
        output_path="C:/tmp/out.mp4",
        output_format="MP4",
        resolution="1080P",
        video_bitrate_kbps=1500,
    )
    cmd_str = " ".join(cmd)
    assert "trim=start=2.0:duration=4.0" in cmd_str


def test_apply_collision_layer_order_high_layer_last():
    e_top = _event(None)
    e_mid = _event(None)
    e_low = _event(None)

    e_top = MatchEvent(**{**e_top.__dict__, "subtitle_index": 5, "layer_rank": 0, "keyword": "A"})
    e_mid = MatchEvent(**{**e_mid.__dict__, "subtitle_index": 5, "layer_rank": 1, "keyword": "B"})
    e_low = MatchEvent(**{**e_low.__dict__, "subtitle_index": 5, "layer_rank": 2, "keyword": "C"})

    labels = [(e_top, "ov_top"), (e_mid, "ov_mid"), (e_low, "ov_low")]
    ordered = _apply_collision_layer_order(labels)
    assert [item[0].keyword for item in ordered] == ["C", "B", "A"]
