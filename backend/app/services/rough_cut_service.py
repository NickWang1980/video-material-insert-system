from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy.orm import Session

from ..config import Settings
from ..models.rough_cut_project import RoughCutProject
from ..models.settings import SettingsRow
from ..models.database import SessionLocal
from ..schemas.rough_cut import RenderSettings
from .asr_service import transcribe_audio_segments, write_segments_to_srt
from .subtitle_service import parse_srt
from .video_service import probe_video


ROUGH_CUT_STATUS_IDLE = "idle"
ROUGH_CUT_STATUS_PROCESSING = "processing"
ROUGH_CUT_STATUS_READY = "ready"
ROUGH_CUT_STATUS_ERROR = "error"
ROUGH_CUT_MATCH_THRESHOLD = 80.0
PROJECT_SETTINGS_SCRIPT_FILE_NAME_KEY = "scriptFileName"
ROLE_COLOR_PALETTE = [
    "#3B82F6",
    "#8B5CF6",
    "#F59E0B",
    "#10B981",
    "#EF4444",
    "#06B6D4",
    "#6366F1",
    "#F97316",
]
_UNSET = object()

_processing_projects_lock = threading.Lock()
_processing_projects: set[int] = set()
_rough_cut_control_lock = threading.Lock()
_running_rough_cut_processes: dict[int, subprocess.Popen] = {}
_stop_requested_rough_cut_projects: set[int] = set()
_rough_cut_asr_lock = threading.Lock()
_running_rough_cut_asset_jobs: set[str] = set()
_auto_preview_lock = threading.Lock()
_auto_preview_projects: set[int] = set()
_auto_preview_signatures: dict[int, str] = {}

_zh_opencc_converter = None
_PUNCTUATION_CATEGORIES = {"Pc", "Pd", "Pe", "Pf", "Pi", "Po", "Ps", "Sm", "Sc", "Sk", "So"}
_MOJIBAKE_CHARS = set("ÂÃÅÆÇÐÑÕØÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿŒœŠšŽž€™…†‡ˆ‰‹›‘’“”•–—")


class RoughCutStopRequested(RuntimeError):
    pass


def default_roles() -> list[dict]:
    return [
        {"id": "A", "name": "角色A", "color": "#3B82F6", "isPrimary": True},
        {"id": "B", "name": "角色B", "color": "#8B5CF6", "isPrimary": False},
        {"id": "C", "name": "角色C", "color": "#F59E0B", "isPrimary": False},
    ]


def default_render_settings() -> dict:
    return RenderSettings().model_dump()


def _load_project_settings_payload(project: RoughCutProject | None) -> dict:
    if project is None:
        return {}
    payload = _safe_json_loads(getattr(project, "settings_json", None), {})
    return payload if isinstance(payload, dict) else {}


def _get_project_script_file_name(project: RoughCutProject | None) -> str | None:
    payload = _load_project_settings_payload(project)
    value = str(payload.get(PROJECT_SETTINGS_SCRIPT_FILE_NAME_KEY) or "").strip()
    return value or None


def _persist_project_settings(
    project: RoughCutProject,
    *,
    settings_payload: dict | None = None,
    script_file_name=_UNSET,
) -> dict:
    current_payload = _load_project_settings_payload(project)
    normalized_settings = RenderSettings(**(settings_payload or current_payload or {})).model_dump()
    if script_file_name is _UNSET:
        effective_script_file_name = str(
            current_payload.get(PROJECT_SETTINGS_SCRIPT_FILE_NAME_KEY) or ""
        ).strip()
    else:
        effective_script_file_name = str(script_file_name or "").strip()
    if effective_script_file_name:
        normalized_settings[PROJECT_SETTINGS_SCRIPT_FILE_NAME_KEY] = effective_script_file_name
    project.settings_json = _safe_json_dumps(normalized_settings)
    return normalized_settings


def _safe_json_loads(value: str | None, default):
    if not value:
        return default
    try:
        parsed = json.loads(value)
        return parsed if parsed is not None else default
    except Exception:
        return default


def _safe_json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _count_cjk_characters(text: str) -> int:
    return sum(1 for char in text if "\u4e00" <= char <= "\u9fff")


def _count_suspicious_characters(text: str) -> int:
    return sum(1 for char in text if char in _MOJIBAKE_CHARS) + text.count("Â·") + text.count("Ã—")


def _repair_text_if_needed(value: str | None) -> str:
    text = str(value or "")
    if not text:
        return ""

    def _fix_common(candidate: str) -> str:
        return (
            candidate.replace("Â·", "·")
            .replace("Ã—", "×")
            .replace("â€œ", "“")
            .replace("â€", "”")
            .replace("â€˜", "‘")
            .replace("â€™", "’")
            .replace("â€”", "—")
            .replace("â€“", "–")
        )

    best = _fix_common(text)
    best_score = (_count_cjk_characters(best), -_count_suspicious_characters(best))

    for encoding in ("cp1252", "latin1"):
        current = text
        for _ in range(2):
            try:
                current = current.encode(encoding).decode("utf-8")
            except Exception:
                break
            current = _fix_common(current)
            score = (_count_cjk_characters(current), -_count_suspicious_characters(current))
            if score > best_score:
                best = current
                best_score = score

    return best


def _repair_json_texts(value):
    if isinstance(value, str):
        return _repair_text_if_needed(value)
    if isinstance(value, list):
        return [_repair_json_texts(item) for item in value]
    if isinstance(value, dict):
        return {key: _repair_json_texts(item) for key, item in value.items()}
    return value


def _get_opencc_converter():
    global _zh_opencc_converter
    if _zh_opencc_converter is not None:
        return _zh_opencc_converter
    try:
        from opencc import OpenCC
    except Exception:
        _zh_opencc_converter = False
        return _zh_opencc_converter
    _zh_opencc_converter = OpenCC("t2s")
    return _zh_opencc_converter


def _to_simplified(text: str) -> str:
    converter = _get_opencc_converter()
    if not converter:
        return text
    try:
        return converter.convert(text or "")
    except Exception:
        return text


def _normalize_text_for_matching(text: str) -> str:
    simplified = _to_simplified(text or "")
    output_chars: list[str] = []
    for char in simplified:
        if char.isspace():
            continue
        category = unicodedata.category(char)
        if category in _PUNCTUATION_CATEGORIES:
            continue
        output_chars.append(char)
    return "".join(output_chars)


def _lcs_length(text_a: str, text_b: str) -> int:
    if not text_a or not text_b:
        return 0
    if len(text_a) < len(text_b):
        short_text, long_text = text_a, text_b
    else:
        short_text, long_text = text_b, text_a
    prev = [0] * (len(short_text) + 1)
    curr = [0] * (len(short_text) + 1)
    for char_long in long_text:
        for idx, char_short in enumerate(short_text, start=1):
            if char_long == char_short:
                curr[idx] = prev[idx - 1] + 1
            else:
                curr[idx] = prev[idx] if prev[idx] >= curr[idx - 1] else curr[idx - 1]
        prev, curr = curr, prev
    return prev[-1]


def _role_sentence_text_map(project: RoughCutProject) -> dict[str, str]:
    sentences = _safe_json_loads(project.sentences_json, [])
    role_to_chunks: dict[str, list[str]] = {}
    for sentence in sentences:
        role_id = str(sentence.get("roleId") or "").strip()
        text = str(sentence.get("text") or "").strip()
        if not role_id or not text:
            continue
        role_to_chunks.setdefault(role_id, []).append(text)
    return {role_id: "".join(chunks) for role_id, chunks in role_to_chunks.items()}


def _parse_asr_segments_from_path(asr_srt_path: str | None) -> list[dict]:
    path_str = str(asr_srt_path or "").strip()
    if not path_str:
        return []
    path = Path(path_str)
    if not path.exists():
        return []
    try:
        lines = parse_srt(path.as_posix(), encoding="utf-8", time_offset_seconds=0.0)
    except Exception:
        return []
    segments: list[dict] = []
    for line in lines:
        text = str(line.get("text") or "").strip()
        if not text:
            continue
        start = max(0.0, float(line.get("start_seconds") or 0.0))
        end = max(start + 0.01, float(line.get("end_seconds") or (start + 0.01)))
        segments.append({"start": start, "end": end, "text": _to_simplified(text)})
    return segments


def _calculate_asr_time_range(segments: list[dict]) -> tuple[float, float, float]:
    if not segments:
        return 0.0, 0.0, 0.0
    start = min(max(0.0, float(item.get("start") or 0.0)) for item in segments)
    end = max(
        max(start + 0.01, float(item.get("end") or (float(item.get("start") or 0.0) + 0.01)))
        for item in segments
    )
    return round(start, 3), round(end, 3), round(max(0.0, end - start), 3)


def _match_metrics_for_asset(asset: dict, role_text: str) -> dict:
    asr_text = "".join(seg.get("text", "") for seg in _parse_asr_segments_from_path(asset.get("asrSrtPath")))
    return _match_metrics_for_text(asr_text, role_text)


def _match_metrics_for_text(asr_text: str, role_text: str) -> dict:
    normalized_asr = _normalize_text_for_matching(asr_text)
    normalized_role = _normalize_text_for_matching(role_text)
    srt_total_chars = len(normalized_asr)
    matched_chars = _lcs_length(normalized_role, normalized_asr) if srt_total_chars > 0 else 0
    unmatched_chars = max(0, srt_total_chars - matched_chars)
    match_percent = round((matched_chars / srt_total_chars) * 100, 1) if srt_total_chars > 0 else 0.0
    error_percent = round((unmatched_chars / srt_total_chars) * 100, 1) if srt_total_chars > 0 else 100.0
    gate_passed = match_percent >= ROUGH_CUT_MATCH_THRESHOLD
    return {
        "matchedChars": matched_chars,
        "srtTotalChars": srt_total_chars,
        "unmatchedChars": unmatched_chars,
        "matchPercent": match_percent,
        "errorPercent": error_percent,
        "gatePassed": gate_passed,
    }


def _compute_rough_cut_gate_state(project: RoughCutProject, assets: list[dict]) -> dict:
    role_text_map = _role_sentence_text_map(project)
    assets_by_role = _group_assets_by_role(assets)
    role_progress_items: list[dict] = []
    minimum_match_percent: float | None = None
    rough_cut_enabled = True
    rough_cut_reason = ""
    all_assets_progress: list[int] = []

    for role_id, role_text in role_text_map.items():
        role_assets = assets_by_role.get(role_id) or []
        if not role_assets:
            role_progress_items.append(
                {
                    "roleId": role_id,
                    "status": "missing",
                    "progress": 0,
                    "matchPercent": 0.0,
                    "gatePassed": False,
                    "assetCount": 0,
                }
            )
            rough_cut_enabled = False
            rough_cut_reason = rough_cut_reason or f"角色 {role_id} 未上传素材"
            continue

        role_min_match: float | None = None
        role_all_completed = True
        role_all_gate_passed = True
        role_max_progress = 0
        role_has_failed = False

        for role_asset in role_assets:
            asr_status = str(role_asset.get("asrStatus") or "pending").strip().lower()
            asr_progress = max(0, min(100, int(role_asset.get("asrProgress") or 0)))
            role_max_progress = max(role_max_progress, asr_progress)
            all_assets_progress.append(asr_progress)
            if asr_status == "failed":
                role_has_failed = True
            if asr_status != "completed":
                role_all_completed = False

            metrics = _match_metrics_for_asset(role_asset, role_text)
            role_asset.update(metrics)
            manual_gate_passed = bool(role_asset.get("manualGatePassed"))
            effective_gate_passed = bool(metrics.get("gatePassed")) or manual_gate_passed
            role_asset["gatePassed"] = effective_gate_passed
            if role_min_match is None or metrics["matchPercent"] < role_min_match:
                role_min_match = metrics["matchPercent"]
            if not effective_gate_passed:
                role_all_gate_passed = False

        if role_min_match is None:
            role_min_match = 0.0
            role_all_gate_passed = False

        role_progress_items.append(
            {
                "roleId": role_id,
                "status": "failed" if role_has_failed else ("completed" if role_all_completed else "running"),
                "progress": role_max_progress,
                "matchPercent": round(role_min_match, 1),
                "gatePassed": bool(role_all_gate_passed and role_all_completed),
                "assetCount": len(role_assets),
            }
        )

        if minimum_match_percent is None or role_min_match < minimum_match_percent:
            minimum_match_percent = role_min_match

        if not role_all_completed:
            rough_cut_enabled = False
            rough_cut_reason = rough_cut_reason or f"角色 {role_id} 字幕识别尚未完成"
        elif not role_all_gate_passed:
            rough_cut_enabled = False
            rough_cut_reason = rough_cut_reason or f"角色 {role_id} 匹配率不足{int(ROUGH_CUT_MATCH_THRESHOLD)}%"

    if minimum_match_percent is None:
        minimum_match_percent = 0.0
        if role_text_map:
            rough_cut_enabled = False
            rough_cut_reason = rough_cut_reason or "暂无可用于匹配的角色素材"

    asr_avg_progress = (
        sum(all_assets_progress) / len(all_assets_progress)
        if all_assets_progress
        else 0.0
    )
    gate_progress = (
        min(100.0, (minimum_match_percent / ROUGH_CUT_MATCH_THRESHOLD) * 100.0)
        if minimum_match_percent > 0
        else 0.0
    )
    if project.status == ROUGH_CUT_STATUS_READY:
        pipeline_progress = 100
    elif project.status == ROUGH_CUT_STATUS_PROCESSING:
        pipeline_progress = max(int(project.progress or 0), int(round((asr_avg_progress * 0.4) + (gate_progress * 0.2))))
    else:
        pipeline_progress = int(round((asr_avg_progress * 0.6) + (gate_progress * 0.4)))
    pipeline_progress = max(0, min(100, pipeline_progress))

    return {
        "roughCutEnabled": rough_cut_enabled,
        "roughCutEnabledReason": rough_cut_reason,
        "minimumMatchPercent": round(minimum_match_percent, 1),
        "pipelineProgress": pipeline_progress,
        "rolesAsrProgress": role_progress_items,
    }


def _ensure_asset_defaults(asset: dict) -> dict:
    normalized = dict(asset or {})
    normalized["asrStatus"] = str(normalized.get("asrStatus") or "pending")
    normalized["asrProgress"] = max(0, min(100, int(normalized.get("asrProgress") or 0)))
    normalized["asrError"] = normalized.get("asrError")
    normalized["asrSrtPath"] = str(normalized.get("asrSrtPath") or "").strip() or None
    normalized["asrStartSeconds"] = round(float(normalized.get("asrStartSeconds") or 0.0), 3)
    normalized["asrEndSeconds"] = round(float(normalized.get("asrEndSeconds") or 0.0), 3)
    normalized["asrDuration"] = round(float(normalized.get("asrDuration") or 0.0), 3)
    normalized.setdefault("matchedChars", 0)
    normalized.setdefault("srtTotalChars", 0)
    normalized.setdefault("unmatchedChars", 0)
    normalized.setdefault("matchPercent", 0.0)
    normalized.setdefault("errorPercent", 100.0)
    normalized.setdefault("manualGatePassed", False)
    normalized.setdefault("gatePassed", False)
    if normalized["asrSrtPath"] and (
        normalized["asrDuration"] <= 0.0
        or normalized["asrEndSeconds"] <= 0.0
        or normalized["asrEndSeconds"] < normalized["asrStartSeconds"]
    ):
        asr_segments = _parse_asr_segments_from_path(normalized["asrSrtPath"])
        asr_start, asr_end, asr_duration = _calculate_asr_time_range(asr_segments)
        normalized["asrStartSeconds"] = asr_start
        normalized["asrEndSeconds"] = asr_end
        normalized["asrDuration"] = asr_duration
    return normalized


def _estimate_duration(text: str) -> float:
    length = len((text or "").strip())
    raw = length / 4.5 if length > 0 else 1.2
    return round(max(1.2, min(5.0, raw)), 2)


SPEAKER_LINE_REGEX = re.compile(
    r"^\s*([A-Za-z])(?:\s*[（(][^）)]*[）)])?\s*[：:]\s*(.+?)\s*$"
)


def _parse_speaker_line(line: str) -> tuple[str, str] | None:
    match = SPEAKER_LINE_REGEX.match(line.strip())
    if not match:
        return None
    role_id = str(match.group(1) or "").strip().upper()
    text = str(match.group(2) or "").strip()
    if not role_id or not text:
        return None
    return role_id, text


def _split_default_script_chunks(lines: list[str]) -> list[str]:
    first_chunks: list[str] = []
    for line in lines:
        pieces = re.split(r"([。！？；!?;])", line)
        buffer = ""
        for piece in pieces:
            if not piece:
                continue
            buffer += piece
            if piece in "。！？；!?;":
                first_chunks.append(buffer.strip())
                buffer = ""
        if buffer.strip():
            first_chunks.append(buffer.strip())

    second_chunks: list[str] = []
    for chunk in first_chunks:
        if len(chunk) <= 24:
            second_chunks.append(chunk)
            continue
        comma_pieces = re.split(r"([，、,])", chunk)
        buffer = ""
        for piece in comma_pieces:
            if not piece:
                continue
            buffer += piece
            if piece in "，、,":
                second_chunks.append(buffer.strip())
                buffer = ""
        if buffer.strip():
            second_chunks.append(buffer.strip())

    final_chunks: list[str] = []
    for chunk in second_chunks:
        clean = chunk.strip()
        if not clean:
            continue
        if len(clean) <= 24:
            final_chunks.append(clean)
            continue
        start = 0
        while start < len(clean):
            final_chunks.append(clean[start : start + 24].strip())
            start += 24
    return [item for item in final_chunks if item]


def split_script_to_text_items(script: str) -> list[dict]:
    source = (script or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not source:
        return []

    lines = [line.strip() for line in source.split("\n") if line.strip()]
    if not lines:
        return []

    speaker_items: list[dict] = []
    has_speaker_prefix = False
    for line in lines:
        parsed = _parse_speaker_line(line)
        if parsed:
            has_speaker_prefix = True
            role_id, text = parsed
            speaker_items.append(
                {
                    "text": text,
                    "roleId": role_id,
                    "speakerTagged": True,
                }
            )
            continue

        if has_speaker_prefix and speaker_items:
            speaker_items[-1]["text"] = f"{speaker_items[-1]['text']} {line}".strip()

    if has_speaker_prefix and speaker_items:
        return speaker_items

    return [
        {"text": item, "roleId": None, "speakerTagged": False}
        for item in _split_default_script_chunks(lines)
    ]


def build_sentences(script: str) -> list[dict]:
    items = split_script_to_text_items(script)
    sentences = []
    for idx, item in enumerate(items, start=1):
        text = str(item.get("text", "")).strip()
        role_id = str(item.get("roleId") or "").strip() or None
        speaker_tagged = bool(item.get("speakerTagged"))
        sentences.append(
            {
                "id": uuid4().hex[:12],
                "index": idx,
                "text": text,
                "roleId": role_id,
                "estimatedDuration": _estimate_duration(text),
                "locked": False,
                "clipId": None,
                "speakerTagged": speaker_tagged,
            }
        )
    return sentences


def build_roles_from_script(script: str) -> list[dict]:
    items = split_script_to_text_items(script)
    ordered_role_ids: list[str] = []
    seen_role_ids: set[str] = set()
    for item in items:
        if not item.get("speakerTagged"):
            continue
        role_id = str(item.get("roleId") or "").strip().upper()
        if not role_id or role_id in seen_role_ids:
            continue
        seen_role_ids.add(role_id)
        ordered_role_ids.append(role_id)

    roles: list[dict] = []
    for idx, role_id in enumerate(ordered_role_ids):
        roles.append(
            {
                "id": role_id,
                "name": f"角色{role_id}",
                "color": ROLE_COLOR_PALETTE[idx % len(ROLE_COLOR_PALETTE)],
                "isPrimary": idx == 0,
            }
        )
    return roles


def _sanitize_primary_role_id(primary_role_id: str | None, roles: list[dict]) -> str:
    role_ids = [str(role.get("id") or "").strip() for role in roles if str(role.get("id") or "").strip()]
    if not role_ids:
        return "A"
    candidate = str(primary_role_id or "").strip()
    return candidate if candidate in role_ids else role_ids[0]


def _sanitize_manual_sequence_for_roles(manual_sequence: str | None, roles: list[dict]) -> str | None:
    role_ids = {str(role.get("id") or "").strip() for role in roles if str(role.get("id") or "").strip()}
    if not role_ids:
        return None
    sequence = [item for item in _parse_manual_sequence(manual_sequence) if item in role_ids]
    return "+".join(sequence) if sequence else None


def _parse_manual_sequence(manual_sequence: str | None) -> list[str]:
    raw = (manual_sequence or "").strip()
    if not raw:
        return []
    candidates = [seg.strip() for seg in raw.split("+")]
    return [item for item in candidates if item]


def assign_roles_to_sentences(
    sentences: list[dict],
    roles: list[dict],
    strategy: str,
    manual_sequence: str | None,
    primary_role_id: str | None,
) -> list[dict]:
    if not roles:
        roles = default_roles()
    role_ids = [str(role.get("id", "")).strip() for role in roles if str(role.get("id", "")).strip()]
    if not role_ids:
        role_ids = ["A"]

    primary = primary_role_id if primary_role_id in role_ids else role_ids[0]
    manual_ids = [item for item in _parse_manual_sequence(manual_sequence) if item in role_ids]

    for idx, sentence in enumerate(sentences):
        role_from_script = str(sentence.get("roleId") or "").strip()
        if sentence.get("speakerTagged") and role_from_script in role_ids:
            sentence["roleId"] = role_from_script
            if not sentence.get("locked"):
                sentence["estimatedDuration"] = _estimate_duration(sentence.get("text", ""))
            continue

        if sentence.get("locked") and sentence.get("roleId"):
            continue

        if strategy == "manual-sequence" and manual_ids:
            role = manual_ids[idx % len(manual_ids)]
        elif strategy == "primary-first":
            if len(role_ids) == 1:
                role = role_ids[0]
            elif len(role_ids) == 2:
                role = role_ids[idx % 2]
            else:
                others = [rid for rid in role_ids if rid != primary]
                if not others:
                    role = primary
                else:
                    pattern = [primary]
                    for item in others:
                        pattern.append(item)
                        pattern.append(primary)
                    role = pattern[idx % len(pattern)]
        else:
            role = role_ids[idx % len(role_ids)]

        sentence["roleId"] = role
        if not sentence.get("locked"):
            sentence["estimatedDuration"] = _estimate_duration(sentence.get("text", ""))
    return sentences


def _group_assets_by_role(assets: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for asset in assets:
        role_id = str(asset.get("roleId", "")).strip()
        if not role_id:
            continue
        grouped.setdefault(role_id, []).append(asset)
    return grouped


def _sentence_segment_score(sentence_text: str, segment_text: str) -> float:
    sentence_normalized = _normalize_text_for_matching(sentence_text)
    segment_normalized = _normalize_text_for_matching(segment_text)
    if not sentence_normalized or not segment_normalized:
        return 0.0
    lcs = _lcs_length(sentence_normalized, segment_normalized)
    return lcs / max(1, len(sentence_normalized))


def _find_best_segment_window(
    segments: list[dict],
    cursor_index: int,
    sentence_text: str,
    max_window_segments: int = 20,
) -> tuple[int, dict] | None:
    if not segments:
        return None
    normalized_sentence = _normalize_text_for_matching(sentence_text)
    if not normalized_sentence:
        return None
    best: tuple[int, dict] | None = None
    best_score = 0.0
    best_coverage = 0.0
    best_matched = 0
    best_window_chars = 0
    start = max(0, cursor_index)
    end = len(segments)
    for start_idx in range(start, end):
        window_text_parts: list[str] = []
        window_char_limit = max(80, int(len(normalized_sentence) * 6))
        for end_idx in range(start_idx, min(len(segments), start_idx + max_window_segments)):
            segment = segments[end_idx]
            window_text_parts.append(str(segment.get("text") or ""))
            window_text = "".join(window_text_parts)
            normalized_window = _normalize_text_for_matching(window_text)
            if not normalized_window:
                continue
            matched_chars = _lcs_length(normalized_sentence, normalized_window)
            coverage = matched_chars / max(1, len(normalized_sentence))
            precision = matched_chars / max(1, len(normalized_window))
            score = coverage * 0.88 + precision * 0.12
            if (
                score > best_score
                or (
                    abs(score - best_score) < 1e-9
                    and (
                        coverage > best_coverage
                        or (
                            abs(coverage - best_coverage) < 1e-9
                            and (
                                matched_chars > best_matched
                                or (matched_chars == best_matched and len(normalized_window) < best_window_chars)
                            )
                        )
                    )
                )
            ):
                best_score = score
                best_coverage = coverage
                best_matched = matched_chars
                best_window_chars = len(normalized_window)
                best = (
                    end_idx,
                    {
                        "start": float(segments[start_idx].get("start") or 0.0),
                        "end": float(segment.get("end") or 0.0),
                        "text": window_text,
                        "startIndex": start_idx,
                        "endIndex": end_idx,
                        "matchedChars": matched_chars,
                        "coverage": round(coverage, 4),
                        "precision": round(precision, 4),
                    },
                )
            if len(normalized_window) >= window_char_limit:
                break
    min_coverage = 0.55 if len(normalized_sentence) <= 8 else 0.62
    if (
        best is None
        or best_score < 0.4
        or best_coverage < min_coverage
        or best_matched < max(3, int(len(normalized_sentence) * 0.35))
    ):
        return None
    return best


def _build_role_asr_pools(role_assets: list[dict]) -> list[dict]:
    pools: list[dict] = []
    for asset in role_assets:
        segments = _parse_asr_segments_from_path(asset.get("asrSrtPath"))
        if not segments:
            continue
        pools.append(
            {
                "asset": asset,
                "segments": segments,
                "cursor": 0,
            }
        )
    return pools


def _find_best_asset_segment(role_pools: list[dict], sentence_text: str) -> tuple[dict, dict] | None:
    selected_pool: dict | None = None
    selected_segment: dict | None = None
    selected_index = -1
    selected_score = 0.0

    for pool in role_pools:
        candidate = _find_best_segment_window(pool.get("segments") or [], int(pool.get("cursor") or 0), sentence_text)
        if candidate is None:
            continue
        seg_index, segment = candidate
        score = float(segment.get("coverage") or 0.0) * 0.75 + float(segment.get("precision") or 0.0) * 0.25
        if score > selected_score:
            selected_score = score
            selected_pool = pool
            selected_segment = segment
            selected_index = seg_index

    if selected_pool is None or selected_segment is None or selected_index < 0:
        return None
    selected_pool["cursor"] = selected_index + 1
    return selected_pool["asset"], selected_segment


def _consume_fallback_clip(
    role_assets: list[dict],
    role_cursor: dict,
    required_duration: float,
) -> tuple[dict, float, float, bool]:
    looped_used = False
    guard = 0
    while True:
        guard += 1
        if guard > 200:
            raise ValueError("素材切片异常：未找到可用片段。")
        asset = role_assets[role_cursor["assetIndex"]]
        asset_duration = float(asset.get("duration") or 0.0)
        available = max(0.0, asset_duration - float(role_cursor["offset"]))
        if available < 0.05:
            next_index = role_cursor["assetIndex"] + 1
            if next_index >= len(role_assets):
                next_index = 0
                looped_used = True
            role_cursor["assetIndex"] = next_index
            role_cursor["offset"] = 0.0
            continue

        duration = min(required_duration, available)
        source_start = float(role_cursor["offset"])
        source_end = source_start + duration
        role_cursor["offset"] = source_end
        if role_cursor["offset"] >= asset_duration - 0.05:
            next_index = role_cursor["assetIndex"] + 1
            if next_index >= len(role_assets):
                next_index = 0
                looped_used = True
            role_cursor["assetIndex"] = next_index
            role_cursor["offset"] = 0.0
        return asset, source_start, source_end, looped_used


def build_timeline(
    sentences: list[dict],
    assets: list[dict],
    recalculate_durations: bool = True,
) -> tuple[list[dict], list[dict]]:
    normalized_assets = [_ensure_asset_defaults(item) for item in assets]
    grouped_assets = _group_assets_by_role(normalized_assets)
    if not grouped_assets:
        raise ValueError("请先上传角色素材后再生成时间线。")

    role_cursors = {
        role_id: {"assetIndex": 0, "offset": 0.0}
        for role_id in grouped_assets.keys()
    }
    role_asr_pools: dict[str, list[dict]] = {}
    for role_id, role_assets in grouped_assets.items():
        role_asr_pools[role_id] = _build_role_asr_pools(role_assets)

    timeline: list[dict] = []
    timeline_cursor = 0.0

    for sentence in sentences:
        text = str(sentence.get("text", "")).strip()
        if not text:
            continue
        role_id = str(sentence.get("roleId", "")).strip()
        if not role_id:
            role_id = next(iter(grouped_assets.keys()))
            sentence["roleId"] = role_id

        role_assets = grouped_assets.get(role_id) or []
        if not role_assets:
            raise ValueError(f"角色 {role_id} 没有可用素材，无法为句子“{text}”选片。")

        if recalculate_durations and not sentence.get("locked"):
            sentence["estimatedDuration"] = _estimate_duration(text)

        required = float(sentence.get("estimatedDuration") or _estimate_duration(text))
        required = max(0.8, required)
        sentence["clipId"] = None

        chosen_asset = role_assets[-1]
        source_start = 0.0
        source_end = 0.0
        duration = required
        looped_used = False
        role_pools = role_asr_pools.get(role_id) or []
        best_match = _find_best_asset_segment(role_pools, text)
        if best_match is not None:
            chosen_asset, seg = best_match
            source_start = max(0.0, float(seg.get("start") or 0.0))
            if sentence.get("locked"):
                locked_duration = max(0.3, required)
                asset_duration = max(source_start + 0.01, float(chosen_asset.get("duration") or 0.0))
                source_end = min(asset_duration, source_start + locked_duration)
                source_end = max(source_start + 0.01, source_end)
                duration = max(0.3, source_end - source_start)
            else:
                source_end = max(source_start + 0.01, float(seg.get("end") or (source_start + 0.01)))
                duration = max(0.3, source_end - source_start)
            sentence["estimatedDuration"] = round(duration, 2)
            fallback_cursor = role_cursors[role_id]
            chosen_asset_idx = next(
                (idx for idx, item in enumerate(role_assets) if str(item.get("id") or "") == str(chosen_asset.get("id") or "")),
                0,
            )
            fallback_cursor["assetIndex"] = max(0, chosen_asset_idx)
            fallback_cursor["offset"] = source_end
        else:
            chosen_asset, source_start, source_end, looped_used = _consume_fallback_clip(
                role_assets=role_assets,
                role_cursor=role_cursors[role_id],
                required_duration=required,
            )
            duration = max(0.3, source_end - source_start)
            sentence["estimatedDuration"] = round(duration, 2)

        clip_id = uuid4().hex[:12]
        clip = {
            "id": clip_id,
            "sentenceId": sentence["id"],
            "roleId": role_id,
            "assetId": chosen_asset["id"],
            "filePath": chosen_asset["filePath"],
            "sourceStart": round(source_start, 3),
            "sourceEnd": round(source_end, 3),
            "duration": round(duration, 3),
            "timelineStart": round(timeline_cursor, 3),
            "timelineEnd": round(timeline_cursor + duration, 3),
            "subtitleText": text,
            "looped": bool(looped_used),
        }
        timeline.append(clip)
        sentence["clipId"] = clip_id
        timeline_cursor += duration

    for idx, sentence in enumerate(sentences, start=1):
        sentence["index"] = idx
    return sentences, timeline


def refresh_sentence_durations_from_asr(project: RoughCutProject) -> bool:
    sentences = _safe_json_loads(project.sentences_json, [])
    assets = [_ensure_asset_defaults(item) for item in _safe_json_loads(project.assets_json, [])]
    grouped_assets = _group_assets_by_role(assets)
    if not sentences or not grouped_assets:
        return False

    role_asr_pools: dict[str, list[dict]] = {}
    for role_id, role_assets in grouped_assets.items():
        role_asr_pools[role_id] = _build_role_asr_pools(role_assets)

    changed = False
    for sentence in sentences:
        if sentence.get("locked"):
            continue
        text = str(sentence.get("text", "")).strip()
        role_id = str(sentence.get("roleId") or "").strip()
        if not text or not role_id:
            continue
        role_pools = role_asr_pools.get(role_id) or []
        if not role_pools:
            continue
        best_match = _find_best_asset_segment(role_pools, text)
        if best_match is None:
            continue
        _, seg = best_match
        source_start = max(0.0, float(seg.get("start") or 0.0))
        source_end = max(source_start + 0.01, float(seg.get("end") or (source_start + 0.01)))
        duration = round(max(0.3, source_end - source_start), 2)
        if round(float(sentence.get("estimatedDuration") or 0.0), 2) != duration:
            sentence["estimatedDuration"] = duration
            changed = True

    if changed:
        project.sentences_json = _safe_json_dumps(sentences)
    return changed


def _resolution_size(aspect_ratio: str, resolution: str) -> tuple[int, int]:
    base = 1080 if resolution == "1080p" else 720
    if aspect_ratio == "16:9":
        return (base * 16 // 9, base)
    if aspect_ratio == "1:1":
        return (base, base)
    return (base, base * 16 // 9)


def _append_log(project: RoughCutProject, message: str) -> None:
    now = datetime.now().strftime("%H:%M:%S")
    existing = _repair_text_if_needed(project.log_text or "")
    normalized_message = _repair_text_if_needed(message)
    project.log_text = f"{existing}[{now}] {normalized_message}\n"


def _set_processing(project: RoughCutProject, phase: str, progress: int, db: Session, log: str | None = None) -> None:
    project.status = ROUGH_CUT_STATUS_PROCESSING
    project.phase = phase
    project.progress = max(0, min(99, int(progress)))
    if log:
        _append_log(project, log)
    db.commit()


def _register_rough_cut_process(project_id: int, process: subprocess.Popen) -> None:
    with _rough_cut_control_lock:
        _running_rough_cut_processes[project_id] = process


def _unregister_rough_cut_process(project_id: int) -> None:
    with _rough_cut_control_lock:
        _running_rough_cut_processes.pop(project_id, None)


def _is_rough_cut_stop_requested(project_id: int) -> bool:
    with _rough_cut_control_lock:
        return project_id in _stop_requested_rough_cut_projects


def _clear_rough_cut_stop_requested(project_id: int) -> None:
    with _rough_cut_control_lock:
        _stop_requested_rough_cut_projects.discard(project_id)


def request_stop_project_export(db: Session, project: RoughCutProject) -> RoughCutProject:
    process = None
    with _rough_cut_control_lock:
        _stop_requested_rough_cut_projects.add(project.id)
        process = _running_rough_cut_processes.get(project.id)

    if project.status == ROUGH_CUT_STATUS_PROCESSING:
        project.phase = "stopping"
        project.error_message = None
        _append_log(project, "已收到停止请求，正在停止生成任务。")
        db.commit()
        db.refresh(project)

    if process and process.poll() is None:
        try:
            process.terminate()
        except Exception:
            pass
    return project


def _mark_project_stopped(db: Session, project: RoughCutProject, message: str = "已停止当前生成任务。") -> None:
    project.status = ROUGH_CUT_STATUS_IDLE
    project.phase = "stopped"
    project.error_message = None
    project.progress = max(0, min(99, int(project.progress or 0)))
    _append_log(project, message)
    db.commit()


def _raise_if_rough_cut_stop_requested(project_id: int) -> None:
    if _is_rough_cut_stop_requested(project_id):
        raise RoughCutStopRequested("已停止当前生成任务。")


def _run_ffmpeg_command(cmd: list[str], error_prefix: str, *, project_id: int | None = None) -> None:
    if project_id is not None:
        _raise_if_rough_cut_stop_requested(project_id)

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdin=subprocess.DEVNULL,
    )
    if project_id is not None:
        _register_rough_cut_process(project_id, process)

    try:
        while process.poll() is None:
            if project_id is not None and _is_rough_cut_stop_requested(project_id):
                try:
                    process.terminate()
                except Exception:
                    pass
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    try:
                        process.kill()
                    except Exception:
                        pass
                raise RoughCutStopRequested("已停止当前生成任务。")
            time.sleep(0.2)

        stdout, stderr = process.communicate()
    finally:
        if project_id is not None:
            _unregister_rough_cut_process(project_id)

    if project_id is not None and _is_rough_cut_stop_requested(project_id):
        raise RoughCutStopRequested("已停止当前生成任务。")

    if process.returncode != 0:
        err = (stderr or "").strip() or (stdout or "").strip() or str(process.returncode)
        raise RuntimeError(f"{_repair_text_if_needed(error_prefix)}: {err}")


def _probe_has_audio(settings: Settings, file_path: str) -> bool:
    try:
        return bool(probe_video(settings, file_path).has_audio)
    except Exception:
        return False


def _render_timeline(
    settings: Settings,
    project: RoughCutProject,
    timeline: list[dict],
    render_settings: dict,
    mode: str,
) -> str:
    _raise_if_rough_cut_stop_requested(project.id)
    if not timeline:
        raise ValueError("当前时间线为空，无法导出。")

    aspect_ratio = str(render_settings.get("aspectRatio", "9:16"))
    resolution = str(render_settings.get("resolution", "1080p"))
    fps = int(render_settings.get("fps", 30))
    audio_mode = str(render_settings.get("audioMode", "keep"))
    subtitle_mode = str(render_settings.get("subtitleMode", "off"))
    width, height = _resolution_size(aspect_ratio, resolution)

    outputs_root = settings.data_dir / "outputs" / "rough_cut"
    temp_root = outputs_root / "temp" / f"project_{project.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    clips_root = temp_root / "clips"
    clips_root.mkdir(parents=True, exist_ok=True)
    render_list: list[Path] = []

    for idx, clip in enumerate(timeline, start=1):
        _raise_if_rough_cut_stop_requested(project.id)
        source_path = Path(str(clip.get("filePath", "")))
        if not source_path.exists():
            raise ValueError(f"素材不存在：{source_path}")

        source_start = float(clip.get("sourceStart") or 0.0)
        source_end = float(clip.get("sourceEnd") or source_start + 0.5)
        duration = max(0.3, source_end - source_start)

        output_clip = clips_root / f"clip_{idx:04d}.mp4"
        render_list.append(output_clip)
        vf = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,fps={fps},setsar=1"
        )

        if audio_mode == "mute" or audio_mode == "tts":
            cmd = [
                settings.ffmpeg_bin,
                "-y",
                "-ss",
                f"{source_start:.3f}",
                "-to",
                f"{source_end:.3f}",
                "-i",
                source_path.as_posix(),
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-pix_fmt",
                "yuv420p",
                "-an",
                output_clip.as_posix(),
            ]
        else:
            if _probe_has_audio(settings, source_path.as_posix()):
                cmd = [
                    settings.ffmpeg_bin,
                    "-y",
                    "-ss",
                    f"{source_start:.3f}",
                    "-to",
                    f"{source_end:.3f}",
                    "-i",
                    source_path.as_posix(),
                    "-vf",
                    vf,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-ar",
                    "48000",
                    "-ac",
                    "2",
                    output_clip.as_posix(),
                ]
            else:
                cmd = [
                    settings.ffmpeg_bin,
                    "-y",
                    "-ss",
                    f"{source_start:.3f}",
                    "-to",
                    f"{source_end:.3f}",
                    "-i",
                    source_path.as_posix(),
                    "-f",
                    "lavfi",
                    "-t",
                    f"{duration:.3f}",
                    "-i",
                    "anullsrc=channel_layout=stereo:sample_rate=48000",
                    "-vf",
                    vf,
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-shortest",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "23",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    output_clip.as_posix(),
                ]

        _run_ffmpeg_command(cmd, f"片段渲染失败（#{idx}）", project_id=project.id)

    concat_file = temp_root / "concat.txt"
    concat_file.write_text(
        "\n".join([f"file '{path.as_posix()}'" for path in render_list]) + "\n",
        encoding="utf-8",
    )

    video_root = outputs_root / "videos"
    video_root.mkdir(parents=True, exist_ok=True)
    output_name = f"rough_cut_{project.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{mode}.mp4"
    output_path = video_root / output_name

    concat_cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        concat_file.as_posix(),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
    ]
    if audio_mode == "mute" or audio_mode == "tts":
        concat_cmd += ["-an"]
    else:
        concat_cmd += ["-c:a", "aac", "-b:a", "128k"]
    concat_cmd.append(output_path.as_posix())
    _run_ffmpeg_command(concat_cmd, "时间线拼接失败", project_id=project.id)

    if subtitle_mode in {"srt", "burn"}:
        srt_root = outputs_root / "subtitles"
        srt_root.mkdir(parents=True, exist_ok=True)
        srt_path = srt_root / f"rough_cut_{project.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.srt"
        _write_timeline_srt(srt_path, timeline)
        if subtitle_mode == "burn":
            burned_path = video_root / output_name.replace(".mp4", "_burn.mp4")
            burn_cmd = [
                settings.ffmpeg_bin,
                "-y",
                "-i",
                output_path.as_posix(),
                "-vf",
                f"subtitles='{srt_path.as_posix()}'",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-c:a",
                "copy",
                burned_path.as_posix(),
            ]
            _run_ffmpeg_command(burn_cmd, "字幕烧录失败", project_id=project.id)
            output_path = burned_path

    return output_path.as_posix()


def _format_srt_time(seconds: float) -> str:
    total_ms = max(0, int(round(seconds * 1000)))
    hours = total_ms // 3_600_000
    minutes = (total_ms % 3_600_000) // 60_000
    secs = (total_ms % 60_000) // 1000
    millis = total_ms % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _write_timeline_srt(path: Path, timeline: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_handle:
        for idx, clip in enumerate(timeline, start=1):
            file_handle.write(f"{idx}\n")
            file_handle.write(
                f"{_format_srt_time(float(clip['timelineStart']))} --> {_format_srt_time(float(clip['timelineEnd']))}\n"
            )
            file_handle.write(f"{str(clip.get('subtitleText', '')).strip()}\n\n")


def _reset_project_outputs(project: RoughCutProject) -> None:
    previous_preview_path = str(project.preview_path or "").strip()
    previous_output_path = str(project.output_path or "").strip()
    if previous_preview_path and previous_preview_path != str(project.output_path or "").strip():
        _safe_remove_path(previous_preview_path)
    if previous_output_path:
        _safe_remove_path(previous_output_path)
    project.preview_path = None
    project.output_path = None
    project.timeline_json = "[]"
    project.status = ROUGH_CUT_STATUS_IDLE
    project.progress = 0
    project.error_message = None


def _apply_project_script(
    project: RoughCutProject,
    *,
    script: str,
    script_file_name=_UNSET,
    require_role_prefix: bool,
    log_prefix: str,
) -> tuple[list[dict], list[dict]]:
    normalized_script = str(script or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    project.script_text = normalized_script
    roles = build_roles_from_script(normalized_script)
    if require_role_prefix and normalized_script and not roles:
        raise ValueError("剧本中未识别到合法角色前缀，请使用 A:、A：或 A（说明）：格式。")

    if roles:
        project.roles_json = _safe_json_dumps(roles)
    elif not str(project.roles_json or "").strip():
        project.roles_json = _safe_json_dumps(default_roles())

    sentences = build_sentences(normalized_script) if normalized_script else []
    project.sentences_json = _safe_json_dumps(sentences)
    _reset_project_outputs(project)
    project.phase = "split_script" if normalized_script else "init"

    settings_payload = _load_project_settings_payload(project)
    settings_payload["primaryRoleId"] = _sanitize_primary_role_id(
        settings_payload.get("primaryRoleId"),
        roles or _safe_json_loads(project.roles_json, default_roles()),
    )
    settings_payload["manualSequence"] = _sanitize_manual_sequence_for_roles(
        settings_payload.get("manualSequence"),
        roles or _safe_json_loads(project.roles_json, default_roles()),
    )
    _persist_project_settings(
        project,
        settings_payload=settings_payload,
        script_file_name=script_file_name,
    )

    if normalized_script:
        _append_log(project, f"{log_prefix}，共 {len(sentences)} 句。")
    return roles, sentences


def _build_stage_summary(project: RoughCutProject, gate_state: dict, roles: list[dict], assets: list[dict]) -> str:
    if project.status == ROUGH_CUT_STATUS_ERROR:
        return "error"
    if str(project.phase or "").strip() == "stopping":
        return "stopping"
    if str(project.phase or "").strip() == "stopped":
        return "stopped"
    if project.status == ROUGH_CUT_STATUS_PROCESSING:
        return "rendering"
    if not str(project.script_text or "").strip():
        return "draft"
    if not roles:
        return "script_invalid"
    if not assets:
        return "waiting_assets"

    progress_items = gate_state.get("rolesAsrProgress") or []
    statuses = {str(item.get("status") or "").strip().lower() for item in progress_items}
    if "missing" in statuses:
        return "waiting_assets"
    if "pending" in statuses or "running" in statuses:
        return "waiting_asr"
    if not gate_state.get("roughCutEnabled"):
        return "waiting_gate"
    if _safe_json_loads(project.timeline_json, []):
        return "timeline_ready"
    return "script_ready"


def _compute_auto_preview_signature(project: RoughCutProject, assets: list[dict], gate_state: dict) -> str:
    signature_payload = {
        "projectId": int(project.id),
        "script": str(project.script_text or ""),
        "roles": _safe_json_loads(project.roles_json, []),
        "sentences": _safe_json_loads(project.sentences_json, []),
        "settings": _load_project_settings_payload(project),
        "roughCutEnabled": bool(gate_state.get("roughCutEnabled")),
        "assets": [
            {
                "id": str(asset.get("id") or ""),
                "roleId": str(asset.get("roleId") or ""),
                "status": str(asset.get("asrStatus") or ""),
                "progress": int(asset.get("asrProgress") or 0),
                "srt": str(asset.get("asrSrtPath") or ""),
                "manual": bool(asset.get("manualGatePassed")),
                "gate": bool(asset.get("gatePassed")),
                "match": float(asset.get("matchPercent") or 0.0),
            }
            for asset in assets
        ],
    }
    return _safe_json_dumps(signature_payload)


def project_to_payload(project: RoughCutProject) -> dict:
    settings_payload = _load_project_settings_payload(project)
    try:
        normalized_settings = RenderSettings(**settings_payload).model_dump()
    except Exception:
        normalized_settings = default_render_settings()
    assets = _repair_json_texts([_ensure_asset_defaults(item) for item in _safe_json_loads(project.assets_json, [])])
    roles = _repair_json_texts(_safe_json_loads(project.roles_json, default_roles()))
    gate_state = _compute_rough_cut_gate_state(project, assets)
    stage_summary = _build_stage_summary(project, gate_state, roles, assets)
    return {
        "id": project.id,
        "title": _repair_text_if_needed(project.title),
        "script": project.script_text or "",
        "scriptFileName": _repair_text_if_needed(_get_project_script_file_name(project)),
        "sentences": _safe_json_loads(project.sentences_json, []),
        "roles": roles,
        "roleCount": len(roles),
        "assets": assets,
        "assetCount": len(assets),
        "settings": normalized_settings,
        "timeline": _safe_json_loads(project.timeline_json, []),
        "status": project.status if project.status in {"idle", "processing", "ready", "error"} else "idle",
        "progress": max(0, min(100, int(project.progress or 0))),
        "pipelineProgress": gate_state["pipelineProgress"],
        "rolesAsrProgress": gate_state["rolesAsrProgress"],
        "roughCutEnabled": gate_state["roughCutEnabled"],
        "roughCutEnabledReason": _repair_text_if_needed(gate_state["roughCutEnabledReason"]),
        "minimumMatchPercent": gate_state["minimumMatchPercent"],
        "phase": project.phase,
        "error": _repair_text_if_needed(project.error_message),
        "log": _repair_text_if_needed(project.log_text or ""),
        "previewUrl": f"/api/rough-cut/projects/{project.id}/media?type=preview" if project.preview_path else None,
        "outputUrl": f"/api/rough-cut/projects/{project.id}/media?type=output" if project.output_path else None,
        "stageSummary": stage_summary,
        "createdAt": project.created_at,
        "updatedAt": project.updated_at,
    }


def build_project_compare_payload(project: RoughCutProject) -> dict:
    roles = _repair_json_texts(_safe_json_loads(project.roles_json, default_roles()))
    assets = _repair_json_texts([_ensure_asset_defaults(item) for item in _safe_json_loads(project.assets_json, [])])
    assets_by_role = _group_assets_by_role(assets)
    role_text_map = _role_sentence_text_map(project)

    compare_roles: list[dict] = []
    for role in roles:
        role_id = str(role.get("id") or "").strip()
        if not role_id:
            continue
        role_name = _repair_text_if_needed(str(role.get("name") or role_id).strip() or role_id)
        main_text = _to_simplified(role_text_map.get(role_id, "") or "")
        role_assets = assets_by_role.get(role_id) or []
        compare_assets: list[dict] = []
        asr_text_parts: list[str] = []
        total_matched = 0
        total_srt = 0
        total_unmatched = 0
        all_gate_passed = True
        all_completed = True
        any_manual_gate_passed = False
        has_failed = False
        has_running = False
        has_pending = False
        progress_values: list[int] = []
        first_error: str | None = None

        for role_asset in role_assets:
            asr_segments = _parse_asr_segments_from_path(role_asset.get("asrSrtPath"))
            asr_text = "".join(str(seg.get("text") or "") for seg in asr_segments)
            metrics = _match_metrics_for_text(asr_text, main_text)
            role_asset.update(metrics)
            manual_gate_passed = bool(role_asset.get("manualGatePassed"))
            effective_gate_passed = bool(metrics.get("gatePassed")) or manual_gate_passed
            any_manual_gate_passed = any_manual_gate_passed or manual_gate_passed
            role_asset["gatePassed"] = effective_gate_passed
            asr_text_parts.append(asr_text)

            asr_status = str(role_asset.get("asrStatus") or "pending").strip().lower()
            asr_progress = max(0, min(100, int(role_asset.get("asrProgress") or 0)))
            asr_error = str(role_asset.get("asrError")) if role_asset.get("asrError") else None
            if not asr_error and asr_status == "completed" and not asr_text:
                asr_error = "ASR已完成，但识别文本为空或SRT解析失败。"

            total_matched += int(metrics.get("matchedChars") or 0)
            total_srt += int(metrics.get("srtTotalChars") or 0)
            total_unmatched += int(metrics.get("unmatchedChars") or 0)
            all_gate_passed = all_gate_passed and effective_gate_passed
            all_completed = all_completed and asr_status == "completed"
            has_failed = has_failed or asr_status == "failed"
            has_running = has_running or asr_status == "running"
            has_pending = has_pending or asr_status == "pending"
            progress_values.append(asr_progress)
            if first_error is None and asr_error:
                first_error = asr_error

            compare_assets.append(
                {
                    "assetId": str(role_asset.get("id") or ""),
                    "fileName": _repair_text_if_needed(str(role_asset.get("fileName") or "")),
                    "asrText": asr_text,
                    "asrStartSeconds": float(role_asset.get("asrStartSeconds") or 0.0),
                    "asrEndSeconds": float(role_asset.get("asrEndSeconds") or 0.0),
                    "asrDuration": float(role_asset.get("asrDuration") or 0.0),
                    "matchedChars": int(metrics.get("matchedChars") or 0),
                    "srtTotalChars": int(metrics.get("srtTotalChars") or 0),
                    "unmatchedChars": int(metrics.get("unmatchedChars") or 0),
                    "matchPercent": float(metrics.get("matchPercent") or 0.0),
                    "errorPercent": float(metrics.get("errorPercent") or 100.0),
                    "manualGatePassed": bool(manual_gate_passed),
                    "gatePassed": bool(effective_gate_passed),
                    "asrStatus": asr_status,
                    "asrProgress": asr_progress,
                    "asrError": asr_error,
                }
            )

        if not role_assets:
            role_status = "missing"
            role_progress = 0
            gate_passed = False
        else:
            if has_failed:
                role_status = "failed"
            elif all_completed:
                role_status = "completed"
            elif has_running:
                role_status = "running"
            elif has_pending:
                role_status = "pending"
            else:
                role_status = "running"
            role_progress = int(round(sum(progress_values) / len(progress_values))) if progress_values else 0
            gate_passed = all_completed and all_gate_passed

        role_match_percent = round((total_matched / total_srt) * 100, 1) if total_srt > 0 else 0.0
        role_error_percent = round((total_unmatched / total_srt) * 100, 1) if total_srt > 0 else 100.0
        combined_asr_text = "\n".join(part for part in asr_text_parts if part)
        role_summary = {
            "matchedChars": int(total_matched),
            "srtTotalChars": int(total_srt),
            "unmatchedChars": int(total_unmatched),
            "matchPercent": float(role_match_percent),
            "errorPercent": float(role_error_percent),
            "gatePassed": bool(gate_passed),
            "asrStatus": role_status,
            "asrProgress": int(role_progress),
            "asrError": first_error,
        }

        compare_roles.append(
            {
                "roleId": role_id,
                "roleName": role_name,
                "mainText": main_text,
                "asrText": combined_asr_text,
                "matchedChars": role_summary["matchedChars"],
                "srtTotalChars": role_summary["srtTotalChars"],
                "unmatchedChars": role_summary["unmatchedChars"],
                "matchPercent": role_summary["matchPercent"],
                "errorPercent": role_summary["errorPercent"],
                "gatePassed": role_summary["gatePassed"],
                "manualGatePassed": bool(any_manual_gate_passed),
                "asrStatus": role_summary["asrStatus"],
                "asrProgress": role_summary["asrProgress"],
                "asrError": role_summary["asrError"],
                "roleSummary": role_summary,
                "assets": compare_assets,
            }
        )

    return {
        "projectId": int(project.id),
        "projectTitle": _repair_text_if_needed(str(project.title or "")),
        "roles": compare_roles,
    }


def create_project(
    db: Session,
    *,
    title: str,
    script: str,
    script_file_name: str | None = None,
) -> RoughCutProject:
    project = RoughCutProject(
        title=(title or "混剪项目").strip() or "混剪项目",
        script_text="",
        sentences_json="[]",
        roles_json=_safe_json_dumps(default_roles()),
        assets_json="[]",
        settings_json="{}",
        timeline_json="[]",
        status=ROUGH_CUT_STATUS_IDLE,
        progress=0,
        phase="init",
        log_text="",
    )
    _persist_project_settings(project, settings_payload=default_render_settings(), script_file_name=script_file_name)
    normalized_script = str(script or "").strip()
    if normalized_script:
        _apply_project_script(
            project,
            script=normalized_script,
            script_file_name=script_file_name,
            require_role_prefix=bool(str(script_file_name or "").strip()),
            log_prefix="脚本拆句完成",
        )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def split_project_script(db: Session, project: RoughCutProject, script_override: str | None = None) -> RoughCutProject:
    if script_override is not None:
        _apply_project_script(
            project,
            script=script_override,
            script_file_name=_UNSET,
            require_role_prefix=False,
            log_prefix="脚本拆句完成",
        )
    else:
        _apply_project_script(
            project,
            script=project.script_text or "",
            script_file_name=_UNSET,
            require_role_prefix=False,
            log_prefix="脚本拆句完成",
        )
    db.commit()
    db.refresh(project)
    return project


def patch_project(
    db: Session,
    project: RoughCutProject,
    *,
    patch: dict,
) -> RoughCutProject:
    if "title" in patch:
        normalized_title = str(patch.get("title") or "").strip()
        if normalized_title:
            project.title = normalized_title

    has_script_field = "script" in patch
    has_script_file_name_field = "scriptFileName" in patch
    next_script_file_name = (
        patch.get("scriptFileName")
        if has_script_file_name_field
        else _get_project_script_file_name(project)
    )

    if has_script_field:
        _apply_project_script(
            project,
            script=patch.get("script") or "",
            script_file_name=next_script_file_name,
            require_role_prefix=bool(str(next_script_file_name or "").strip()),
            log_prefix="脚本已更新并重新拆句",
        )
    elif has_script_file_name_field:
        _persist_project_settings(
            project,
            settings_payload=_load_project_settings_payload(project),
            script_file_name=next_script_file_name,
        )

    project.phase = "project_updated"
    project.error_message = None
    db.commit()
    db.refresh(project)
    return project


def assign_project_roles(
    db: Session,
    project: RoughCutProject,
    *,
    strategy: str,
    manual_sequence: str | None,
    primary_role_id: str,
) -> RoughCutProject:
    sentences = _safe_json_loads(project.sentences_json, [])
    roles = _safe_json_loads(project.roles_json, default_roles())
    sentences = assign_roles_to_sentences(
        sentences=sentences,
        roles=roles,
        strategy=strategy,
        manual_sequence=manual_sequence,
        primary_role_id=primary_role_id,
    )
    settings_payload = _load_project_settings_payload(project)
    settings_payload["roleStrategy"] = strategy
    settings_payload["manualSequence"] = manual_sequence
    settings_payload["primaryRoleId"] = _sanitize_primary_role_id(primary_role_id, roles)
    project.sentences_json = _safe_json_dumps(sentences)
    _persist_project_settings(project, settings_payload=settings_payload)
    project.timeline_json = "[]"
    project.status = ROUGH_CUT_STATUS_IDLE
    project.progress = 0
    project.phase = "assign_roles"
    project.error_message = None
    _append_log(project, "角色分配完成。")
    db.commit()
    db.refresh(project)
    return project


def update_project_settings(
    db: Session,
    project: RoughCutProject,
    *,
    settings_payload: dict,
) -> RoughCutProject:
    _persist_project_settings(project, settings_payload=settings_payload)
    project.status = ROUGH_CUT_STATUS_IDLE
    project.progress = 0
    project.phase = "settings_updated"
    project.error_message = None
    _append_log(project, "生成参数已更新。")
    db.commit()
    db.refresh(project)
    return project


def build_project_timeline(db: Session, project: RoughCutProject, *, recalculate_durations: bool = True) -> RoughCutProject:
    sentences = _safe_json_loads(project.sentences_json, [])
    assets = _safe_json_loads(project.assets_json, [])
    if not sentences:
        raise ValueError("请先输入文案并拆句。")
    if not assets:
        raise ValueError("请先上传角色素材。")
    sentences, timeline = build_timeline(
        sentences=sentences,
        assets=assets,
        recalculate_durations=recalculate_durations,
    )
    project.sentences_json = _safe_json_dumps(sentences)
    project.timeline_json = _safe_json_dumps(timeline)
    project.status = ROUGH_CUT_STATUS_IDLE
    project.progress = 0
    project.phase = "build_timeline"
    project.error_message = None
    _append_log(project, f"时间线生成完成，共 {len(timeline)} 段。")
    db.commit()
    db.refresh(project)
    return project


def update_sentence(
    db: Session,
    project: RoughCutProject,
    *,
    sentence_id: str,
    role_id: str | None = None,
    estimated_duration: float | None = None,
    locked: bool | None = None,
) -> RoughCutProject:
    sentences = _safe_json_loads(project.sentences_json, [])
    found = False
    for sentence in sentences:
        if sentence.get("id") != sentence_id:
            continue
        found = True
        if role_id is not None:
            sentence["roleId"] = role_id
        if estimated_duration is not None:
            sentence["estimatedDuration"] = round(max(0.8, float(estimated_duration)), 2)
        if locked is not None:
            sentence["locked"] = bool(locked)
        break
    if not found:
        raise ValueError("句子不存在。")

    project.sentences_json = _safe_json_dumps(sentences)
    project.timeline_json = "[]"
    project.status = ROUGH_CUT_STATUS_IDLE
    project.progress = 0
    project.phase = "update_sentence"
    project.error_message = None
    _append_log(project, f"句子 {sentence_id} 已更新。")
    db.commit()
    db.refresh(project)
    return project


def _start_processing(project_id: int) -> bool:
    with _processing_projects_lock:
        if project_id in _processing_projects:
            return False
        _processing_projects.add(project_id)
        return True


def _finish_processing(project_id: int) -> None:
    with _processing_projects_lock:
        _processing_projects.discard(project_id)


def _start_auto_preview_dispatch(project_id: int) -> bool:
    with _auto_preview_lock:
        if project_id in _auto_preview_projects:
            return False
        _auto_preview_projects.add(project_id)
        return True


def _finish_auto_preview_dispatch(project_id: int) -> None:
    with _auto_preview_lock:
        _auto_preview_projects.discard(project_id)


def _should_auto_schedule_preview(project: RoughCutProject, assets: list[dict], gate_state: dict) -> tuple[bool, str]:
    if not str(project.script_text or "").strip():
        return False, ""
    if not _role_sentence_text_map(project):
        return False, ""
    if not assets:
        return False, ""
    if project.status == ROUGH_CUT_STATUS_PROCESSING:
        return False, ""
    if not gate_state.get("roughCutEnabled"):
        return False, ""
    signature = _compute_auto_preview_signature(project, assets, gate_state)
    with _auto_preview_lock:
        if project.id in _auto_preview_projects:
            return False, signature
        if _auto_preview_signatures.get(project.id) == signature:
            return False, signature
    return True, signature


def schedule_project_auto_preview(settings: Settings, *, project_id: int) -> bool:
    db = SessionLocal()
    try:
        project = db.query(RoughCutProject).filter(RoughCutProject.id == project_id).first()
        if not project:
            return False
        assets = [_ensure_asset_defaults(item) for item in _safe_json_loads(project.assets_json, [])]
        gate_state = _compute_rough_cut_gate_state(project, assets)
        should_schedule, signature = _should_auto_schedule_preview(project, assets, gate_state)
    finally:
        db.close()

    if not should_schedule or not signature:
        return False
    if not _start_auto_preview_dispatch(project_id):
        return False

    thread = threading.Thread(
        target=_run_auto_preview_dispatch,
        args=(settings, project_id, signature),
        daemon=True,
    )
    thread.start()
    return True


def _run_auto_preview_dispatch(settings: Settings, project_id: int, signature: str) -> None:
    db = SessionLocal()
    try:
        project = db.query(RoughCutProject).filter(RoughCutProject.id == project_id).first()
        if not project:
            return

        assets = [_ensure_asset_defaults(item) for item in _safe_json_loads(project.assets_json, [])]
        gate_state = _compute_rough_cut_gate_state(project, assets)
        current_signature = _compute_auto_preview_signature(project, assets, gate_state)
        if not gate_state.get("roughCutEnabled") or current_signature != signature:
            return

        settings_payload = _load_project_settings_payload(project)
        roles = _safe_json_loads(project.roles_json, default_roles())
        project = assign_project_roles(
            db,
            project,
            strategy=str(settings_payload.get("roleStrategy", "primary-first")),
            manual_sequence=settings_payload.get("manualSequence"),
            primary_role_id=_sanitize_primary_role_id(settings_payload.get("primaryRoleId"), roles),
        )
        project = build_project_timeline(db, project, recalculate_durations=True)
        with _auto_preview_lock:
            _auto_preview_signatures[project_id] = signature
    except Exception as exc:
        project = db.query(RoughCutProject).filter(RoughCutProject.id == project_id).first()
        if project:
            project.phase = "auto_prepare_failed"
            project.error_message = str(exc)
            _append_log(project, f"自动生成时间线失败：{str(exc)[:160]}")
            db.commit()
    finally:
        db.close()
        _finish_auto_preview_dispatch(project_id)


def _make_asset_job_key(project_id: int, asset_id: str) -> str:
    return f"{project_id}:{asset_id}"


def _get_system_asr_model(db: Session) -> str:
    row = db.query(SettingsRow).filter(SettingsRow.id == 1).first()
    model = str(getattr(row, "asr_model", "small") or "small").strip().lower()
    return model if model in {"small", "medium"} else "small"


def _update_project_asset(
    db: Session,
    project: RoughCutProject,
    *,
    asset_id: str,
    patch: dict,
) -> tuple[RoughCutProject, dict]:
    assets = [_ensure_asset_defaults(item) for item in _safe_json_loads(project.assets_json, [])]
    target: dict | None = None
    for asset in assets:
        if str(asset.get("id") or "").strip() == asset_id:
            asset.update(patch or {})
            target = asset
            break
    if target is None:
        raise ValueError("角色素材不存在。")
    project.assets_json = _safe_json_dumps(assets)
    db.commit()
    db.refresh(project)
    return project, target


def schedule_asr_for_rough_cut_asset(settings: Settings, *, project_id: int, asset_id: str) -> None:
    db = SessionLocal()
    try:
        project = db.query(RoughCutProject).filter(RoughCutProject.id == project_id).first()
        if not project:
            return
        assets = [_ensure_asset_defaults(item) for item in _safe_json_loads(project.assets_json, [])]
        target = next((item for item in assets if str(item.get("id") or "").strip() == asset_id), None)
        if target is None:
            return
        target["asrStatus"] = "pending"
        target["asrProgress"] = 5
        target["asrError"] = None
        target["asrSrtPath"] = None
        target["asrStartSeconds"] = 0.0
        target["asrEndSeconds"] = 0.0
        target["asrDuration"] = 0.0
        target["manualGatePassed"] = False
        target["matchPercent"] = 0.0
        target["matchedChars"] = 0
        target["srtTotalChars"] = 0
        target["unmatchedChars"] = 0
        target["errorPercent"] = 100.0
        target["gatePassed"] = False
        project.assets_json = _safe_json_dumps(assets)
        db.commit()
    finally:
        db.close()

    job_key = _make_asset_job_key(project_id, asset_id)
    with _rough_cut_asr_lock:
        if job_key in _running_rough_cut_asset_jobs:
            return
        _running_rough_cut_asset_jobs.add(job_key)

    thread = threading.Thread(
        target=_run_rough_cut_asset_asr_job,
        args=(settings, project_id, asset_id),
        daemon=True,
    )
    thread.start()


def _run_rough_cut_asset_asr_job(settings: Settings, project_id: int, asset_id: str) -> None:
    db = SessionLocal()
    job_key = _make_asset_job_key(project_id, asset_id)
    try:
        project = db.query(RoughCutProject).filter(RoughCutProject.id == project_id).first()
        if not project:
            return

        assets = [_ensure_asset_defaults(item) for item in _safe_json_loads(project.assets_json, [])]
        asset = next((item for item in assets if str(item.get("id") or "").strip() == asset_id), None)
        if asset is None:
            return

        source_path = str(asset.get("filePath") or "").strip()
        if not source_path or not Path(source_path).exists():
            _update_project_asset(
                db,
                project,
                asset_id=asset_id,
                patch={
                    "asrStatus": "failed",
                    "asrProgress": 100,
                    "asrError": "素材文件不存在",
                    "asrStartSeconds": 0.0,
                    "asrEndSeconds": 0.0,
                    "asrDuration": 0.0,
                },
            )
            return

        asr_model = _get_system_asr_model(db)
        _update_project_asset(
            db,
            project,
            asset_id=asset_id,
            patch={"asrStatus": "running", "asrProgress": 35, "asrError": None},
        )

        segments = transcribe_audio_segments(audio_path=source_path, model_name=asr_model)
        _update_project_asset(
            db,
            project,
            asset_id=asset_id,
            patch={"asrStatus": "running", "asrProgress": 75},
        )

        output_dir = settings.data_dir / "uploads" / "rough_cut_subtitles" / f"project_{project_id}"
        output_dir.mkdir(parents=True, exist_ok=True)
        source_name = Path(source_path).stem or f"asset_{asset_id}"
        output_path = output_dir / f"{source_name}_{asset_id}.srt"
        write_segments_to_srt(output_path=output_path, segments=segments)

        parsed_segments = _parse_asr_segments_from_path(output_path.as_posix())
        asr_start_seconds, asr_end_seconds, asr_duration = _calculate_asr_time_range(parsed_segments)
        _update_project_asset(
            db,
            project,
            asset_id=asset_id,
            patch={
                "asrStatus": "completed",
                "asrProgress": 100,
                "asrError": None,
                "asrSrtPath": output_path.as_posix(),
                "asrStartSeconds": asr_start_seconds,
                "asrEndSeconds": asr_end_seconds,
                "asrDuration": asr_duration,
                "srtLineCount": len(parsed_segments),
            },
        )
        project = db.query(RoughCutProject).filter(RoughCutProject.id == project_id).first()
        if project:
            _append_log(project, f"角色素材ASR识别完成：{Path(source_path).name}")
            db.commit()
        schedule_project_auto_preview(settings, project_id=project_id)
    except Exception as exc:
        project = db.query(RoughCutProject).filter(RoughCutProject.id == project_id).first()
        if project:
            try:
                _update_project_asset(
                    db,
                    project,
                    asset_id=asset_id,
                    patch={
                        "asrStatus": "failed",
                        "asrProgress": 100,
                        "asrError": str(exc)[:500],
                        "asrStartSeconds": 0.0,
                        "asrEndSeconds": 0.0,
                        "asrDuration": 0.0,
                    },
                )
                project = db.query(RoughCutProject).filter(RoughCutProject.id == project_id).first()
                if project:
                    _append_log(project, f"角色素材ASR识别失败：{str(exc)[:120]}")
                    db.commit()
            except Exception:
                pass
    finally:
        with _rough_cut_asr_lock:
            _running_rough_cut_asset_jobs.discard(job_key)
        db.close()


def is_rough_cut_enabled(project: RoughCutProject) -> tuple[bool, str]:
    assets = [_ensure_asset_defaults(item) for item in _safe_json_loads(project.assets_json, [])]
    gate_state = _compute_rough_cut_gate_state(project, assets)
    return bool(gate_state["roughCutEnabled"]), str(gate_state.get("roughCutEnabledReason") or "")


def start_export_job(settings: Settings, project_id: int, mode: str) -> bool:
    if not _start_processing(project_id):
        return False
    _clear_rough_cut_stop_requested(project_id)
    thread = threading.Thread(
        target=_export_worker,
        args=(settings, project_id, mode),
        daemon=True,
    )
    thread.start()
    return True


def _export_worker(settings: Settings, project_id: int, mode: str) -> None:
    db = SessionLocal()
    try:
        project = db.query(RoughCutProject).filter(RoughCutProject.id == project_id).first()
        if not project:
            return

        _raise_if_rough_cut_stop_requested(project_id)

        previous_preview_path = str(project.preview_path or "").strip()
        previous_output_path = str(project.output_path or "").strip()
        if mode == "preview" and previous_preview_path:
            _safe_remove_path(previous_preview_path)
            project.preview_path = None
            db.commit()

        _raise_if_rough_cut_stop_requested(project_id)
        _set_processing(project, "normalize_script", 5, db, "开始生成粗剪任务。")
        if not (project.script_text or "").strip():
            raise ValueError("文案为空，请先输入文案。")

        sentences = _safe_json_loads(project.sentences_json, [])
        if not sentences:
            sentences = build_sentences(project.script_text)
            project.sentences_json = _safe_json_dumps(sentences)
            _append_log(project, f"自动拆句完成，共 {len(sentences)} 句。")
            db.commit()

        _raise_if_rough_cut_stop_requested(project_id)
        _set_processing(project, "assign_roles", 18, db, "开始分配角色。")
        roles = _safe_json_loads(project.roles_json, default_roles())
        settings_payload = _safe_json_loads(project.settings_json, default_render_settings())
        strategy = str(settings_payload.get("roleStrategy", "primary-first"))
        manual_seq = settings_payload.get("manualSequence")
        primary_role = str(settings_payload.get("primaryRoleId", "A"))
        sentences = assign_roles_to_sentences(sentences, roles, strategy, manual_seq, primary_role)
        project.sentences_json = _safe_json_dumps(sentences)
        db.commit()

        _raise_if_rough_cut_stop_requested(project_id)
        _set_processing(project, "build_timeline", 36, db, "开始选片并生成时间线。")
        assets = _safe_json_loads(project.assets_json, [])
        if not assets:
            raise ValueError("请先上传至少一个角色素材。")
        sentences, timeline = build_timeline(sentences, assets, recalculate_durations=True)
        project.sentences_json = _safe_json_dumps(sentences)
        project.timeline_json = _safe_json_dumps(timeline)
        _append_log(project, f"时间线生成完成，共 {len(timeline)} 段。")
        db.commit()

        _raise_if_rough_cut_stop_requested(project_id)
        _set_processing(project, "render_preview", 65, db, "开始渲染视频。")
        out_path = _render_timeline(settings, project, timeline, settings_payload, mode)

        if mode == "preview":
            project.preview_path = out_path
        else:
            project.output_path = out_path
            if previous_output_path and previous_output_path != out_path:
                _safe_remove_path(previous_output_path)

        project.status = ROUGH_CUT_STATUS_READY
        project.phase = "completed"
        project.progress = 100
        project.error_message = None
        _append_log(project, f"视频导出完成：{Path(out_path).name}")
        db.commit()
    except RoughCutStopRequested as exc:
        project = db.query(RoughCutProject).filter(RoughCutProject.id == project_id).first()
        if project:
            _mark_project_stopped(db, project, str(exc) or "已停止当前生成任务。")
        _clear_rough_cut_stop_requested(project_id)
    except Exception as exc:
        project = db.query(RoughCutProject).filter(RoughCutProject.id == project_id).first()
        if project:
            project.status = ROUGH_CUT_STATUS_ERROR
            project.phase = "failed"
            project.progress = 100
            project.error_message = _repair_text_if_needed(str(exc))
            _append_log(project, f"失败：{str(exc)}")
            db.commit()
    finally:
        _clear_rough_cut_stop_requested(project_id)
        db.close()
        _finish_processing(project_id)


def ensure_project_exists(db: Session, project_id: int) -> RoughCutProject:
    project = db.query(RoughCutProject).filter(RoughCutProject.id == project_id).first()
    if not project:
        raise ValueError("粗剪项目不存在。")
    return project


def regenerate_one_sentence(db: Session, project: RoughCutProject, sentence_id: str) -> RoughCutProject:
    sentences = _safe_json_loads(project.sentences_json, [])
    if not any(item.get("id") == sentence_id for item in sentences):
        raise ValueError("句子不存在。")
    # V1：单句重生成触发时间线重建，保留其它句子配置（角色/时长/锁定）。
    return build_project_timeline(db, project, recalculate_durations=False)


def append_assets(
    db: Session,
    settings: Settings,
    project: RoughCutProject,
    *,
    role_id: str,
    files: list[tuple[str, bytes]],
) -> tuple[RoughCutProject, list[dict]]:
    if not files:
        raise ValueError("请至少上传一个素材文件。")
    role = (role_id or "A").strip() or "A"
    assets = _safe_json_loads(project.assets_json, [])
    asset_root = settings.data_dir / "uploads" / "rough_cut_assets" / f"project_{project.id}" / role
    asset_root.mkdir(parents=True, exist_ok=True)

    valid_files: list[tuple[str, bytes]] = []
    for filename, payload in files:
        safe_name = Path(filename or "").name
        if safe_name and payload:
            valid_files.append((safe_name, payload))
    if not valid_files:
        raise ValueError("未识别到有效视频文件。")

    appended_assets: list[dict] = []
    for safe_name, payload in valid_files:
        file_path = asset_root / f"{uuid4().hex[:8]}_{safe_name}"
        file_path.write_bytes(payload)
        try:
            probe = probe_video(settings, file_path.as_posix())
        except Exception as exc:
            try:
                if file_path.exists():
                    file_path.unlink()
            except Exception:
                pass
            raise ValueError(f"上传文件不可用：{safe_name}") from exc

        appended_assets.append(
            {
                "id": uuid4().hex[:12],
                "roleId": role,
                "fileName": safe_name,
                "filePath": file_path.as_posix(),
                "duration": round(float(probe.duration or 0.0), 3),
                "width": int(probe.width),
                "height": int(probe.height),
                "asrStatus": "pending",
                "asrProgress": 0,
                "asrError": None,
                "asrSrtPath": None,
                "asrStartSeconds": 0.0,
                "asrEndSeconds": 0.0,
                "asrDuration": 0.0,
                "manualGatePassed": False,
                "matchedChars": 0,
                "srtTotalChars": 0,
                "unmatchedChars": 0,
                "matchPercent": 0.0,
                "errorPercent": 100.0,
                "gatePassed": False,
            }
        )

    next_assets = [*assets, *appended_assets]

    if not next_assets:
        raise ValueError("未识别到有效视频素材。")

    project.assets_json = _safe_json_dumps(next_assets)
    _reset_project_timeline_for_asset_change(project)
    _append_log(
        project,
        f"角色 {role} 素材上传完成，新增 {len(appended_assets)} 个，当前项目总素材 {len(next_assets)} 个。",
    )
    db.commit()
    db.refresh(project)
    return project, appended_assets


def _reset_project_timeline_for_asset_change(project: RoughCutProject) -> None:
    sentences = _safe_json_loads(project.sentences_json, [])
    for sentence in sentences:
        sentence["clipId"] = None
    project.sentences_json = _safe_json_dumps(sentences)
    project.timeline_json = "[]"
    project.preview_path = None
    project.output_path = None
    project.status = ROUGH_CUT_STATUS_IDLE
    project.phase = "assets_changed"
    project.progress = 0
    project.error_message = None


def delete_asset(
    db: Session,
    project: RoughCutProject,
    *,
    asset_id: str,
) -> RoughCutProject:
    assets = _safe_json_loads(project.assets_json, [])
    kept_assets: list[dict] = []
    removed_asset: dict | None = None
    for asset in assets:
        if str(asset.get("id", "")).strip() == asset_id and removed_asset is None:
            removed_asset = asset
            continue
        kept_assets.append(asset)

    if removed_asset is None:
        raise ValueError("素材不存在。")

    removed_path = str(removed_asset.get("filePath") or "").strip()
    if removed_path:
        still_used = any(str(item.get("filePath") or "").strip() == removed_path for item in kept_assets)
        if not still_used:
            try:
                file_path = Path(removed_path)
                if file_path.exists():
                    file_path.unlink()
            except Exception:
                pass
    removed_asr_srt_path = str(removed_asset.get("asrSrtPath") or "").strip()
    if removed_asr_srt_path:
        try:
            asr_srt_path = Path(removed_asr_srt_path)
            if asr_srt_path.exists():
                asr_srt_path.unlink()
        except Exception:
            pass

    project.assets_json = _safe_json_dumps(kept_assets)
    _reset_project_timeline_for_asset_change(project)
    _append_log(project, f"素材已删除：{removed_asset.get('fileName', asset_id)}")
    db.commit()
    db.refresh(project)
    return project


def _safe_remove_path(path_like: str | None) -> None:
    path_str = str(path_like or "").strip()
    if not path_str:
        return
    try:
        path = Path(path_str)
        if path.is_file():
            path.unlink(missing_ok=True)
        elif path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


def delete_project(db: Session, settings: Settings, project: RoughCutProject) -> None:
    assets = _safe_json_loads(project.assets_json, [])
    for asset in assets:
        _safe_remove_path(asset.get("filePath"))
        _safe_remove_path(asset.get("asrSrtPath"))

    _safe_remove_path(project.preview_path)
    _safe_remove_path(project.output_path)

    project_asset_dir = settings.data_dir / "uploads" / "rough_cut_assets" / f"project_{project.id}"
    project_subtitle_dir = settings.data_dir / "uploads" / "rough_cut_subtitles" / f"project_{project.id}"
    _safe_remove_path(project_asset_dir.as_posix())
    _safe_remove_path(project_subtitle_dir.as_posix())

    db.delete(project)
    db.commit()


def set_asset_manual_gate(
    db: Session,
    project: RoughCutProject,
    *,
    asset_id: str,
    manual_passed: bool,
) -> RoughCutProject:
    assets = [_ensure_asset_defaults(item) for item in _safe_json_loads(project.assets_json, [])]
    target: dict | None = None
    for asset in assets:
        if str(asset.get("id", "")).strip() == str(asset_id).strip():
            target = asset
            break

    if target is None:
        raise ValueError("素材不存在。")

    target["manualGatePassed"] = bool(manual_passed)
    project.assets_json = _safe_json_dumps(assets)
    _append_log(
        project,
        f"素材 {target.get('fileName', asset_id)} 手动通过已{'开启' if manual_passed else '关闭'}。",
    )
    db.commit()
    db.refresh(project)
    return project

