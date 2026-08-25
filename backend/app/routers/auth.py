"""JWT 登录/注册/当前用户。"""
import threading
from collections import defaultdict
from datetime import datetime, timezone
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.core.config import settings
from app.services.auth_service import create_token, decode_token, hash_password, verify_password
from app.services.guide_store import (
    User,
    bump_token_version,
    get_session_factory,
    get_user,
    get_user_by_username,
    set_last_login,
)

router = APIRouter()
bearer = HTTPBearer(auto_error=False)

_login_failures: defaultdict[str, list] = defaultdict(list)
_login_lock = threading.Lock()
LOGIN_FAIL_MAX = 5
LOGIN_FAIL_LOCK_SECONDS = 15 * 60


def _login_locked(client_ip: str, username: str) -> bool:
    """按 IP+用户名 独立限流，避免 NAT 出口误伤同网络其他用户。"""
    key = f"{client_ip}:{username.strip().lower()}"
    now = monotonic()
    with _login_lock:
        failures = [t for t in _login_failures[key] if now - t < LOGIN_FAIL_LOCK_SECONDS]
        _login_failures[key] = failures
        return len(failures) >= LOGIN_FAIL_MAX


def _add_login_failure(client_ip: str, username: str) -> None:
    key = f"{client_ip}:{username.strip().lower()}"
    with _login_lock:
        _login_failures[key].append(monotonic())


def _clear_login_failure(client_ip: str, username: str) -> None:
    key = f"{client_ip}:{username.strip().lower()}"
    with _login_lock:
        _login_failures.pop(key, None)




def _strong_password(value: str) -> str:
    if len(value) < 8 or not any(ch.isalpha() for ch in value) or not any(ch.isdigit() for ch in value):
        raise ValueError("密码至少 8 位，且必须同时包含字母和数字")
    return value


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=6, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        try:
            return _strong_password(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class LibraryUser(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool = True
    token_version: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "LibraryUser":
        return cls(**data)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool = True
    token_version: int = 0

    @classmethod
    def from_dict(cls, data: dict) -> "UserOut":
        return cls(**data)


def _user_hash(username: str) -> str | None:
    factory = get_session_factory()
    with factory() as session:
        row = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
        return row.password_hash if row else None


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> UserOut:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    user_id = int(payload.get("sub", 0))
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    if not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="账号已禁用，请联系管理员")
    # 兼容旧 token 没有 tv；当前 token 版本与库中不一致则视为已被踢下线
    if int(payload.get("tv", 0)) != int(user.get("token_version", 0)):
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return UserOut.from_dict(user)


@router.post("/register", response_model=dict)
async def register(body: RegisterRequest):
    # 产品化前关闭公开注册；内部账号由管理员/启动 seed 创建。
    raise HTTPException(status_code=410, detail="当前关闭公开注册，如需账号请联系管理员")


@router.post("/login", response_model=dict)
async def login(body: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    username_key = (body.username or "").strip().lower()
    if _login_locked(client_ip, username_key):
        raise HTTPException(status_code=429, detail="登录失败次数过多，请15分钟后再试")

    user = get_user_by_username(body.username)
    password_hash = _user_hash(body.username)
    if not user or not password_hash or not verify_password(body.password, password_hash):
        _add_login_failure(client_ip, username_key)
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.get("is_active", True):
        raise HTTPException(status_code=401, detail="账号已禁用，请联系管理员")

    _clear_login_failure(client_ip, username_key)
    # 多端在线模式：不递增版本号，新旧 token 都有效；单点模式：递增踢掉旧 token。
    if settings.ALLOW_MULTI_SESSION:
        new_version = int(user.get("token_version", 0))
    else:
        new_version = int(user.get("token_version", 0)) + 1
        bump_token_version(user["id"])
        user["token_version"] = new_version
    set_last_login(user["id"], datetime.now(timezone.utc))
    return {"token": create_token(user["id"], user["username"], user["role"], new_version), "user": user}


@router.get("/me", response_model=dict)
async def me(user: UserOut = Depends(current_user)):
    return {"user": user.model_dump()}


@router.post("/logout", response_model=dict)
async def logout(user: UserOut = Depends(current_user)):
    bump_token_version(user.id)
    return {"message": "已退出登录"}


@router.post("/change-password", response_model=dict)
async def change_password(body: ChangePasswordRequest, user: UserOut = Depends(current_user)):
    factory = get_session_factory()
    with factory() as session:
        row = session.get(User, user.id)
        if not row:
            raise HTTPException(status_code=404, detail="用户不存在")
        if not verify_password(body.old_password, row.password_hash):
            raise HTTPException(status_code=401, detail="原密码错误")
        if verify_password(body.new_password, row.password_hash):
            raise HTTPException(status_code=400, detail="新密码不能与旧密码相同")
        row.password_hash = hash_password(body.new_password)
        row.token_version = int(row.token_version or 0) + 1
        session.commit()
    return {"message": "密码已修改，请重新登录"}
