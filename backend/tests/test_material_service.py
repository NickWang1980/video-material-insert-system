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

    def filter(self, *args, **kwargs):
        return self

    def first(self):
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


def test_build_match_events_size_ratio_default_and_explicit(tmp_path):
    material_path = tmp_path / "hello.png"
    material_path.write_bytes(b"png")
    db = _DB(
        materials={
            "hello.png": _Material(
                file_name="hello.png",
                file_path=Path(material_path).as_posix(),
            )
        }
    )
    subtitles = [{"index": 1, "text": "家人们", "start_seconds": 1.0, "end_seconds": 2.0}]
    config = [
        {"关键字": "家人们", "素材文件名": "hello.png", "素材类型": "图片"},
        {"关键字": "家人们", "素材文件名": "hello.png", "素材类型": "图片", "素材宽度占比(%)": 35, "提示音": "ding.mp3"},
    ]
    events = build_match_events(db, subtitles, config)
    assert events[0].size_ratio_percent == 25.0
    assert events[0].cue_sound_config == "随机"
    assert events[1].size_ratio_percent == 35.0
    assert events[1].cue_sound_config == "ding.mp3"
