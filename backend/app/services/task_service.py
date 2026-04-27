from __future__ import annotations

import json
import os
import random
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config import Settings
from ..models.config_template import ConfigTemplate
from ..models.material import Material
from ..models.settings import SettingsRow
from ..models.source_video_entry import SourceVideoEntry
from ..models.task import Task
from ..models.task_snapshot import TaskConfigSnapshot
from ..utils.file_utils import normalize_storage_path
from ..utils.logger import get_logger
from .material_service import build_match_events
from .report_service import write_report_xlsx
from .subtitle_service import parse_srt
from .video_service import build_ffmpeg_command, probe_video, run_ffmpeg


logger = get_logger()
_concurrency = 2
_semaphore = threading.BoundedSemaphore(_concurrency)
_task_control_lock = threading.Lock()
_running_ffmpeg_processes: dict[int, subprocess.Popen] = {}
_stop_requested_task_ids: set[int] = set()


@dataclass(frozen=True)
class KeywordCollisionWarning:
    subtitle_index: int
    start: str
    end: str
    text: str
    matched_keywords: list[str]
    winner_keyword: str
    suppressed_keywords: list[str]


class TemplateNotFoundError(Exception):
    def __init__(self, missing_template_ids: list[int]):
        self.missing_template_ids = missing_template_ids
        super().__init__(f"Templates not found: {missing_template_ids}")


class TemplateKeywordConflictError(Exception):
    def __init__(self, conflicts: dict[str, list[str]]):
        self.conflicts = conflicts
        super().__init__("Duplicate keywords found across selected templates")


class SourceVideoEntryNotFoundError(Exception):
    def __init__(self, source_entry_id: int):
        self.source_entry_id = source_entry_id
        super().__init__(f"Source video entry not found: {source_entry_id}")


class AsrSubtitleUnavailableError(Exception):
    def __init__(self, source_entry_id: int, reason: str):
        self.source_entry_id = source_entry_id
        self.reason = reason
        super().__init__(f"ASR subtitle unavailable for source entry {source_entry_id}: {reason}")


def _timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d%H%M%S")


def merge_templates_and_validate_keywords(
    db: Session, config_ids: list[int]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not config_ids:
        raise ValueError("至少选择一个模板")
    if len(set(config_ids)) != len(config_ids):
        raise ValueError("模板不能重复选择")

    templates = db.query(ConfigTemplate).filter(ConfigTemplate.id.in_(config_ids)).all()
    templates_by_id = {template.id: template for template in templates}
    missing_template_ids = [
        template_id for template_id in config_ids if template_id not in templates_by_id
    ]
    if missing_template_ids:
        raise TemplateNotFoundError(missing_template_ids)

    ordered_templates = [templates_by_id[template_id] for template_id in config_ids]
    source_templates = [
        {"id": template.id, "name": template.template_name}
        for template in ordered_templates
    ]

    merged_config: list[dict[str, Any]] = []
    keyword_to_templates: dict[str, list[str]] = {}
    conflicts: dict[str, list[str]] = {}

    for template in ordered_templates:
        config_content = json.loads(template.config_content or "[]")
        if not isinstance(config_content, list):
            raise ValueError(f"模板配置格式错误: {template.template_name}")

        for rule in config_content:
            if not isinstance(rule, dict):
                continue

            keyword_value = rule.get("关键词", rule.get("关键字"))
            keyword = keyword_value if isinstance(keyword_value, str) else str(keyword_value or "")

            exists = keyword_to_templates.get(keyword)
            if exists:
                exists.append(template.template_name)
                conflicts[keyword] = exists
            else:
                keyword_to_templates[keyword] = [template.template_name]

            merged_config.append(rule)

    if conflicts:
        raise TemplateKeywordConflictError(conflicts)

    return merged_config, source_templates


def _normalize_subtitle_source(subtitle_source: str | None) -> str:
    value = (subtitle_source or "uploaded").strip().lower()
    if value not in {"uploaded", "asr"}:
        raise ValueError("subtitle_source 仅支持 uploaded 或 asr")
    return value


def resolve_source_subtitle_path(
    *,
    source_entry: SourceVideoEntry,
    subtitle_source: str,
) -> str:
    subtitle_source_normalized = _normalize_subtitle_source(subtitle_source)
    selected_subtitle_path = source_entry.subtitle_path

    if subtitle_source_normalized == "uploaded":
        if not source_entry.subtitle_path:
            raise ValueError("当前源视频条目缺少上传SRT路径")
        if not os.path.exists(source_entry.subtitle_path):
            raise ValueError("当前源视频条目的上传SRT文件不存在")
        return source_entry.subtitle_path

    if source_entry.asr_srt_path and os.path.exists(source_entry.asr_srt_path):
        return source_entry.asr_srt_path

    asr_status = source_entry.asr_status or "pending"
    if asr_status != "completed":
        raise AsrSubtitleUnavailableError(
            source_entry_id=source_entry.id,
            reason=f"当前 ASR 状态为 {asr_status}",
        )
    if not source_entry.asr_srt_path:
        raise AsrSubtitleUnavailableError(
            source_entry_id=source_entry.id,
            reason="ASR 字幕路径不存在",
        )
    raise AsrSubtitleUnavailableError(
        source_entry_id=source_entry.id,
        reason="ASR 字幕文件不存在",
    )


def detect_keyword_collision_warnings(
    subtitles: list[dict[str, Any]],
    merged_config: list[dict[str, Any]],
) -> list[KeywordCollisionWarning]:
    indexed_rules: list[tuple[int, str]] = []
    for index, rule in enumerate(merged_config):
        if not isinstance(rule, dict):
            continue
        keyword_raw = rule.get("关键词", rule.get("关键字"))
        keyword = keyword_raw if isinstance(keyword_raw, str) else str(keyword_raw or "")
        keyword = keyword.strip()
        if keyword:
            indexed_rules.append((index, keyword))

    warnings: list[KeywordCollisionWarning] = []
    for subtitle in subtitles:
        text = str(subtitle.get("text", "") or "")
        matched_rules: list[tuple[int, str]] = [
            (rule_index, keyword)
            for rule_index, keyword in indexed_rules
            if keyword in text
        ]
        if len(matched_rules) <= 1:
            continue

        sorted_candidates = sorted(
            matched_rules,
            key=lambda item: (-len(item[1]), item[0]),
        )
        winner_keyword = sorted_candidates[0][1]
        matched_keywords = [keyword for _, keyword in matched_rules]
        suppressed_keywords = [keyword for _, keyword in sorted_candidates[1:]]
        warnings.append(
            KeywordCollisionWarning(
                subtitle_index=int(subtitle.get("index", 0)),
                start=str(subtitle.get("start", "")),
                end=str(subtitle.get("end", "")),
                text=text,
                matched_keywords=matched_keywords,
                winner_keyword=winner_keyword,
                suppressed_keywords=suppressed_keywords,
            )
        )
    return warnings


def build_keyword_collision_warnings_for_task(
    *,
    db: Session,
    source_entry_id: int,
    config_ids: list[int],
    subtitle_source: str,
) -> list[KeywordCollisionWarning]:
    merged_snapshot, _ = merge_templates_and_validate_keywords(db, config_ids)
    source_entry = (
        db.query(SourceVideoEntry).filter(SourceVideoEntry.id == source_entry_id).first()
    )
    if not source_entry:
        raise SourceVideoEntryNotFoundError(source_entry_id)

    subtitle_path = resolve_source_subtitle_path(
        source_entry=source_entry,
        subtitle_source=subtitle_source,
    )
    settings_row = ensure_settings_row(db)
    encoding = "utf-8" if _normalize_subtitle_source(subtitle_source) == "asr" else settings_row.subtitle_encoding
    subtitles = parse_srt(
        subtitle_path,
        encoding=encoding,
        time_offset_seconds=float(settings_row.subtitle_time_offset_seconds),
    )
    return detect_keyword_collision_warnings(subtitles, merged_snapshot)


def create_task(
    *,
    settings: Settings,
    db: Session,
    task_name: str,
    source_entry_id: int,
    config_ids: list[int],
    subtitle_source: str = "uploaded",
    add_subtitle_to_video: bool = False,
    collision_priority: dict[int, list[str]] | None = None,
) -> tuple[Task, list[KeywordCollisionWarning]]:
    merged_snapshot, source_templates = merge_templates_and_validate_keywords(db, config_ids)
    primary_config_id = source_templates[0]["id"] if source_templates else None

    source_entry = (
        db.query(SourceVideoEntry).filter(SourceVideoEntry.id == source_entry_id).first()
    )
    if not source_entry:
        raise SourceVideoEntryNotFoundError(source_entry_id)

    subtitle_source_normalized = (subtitle_source or "uploaded").strip().lower()
    if subtitle_source_normalized not in {"uploaded", "asr"}:
        raise ValueError("subtitle_source 仅支持 uploaded 或 asr")

    selected_subtitle_path = source_entry.subtitle_path
    if subtitle_source_normalized == "uploaded":
        if not source_entry.subtitle_path:
            raise ValueError("当前源视频条目缺少上传SRT路径")
        if not os.path.exists(source_entry.subtitle_path):
            raise ValueError("当前源视频条目的上传SRT文件不存在")
    if subtitle_source_normalized == "asr":
        if source_entry.asr_srt_path and os.path.exists(source_entry.asr_srt_path):
            selected_subtitle_path = source_entry.asr_srt_path
        else:
            asr_status = source_entry.asr_status or "pending"
            if asr_status != "completed":
                raise AsrSubtitleUnavailableError(
                    source_entry_id=source_entry.id,
                    reason=f"当前 ASR 状态为 {asr_status}",
                )
            if not source_entry.asr_srt_path:
                raise AsrSubtitleUnavailableError(
                    source_entry_id=source_entry.id,
                    reason="ASR 字幕路径不存在",
                )
            raise AsrSubtitleUnavailableError(
                source_entry_id=source_entry.id,
                reason="ASR 字幕文件不存在",
            )

    settings_row = ensure_settings_row(db)
    subtitle_encoding = (
        "utf-8"
        if subtitle_source_normalized == "asr"
        else settings_row.subtitle_encoding
    )
    subtitles = parse_srt(
        selected_subtitle_path,
        encoding=subtitle_encoding,
        time_offset_seconds=float(settings_row.subtitle_time_offset_seconds),
    )
    keyword_collision_warnings = detect_keyword_collision_warnings(subtitles, merged_snapshot)

    task = Task(
        task_name=task_name,
        video_path=source_entry.video_path,
        subtitle_path=selected_subtitle_path,
        source_entry_id=source_entry.id,
        subtitle_source=subtitle_source_normalized,
        add_subtitle_to_video=bool(add_subtitle_to_video),
        config_id=primary_config_id,
        status="pending",
        progress=0,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    snapshot = TaskConfigSnapshot(
        task_id=task.id,
        config_json=json.dumps(merged_snapshot, ensure_ascii=False),
        source_templates_json=json.dumps(source_templates, ensure_ascii=False),
        keyword_collision_warnings_json=json.dumps(
            [asdict(item) for item in keyword_collision_warnings],
            ensure_ascii=False,
        ),
        collision_priority_json=(
            json.dumps(collision_priority, ensure_ascii=False) if collision_priority else None
        ),
    )
    db.add(snapshot)
    db.commit()

    start_task_processing(settings, task.id)
    return task, keyword_collision_warnings


def start_task_processing(settings: Settings, task_id: int) -> None:
    thread = threading.Thread(target=process_task, args=(settings, task_id), daemon=True)
    thread.start()


def ensure_settings_row(db: Session) -> SettingsRow:
    row = db.query(SettingsRow).filter(SettingsRow.id == 1).first()
    if row is None:
        row = SettingsRow(id=1)
        db.add(row)
        db.commit()
        db.refresh(row)
    elif not row.asr_model or row.asr_model not in {"small", "medium"}:
        row.asr_model = "small"
        db.commit()
        db.refresh(row)
    return row


def load_or_create_task_snapshot(db: Session, task: Task) -> list[dict]:
    snap = (
        db.query(TaskConfigSnapshot)
        .filter(TaskConfigSnapshot.task_id == task.id)
        .order_by(TaskConfigSnapshot.id.desc())
        .first()
    )
    if snap:
        return json.loads(snap.config_json)

    if task.config_id:
        template = db.query(ConfigTemplate).filter(ConfigTemplate.id == task.config_id).first()
        if template:
            config = json.loads(template.config_content)
            snap = TaskConfigSnapshot(
                task_id=task.id,
                config_json=json.dumps(config, ensure_ascii=False),
                source_templates_json=json.dumps(
                    [{"id": template.id, "name": template.template_name}],
                    ensure_ascii=False,
                ),
                keyword_collision_warnings_json="[]",
                collision_priority_json=None,
            )
            db.add(snap)
            db.commit()
            return config

    return []


def get_task_source_templates(db: Session, task_id: int) -> list[dict[str, Any]]:
    snap = (
        db.query(TaskConfigSnapshot)
        .filter(TaskConfigSnapshot.task_id == task_id)
        .order_by(TaskConfigSnapshot.id.desc())
        .first()
    )
    if not snap or not snap.source_templates_json:
        return []
    try:
        source_templates = json.loads(snap.source_templates_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(source_templates, list):
        return []

    normalized: list[dict[str, Any]] = []
    for item in source_templates:
        if not isinstance(item, dict):
            continue
        if "id" not in item or "name" not in item:
            continue
        normalized.append({"id": item["id"], "name": item["name"]})
    return normalized


def get_task_keyword_collision_warnings(db: Session, task_id: int) -> list[dict[str, Any]]:
    snap = (
        db.query(TaskConfigSnapshot)
        .filter(TaskConfigSnapshot.task_id == task_id)
        .order_by(TaskConfigSnapshot.id.desc())
        .first()
    )
    if not snap or not snap.keyword_collision_warnings_json:
        return []
    try:
        warnings = json.loads(snap.keyword_collision_warnings_json)
    except json.JSONDecodeError:
        return []
    if not isinstance(warnings, list):
        return []
    normalized: list[dict[str, Any]] = []
    for item in warnings:
        if not isinstance(item, dict):
            continue
        if "winner_keyword" not in item:
            continue
        matched_keywords = item.get("matched_keywords", [])
        if not isinstance(matched_keywords, list):
            matched_keywords = []
        suppressed_keywords = item.get("suppressed_keywords", [])
        if not isinstance(suppressed_keywords, list):
            suppressed_keywords = []
        normalized.append(
            {
                "subtitle_index": int(item.get("subtitle_index", 0)),
                "start": str(item.get("start", "")),
                "end": str(item.get("end", "")),
                "text": str(item.get("text", "")),
                "matched_keywords": [str(keyword) for keyword in matched_keywords],
                "winner_keyword": str(item.get("winner_keyword", "")),
                "suppressed_keywords": [str(keyword) for keyword in suppressed_keywords],
            }
        )
    return normalized


def get_task_collision_priority(db: Session, task_id: int) -> dict[int, list[str]]:
    snap = (
        db.query(TaskConfigSnapshot)
        .filter(TaskConfigSnapshot.task_id == task_id)
        .order_by(TaskConfigSnapshot.id.desc())
        .first()
    )
    if not snap or not snap.collision_priority_json:
        return {}
    try:
        payload = json.loads(snap.collision_priority_json)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    normalized: dict[int, list[str]] = {}
    for key, value in payload.items():
        try:
            subtitle_index = int(key)
        except (TypeError, ValueError):
            continue
        if not isinstance(value, list):
            continue
        keywords = [str(item).strip() for item in value if str(item).strip()]
        if keywords:
            normalized[subtitle_index] = keywords
    return normalized


def get_task_source_video(db: Session, task: Task) -> dict[str, Any] | None:
    if not task.source_entry_id:
        return None
    entry = (
        db.query(SourceVideoEntry).filter(SourceVideoEntry.id == task.source_entry_id).first()
    )
    if not entry:
        return None
    return {"id": entry.id, "name": entry.name}


def resume_all_tasks(settings: Settings, include_failed: bool = True) -> int:
    from ..models.database import SessionLocal

    db = SessionLocal()
    try:
        statuses = ["pending", "processing"]
        if include_failed:
            statuses.append("failed")
        tasks = db.query(Task).filter(Task.status.in_(statuses)).all()
        for task in tasks:
            task.status = "pending"
            task.progress = 0
            task.completed_at = None
        db.commit()

        for task in tasks:
            start_task_processing(settings, task.id)
        return len(tasks)
    finally:
        db.close()


def request_stop_task(task_id: int) -> str:
    with _task_control_lock:
        _stop_requested_task_ids.add(task_id)
        process = _running_ffmpeg_processes.get(task_id)

    if process and process.poll() is None:
        try:
            process.terminate()
        except Exception:
            pass
        return "stopping"
    return "requested"


def _is_stop_requested(task_id: int) -> bool:
    with _task_control_lock:
        return task_id in _stop_requested_task_ids


def _clear_stop_requested(task_id: int) -> None:
    with _task_control_lock:
        _stop_requested_task_ids.discard(task_id)


def _register_ffmpeg_process(task_id: int, process: subprocess.Popen) -> None:
    with _task_control_lock:
        _running_ffmpeg_processes[task_id] = process


def _unregister_ffmpeg_process(task_id: int) -> None:
    with _task_control_lock:
        _running_ffmpeg_processes.pop(task_id, None)


def _mark_task_stopped(db: Session, task: Task) -> None:
    task.status = "stopped"
    task.completed_at = datetime.utcnow()
    db.commit()


def attach_random_sound_effects(db: Session, events):
    audio_materials = db.query(Material).filter(Material.file_type == "audio").all()
    available_audios = sorted(
        [material for material in audio_materials if os.path.exists(material.file_path)],
        key=lambda item: item.file_name.lower(),
    )
    available_by_name = {material.file_name: material for material in available_audios}
    pool_empty = len(available_audios) == 0

    out = []
    for event in events:
        if event.status != "success":
            out.append(event)
            continue

        cue_sound = (event.cue_sound_config or "随机").strip() or "随机"

        if cue_sound != "随机":
            selected = available_by_name.get(cue_sound)
            if selected:
                out.append(
                    replace(
                        event,
                        sound_effect_file_name=selected.file_name,
                        sound_effect_status="已添加",
                        sound_effect_reason=None,
                        sound_effect_path=selected.file_path,
                    )
                )
                continue
            if not pool_empty:
                fallback = random.choice(available_audios)
                out.append(
                    replace(
                        event,
                        sound_effect_file_name=fallback.file_name,
                        sound_effect_status="已添加",
                        sound_effect_reason=f"指定提示音不存在，已回退随机: {cue_sound}",
                        sound_effect_path=fallback.file_path,
                    )
                )
                continue
            out.append(
                replace(
                    event,
                    sound_effect_file_name=None,
                    sound_effect_status="未播放",
                    sound_effect_reason=f"指定提示音不存在且音效池为空: {cue_sound}",
                    sound_effect_path=None,
                )
            )
            continue

        if pool_empty:
            out.append(
                replace(
                    event,
                    sound_effect_file_name=None,
                    sound_effect_status="未播放",
                    sound_effect_reason="音效池为空",
                    sound_effect_path=None,
                )
            )
            continue

        selected = random.choice(available_audios)
        out.append(
            replace(
                event,
                sound_effect_file_name=selected.file_name,
                sound_effect_status="已添加",
                sound_effect_reason=None,
                sound_effect_path=selected.file_path,
            )
        )
    return out


def process_task(settings: Settings, task_id: int) -> None:
    from ..models.database import SessionLocal

    with _semaphore:
        db = SessionLocal()
        log_path = normalize_storage_path(
            settings.data_dir / "outputs" / "logs" / f"task_{task_id}.txt"
        )
        try:
            task = db.query(Task).filter(Task.id == task_id).first()
            if not task:
                _clear_stop_requested(task_id)
                return

            if _is_stop_requested(task_id):
                _mark_task_stopped(db, task)
                _clear_stop_requested(task_id)
                return

            task.status = "processing"
            task.progress = 5
            task.completed_at = None
            task.output_path = None
            db.commit()

            if _is_stop_requested(task_id):
                _mark_task_stopped(db, task)
                _clear_stop_requested(task_id)
                return

            settings_row = ensure_settings_row(db)
            config_snapshot = load_or_create_task_snapshot(db, task)

            task.progress = 15
            db.commit()
            if _is_stop_requested(task_id):
                _mark_task_stopped(db, task)
                _clear_stop_requested(task_id)
                return

            subtitle_encoding = (
                "utf-8"
                if (task.subtitle_source or "uploaded").strip().lower() == "asr"
                else settings_row.subtitle_encoding
            )
            subtitles = parse_srt(
                task.subtitle_path,
                encoding=subtitle_encoding,
                time_offset_seconds=float(settings_row.subtitle_time_offset_seconds),
            )

            task.progress = 35
            db.commit()
            if _is_stop_requested(task_id):
                _mark_task_stopped(db, task)
                _clear_stop_requested(task_id)
                return

            words_index = None
            if (task.subtitle_source or "").strip().lower() == "asr":
                words_json_path = Path(task.subtitle_path).with_suffix(".words.json")
                if words_json_path.exists():
                    try:
                        payload = json.loads(words_json_path.read_text(encoding="utf-8"))
                        words_index = payload.get("words") if isinstance(payload, dict) else None
                        time_offset = float(settings_row.subtitle_time_offset_seconds)
                        if words_index and time_offset:
                            words_index = [
                                {**w, "start": w["start"] + time_offset, "end": w["end"] + time_offset}
                                for w in words_index
                            ]
                    except Exception:
                        words_index = None

            collision_priority_by_subtitle = get_task_collision_priority(db, task.id)
            events = build_match_events(
                db,
                subtitles,
                config_snapshot,
                collision_priority_by_subtitle=collision_priority_by_subtitle,
                words_index=words_index,
            )
            events = attach_random_sound_effects(db, events)

            report_path = normalize_storage_path(
                settings.data_dir
                / "outputs"
                / "reports"
                / f"report_{task_id}_{_timestamp()}.xlsx"
            )
            write_report_xlsx(report_path, events)
            task.report_path = report_path

            task.progress = 55
            db.commit()
            if _is_stop_requested(task_id):
                _mark_task_stopped(db, task)
                _clear_stop_requested(task_id)
                return

            output_ext = "mp4" if settings_row.output_format.upper() != "MOV" else "mov"
            output_path = normalize_storage_path(
                settings.data_dir
                / "outputs"
                / "videos"
                / f"output_{task_id}_{_timestamp()}.{output_ext}"
            )

            ffmpeg_cmd = build_ffmpeg_command(
                settings,
                video_path=task.video_path,
                subtitle_path=task.subtitle_path,
                subtitle_encoding=settings_row.subtitle_encoding,
                events=events,
                output_path=output_path,
                output_format=settings_row.output_format,
                resolution=settings_row.resolution,
                video_bitrate_kbps=int(settings_row.video_bitrate_kbps),
                add_subtitle_to_video=bool(task.add_subtitle_to_video),
            )

            task.progress = 75
            db.commit()
            if _is_stop_requested(task_id):
                _mark_task_stopped(db, task)
                _clear_stop_requested(task_id)
                return

            estimated_video_duration = 60.0
            try:
                estimated_video_duration = max(
                    10.0, float(probe_video(settings, task.video_path).duration)
                )
            except Exception:
                estimated_video_duration = 60.0
            ffmpeg_started_at = time.monotonic()
            max_run_seconds = max(300.0, estimated_video_duration * 8.0)

            def _ffmpeg_tick(_elapsed: float) -> None:
                if task.status != "processing":
                    return
                elapsed = max(0.0, time.monotonic() - ffmpeg_started_at)
                ratio = min(1.0, elapsed / max(estimated_video_duration * 1.4, 20.0))
                expected_progress = 75 + int(ratio * 23)
                expected_progress = min(98, max(75, expected_progress))
                if expected_progress > int(task.progress or 0):
                    task.progress = expected_progress
                    db.commit()

            run_ffmpeg(
                ffmpeg_cmd,
                log_path=log_path,
                on_started=lambda process: _register_ffmpeg_process(task_id, process),
                should_stop=lambda: _is_stop_requested(task_id),
                on_tick=_ffmpeg_tick,
                max_run_seconds=max_run_seconds,
            )
            _unregister_ffmpeg_process(task_id)

            if _is_stop_requested(task_id):
                _mark_task_stopped(db, task)
                _clear_stop_requested(task_id)
                return

            task.output_path = output_path
            task.status = "completed"
            task.progress = 100
            task.completed_at = datetime.utcnow()
            db.commit()
            _clear_stop_requested(task_id)

        except Exception as exc:
            _unregister_ffmpeg_process(task_id)
            task = db.query(Task).filter(Task.id == task_id).first()
            if task and _is_stop_requested(task_id):
                _mark_task_stopped(db, task)
                _clear_stop_requested(task_id)
                try:
                    Path(log_path).parent.mkdir(parents=True, exist_ok=True)
                    with Path(log_path).open("a", encoding="utf-8") as file_handle:
                        file_handle.write(f"\nSTOPPED: {exc}\n")
                except Exception:
                    pass
                return

            logger.exception("Task failed: {}", exc)
            if task:
                task.status = "failed"
                task.progress = 0
                task.completed_at = datetime.utcnow()
                db.commit()
            try:
                Path(log_path).parent.mkdir(parents=True, exist_ok=True)
                with Path(log_path).open("a", encoding="utf-8") as file_handle:
                    file_handle.write(f"\nERROR: {exc}\n")
            except Exception:
                pass
            _clear_stop_requested(task_id)
        finally:
            _unregister_ffmpeg_process(task_id)
            db.close()
