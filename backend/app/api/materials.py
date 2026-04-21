from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..config import Settings
from ..dependencies import get_app_settings, get_db
from ..models.material import Material
from ..schemas.common import MessageResponse
from ..schemas.material import MaterialRenameRequest, MaterialResponse
from ..utils.file_utils import classify_material_subdir, normalize_storage_path


router = APIRouter(prefix="/api/materials", tags=["materials"])


@router.post("", response_model=dict)
async def upload_materials(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    results = {"success": [], "failed": []}
    for f in files:
        existing = db.query(Material).filter(Material.file_name == f.filename).first()
        if existing:
            results["failed"].append({"file": f.filename, "reason": "素材文件名已存在"})
            continue

        subdir = classify_material_subdir(f.filename)
        dst = settings.data_dir / "uploads" / "materials" / subdir / f.filename
        dst.parent.mkdir(parents=True, exist_ok=True)
        with dst.open("wb") as out:
            out.write(await f.read())

        size = dst.stat().st_size
        if subdir == "images":
            file_type = "image"
        elif subdir == "gifs":
            file_type = "gif"
        elif subdir == "audios":
            file_type = "audio"
        else:
            file_type = "video"
        material = Material(
            file_name=f.filename,
            file_type=file_type,
            file_size=int(size),
            file_path=normalize_storage_path(dst),
        )
        db.add(material)
        db.commit()
        db.refresh(material)
        results["success"].append(MaterialResponse.model_validate(material).model_dump())

    return results


@router.get("", response_model=list[MaterialResponse])
async def list_materials(
    file_type: str | None = None, db: Session = Depends(get_db)
):
    q = db.query(Material)
    if file_type:
        q = q.filter(Material.file_type == file_type)
    return q.order_by(Material.id.desc()).all()


@router.get("/{material_id}/preview")
async def preview_material(material_id: int, db: Session = Depends(get_db)):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="素材不存在")
    if not os.path.exists(material.file_path):
        raise HTTPException(status_code=404, detail="素材文件不存在")
    media_type, _ = mimetypes.guess_type(material.file_path)
    return FileResponse(
        material.file_path,
        media_type=media_type or "application/octet-stream",
        filename=Path(material.file_path).name,
    )


@router.put("/{material_id}", response_model=MaterialResponse)
async def rename_material(
    material_id: int,
    payload: MaterialRenameRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="素材不存在")

    new_name = payload.new_file_name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="新文件名不能为空")
    existing = db.query(Material).filter(Material.file_name == new_name).first()
    if existing:
        raise HTTPException(status_code=400, detail="素材文件名已存在")

    src = Path(material.file_path)
    subdir = classify_material_subdir(new_name)
    dst = settings.data_dir / "uploads" / "materials" / subdir / new_name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        src.rename(dst)

    material.file_name = new_name
    material.file_path = normalize_storage_path(dst)
    db.commit()
    db.refresh(material)
    return material


@router.delete("/{material_id}", response_model=MessageResponse)
async def delete_material(material_id: int, db: Session = Depends(get_db)):
    material = db.query(Material).filter(Material.id == material_id).first()
    if not material:
        raise HTTPException(status_code=404, detail="素材不存在")
    try:
        if os.path.exists(material.file_path):
            os.remove(material.file_path)
    except Exception:
        pass
    db.delete(material)
    db.commit()
    return MessageResponse(message="素材已删除")
