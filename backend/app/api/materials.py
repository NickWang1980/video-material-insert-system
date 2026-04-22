from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from ..config import Settings
from ..dependencies import get_app_settings, get_db
from ..models.material import Material
from ..models.material_folder_binding import MaterialFolderBinding
from ..models.material_product import MaterialProduct
from ..models.material_script_folder import MaterialScriptFolder
from ..schemas.common import MessageResponse
from ..schemas.material import (
    MaterialFilePayload,
    MaterialFolderLink,
    MaterialProductPayload,
    MaterialProductResponse,
    MaterialRenameRequest,
    MaterialResponse,
    MaterialScriptFolderPayload,
    MaterialScriptFolderResponse,
    MaterialTreeProductNode,
    MaterialTreeResponse,
    MaterialTreeScriptNode,
)
from ..services.video_service import strip_video_audio
from ..utils.file_utils import classify_material_subdir, normalize_storage_path


router = APIRouter(prefix="/api/materials", tags=["materials"])

LIBRARY_KIND_GENERAL = "general"
LIBRARY_KIND_PRODUCT = "product"
LIBRARY_KIND_UNFILED = "unfiled"
VALID_LIBRARY_KINDS = {LIBRARY_KIND_GENERAL, LIBRARY_KIND_PRODUCT, LIBRARY_KIND_UNFILED}
VALID_FILE_TARGET_TYPES = {LIBRARY_KIND_GENERAL, LIBRARY_KIND_UNFILED, "script"}


def _clean_name(value: str, field_name: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"{field_name}不能为空")
    if any(segment in cleaned for segment in ["..", "/", "\\"]):
        raise HTTPException(status_code=400, detail=f"{field_name}包含非法路径字符")
    return cleaned


def _validate_library_kind(value: str | None) -> str:
    normalized = (value or LIBRARY_KIND_UNFILED).strip().lower()
    if normalized not in VALID_LIBRARY_KINDS:
        raise HTTPException(status_code=400, detail="素材库分类仅支持 general/product/unfiled")
    return normalized


def _resolve_material_dir(
    settings: Settings,
    *,
    file_name: str,
    library_kind: str,
    product_name: str | None,
    script_folder_name: str | None,
):
    subdir = classify_material_subdir(file_name)
    root = settings.data_dir / "uploads" / "materials"
    if library_kind == LIBRARY_KIND_GENERAL:
        return root / "general" / subdir / file_name, subdir
    if library_kind == LIBRARY_KIND_UNFILED:
        return root / "unfiled" / subdir / file_name, subdir

    if not product_name or not script_folder_name:
        raise HTTPException(status_code=400, detail="产品分类素材需要有效目录")
    return root / "products" / product_name / script_folder_name / subdir / file_name, subdir


def _map_subdir_to_type(subdir: str) -> str:
    if subdir == "images":
        return "image"
    if subdir == "gifs":
        return "gif"
    if subdir == "audios":
        return "audio"
    return "video"


def _get_folder_links(db: Session, material_id: int) -> list[MaterialFolderLink]:
    rows = (
        db.query(MaterialFolderBinding, MaterialScriptFolder, MaterialProduct)
        .join(MaterialScriptFolder, MaterialScriptFolder.id == MaterialFolderBinding.script_folder_id)
        .join(MaterialProduct, MaterialProduct.id == MaterialScriptFolder.product_id)
        .filter(MaterialFolderBinding.material_id == material_id)
        .order_by(MaterialProduct.name.asc(), MaterialScriptFolder.name.asc())
        .all()
    )
    return [
        MaterialFolderLink(
            product_id=product.id,
            product_name=product.name,
            script_folder_id=script.id,
            script_folder_name=script.name,
        )
        for _, script, product in rows
    ]


def _serialize_material(db: Session, material: Material) -> MaterialResponse:
    product_name = (
        material.product.name
        if getattr(material, "product", None) is not None
        else material.product_name
    )
    script_folder_name = (
        material.script_folder_ref.name
        if getattr(material, "script_folder_ref", None) is not None
        else material.script_folder
    )
    return MaterialResponse(
        id=material.id,
        file_name=material.file_name,
        file_type=material.file_type,
        file_size=material.file_size,
        file_path=material.file_path,
        library_kind=material.library_kind,
        product_id=material.product_id,
        script_folder_id=material.script_folder_id,
        product_name=product_name,
        script_folder=script_folder_name,
        script_folder_name=script_folder_name,
        folder_links=_get_folder_links(db, material.id),
        audio_removed=material.audio_removed,
        created_at=material.created_at,
    )


def _ensure_folder_duplicate_safe(
    db: Session,
    *,
    script_folder_id: int,
    file_name: str,
    exclude_material_id: int | None = None,
):
    query = (
        db.query(Material)
        .join(MaterialFolderBinding, MaterialFolderBinding.material_id == Material.id)
        .filter(
            MaterialFolderBinding.script_folder_id == script_folder_id,
            Material.file_name == file_name,
        )
    )
    if exclude_material_id is not None:
        query = query.filter(Material.id != exclude_material_id)
    duplicate = query.first()
    if duplicate:
        raise HTTPException(status_code=400, detail="目标子文件夹下已存在同名素材")


@router.get("/tree", response_model=MaterialTreeResponse)
async def get_material_tree(db: Session = Depends(get_db)):
    products = (
        db.query(MaterialProduct)
        .options(joinedload(MaterialProduct.script_folders))
        .order_by(MaterialProduct.name.asc())
        .all()
    )
    product_nodes = []
    for product in products:
        scripts = sorted(product.script_folders, key=lambda item: item.name)
        product_nodes.append(
            MaterialTreeProductNode(
                id=product.id,
                name=product.name,
                scripts=[MaterialTreeScriptNode(id=s.id, name=s.name) for s in scripts],
            )
        )
    return MaterialTreeResponse(products=product_nodes)


@router.post("/products", response_model=MaterialProductResponse)
async def create_product(
    payload: MaterialProductPayload,
    db: Session = Depends(get_db),
):
    name = _clean_name(payload.name, "产品目录")
    exists = db.query(MaterialProduct).filter(MaterialProduct.name == name).first()
    if exists:
        raise HTTPException(status_code=400, detail="产品目录已存在")

    now = datetime.utcnow()
    product = MaterialProduct(name=name, created_at=now, updated_at=now)
    db.add(product)
    db.commit()
    db.refresh(product)
    return MaterialProductResponse(
        id=product.id,
        name=product.name,
        created_at=product.created_at,
        updated_at=product.updated_at,
        scripts=[],
    )


@router.put("/products/{product_id}", response_model=MaterialProductResponse)
async def rename_product(
    product_id: int,
    payload: MaterialProductPayload,
    db: Session = Depends(get_db),
):
    product = db.query(MaterialProduct).filter(MaterialProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品目录不存在")

    name = _clean_name(payload.name, "产品目录")
    exists = (
        db.query(MaterialProduct)
        .filter(MaterialProduct.name == name, MaterialProduct.id != product_id)
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="产品目录已存在")

    product.name = name
    product.updated_at = datetime.utcnow()
    materials = db.query(Material).filter(Material.product_id == product_id).all()
    for material in materials:
        material.product_name = name
    db.commit()
    db.refresh(product)

    scripts = (
        db.query(MaterialScriptFolder)
        .filter(MaterialScriptFolder.product_id == product.id)
        .order_by(MaterialScriptFolder.name.asc())
        .all()
    )
    return MaterialProductResponse(
        id=product.id,
        name=product.name,
        created_at=product.created_at,
        updated_at=product.updated_at,
        scripts=[
            MaterialScriptFolderResponse(
                id=s.id,
                product_id=s.product_id,
                name=s.name,
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in scripts
        ],
    )


@router.delete("/products/{product_id}", response_model=MessageResponse)
async def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(MaterialProduct).filter(MaterialProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品目录不存在")

    has_scripts = (
        db.query(MaterialScriptFolder)
        .filter(MaterialScriptFolder.product_id == product_id)
        .first()
        is not None
    )
    has_materials = (
        db.query(Material).filter(Material.product_id == product_id).first() is not None
    )
    if has_scripts or has_materials:
        raise HTTPException(status_code=400, detail="目录非空，请先清空子文件夹和素材")

    db.delete(product)
    db.commit()
    return MessageResponse(message="产品目录已删除")


@router.post("/products/{product_id}/scripts", response_model=MaterialScriptFolderResponse)
async def create_script_folder(
    product_id: int,
    payload: MaterialScriptFolderPayload,
    db: Session = Depends(get_db),
):
    product = db.query(MaterialProduct).filter(MaterialProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品目录不存在")

    name = _clean_name(payload.name, "脚本子文件夹")
    exists = (
        db.query(MaterialScriptFolder)
        .filter(
            MaterialScriptFolder.product_id == product_id,
            MaterialScriptFolder.name == name,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="脚本子文件夹已存在")

    now = datetime.utcnow()
    folder = MaterialScriptFolder(
        product_id=product_id,
        name=name,
        created_at=now,
        updated_at=now,
    )
    db.add(folder)
    db.commit()
    db.refresh(folder)

    return MaterialScriptFolderResponse(
        id=folder.id,
        product_id=folder.product_id,
        name=folder.name,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


@router.put("/scripts/{script_id}", response_model=MaterialScriptFolderResponse)
async def rename_script_folder(
    script_id: int,
    payload: MaterialScriptFolderPayload,
    db: Session = Depends(get_db),
):
    folder = db.query(MaterialScriptFolder).filter(MaterialScriptFolder.id == script_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="脚本子文件夹不存在")

    name = _clean_name(payload.name, "脚本子文件夹")
    exists = (
        db.query(MaterialScriptFolder)
        .filter(
            MaterialScriptFolder.product_id == folder.product_id,
            MaterialScriptFolder.name == name,
            MaterialScriptFolder.id != folder.id,
        )
        .first()
    )
    if exists:
        raise HTTPException(status_code=400, detail="脚本子文件夹已存在")

    folder.name = name
    folder.updated_at = datetime.utcnow()
    materials = db.query(Material).filter(Material.script_folder_id == folder.id).all()
    for material in materials:
        material.script_folder = name
    db.commit()
    db.refresh(folder)

    return MaterialScriptFolderResponse(
        id=folder.id,
        product_id=folder.product_id,
        name=folder.name,
        created_at=folder.created_at,
        updated_at=folder.updated_at,
    )


@router.delete("/scripts/{script_id}", response_model=MessageResponse)
async def delete_script_folder(script_id: int, db: Session = Depends(get_db)):
    folder = db.query(MaterialScriptFolder).filter(MaterialScriptFolder.id == script_id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="脚本子文件夹不存在")

    has_materials = (
        db.query(MaterialFolderBinding)
        .filter(MaterialFolderBinding.script_folder_id == script_id)
        .first()
        is not None
    )
    if has_materials:
        raise HTTPException(status_code=400, detail="目录非空，请先清空素材")

    db.delete(folder)
    db.commit()
    return MessageResponse(message="脚本子文件夹已删除")


@router.post("", response_model=dict)
async def upload_materials(
    files: list[UploadFile] = File(...),
    library_kind: str = Form(default=LIBRARY_KIND_UNFILED),
    script_folder_id: int | None = Form(default=None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    normalized_library = _validate_library_kind(library_kind)

    script_folder = None
    product = None
    if normalized_library == LIBRARY_KIND_PRODUCT:
        if not script_folder_id:
            raise HTTPException(status_code=400, detail="产品分类素材上传必须选择脚本子文件夹")
        script_folder = (
            db.query(MaterialScriptFolder)
            .filter(MaterialScriptFolder.id == int(script_folder_id))
            .first()
        )
        if not script_folder:
            raise HTTPException(status_code=404, detail="脚本子文件夹不存在")
        product = db.query(MaterialProduct).filter(MaterialProduct.id == script_folder.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="产品目录不存在")

    results = {"success": [], "failed": []}
    for upload in files:
        filename = (upload.filename or "").strip()
        if not filename:
            results["failed"].append({"file": "", "reason": "素材文件名不能为空"})
            continue

        existing = db.query(Material).filter(Material.file_name == filename).first()
        if existing:
            results["failed"].append({"file": filename, "reason": "素材文件名已存在"})
            continue

        dst, subdir = _resolve_material_dir(
            settings,
            file_name=filename,
            library_kind=normalized_library,
            product_name=product.name if product else None,
            script_folder_name=script_folder.name if script_folder else None,
        )
        dst.parent.mkdir(parents=True, exist_ok=True)

        audio_removed: bool | None = None
        if subdir == "videos":
            tmp = dst.parent / f".tmp_{uuid4().hex}_{filename}"
            try:
                with tmp.open("wb") as out:
                    out.write(await upload.read())
                strip_video_audio(
                    settings,
                    input_path=normalize_storage_path(tmp),
                    output_path=normalize_storage_path(dst),
                )
                audio_removed = True
            except Exception as exc:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
                if dst.exists():
                    dst.unlink(missing_ok=True)
                results["failed"].append({"file": filename, "reason": str(exc)})
                continue
            finally:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
        else:
            with dst.open("wb") as out:
                out.write(await upload.read())

        material = Material(
            file_name=filename,
            file_type=_map_subdir_to_type(subdir),
            file_size=int(dst.stat().st_size),
            file_path=normalize_storage_path(dst),
            library_kind=normalized_library,
            product_id=product.id if product else None,
            script_folder_id=script_folder.id if script_folder else None,
            product_name=product.name if product else None,
            script_folder=script_folder.name if script_folder else None,
            audio_removed=audio_removed,
        )
        db.add(material)
        db.commit()
        db.refresh(material)

        if script_folder is not None:
            db.add(
                MaterialFolderBinding(
                    material_id=material.id,
                    script_folder_id=script_folder.id,
                )
            )
            db.commit()
            db.refresh(material)

        results["success"].append(_serialize_material(db, material).model_dump())

    return results


@router.post("/{material_id}/file", response_model=MaterialResponse)
async def file_material(
    material_id: int,
    payload: MaterialFilePayload,
    db: Session = Depends(get_db),
):
    material = (
        db.query(Material)
        .options(joinedload(Material.product), joinedload(Material.script_folder_ref))
        .filter(Material.id == material_id)
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="素材不存在")

    target_type = (payload.target_type or "").strip().lower()
    if target_type not in VALID_FILE_TARGET_TYPES:
        raise HTTPException(status_code=400, detail="目标目录类型仅支持 general/unfiled/script")

    if target_type == LIBRARY_KIND_GENERAL:
        material.library_kind = LIBRARY_KIND_GENERAL
        material.product_id = None
        material.script_folder_id = None
        material.product_name = None
        material.script_folder = None
        db.commit()
        db.refresh(material)
        return _serialize_material(db, material)

    if target_type == LIBRARY_KIND_UNFILED:
        material.library_kind = LIBRARY_KIND_UNFILED
        material.product_id = None
        material.script_folder_id = None
        material.product_name = None
        material.script_folder = None
        db.commit()
        db.refresh(material)
        return _serialize_material(db, material)

    if not payload.script_folder_id:
        raise HTTPException(status_code=400, detail="归档到脚本子文件夹时必须提供 script_folder_id")

    script_folder = (
        db.query(MaterialScriptFolder)
        .filter(MaterialScriptFolder.id == int(payload.script_folder_id))
        .first()
    )
    if not script_folder:
        raise HTTPException(status_code=404, detail="脚本子文件夹不存在")

    product = db.query(MaterialProduct).filter(MaterialProduct.id == script_folder.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品目录不存在")

    _ensure_folder_duplicate_safe(
        db,
        script_folder_id=script_folder.id,
        file_name=material.file_name,
        exclude_material_id=material.id,
    )

    exists_binding = (
        db.query(MaterialFolderBinding)
        .filter(
            MaterialFolderBinding.material_id == material.id,
            MaterialFolderBinding.script_folder_id == script_folder.id,
        )
        .first()
    )
    if exists_binding is None:
        db.add(
            MaterialFolderBinding(
                material_id=material.id,
                script_folder_id=script_folder.id,
            )
        )

    material.library_kind = LIBRARY_KIND_PRODUCT
    material.product_id = product.id
    material.script_folder_id = script_folder.id
    material.product_name = product.name
    material.script_folder = script_folder.name
    db.commit()
    db.refresh(material)
    return _serialize_material(db, material)


@router.delete("/{material_id}/folders/{script_folder_id}", response_model=MaterialResponse)
async def unfile_material_from_script_folder(
    material_id: int,
    script_folder_id: int,
    db: Session = Depends(get_db),
):
    material = (
        db.query(Material)
        .options(joinedload(Material.product), joinedload(Material.script_folder_ref))
        .filter(Material.id == material_id)
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="素材不存在")

    binding = (
        db.query(MaterialFolderBinding)
        .filter(
            MaterialFolderBinding.material_id == material.id,
            MaterialFolderBinding.script_folder_id == script_folder_id,
        )
        .first()
    )
    if not binding:
        raise HTTPException(status_code=404, detail="素材未归档到该脚本子文件夹")

    db.delete(binding)
    db.commit()

    has_any = (
        db.query(MaterialFolderBinding)
        .filter(MaterialFolderBinding.material_id == material.id)
        .first()
        is not None
    )
    if not has_any and material.library_kind == LIBRARY_KIND_PRODUCT:
        material.library_kind = LIBRARY_KIND_UNFILED
        material.product_id = None
        material.script_folder_id = None
        material.product_name = None
        material.script_folder = None
        db.commit()

    db.refresh(material)
    return _serialize_material(db, material)


@router.get("", response_model=list[MaterialResponse])
async def list_materials(
    file_type: str | None = None,
    library_kind: str | None = None,
    product_id: int | None = None,
    script_folder_id: int | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(Material).options(
        joinedload(Material.product),
        joinedload(Material.script_folder_ref),
    )
    if file_type:
        query = query.filter(Material.file_type == file_type)

    if script_folder_id:
        query = (
            query.join(
                MaterialFolderBinding,
                MaterialFolderBinding.material_id == Material.id,
            )
            .filter(MaterialFolderBinding.script_folder_id == int(script_folder_id))
            .distinct()
        )
    elif product_id:
        query = (
            query.join(
                MaterialFolderBinding,
                MaterialFolderBinding.material_id == Material.id,
            )
            .join(
                MaterialScriptFolder,
                MaterialScriptFolder.id == MaterialFolderBinding.script_folder_id,
            )
            .filter(MaterialScriptFolder.product_id == int(product_id))
            .distinct()
        )
    elif library_kind:
        normalized_kind = _validate_library_kind(library_kind)
        if normalized_kind == LIBRARY_KIND_PRODUCT:
            query = (
                query.join(
                    MaterialFolderBinding,
                    MaterialFolderBinding.material_id == Material.id,
                )
                .distinct()
            )
        else:
            query = query.filter(Material.library_kind == normalized_kind)

    items = query.order_by(Material.id.desc()).all()
    return [_serialize_material(db, item) for item in items]


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
        content_disposition_type="inline",
    )


@router.put("/{material_id}", response_model=MaterialResponse)
async def rename_material(
    material_id: int,
    payload: MaterialRenameRequest,
    db: Session = Depends(get_db),
):
    material = (
        db.query(Material)
        .options(joinedload(Material.product), joinedload(Material.script_folder_ref))
        .filter(Material.id == material_id)
        .first()
    )
    if not material:
        raise HTTPException(status_code=404, detail="素材不存在")

    new_name = payload.new_file_name.strip()
    if not new_name:
        raise HTTPException(status_code=400, detail="新文件名不能为空")

    existing = (
        db.query(Material)
        .filter(Material.file_name == new_name, Material.id != material.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="素材文件名已存在")

    src = material.file_path
    dst = os.path.join(os.path.dirname(src), new_name)
    if os.path.exists(src):
        os.replace(src, dst)

    material.file_name = new_name
    material.file_path = normalize_storage_path(Path(dst))
    db.commit()
    db.refresh(material)
    return _serialize_material(db, material)


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

    db.query(MaterialFolderBinding).filter(MaterialFolderBinding.material_id == material.id).delete()
    db.delete(material)
    db.commit()
    return MessageResponse(message="素材已删除")
