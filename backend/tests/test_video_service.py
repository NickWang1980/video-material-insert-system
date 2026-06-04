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


def test_build_ffmpeg_command_rounded_pip(tmp_path, monkeypatch):
    def _probe(_settings, _path):
        return VideoProbe(width=1080, height=1920, duration=60.0, has_audio=False)

    monkeypatch.setattr("backend.app.services.video_service.probe_video", _probe)

    class _S:
        ffmpeg_bin = "ffmpeg"
        ffprobe_bin = "ffprobe"
        data_dir = tmp_path

    event = _event(None)
    event = MatchEvent(
        **{
            **event.__dict__,
            "corner_style": "圆角",
            "corner_radius_px": 30,
            "border_color": "#FFFFFF",
            "border_width_px": 3,
        }
    )
    cmd = build_ffmpeg_command(
        _S(),
        video_path="C:/tmp/in.mp4",
        subtitle_path="C:/tmp/in.srt",
        subtitle_encoding="utf-8",
        events=[event],
        output_path="C:/tmp/out.mp4",
        output_format="MP4",
        resolution="1080P",
        video_bitrate_kbps=1500,
    )
    cmd_str = " ".join(cmd)
    # 圆角分支：精确 scale（1080*0.3=324 宽，等比 576 高）、alphamerge、描边 overlay。
    assert "scale=324:576" in cmd_str
    assert "alphamerge=shortest=1" in cmd_str
    assert "overlay=0:0:shortest=1" in cmd_str
    # 普通分支用的 decrease 不应出现在这条圆角链上。
    assert "force_original_aspect_ratio=decrease" not in cmd_str
    # 图片素材本身 1 个 -loop 1 -i，再加遮罩 + 描边各 1 个 = 共 3 个。
    assert cmd_str.count("-loop 1 -i") == 3


def test_build_ffmpeg_command_normal_pip_unchanged(tmp_path, monkeypatch):
    """corner_style=普通 时，filter 链应与未引入圆角前一致（零回归）。"""

    def _probe(_settings, _path):
        return VideoProbe(width=1080, height=1920, duration=60.0, has_audio=False)

    monkeypatch.setattr("backend.app.services.video_service.probe_video", _probe)

    class _S:
        ffmpeg_bin = "ffmpeg"
        ffprobe_bin = "ffprobe"
        data_dir = tmp_path

    cmd = build_ffmpeg_command(
        _S(),
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
    assert "force_original_aspect_ratio=decrease" in cmd_str
    assert "alphamerge" not in cmd_str
    # 仅图片素材自身 1 个 -loop 1 -i，无遮罩输入。
    assert cmd_str.count("-loop 1 -i") == 1


def test_build_ffmpeg_command_phone_frame(tmp_path, monkeypatch):
    from PIL import Image

    def _probe(_settings, _path):
        return VideoProbe(width=1080, height=1920, duration=60.0, has_audio=False)

    monkeypatch.setattr("backend.app.services.video_service.probe_video", _probe)

    # 造一张手机边框 PNG（外透明 + 不透明边框 + 中间透明屏幕）放到约定目录。
    frames_dir = tmp_path / "uploads" / "phone_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame = frames_dir / "iphone.png"
    im = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
    px = im.load()
    for y in range(10, 390):
        for x in range(10, 190):
            px[x, y] = (0, 0, 0, 255)
    for y in range(24, 376):
        for x in range(24, 176):
            px[x, y] = (0, 0, 0, 0)
    im.save(frame)

    class _S:
        ffmpeg_bin = "ffmpeg"
        ffprobe_bin = "ffprobe"
        data_dir = tmp_path

    event = _event(None, material_type="短视频")
    event = MatchEvent(
        **{**event.__dict__, "corner_style": "手机边框", "phone_frame_file": "iphone.png"}
    )
    cmd = build_ffmpeg_command(
        _S(),
        video_path="C:/tmp/in.mp4",
        subtitle_path="C:/tmp/in.srt",
        subtitle_encoding="utf-8",
        events=[event],
        output_path="C:/tmp/out.mp4",
        output_format="MP4",
        resolution="1080P",
        video_bitrate_kbps=1500,
    )
    cmd_str = " ".join(cmd)
    # cover 裁切 + pad 到屏幕位置 + 边框 overlay。
    assert "force_original_aspect_ratio=increase" in cmd_str
    assert "crop=" in cmd_str
    assert "pad=" in cmd_str and "color=black@0" in cmd_str
    assert "overlay=0:0:shortest=1" in cmd_str
    # 视频素材是 短视频(plain -i)，边框 PNG 注册为 1 个 -loop 1 -i。
    assert cmd_str.count("-loop 1 -i") == 1


def test_build_ffmpeg_command_phone_frame_solid_uses_cut(tmp_path, monkeypatch):
    """纯色屏幕边框：注册的 -i 应指向自动抠洞的 .cut.png。"""
    from PIL import Image

    def _probe(_settings, _path):
        return VideoProbe(width=1080, height=1920, duration=60.0, has_audio=False)

    monkeypatch.setattr("backend.app.services.video_service.probe_video", _probe)

    frames_dir = tmp_path / "uploads" / "phone_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame = frames_dir / "solid.png"
    im = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
    px = im.load()
    for y in range(8, 392):
        for x in range(8, 192):
            px[x, y] = (20, 20, 20, 255)  # 边框
    for y in range(22, 378):
        for x in range(22, 178):
            px[x, y] = (255, 255, 255, 255)  # 纯白不透明屏幕
    im.save(frame)

    class _S:
        ffmpeg_bin = "ffmpeg"
        ffprobe_bin = "ffprobe"
        data_dir = tmp_path

    event = _event(None, material_type="短视频")
    event = MatchEvent(
        **{**event.__dict__, "corner_style": "手机边框", "phone_frame_file": "solid.png"}
    )
    cmd = build_ffmpeg_command(
        _S(),
        video_path="C:/tmp/in.mp4",
        subtitle_path="C:/tmp/in.srt",
        subtitle_encoding="utf-8",
        events=[event],
        output_path="C:/tmp/out.mp4",
        output_format="MP4",
        resolution="1080P",
        video_bitrate_kbps=1500,
    )
    # 注册输入里应出现抠洞后的 cut 图。
    assert any(arg.endswith("solid.cut.png") for arg in cmd)
    cmd_str = " ".join(cmd)
    assert "overlay=0:0:shortest=1" in cmd_str
    assert "pad=" in cmd_str


def test_build_ffmpeg_command_phone_frame_image_scrolls(tmp_path, monkeypatch):
    """手机边框 + 图片素材且比屏幕高 → 生成竖向滚动 crop（含时间表达式）。"""
    from PIL import Image

    def _probe(_settings, path):
        # 素材是超高长图；源视频正常竖屏。
        if "mat" in str(path):
            return VideoProbe(width=1080, height=6000, duration=60.0, has_audio=False)
        return VideoProbe(width=1080, height=1920, duration=60.0, has_audio=False)

    monkeypatch.setattr("backend.app.services.video_service.probe_video", _probe)

    frames_dir = tmp_path / "uploads" / "phone_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame = frames_dir / "f.png"
    im = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
    px = im.load()
    for y in range(8, 392):
        for x in range(8, 192):
            px[x, y] = (0, 0, 0, 255)
    for y in range(22, 378):
        for x in range(22, 178):
            px[x, y] = (0, 0, 0, 0)
    im.save(frame)

    class _S:
        ffmpeg_bin = "ffmpeg"
        ffprobe_bin = "ffprobe"
        data_dir = tmp_path

    event = _event(None, material_type="图片")  # material_path = C:/tmp/hello.png
    event = MatchEvent(
        **{**event.__dict__, "corner_style": "手机边框", "phone_frame_file": "f.png",
           "material_path": "C:/tmp/mat_hello.png"}
    )
    cmd = build_ffmpeg_command(
        _S(),
        video_path="C:/tmp/in.mp4",
        subtitle_path="C:/tmp/in.srt",
        subtitle_encoding="utf-8",
        events=[event],
        output_path="C:/tmp/out.mp4",
        output_format="MP4",
        resolution="1080P",
        video_bitrate_kbps=1500,
    )
    cmd_str = " ".join(cmd)
    # 滚动：crop 的 y 用时间表达式 min(t/dur,1)。
    assert "min(t/" in cmd_str
    assert "crop=" in cmd_str and "pad=" in cmd_str


def test_build_ffmpeg_command_phone_frame_video_no_scroll(tmp_path, monkeypatch):
    """手机边框 + 视频素材 → 不滚动（cover 裁切）。"""
    from PIL import Image

    def _probe(_settings, path):
        if "mat" in str(path):
            return VideoProbe(width=1080, height=6000, duration=60.0, has_audio=False)
        return VideoProbe(width=1080, height=1920, duration=60.0, has_audio=False)

    monkeypatch.setattr("backend.app.services.video_service.probe_video", _probe)
    frames_dir = tmp_path / "uploads" / "phone_frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frame = frames_dir / "f.png"
    im = Image.new("RGBA", (200, 400), (0, 0, 0, 0))
    px = im.load()
    for y in range(8, 392):
        for x in range(8, 192):
            px[x, y] = (0, 0, 0, 255)
    for y in range(22, 378):
        for x in range(22, 178):
            px[x, y] = (0, 0, 0, 0)
    im.save(frame)

    class _S:
        ffmpeg_bin = "ffmpeg"
        ffprobe_bin = "ffprobe"
        data_dir = tmp_path

    event = _event(None, material_type="短视频")
    event = MatchEvent(
        **{**event.__dict__, "corner_style": "手机边框", "phone_frame_file": "f.png",
           "material_path": "C:/tmp/mat_clip.mp4"}
    )
    cmd = build_ffmpeg_command(
        _S(), video_path="C:/tmp/in.mp4", subtitle_path="C:/tmp/in.srt",
        subtitle_encoding="utf-8", events=[event], output_path="C:/tmp/out.mp4",
        output_format="MP4", resolution="1080P", video_bitrate_kbps=1500,
    )
    cmd_str = " ".join(cmd)
    assert "min(t/" not in cmd_str
    assert "force_original_aspect_ratio=increase" in cmd_str


def test_build_ffmpeg_command_phone_frame_missing_file_falls_back(tmp_path, monkeypatch):
    """边框文件不存在 → 回退普通画中画，不报错、不注册额外输入。"""

    def _probe(_settings, _path):
        return VideoProbe(width=1080, height=1920, duration=60.0, has_audio=False)

    monkeypatch.setattr("backend.app.services.video_service.probe_video", _probe)

    class _S:
        ffmpeg_bin = "ffmpeg"
        ffprobe_bin = "ffprobe"
        data_dir = tmp_path

    event = _event(None)
    event = MatchEvent(
        **{**event.__dict__, "corner_style": "手机边框", "phone_frame_file": "nope.png"}
    )
    cmd = build_ffmpeg_command(
        _S(),
        video_path="C:/tmp/in.mp4",
        subtitle_path="C:/tmp/in.srt",
        subtitle_encoding="utf-8",
        events=[event],
        output_path="C:/tmp/out.mp4",
        output_format="MP4",
        resolution="1080P",
        video_bitrate_kbps=1500,
    )
    cmd_str = " ".join(cmd)
    assert "force_original_aspect_ratio=decrease" in cmd_str  # 退回普通
    assert "overlay=0:0:shortest=1" not in cmd_str


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
