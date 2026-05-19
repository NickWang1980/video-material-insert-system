"""日志查看器：聚合 4 类日志源并提供 list / tail / download。

类别：
  asr        — data/outputs/logs/asr_*.log    (loguru，10MB 轮转，仅 asr_service)
  task       — data/outputs/logs/task_*.txt   (FFmpeg stdout/stderr + 业务消息)
  app        — data/outputs/logs/app_*.log    (loguru，10MB 轮转，非 ASR 全部)
  rough_cut  — DB RoughCutProject.log_text    (按项目存)

设计要点：
  - tail 使用 collections.deque(maxlen=N) 流式读，O(N) 内存即可处理 GB 级文件。
  - 文件名当 item_id；为防路径穿越，路径校验严格走 LOGS_DIR 下白名单。
"""
from __future__ import annotations

import collections
from dataclasses import dataclass
from pathlib import Path

from ..models.database import SessionLocal
from ..models.rough_cut_project import RoughCutProject

CATEGORY_ASR = "asr"
CATEGORY_TASK = "task"
CATEGORY_APP = "app"
CATEGORY_ROUGH_CUT = "rough_cut"
CATEGORY_COPY_GEN = "copy_gen"
CATEGORY_TTS = "tts"
CATEGORY_VIDEO_GEN = "video_gen"

_FILE_CATEGORIES = {
    CATEGORY_COPY_GEN: ("文案生成", "copy_gen_*.log"),
    CATEGORY_TTS: ("语音生成", "tts_*.log"),
    CATEGORY_VIDEO_GEN: ("视频生成", "video_gen_*.log"),
    CATEGORY_ASR: ("ASR", "asr_*.log"),
    CATEGORY_TASK: ("任务（FFmpeg）", "task_*.txt"),
    CATEGORY_APP: ("系统", "app_*.log"),
}
_DB_CATEGORIES = {
    CATEGORY_ROUGH_CUT: ("混剪", None),
}


@dataclass
class LogItem:
    id: str
    name: str
    size_bytes: int
    mtime_ts: float


def _logs_dir(data_dir: Path) -> Path:
    return data_dir / "outputs" / "logs"


def list_categories(data_dir: Path) -> list[dict]:
    out: list[dict] = []
    log_dir = _logs_dir(data_dir)

    for key, (label, pattern) in _FILE_CATEGORIES.items():
        files = list(log_dir.glob(pattern)) if log_dir.exists() else []
        out.append({
            "key": key,
            "label": label,
            "kind": "file",
            "item_count": len(files),
            "total_bytes": sum(f.stat().st_size for f in files if f.is_file()),
        })

    for key, (label, _) in _DB_CATEGORIES.items():
        if key == CATEGORY_ROUGH_CUT:
            db = SessionLocal()
            try:
                projects = db.query(RoughCutProject).all()
                count = sum(1 for p in projects if (p.log_text or "").strip())
                total = sum(len((p.log_text or "").encode("utf-8")) for p in projects)
            finally:
                db.close()
            out.append({
                "key": key,
                "label": label,
                "kind": "db",
                "item_count": count,
                "total_bytes": total,
            })

    return out


def list_items(data_dir: Path, category: str) -> list[dict]:
    if category in _FILE_CATEGORIES:
        _, pattern = _FILE_CATEGORIES[category]
        log_dir = _logs_dir(data_dir)
        if not log_dir.exists():
            return []
        files = sorted(
            (f for f in log_dir.glob(pattern) if f.is_file()),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        return [{
            "id": f.name,
            "name": f.name,
            "size_bytes": f.stat().st_size,
            "mtime_ts": f.stat().st_mtime,
        } for f in files]

    if category == CATEGORY_ROUGH_CUT:
        db = SessionLocal()
        try:
            projects = (
                db.query(RoughCutProject)
                .order_by(RoughCutProject.updated_at.desc())
                .all()
            )
            results: list[dict] = []
            for p in projects:
                text = p.log_text or ""
                if not text.strip():
                    continue
                results.append({
                    "id": str(p.id),
                    "name": (p.title or f"project_{p.id}"),
                    "size_bytes": len(text.encode("utf-8")),
                    "mtime_ts": p.updated_at.timestamp() if p.updated_at else 0.0,
                })
            return results
        finally:
            db.close()

    return []


def _resolve_file_path(data_dir: Path, category: str, item_id: str) -> Path:
    """安全地把 (category, item_id) 解析回文件路径，挡掉路径穿越。"""
    _, pattern = _FILE_CATEGORIES[category]
    log_dir = _logs_dir(data_dir).resolve()
    target = (log_dir / item_id).resolve()
    # 防穿越：必须在 log_dir 之内
    try:
        target.relative_to(log_dir)
    except ValueError:
        raise ValueError(f"非法 item_id: {item_id}")
    # 必须匹配 category 的 glob，避免跨类访问
    if not target.match(pattern):
        raise ValueError(f"item_id 与类别不匹配: {item_id} vs {pattern}")
    if not target.is_file():
        raise FileNotFoundError(f"日志文件不存在: {item_id}")
    return target


def tail_log(data_dir: Path, category: str, item_id: str, lines: int) -> dict:
    lines = max(1, min(lines, 100_000))

    if category in _FILE_CATEGORIES:
        path = _resolve_file_path(data_dir, category, item_id)
        size = path.stat().st_size
        # 流式 tail：deque 自动只保留末尾 N
        with path.open("r", encoding="utf-8", errors="replace") as f:
            tail = collections.deque(f, maxlen=lines)
        content = "".join(tail)
        return {
            "category": category,
            "item_id": item_id,
            "name": path.name,
            "size_bytes": size,
            "content": content,
            "is_truncated": size > len(content.encode("utf-8")),
            "shown_lines": len(tail),
        }

    if category == CATEGORY_ROUGH_CUT:
        try:
            project_id = int(item_id)
        except ValueError:
            raise ValueError(f"非法 project_id: {item_id}")
        db = SessionLocal()
        try:
            project = (
                db.query(RoughCutProject)
                .filter(RoughCutProject.id == project_id)
                .first()
            )
            if not project:
                raise FileNotFoundError(f"混剪项目不存在: {project_id}")
            full = project.log_text or ""
            full_lines = full.splitlines(keepends=True)
            shown = full_lines[-lines:] if len(full_lines) > lines else full_lines
            content = "".join(shown)
            return {
                "category": category,
                "item_id": item_id,
                "name": project.title or f"project_{project.id}",
                "size_bytes": len(full.encode("utf-8")),
                "content": content,
                "is_truncated": len(full_lines) > len(shown),
                "shown_lines": len(shown),
            }
        finally:
            db.close()

    raise ValueError(f"未知类别: {category}")


def read_full(data_dir: Path, category: str, item_id: str) -> tuple[bytes, str]:
    """返回 (bytes, 建议的下载文件名)"""
    if category in _FILE_CATEGORIES:
        path = _resolve_file_path(data_dir, category, item_id)
        return path.read_bytes(), path.name

    if category == CATEGORY_ROUGH_CUT:
        try:
            project_id = int(item_id)
        except ValueError:
            raise ValueError(f"非法 project_id: {item_id}")
        db = SessionLocal()
        try:
            project = (
                db.query(RoughCutProject)
                .filter(RoughCutProject.id == project_id)
                .first()
            )
            if not project:
                raise FileNotFoundError(f"混剪项目不存在: {project_id}")
            content = (project.log_text or "").encode("utf-8")
            safe_name = (project.title or f"project_{project.id}").strip()
            for ch in '\\/:*?"<>|':
                safe_name = safe_name.replace(ch, "_")
            return content, f"rough_cut_{project.id}_{safe_name}.log"
        finally:
            db.close()

    raise ValueError(f"未知类别: {category}")
