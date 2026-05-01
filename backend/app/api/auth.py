from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..dependencies import get_db, get_app_settings
from ..models.role_definition import RoleDefinition
from ..models.user import User
from ..schemas.auth import LoginRequest, TokenResponse, UserInfo
from ..schemas.role import ADMIN_MODULE_KEYS, DEFAULT_USER_MODULE_KEYS
from ..services.auth_service import create_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _get_role_info(db: Session, role: str) -> tuple[list[str], str]:
    role_def = db.query(RoleDefinition).filter(RoleDefinition.name == role).first()
    if role_def:
        modules = json.loads(role_def.module_keys) if isinstance(role_def.module_keys, str) else role_def.module_keys
        return modules, role_def.display_name
    if role == "admin":
        return ADMIN_MODULE_KEYS, "管理员"
    return DEFAULT_USER_MODULE_KEYS, "普通用户"


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已被禁用")
    allowed_modules, role_display_name = _get_role_info(db, user.role)
    settings = get_app_settings()
    token = create_token(user.username, user.role, settings.jwt_secret, modules=allowed_modules)
    return TokenResponse(
        access_token=token,
        username=user.username,
        role=user.role,
        role_display_name=role_display_name,
        allowed_modules=allowed_modules,
    )


@router.get("/me", response_model=UserInfo)
async def me(request: Request, db: Session = Depends(get_db)):
    current = getattr(request.state, "current_user", None)
    if not current:
        raise HTTPException(status_code=401, detail="未登录")
    user = db.query(User).filter(User.username == current["sub"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user
