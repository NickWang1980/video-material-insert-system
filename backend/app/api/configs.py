from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..models.config_template import ConfigTemplate
from ..schemas.common import MessageResponse
from ..schemas.config import ConfigTemplateCreate, ConfigTemplateResponse
from ..utils.csv_utils import export_config_csv, parse_config_csv_bytes


router = APIRouter(prefix="/api/config-templates", tags=["config-templates"])


def extract_keywords(config_content: str) -> list[str]:
    try:
        config = json.loads(config_content or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(config, list):
        return []

    seen: set[str] = set()
    keywords: list[str] = []
    for item in config:
        if not isinstance(item, dict):
            continue
        keyword_value = item.get("关键词")
        keyword = keyword_value if isinstance(keyword_value, str) else str(keyword_value or "")
        keyword = keyword.strip()
        if not keyword or keyword in seen:
            continue
        seen.add(keyword)
        keywords.append(keyword)
    return keywords


def to_template_response(template: ConfigTemplate) -> ConfigTemplateResponse:
    keywords = extract_keywords(template.config_content)
    return ConfigTemplateResponse(
        id=template.id,
        template_name=template.template_name,
        description=template.description,
        keywords=keywords,
        keyword_preview="、".join(keywords),
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


@router.post("", response_model=ConfigTemplateResponse)
async def create_template(payload: ConfigTemplateCreate, db: Session = Depends(get_db)):
    template = ConfigTemplate(
        template_name=payload.template_name,
        config_content=json.dumps(payload.config_content, ensure_ascii=False),
        description=payload.description,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return to_template_response(template)


@router.get("", response_model=list[ConfigTemplateResponse])
async def list_templates(db: Session = Depends(get_db)):
    templates = db.query(ConfigTemplate).order_by(ConfigTemplate.id.desc()).all()
    return [to_template_response(template) for template in templates]


@router.get("/{template_id}")
async def get_template(template_id: int, db: Session = Depends(get_db)):
    template = db.query(ConfigTemplate).filter(ConfigTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="配置模板不存在")
    return {
        "id": template.id,
        "template_name": template.template_name,
        "description": template.description,
        "config_content": json.loads(template.config_content),
        "created_at": template.created_at,
        "updated_at": template.updated_at,
    }


@router.put("/{template_id}", response_model=ConfigTemplateResponse)
async def update_template(
    template_id: int, payload: ConfigTemplateCreate, db: Session = Depends(get_db)
):
    template = db.query(ConfigTemplate).filter(ConfigTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="配置模板不存在")
    template.template_name = payload.template_name
    template.description = payload.description
    template.config_content = json.dumps(payload.config_content, ensure_ascii=False)
    db.commit()
    db.refresh(template)
    return to_template_response(template)


@router.delete("/{template_id}", response_model=MessageResponse)
async def delete_template(template_id: int, db: Session = Depends(get_db)):
    template = db.query(ConfigTemplate).filter(ConfigTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="配置模板不存在")
    db.delete(template)
    db.commit()
    return MessageResponse(message="配置模板已删除")


@router.post("/import", response_model=ConfigTemplateResponse)
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    config = parse_config_csv_bytes(content)
    template = ConfigTemplate(
        template_name=file.filename.rsplit(".", 1)[0],
        config_content=json.dumps(config, ensure_ascii=False),
        description="从 CSV 导入",
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return to_template_response(template)


@router.get("/{template_id}/export", response_class=PlainTextResponse)
async def export_csv(template_id: int, db: Session = Depends(get_db)):
    template = db.query(ConfigTemplate).filter(ConfigTemplate.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="配置模板不存在")
    config = json.loads(template.config_content)
    csv_text = export_config_csv(config)
    return PlainTextResponse(csv_text, media_type="text/csv; charset=utf-8")
