from __future__ import annotations

from pathlib import Path

from backend.app.services.material_service import build_match_events


class _Material:
    def __init__(self, file_name: str, file_path: str):
        self.file_name = file_name
        self.file_path = file_path


class _Query:
    def __init__(self, materials: dict[str, _Material]):
        self._materials = materials
        self._target_name: str | None = None

    def filter(self, expr):
        right = getattr(expr, "right", None)
        value = getattr(right, "value", None)
        if isinstance(value, str):
            self._target_name = value
        return self

    def first(self):
        if self._target_name:
            return self._materials.get(self._target_name)
        if not self._materials:
            return None
        return next(iter(self._materials.values()))


class _DB:
    def __init__(self, materials: dict[str, _Material]):
        self._materials = materials

    def query(self, _model):
        return _Query(self._materials)


def test_build_match_events_keyword_missing_material():
    db = _DB(materials={})
    subtitles = [{"index": 1, "text": "家人们", "start_seconds": 1.0, "end_seconds": 2.0}]
    config = [
        {
            "关键字": "家人们",
            "素材文件名": "hello.png",
            "素材类型": "图片",
            "触发规则": "首次触发",
        }
    ]
    events = build_match_events(db, subtitles, config)
    assert events[0].status == "failed"
    assert events[0].reason in ("素材不存在", "素材文件不存在")


def test_build_match_events_default_for_image(tmp_path):
    image_path = tmp_path / "hello.png"
    image_path.write_bytes(b"png")
    db = _DB(materials={"hello.png": _Material(file_name="hello.png", file_path=Path(image_path).as_posix())})
    subtitles = [{"index": 1, "text": "家人们", "start_seconds": 1.0, "end_seconds": 2.0}]
    config = [{"关键字": "家人们", "素材文件名": "hello.png", "素材类型": "图片"}]
    events = build_match_events(db, subtitles, config)
    assert events[0].position == 1
    assert events[0].size_ratio_percent == 25.0
    assert events[0].end_time == 3.0


def test_build_match_events_video_size_ratio_and_video_params(tmp_path):
    video_path = tmp_path / "clip.mp4"
    video_path.write_bytes(b"mp4")
    db = _DB(materials={"clip.mp4": _Material(file_name="clip.mp4", file_path=Path(video_path).as_posix())})
    subtitles = [{"index": 1, "text": "家人们", "start_seconds": 1.0, "end_seconds": 2.0}]
    config = [
        {
            "关键字": "家人们",
            "素材文件名": "clip.mp4",
            "素材类型": "短视频",
            "提示音": "ding.mp3",
            "视频起始秒(秒)": 2,
            "视频持续秒(秒)": 4,
        },
    ]
    events = build_match_events(db, subtitles, config)
    assert events[0].size_ratio_percent == 70.0
    assert events[0].cue_sound_config == "ding.mp3"
    assert events[0].video_start_seconds == 2.0
    assert events[0].video_duration_seconds == 4.0
