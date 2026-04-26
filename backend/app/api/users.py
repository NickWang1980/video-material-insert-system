from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..dependencies import get_db
from ..models.user import User
from ..schemas.auth import UserListItem, CreateUserRequest, UpdateUserRequest
from ..services.auth_service import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])


def _require_admin(request: Request) -> dict:
    user = getattr(request.state, "current_user", None)
    if not user or user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可访问")
    return user


@router.get("", response_model=list[UserListItem])
def list_users(request: Request, db: Session = Depends(get_db)):
    _require_admin(request)
    return db.query(User).order_by(User.created_at).all()


@router.post("", response_model=UserListItem, status_code=201)
def create_user(request: Request, body: CreateUserRequest, db: Session = Depends(get_db)):
    _require_admin(request)
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserListItem)
def update_user(
    request: Request,
    user_id: int,
    body: UpdateUserRequest,
    db: Session = Depends(get_db),
):
    current = _require_admin(request)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    is_self = current.get("sub") == user.username

    if body.role is not None:
        if is_self and body.role != "admin":
            raise HTTPException(status_code=400, detail="不能降低自己的权限")
        user.role = body.role

    if body.is_active is not None:
        if is_self and not body.is_active:
            raise HTTPException(status_code=400, detail="不能禁用自己的账号")
        user.is_active = body.is_active

    if body.new_password:
        user.password_hash = hash_password(body.new_password)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=204)
def delete_user(request: Request, user_id: int, db: Session = Depends(get_db)):
    current = _require_admin(request)
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if current.get("sub") == user.username:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    db.delete(user)
    db.commit()
