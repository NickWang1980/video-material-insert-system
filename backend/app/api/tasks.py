from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from ..config import Settings
from ..dependencies import get_app_settings, get_db
from ..models.task import Task
from ..schemas.common import MessageResponse
from ..schemas.task import TaskResponse, TaskListResponse, SourceVideoRef
from ..services.task_service import (
    AsrSubtitleUnavailableError,
    SourceVideoEntryNotFoundError,
    TemplateKeywordConflictError,
    TemplateNotFoundError,
    create_task,
    get_task_source_templates,
    get_task_source_video,
    request_stop_task,
    resume_all_tasks,
    start_task_processing,
)
from ..services.video_service import probe_video


router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _gcd(a: int, b: int) -> int:
    while b:
        a, b = b, a % b
    return max(1, abs(a))


def _aspect_ratio_text(width: int, height: int) -> str:
    g = _gcd(width, height)
    return f"{width // g}:{height // g}"


def _task_to_response(task: Task, settings: Settings, db: Session) -> TaskResponse:
    width = None
    height = None
    aspect = None
    try:
        if task.video_path and os.path.exists(task.video_path):
            probe = probe_video(settings, task.video_path)
            width = int(probe.width)
            height = int(probe.height)
            aspect = _aspect_ratio_text(width, height)
    except Exception:
        pass

    source_video = get_task_source_video(db, task)
    source_video_ref = None
    if source_video:
        source_video_ref = SourceVideoRef(id=source_video["id"], name=source_video["name"])

    return TaskResponse(
        id=task.id,
        task_name=task.task_name,
        status=task.status,
        progress=task.progress,
        created_at=task.created_at,
        completed_at=task.completed_at,
        output_path=task.output_path,
        report_path=task.report_path,
        video_width=width,
        video_height=height,
        video_aspect_ratio=aspect,
        source_templates=get_task_source_templates(db, task.id),
        source_video=source_video_ref,
        subtitle_source=task.subtitle_source or "uploaded",
        add_subtitle_to_video=bool(task.add_subtitle_to_video),
    )


@router.post("", response_model=TaskResponse)
async def api_create_task(
    task_name: str = Form(...),
    source_entry_id: int = Form(...),
    config_ids: list[int] = Form(...),
    subtitle_source: str = Form("uploaded"),
    add_subtitle_to_video: bool = Form(False),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    try:
        task = create_task(
            settings=settings,
            db=db,
            task_name=task_name,
            source_entry_id=source_entry_id,
            config_ids=config_ids,
            subtitle_source=subtitle_source,
            add_subtitle_to_video=add_subtitle_to_video,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except SourceVideoEntryNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "源视频条目不存在",
                "source_entry_id": exc.source_entry_id,
            },
        ) from exc
    except TemplateNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={
                "message": "模板不存在",
                "missing_template_ids": exc.missing_template_ids,
            },
        ) from exc
    except TemplateKeywordConflictError as exc:
        conflicts = [
            {"keyword": keyword, "template_names": template_names}
            for keyword, template_names in exc.conflicts.items()
        ]
        raise HTTPException(
            status_code=400,
            detail={
                "message": "模板关键词冲突，请调整模板组合",
                "conflicts": conflicts,
            },
        ) from exc
    except AsrSubtitleUnavailableError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "ASR 字幕不可用",
                "source_entry_id": exc.source_entry_id,
                "reason": exc.reason,
            },
        ) from exc

    return _task_to_response(task, settings, db)


@router.get("", response_model=TaskListResponse)
async def api_list_tasks(
    skip: int = 0,
    limit: int = 100,
    status: str | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    query = db.query(Task)
    if status:
        query = query.filter(Task.status == status)
    total = query.count()
    items = query.order_by(Task.id.desc()).offset(skip).limit(limit).all()
    return TaskListResponse(
        items=[_task_to_response(task, settings, db) for task in items],
        total=total,
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def api_get_task(
    task_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_to_response(task, settings, db)


@router.post("/{task_id}/retry", response_model=MessageResponse)
async def api_retry_task(
    task_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    start_task_processing(settings, task_id)
    return MessageResponse(message="已重新开始处理任务")


@router.post("/{task_id}/stop", response_model=MessageResponse)
async def api_stop_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    if task.status not in {"pending", "processing"}:
        return MessageResponse(message=f"当前任务状态为 {task.status}，无需停止")

    action = request_stop_task(task_id)
    if action == "stopping":
        return MessageResponse(message="已发送停止指令，任务正在停止")
    return MessageResponse(message="已记录停止请求，任务将在启动/执行阶段尽快停止")


@router.post("/resume-all", response_model=dict)
async def api_resume_all(
    include_failed: bool = True,
    settings: Settings = Depends(get_app_settings),
):
    count = resume_all_tasks(settings, include_failed=include_failed)
    return {"resumed": count}


@router.delete("/{task_id}", response_model=MessageResponse)
async def api_delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    files_to_remove: list[str | None] = [task.output_path, task.report_path]
    if not task.source_entry_id:
        files_to_remove.extend([task.video_path, task.subtitle_path])

    for file_path in files_to_remove:
        if not file_path:
            continue
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass

    db.delete(task)
    db.commit()
    return MessageResponse(message="任务已删除")


@router.get("/{task_id}/output")
async def api_download_output(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.output_path or not os.path.exists(task.output_path):
        raise HTTPException(status_code=404, detail="成品文件不存在")
    return FileResponse(task.output_path, filename=Path(task.output_path).name)


@router.get("/{task_id}/report")
async def api_download_report(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    if not task.report_path or not os.path.exists(task.report_path):
        raise HTTPException(status_code=404, detail="报告文件不存在")
    return FileResponse(task.report_path, filename=Path(task.report_path).name)


@router.get("/{task_id}/log")
async def api_download_log(
    task_id: int,
    settings: Settings = Depends(get_app_settings),
):
    log_path = settings.data_dir / "outputs" / "logs" / f"task_{task_id}.txt"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="日志文件不存在")
    return FileResponse(str(log_path), filename=log_path.name)


@router.get("/{task_id}/log/text", response_class=PlainTextResponse)
async def api_get_log_text(
    task_id: int,
    settings: Settings = Depends(get_app_settings),
    tail_kb: int = 256,
):
    if tail_kb < 1:
        tail_kb = 1
    if tail_kb > 2048:
        tail_kb = 2048

    log_path = settings.data_dir / "outputs" / "logs" / f"task_{task_id}.txt"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail="日志文件不存在")

    data = log_path.read_bytes()
    limit = tail_kb * 1024
    if len(data) > limit:
        data = data[-limit:]
    text = data.decode("utf-8", errors="replace")
    return PlainTextResponse(text, media_type="text/plain; charset=utf-8")
