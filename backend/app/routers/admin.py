"""S03 管理员用户管理 API（仅 admin；未授权一律 404，避免泄露后台存在性）。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError

from app.routers.auth import current_user, UserOut
from app.services.auth_service import hash_password
from app.services.guide_store import (
    create_user,
    delete_user,
    get_user,
    get_user_by_username,
    list_users,
    reset_password,
    update_user,
)

router = APIRouter(prefix="/admin/users", tags=["管理员用户管理"])


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_]+$")
    password: str
    role: str = Field(default="user", pattern=r"^(admin|user|super_admin)$")

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8 or not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise ValueError("密码至少 8 位，且必须同时包含字母和数字")
        return value


class AdminUserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern=r"^(admin|user|super_admin)$")
    is_active: bool | None = None


class AdminResetPassword(BaseModel):
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if len(value) < 8 or not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
            raise ValueError("密码至少 8 位，且必须同时包含字母和数字")
        return value


def admin_required(user: UserOut = Depends(current_user)) -> UserOut:
    """管理员权限依赖：非 admin/super_admin 一律返回 404，且在 body 校验之前执行。"""
    if user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=404, detail="资源不存在")
    return user


def _ensure_not_super_admin(target: dict, action: str = "修改") -> None:
    """super_admin 账号只能由 super_admin 自己操作，普通管理员不可触碰。"""
    if target.get("role") == "super_admin":
        raise HTTPException(status_code=403, detail=f"无权{action}超级管理员账号")


@router.get("")
async def get_users(
    page: int = 1,
    page_size: int = 20,
    keyword: str = "",
    user: UserOut = Depends(admin_required),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    return list_users(keyword=keyword, page=page, page_size=page_size)


@router.post("", status_code=201)
async def create_admin_user(body: AdminUserCreate, user: UserOut = Depends(admin_required)):
    if body.role == "super_admin" and user.role != "super_admin":
        raise HTTPException(status_code=403, detail="仅超级管理员可创建超级管理员账号")
    if get_user_by_username(body.username):
        raise HTTPException(status_code=409, detail="用户名已存在")
    try:
        item = create_user(body.username, hash_password(body.password), body.role, True)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="用户名已存在") from exc
    return {"user": item}


@router.put("/{user_id}")
async def update_admin_user(user_id: int, body: AdminUserUpdate, user: UserOut = Depends(admin_required)):
    target = get_user(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    # 普通管理员不能修改超级管理员
    if target.get("role") == "super_admin" and user.role != "super_admin":
        raise HTTPException(status_code=403, detail="无权修改超级管理员账号")
    # 只有超级管理员可以授予/撤销超级管理员角色
    if body.role == "super_admin" and user.role != "super_admin":
        raise HTTPException(status_code=403, detail="仅超级管理员可授予超级管理员角色")
    if user.id == user_id:
        if body.is_active is False:
            raise HTTPException(status_code=400, detail="不能禁用当前登录的管理员账号")
        if body.role is not None and body.role != "admin":
            raise HTTPException(status_code=400, detail="不能移除自己的管理员角色")
    item = update_user(user_id, role=body.role, is_active=body.is_active)
    return {"user": item}


@router.post("/{user_id}/reset-password")
async def reset_admin_password(user_id: int, body: AdminResetPassword, user: UserOut = Depends(admin_required)):
    target = get_user(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.get("role") == "super_admin" and user.role != "super_admin":
        raise HTTPException(status_code=403, detail="无权重置超级管理员密码")
    item = reset_password(user_id, hash_password(body.new_password))
    return {"message": "密码已重置", "user": item}


@router.delete("/{user_id}", status_code=200)
async def delete_admin_user(user_id: int, user: UserOut = Depends(admin_required)):
    target = get_user(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.get("role") == "super_admin":
        raise HTTPException(status_code=403, detail="超级管理员账号不可删除")
    if user.id == user_id:
        raise HTTPException(status_code=400, detail="不能删除当前登录的管理员账号")
    delete_user(user_id)
    return {"message": "用户已删除"}
