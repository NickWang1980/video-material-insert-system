from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.app.models.config_template import ConfigTemplate
from backend.app.services.material_service import MatchEvent
from backend.app.services.task_service import (
    TemplateKeywordConflictError,
    TemplateNotFoundError,
    attach_random_sound_effects,
    detect_keyword_collision_warnings,
    merge_templates_and_validate_keywords,
)


class _Material:
    def __init__(self, file_name: str, file_type: str, file_path: str):
        self.file_name = file_name
        self.file_type = file_type
        self.file_path = file_path


class _Template:
    def __init__(self, template_id: int, template_name: str, config_content: list[dict]):
        self.id = template_id
        self.template_name = template_name
        self.config_content = json.dumps(config_content, ensure_ascii=False)


class _Query:
    def __init__(self, materials=None, templates=None):
        self._materials = materials or []
        self._templates = templates or []

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._materials or self._templates


class _DB:
    def __init__(self, materials=None, templates=None):
        self._materials = materials or []
        self._templates = templates or []

    def query(self, model):
        if model is ConfigTemplate:
            return _Query(templates=self._templates)
        return _Query(materials=self._materials)


def _event(material_type: str, cue_sound_config: str = "随机") -> MatchEvent:
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
        size_ratio_percent=25.0,
        start_time=1.0,
        end_time=3.0,
        status="success",
        reason=None,
        material_path="C:/tmp/hello.png",
        cue_sound_config=cue_sound_config,
        sound_effect_status="未播放",
    )


def test_attach_random_sound_effects_pool_empty():
    db = _DB(materials=[])
    events = attach_random_sound_effects(db, [_event("图片"), _event("短视频")])
    assert events[0].sound_effect_status == "未播放"
    assert events[0].sound_effect_reason == "音效池为空"
    assert events[1].sound_effect_path is None


def test_attach_random_sound_effects_pick_audio(tmp_path):
    audio_path = tmp_path / "ding.mp3"
    audio_path.write_bytes(b"audio")
    db = _DB(
        materials=[
            _Material("ding.mp3", "audio", Path(audio_path).as_posix()),
            _Material("voice.mp3", "audio", "C:/not-exist/voice.mp3"),
        ]
    )
    events = attach_random_sound_effects(db, [_event("短视频")])
    assert events[0].sound_effect_status == "已添加"
    assert events[0].sound_effect_file_name == "ding.mp3"
    assert events[0].sound_effect_path == Path(audio_path).as_posix()


def test_attach_random_sound_effects_specific_pick(tmp_path):
    audio_path = tmp_path / "alert.mp3"
    audio_path.write_bytes(b"audio")
    db = _DB(materials=[_Material("alert.mp3", "audio", Path(audio_path).as_posix())])
    events = attach_random_sound_effects(db, [_event("图片", cue_sound_config="alert.mp3")])
    assert events[0].sound_effect_status == "已添加"
    assert events[0].sound_effect_file_name == "alert.mp3"
    assert events[0].sound_effect_reason is None


def test_attach_random_sound_effects_specific_missing_fallback(tmp_path):
    audio_path = tmp_path / "fallback.mp3"
    audio_path.write_bytes(b"audio")
    db = _DB(materials=[_Material("fallback.mp3", "audio", Path(audio_path).as_posix())])
    events = attach_random_sound_effects(db, [_event("GIF", cue_sound_config="missing.mp3")])
    assert events[0].sound_effect_status == "已添加"
    assert events[0].sound_effect_file_name == "fallback.mp3"
    assert "回退随机" in (events[0].sound_effect_reason or "")


def test_merge_templates_without_conflict():
    db = _DB(
        templates=[
            _Template(1, "模板A", [{"关键字": "抖音", "素材文件名": "a.png"}]),
            _Template(2, "模板B", [{"关键字": "福利", "素材文件名": "b.png"}]),
        ]
    )
    merged, source_templates = merge_templates_and_validate_keywords(db, [1, 2])
    assert len(merged) == 2
    assert [item["id"] for item in source_templates] == [1, 2]
    assert [item["name"] for item in source_templates] == ["模板A", "模板B"]


def test_merge_templates_with_conflict():
    db = _DB(
        templates=[
            _Template(1, "模板A", [{"关键字": "抖音", "素材文件名": "a.png"}]),
            _Template(2, "模板B", [{"关键字": "抖音", "素材文件名": "b.png"}]),
        ]
    )
    with pytest.raises(TemplateKeywordConflictError) as exc_info:
        merge_templates_and_validate_keywords(db, [1, 2])
    assert "抖音" in exc_info.value.conflicts
    assert exc_info.value.conflicts["抖音"] == ["模板A", "模板B"]


def test_merge_templates_missing_template():
    db = _DB(templates=[_Template(1, "模板A", [{"关键字": "抖音"}])])
    with pytest.raises(TemplateNotFoundError) as exc_info:
        merge_templates_and_validate_keywords(db, [1, 3])
    assert exc_info.value.missing_template_ids == [3]


def test_detect_keyword_collision_warnings_longest_keyword_wins():
    subtitles = [
        {
            "index": 1,
            "start": "00:00:01,000",
            "end": "00:00:03,000",
            "text": "快乐老家欢迎你",
        }
    ]
    config = [
        {"关键字": "快乐"},
        {"关键字": "快乐老家"},
        {"关键字": "老家"},
    ]
    warnings = detect_keyword_collision_warnings(subtitles, config)
    assert len(warnings) == 1
    assert warnings[0].winner_keyword == "快乐老家"
    assert set(warnings[0].suppressed_keywords) == {"快乐", "老家"}


def test_detect_keyword_collision_warnings_same_length_use_rule_order():
    subtitles = [
        {
            "index": 2,
            "start": "00:00:05,000",
            "end": "00:00:06,000",
            "text": "抖音快手都在这里",
        }
    ]
    config = [
        {"关键字": "抖音"},
        {"关键字": "快手"},
    ]
    warnings = detect_keyword_collision_warnings(subtitles, config)
    assert len(warnings) == 1
    assert warnings[0].winner_keyword == "抖音"
    assert warnings[0].suppressed_keywords == ["快手"]
