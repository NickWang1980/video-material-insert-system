from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..models.role_definition import RoleDefinition
from ..schemas.role import (
    ALL_MODULE_KEYS,
    CreateRoleRequest,
    RoleOut,
    UpdateRoleRequest,
)

router = APIRouter(prefix="/api/roles", tags=["roles"])


def _require_admin(request: Request) -> dict:
    user = getattr(request.state, "current_user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    return user


@router.get("", response_model=list[RoleOut])
def list_roles(db: Session = Depends(get_db)):
    return db.query(RoleDefinition).order_by(RoleDefinition.id).all()


@router.post("", response_model=RoleOut, status_code=201)
def create_role(request: Request, body: CreateRoleRequest, db: Session = Depends(get_db)):
    _require_admin(request)
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="角色名不能为空")
    if db.query(RoleDefinition).filter(RoleDefinition.name == body.name).first():
        raise HTTPException(status_code=400, detail="角色名已存在")
    invalid = set(body.module_keys) - set(ALL_MODULE_KEYS)
    if invalid:
        raise HTTPException(status_code=400, detail=f"无效模块: {invalid}")
    role = RoleDefinition(
        name=body.name.strip(),
        display_name=body.display_name.strip(),
        is_system=False,
        module_keys=json.dumps(body.module_keys),
    )
    db.add(role)
    db.commit()
    db.refresh(role)
    return role


@router.patch("/{role_id}", response_model=RoleOut)
def update_role(
    request: Request,
    role_id: int,
    body: UpdateRoleRequest,
    db: Session = Depends(get_db),
):
    _require_admin(request)
    role = db.query(RoleDefinition).filter(RoleDefinition.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.name == "admin" and body.module_keys is not None:
        raise HTTPException(status_code=400, detail="管理员角色的模块权限不可修改")
    if body.display_name is not None:
        if role.is_system:
            raise HTTPException(status_code=400, detail="系统内置角色的名称不可修改")
        role.display_name = body.display_name.strip()
    if body.module_keys is not None:
        invalid = set(body.module_keys) - set(ALL_MODULE_KEYS)
        if invalid:
            raise HTTPException(status_code=400, detail=f"无效模块: {invalid}")
        role.module_keys = json.dumps(body.module_keys)
    db.commit()
    db.refresh(role)
    return role


@router.delete("/{role_id}", status_code=204)
def delete_role(request: Request, role_id: int, db: Session = Depends(get_db)):
    _require_admin(request)
    role = db.query(RoleDefinition).filter(RoleDefinition.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=400, detail="系统内置角色不可删除")
    db.delete(role)
    db.commit()
