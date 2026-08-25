"""JWT 登录/注册/当前用户。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.services.auth_service import create_token, decode_token, verify_password
from app.services.guide_store import (
    User,
    get_session_factory,
    get_user,
    get_user_by_username,
)

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_]+$")
    password: str = Field(min_length=6, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str


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
    return UserOut(**user)


@router.post("/register", response_model=dict)
async def register(body: RegisterRequest):
    # 产品化前关闭公开注册；内部账号由管理员/启动 seed 创建。
    raise HTTPException(status_code=410, detail="当前关闭公开注册，如需账号请联系管理员")


@router.post("/login", response_model=dict)
async def login(body: LoginRequest):
    user = get_user_by_username(body.username)
    password_hash = _user_hash(body.username)
    if not user or not password_hash or not verify_password(body.password, password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    return {"token": create_token(user["id"], user["username"], user["role"]), "user": user}


@router.get("/me", response_model=dict)
async def me(user: UserOut = Depends(current_user)):
    return {"user": user.model_dump()}
