from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import Settings
from ..dependencies import get_app_settings, get_db
from ..models.rough_cut_project import RoughCutProject
from ..schemas.common import MessageResponse
from ..schemas.rough_cut import (
    AssignRolesRequest,
    BuildTimelineRequest,
    CompareProjectResponse,
    CreateProjectRequest,
    ExportRequest,
    ListProjectsResponse,
    RoleAsset,
    RoughCutProjectResponse,
    SplitScriptRequest,
    StatusResponse,
    UpdateAssetManualGateRequest,
    UpdateProjectRequest,
    UpdateSentenceRequest,
    UpdateSettingsRequest,
)
from ..services.rough_cut_service import (
    append_assets,
    assign_project_roles,
    build_project_compare_payload,
    build_project_timeline,
    create_project,
    delete_project,
    delete_asset,
    ensure_project_exists,
    is_rough_cut_enabled,
    patch_project,
    project_to_payload,
    regenerate_one_sentence,
    request_stop_project_export,
    schedule_project_auto_preview,
    schedule_asr_for_rough_cut_asset,
    set_asset_manual_gate,
    split_project_script,
    start_export_job,
    update_project_settings,
    update_sentence,
)


router = APIRouter(prefix="/api/rough-cut", tags=["rough-cut"])


def _serialize_project(project: RoughCutProject) -> RoughCutProjectResponse:
    return RoughCutProjectResponse(**project_to_payload(project))


def _safe_get_project(db: Session, project_id: int) -> RoughCutProject:
    try:
        return ensure_project_exists(db, project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _normalize_export_mode(mode: str) -> str:
    value = (mode or "").strip().lower()
    return "final" if value == "final" else "preview"


@router.get("/projects", response_model=ListProjectsResponse)
async def api_list_projects(db: Session = Depends(get_db)):
    items = (
        db.query(RoughCutProject)
        .order_by(RoughCutProject.updated_at.desc(), RoughCutProject.id.desc())
        .all()
    )
    return ListProjectsResponse(items=[_serialize_project(item) for item in items])


@router.post("/projects", response_model=RoughCutProjectResponse)
async def api_create_project(
    payload: CreateProjectRequest,
    db: Session = Depends(get_db),
):
    try:
        project = create_project(
            db,
            title=payload.title,
            script=payload.script,
            script_file_name=payload.scriptFileName,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_project(project)


@router.get("/projects/{project_id}", response_model=RoughCutProjectResponse)
async def api_get_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    return _serialize_project(project)


@router.patch("/projects/{project_id}", response_model=RoughCutProjectResponse)
async def api_patch_project(
    project_id: int,
    payload: UpdateProjectRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    project = _safe_get_project(db, project_id)
    try:
        project = patch_project(
            db,
            project,
            patch=payload.model_dump(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    schedule_project_auto_preview(settings, project_id=project.id)
    return _serialize_project(project)


@router.delete("/projects/{project_id}", response_model=MessageResponse)
async def api_delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    project = _safe_get_project(db, project_id)
    delete_project(db, settings, project)
    return MessageResponse(message="项目已删除")


@router.post("/projects/{project_id}/assets", response_model=RoughCutProjectResponse)
async def api_upload_assets(
    project_id: int,
    role_id: str = Form(...),
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    project = _safe_get_project(db, project_id)
    try:
        payload_files: list[tuple[str, bytes]] = []
        for upload in files:
            content = await upload.read()
            payload_files.append((upload.filename or "asset.mp4", content))
        project, appended_assets = append_assets(
            db,
            settings,
            project,
            role_id=role_id,
            files=payload_files,
        )
        for asset in appended_assets:
            schedule_asr_for_rough_cut_asset(
                settings,
                project_id=project.id,
                asset_id=str(asset.get("id") or ""),
            )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_project(project)


@router.get("/projects/{project_id}/assets", response_model=list[RoleAsset])
async def api_list_assets(
    project_id: int,
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    payload = project_to_payload(project)
    return payload.get("assets") or []


@router.get("/projects/{project_id}/compare", response_model=CompareProjectResponse)
async def api_project_compare(
    project_id: int,
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    return CompareProjectResponse(**build_project_compare_payload(project))


@router.delete("/projects/{project_id}/assets/{asset_id}", response_model=RoughCutProjectResponse)
async def api_delete_asset(
    project_id: int,
    asset_id: str,
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    try:
        project = delete_asset(
            db,
            project,
            asset_id=asset_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_project(project)


@router.patch("/projects/{project_id}/assets/{asset_id}/manual-gate", response_model=RoughCutProjectResponse)
async def api_update_asset_manual_gate(
    project_id: int,
    asset_id: str,
    payload: UpdateAssetManualGateRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    project = _safe_get_project(db, project_id)
    try:
        project = set_asset_manual_gate(
            db,
            project,
            asset_id=asset_id,
            manual_passed=bool(payload.manualPassed),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    schedule_project_auto_preview(settings, project_id=project.id)
    return _serialize_project(project)


@router.get("/projects/{project_id}/assets/{asset_id}/media")
async def api_asset_media(
    project_id: int,
    asset_id: str,
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    payload = project_to_payload(project)
    assets = payload.get("assets") or []
    target = next((item for item in assets if str(item.get("id", "")).strip() == asset_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail="素材不存在")

    file_path = Path(str(target.get("filePath", "")).strip())
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="素材文件不存在")
    return FileResponse(file_path.as_posix(), filename=file_path.name)


@router.post("/projects/{project_id}/split-script", response_model=RoughCutProjectResponse)
async def api_split_script(
    project_id: int,
    payload: SplitScriptRequest,
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    project = split_project_script(db, project, payload.script)
    return _serialize_project(project)


@router.post("/projects/{project_id}/assign-roles", response_model=RoughCutProjectResponse)
async def api_assign_roles(
    project_id: int,
    payload: AssignRolesRequest,
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    project = assign_project_roles(
        db,
        project,
        strategy=payload.strategy,
        manual_sequence=payload.manualSequence,
        primary_role_id=payload.primaryRoleId,
    )
    return _serialize_project(project)


@router.put("/projects/{project_id}/settings", response_model=RoughCutProjectResponse)
async def api_update_settings(
    project_id: int,
    payload: UpdateSettingsRequest,
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    project = update_project_settings(
        db,
        project,
        settings_payload=payload.settings.model_dump(),
    )
    return _serialize_project(project)


@router.post("/projects/{project_id}/build-timeline", response_model=RoughCutProjectResponse)
async def api_build_timeline(
    project_id: int,
    payload: BuildTimelineRequest,
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    try:
        project = build_project_timeline(
            db,
            project,
            recalculate_durations=payload.recalculateDurations,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_project(project)


@router.patch(
    "/projects/{project_id}/sentences/{sentence_id}",
    response_model=RoughCutProjectResponse,
)
async def api_update_sentence(
    project_id: int,
    sentence_id: str,
    payload: UpdateSentenceRequest,
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    try:
        project = update_sentence(
            db,
            project,
            sentence_id=sentence_id,
            role_id=payload.roleId,
            estimated_duration=payload.estimatedDuration,
            locked=payload.locked,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_project(project)


@router.post(
    "/projects/{project_id}/regenerate-sentence/{sentence_id}",
    response_model=RoughCutProjectResponse,
)
async def api_regenerate_sentence(
    project_id: int,
    sentence_id: str,
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    try:
        project = regenerate_one_sentence(db, project, sentence_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_project(project)


@router.post("/projects/{project_id}/export", response_model=MessageResponse)
async def api_export_project(
    project_id: int,
    payload: ExportRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    project = _safe_get_project(db, project_id)
    enabled, reason = is_rough_cut_enabled(project)
    if not enabled:
        raise HTTPException(status_code=400, detail=reason or "匹配率未达到80%，暂不可执行混剪")
    mode = _normalize_export_mode(payload.mode)
    start_export_job(settings, project_id, mode)
    if mode == "final":
        return MessageResponse(message="已开始导出 MP4")
    return MessageResponse(message="已开始生成预览")


@router.post("/projects/{project_id}/stop", response_model=RoughCutProjectResponse)
async def api_stop_project(
    project_id: int,
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    project = request_stop_project_export(db, project)
    return _serialize_project(project)


@router.get("/projects/{project_id}/status", response_model=StatusResponse)
async def api_project_status(
    project_id: int,
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    payload = project_to_payload(project)
    return StatusResponse(
        status=payload["status"],
        progress=payload["progress"],
        pipelineProgress=payload.get("pipelineProgress", payload["progress"]),
        rolesAsrProgress=payload.get("rolesAsrProgress") or [],
        roughCutEnabled=bool(payload.get("roughCutEnabled")),
        roughCutEnabledReason=payload.get("roughCutEnabledReason"),
        phase=payload.get("phase"),
        error=payload.get("error"),
        previewUrl=payload.get("previewUrl"),
        outputUrl=payload.get("outputUrl"),
        log=payload.get("log") or "",
    )


@router.get("/projects/{project_id}/media")
async def api_project_media(
    project_id: int,
    type: str = "preview",
    db: Session = Depends(get_db),
):
    project = _safe_get_project(db, project_id)
    media_type = (type or "").strip().lower()
    if media_type == "output":
        path = project.output_path
    else:
        path = project.preview_path

    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="媒体文件不存在")
    return FileResponse(path, filename=Path(path).name)
