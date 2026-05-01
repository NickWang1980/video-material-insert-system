from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..models.audit_log import AuditLog
from ..schemas.audit import AuditLogItem, AuditLogListResponse
from ..schemas.common import MessageResponse

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("/logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    page: int = 1,
    page_size: int = 20,
    entity_type: str | None = None,
    operator: str | None = None,
    source: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if entity_type:
        q = q.filter(AuditLog.entity_type == entity_type)
    if operator:
        q = q.filter(AuditLog.operator.ilike(f"%{operator}%"))
    if source:
        q = q.filter(AuditLog.source == source)
    if start_date:
        q = q.filter(AuditLog.created_at >= start_date)
    if end_date:
        q = q.filter(AuditLog.created_at <= end_date + " 23:59:59")
    total = q.count()
    items = (
        q.order_by(AuditLog.created_at.desc())
        .offset((max(page, 1) - 1) * max(page_size, 1))
        .limit(max(page_size, 1))
        .all()
    )
    return AuditLogListResponse(items=items, total=total)


@router.delete("/logs", response_model=MessageResponse)
async def clear_audit_logs(request: Request, db: Session = Depends(get_db)):
    user = getattr(request.state, "current_user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可清空操作历史")
    count = db.query(AuditLog).count()
    db.query(AuditLog).delete()
    db.commit()
    return MessageResponse(message=f"已清空 {count} 条操作历史")
