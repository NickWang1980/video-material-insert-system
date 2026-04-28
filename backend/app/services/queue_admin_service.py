"""队列管理：盘点 / 清空 ASR 与 FFmpeg 队列。

队列按来源分两类：
  - ASR：源视频 ASR (SourceVideoEntry) + 混剪角色素材 ASR (RoughCutProject.assets_json)
  - FFmpeg：素材插入任务 (Task) + 混剪导出 (RoughCutProject.status='processing')

清空策略：
  - ASR：pending 直接置 failed；running 标记 failed（实际 CTranslate2 转写不可中断，
         结果即便完成也不会被回写——状态已变）。
  - FFmpeg：调用现有 request_stop_task / request_stop_project_export，
            它们会 terminate 子进程并标记 stopped。
"""
from __future__ import annotations

import json
from datetime import datetime

from ..models.database import SessionLocal
from ..models.rough_cut_project import RoughCutProject
from ..models.source_video_entry import SourceVideoEntry
from ..models.task import Task
from ..utils.logger import get_logger
from . import rough_cut_service as _rc_svc
from . import task_service as _task_svc

logger = get_logger()

_ASR_CLEAR_NOTE = "已被用户清空 ASR 队列"


def list_asr_queue() -> dict:
    items: list[dict] = []
    db = SessionLocal()
    try:
        # 源视频 ASR
        source_entries = (
            db.query(SourceVideoEntry)
            .filter(SourceVideoEntry.asr_status.in_(["pending", "running"]))
            .order_by(SourceVideoEntry.id)
            .all()
        )
        for entry in source_entries:
            items.append({
                "kind": "source_video",
                "ref_id": entry.id,
                "name": entry.name or f"source_{entry.id}",
                "status": (entry.asr_status or "pending").lower(),
                "progress": int(entry.asr_progress or 0),
                "model": entry.asr_model_used or "",
                "extra": (entry.asr_error or "")[:200],
            })

        # 混剪 ASR — 遍历每个项目的 assets_json
        projects = db.query(RoughCutProject).order_by(RoughCutProject.id).all()
        for project in projects:
            try:
                assets = json.loads(project.assets_json or "[]")
            except Exception:
                continue
            if not isinstance(assets, list):
                continue
            for asset in assets:
                if not isinstance(asset, dict):
                    continue
                role_assets = asset.get("roleAssets") or {}
                if not isinstance(role_assets, dict):
                    continue
                for role_id, role_asset in role_assets.items():
                    if not isinstance(role_asset, dict):
                        continue
                    status = str(role_asset.get("asrStatus") or "").strip().lower()
                    if status not in ("pending", "running"):
                        continue
                    file_name = role_asset.get("fileName") or role_asset.get("name") or role_id
                    items.append({
                        "kind": "rough_cut_asset",
                        "ref_id": project.id,
                        "name": f"{project.title or '混剪项目'} · {file_name}",
                        "status": status,
                        "progress": int(role_asset.get("asrProgress") or 0),
                        "model": project.asr_model_used or "",
                        "extra": str(role_asset.get("asrError") or "")[:200],
                    })
    finally:
        db.close()

    pending = sum(1 for i in items if i["status"] == "pending")
    running = sum(1 for i in items if i["status"] == "running")
    return {
        "items": items,
        "pending_count": pending,
        "running_count": running,
        "total_count": len(items),
    }


def clear_asr_queue() -> dict:
    cancelled_source = 0
    cancelled_rough = 0

    db = SessionLocal()
    try:
        # 源视频
        source_entries = (
            db.query(SourceVideoEntry)
            .filter(SourceVideoEntry.asr_status.in_(["pending", "running"]))
            .all()
        )
        for entry in source_entries:
            entry.asr_status = "failed"
            entry.asr_progress = 100
            entry.asr_error = _ASR_CLEAR_NOTE
            # 把重试次数顶到上限，确保 resume_pending_asr_jobs 不会自动重排
            entry.asr_retry_count = max(
                int(entry.asr_retry_count or 0),
                int(entry.asr_retry_max or 3),
            )
            cancelled_source += 1

        # 混剪
        projects = db.query(RoughCutProject).all()
        for project in projects:
            try:
                assets = json.loads(project.assets_json or "[]")
            except Exception:
                continue
            if not isinstance(assets, list):
                continue
            modified = False
            for asset in assets:
                if not isinstance(asset, dict):
                    continue
                role_assets = asset.get("roleAssets") or {}
                if not isinstance(role_assets, dict):
                    continue
                for role_asset in role_assets.values():
                    if not isinstance(role_asset, dict):
                        continue
                    status = str(role_asset.get("asrStatus") or "").strip().lower()
                    if status in ("pending", "running"):
                        role_asset["asrStatus"] = "failed"
                        role_asset["asrProgress"] = 100
                        role_asset["asrError"] = _ASR_CLEAR_NOTE
                        cancelled_rough += 1
                        modified = True
            if modified:
                project.assets_json = json.dumps(assets, ensure_ascii=False)

        db.commit()

        # 清空内存中的混剪 ASR 排队集合（不含运行中线程；线程会自然结束并自行 discard）
        try:
            with _rc_svc._asr_queued_lock:
                _rc_svc._asr_queued_jobs.clear()
        except Exception:
            logger.exception("清空 _asr_queued_jobs 失败")
    finally:
        db.close()

    return {
        "cancelled_source_count": cancelled_source,
        "cancelled_rough_cut_count": cancelled_rough,
        "total_cancelled": cancelled_source + cancelled_rough,
        "note": "运行中的转写任务会自然完成，但状态已置为 failed 不会保留结果；待处理任务已取消。",
    }


def list_ffmpeg_queue() -> dict:
    items: list[dict] = []
    db = SessionLocal()
    try:
        # 素材插入任务
        tasks = (
            db.query(Task)
            .filter(Task.status.in_(["pending", "processing"]))
            .order_by(Task.id)
            .all()
        )
        for task in tasks:
            items.append({
                "kind": "task",
                "ref_id": task.id,
                "name": task.task_name or f"task_{task.id}",
                "status": (task.status or "pending").lower(),
                "progress": int(task.progress or 0),
                "extra": "",
            })

        # 混剪导出
        rc_projects = (
            db.query(RoughCutProject)
            .filter(RoughCutProject.status == _rc_svc.ROUGH_CUT_STATUS_PROCESSING)
            .order_by(RoughCutProject.id)
            .all()
        )
        for project in rc_projects:
            items.append({
                "kind": "rough_cut",
                "ref_id": project.id,
                "name": project.title or f"project_{project.id}",
                "status": "processing",
                "progress": int(project.progress or 0),
                "extra": str(project.phase or "")[:80],
            })
    finally:
        db.close()

    pending = sum(1 for i in items if i["status"] == "pending")
    running = sum(1 for i in items if i["status"] == "processing")
    return {
        "items": items,
        "pending_count": pending,
        "running_count": running,
        "total_count": len(items),
    }


def clear_ffmpeg_queue() -> dict:
    stopped_tasks = 0
    stopped_projects = 0

    db = SessionLocal()
    try:
        # 素材插入任务
        tasks = (
            db.query(Task)
            .filter(Task.status.in_(["pending", "processing"]))
            .all()
        )
        for task in tasks:
            try:
                _task_svc.request_stop_task(task.id)
            except Exception:
                logger.exception(f"request_stop_task failed for task {task.id}")
            # pending 任务没有正在运行的子进程；直接置 stopped
            if (task.status or "").lower() == "pending":
                task.status = "stopped"
                task.completed_at = datetime.utcnow()
            stopped_tasks += 1
        db.commit()

        # 混剪导出
        rc_projects = (
            db.query(RoughCutProject)
            .filter(RoughCutProject.status == _rc_svc.ROUGH_CUT_STATUS_PROCESSING)
            .all()
        )
        for project in rc_projects:
            try:
                _rc_svc.request_stop_project_export(db, project)
            except Exception:
                logger.exception(f"request_stop_project_export failed for project {project.id}")
            stopped_projects += 1
    finally:
        db.close()

    return {
        "stopped_task_count": stopped_tasks,
        "stopped_rough_cut_count": stopped_projects,
        "total_stopped": stopped_tasks + stopped_projects,
        "note": "正在运行的 FFmpeg 子进程已 terminate；任务/项目状态已置为 stopped。",
    }
