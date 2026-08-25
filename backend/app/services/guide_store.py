"""Sprint 01 导办数据存储：用户、导办主题/步骤、用户进度。

- PG / SQLite 由 DATABASE_URL 自动适配。
- 主题与步骤首次启动从 data/guide_scenarios.json 种子写入。
- 任何数据库失败时，主题/步骤仍可从 JSON 读取，导办浏览不依赖 DB。
"""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import settings
from app.core.logger import logger

_SEED_PATH = settings.DATA_DIR / "guide_scenarios.json"


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="user", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GuideTheme(Base):
    __tablename__ = "guide_themes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(16))
    description: Mapped[Optional[str]] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String(32))
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    estimated_days: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class GuideStep(Base):
    __tablename__ = "guide_steps"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    theme_id: Mapped[str] = mapped_column(String(64), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(128))
    duration_days: Mapped[int] = mapped_column(Integer, default=0)
    channel: Mapped[str] = mapped_column(String(16), default="both")
    channel_detail: Mapped[Optional[str]] = mapped_column(Text)
    materials: Mapped[list] = mapped_column(JSON, default=list)
    prerequisites: Mapped[list] = mapped_column(JSON, default=list)
    fee: Mapped[str] = mapped_column(String(64), default="免费")
    notes: Mapped[Optional[str]] = mapped_column(Text)


class GuideUserProgress(Base):
    __tablename__ = "guide_user_progress"
    __table_args__ = (UniqueConstraint("user_id", "theme_id", "step_id", name="uq_user_theme_step"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    theme_id: Mapped[str] = mapped_column(String(64), nullable=False)
    step_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


_engine = None
_session_factory: sessionmaker | None = None


def _load_seed() -> dict:
    if _SEED_PATH.exists():
        try:
            return json.loads(_SEED_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(f"导办场景 JSON 读取失败: {exc}")
    return {"themes": []}


def _ensure_engine():
    global _engine, _session_factory
    if _session_factory is not None:
        return _session_factory
    url = settings.DATABASE_URL
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        db_path = settings.DATA_DIR / "gov_assistant.db"
        engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    else:
        engine = create_engine(url, connect_args={"connect_timeout": 3}, **kwargs)
    _engine = engine
    _session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _session_factory


def init_guide_db() -> bool:
    """建表并种子化主题、步骤；返回 DB 是否可用。"""
    try:
        session_factory = _ensure_engine()
        Base.metadata.create_all(_engine)
        with session_factory() as session:
            themes = _load_seed().get("themes", [])
            if session.scalar(select(func.count()).select_from(GuideTheme)) == 0 and themes:
                for idx, t in enumerate(themes):
                    session.add(
                        GuideTheme(
                            id=t["id"],
                            name=t["name"],
                            icon=t.get("icon"),
                            description=t.get("description"),
                            category=t.get("category"),
                            keywords=t.get("keywords", []),
                            estimated_days=t.get("estimated_days", 0),
                            is_active=True,
                        )
                    )
                    for s in t.get("steps", []):
                        session.add(
                            GuideStep(
                                id=s["id"],
                                theme_id=t["id"],
                                step_order=s.get("step_order", idx + 1),
                                name=s["name"],
                                department=s.get("department"),
                                duration_days=s.get("duration_days", 0),
                                channel=s.get("channel", "both"),
                                channel_detail=s.get("channel_detail"),
                                materials=s.get("materials", []),
                                prerequisites=s.get("prerequisites", []),
                                fee=s.get("fee", "免费"),
                                notes=s.get("notes"),
                            )
                        )
                session.commit()
        return True
    except Exception as exc:
        logger.warning(f"导办数据库初始化失败，使用 JSON 内存模式: {exc}")
        return False


def get_session_factory() -> sessionmaker:
    return _ensure_engine()


def ensure_demo_user():
    """预置测试账号 demo / demo123，不存在则创建，存在则修复旧哈希。"""
    try:
        from app.services.auth_service import hash_password

        factory = get_session_factory()
        with factory() as session:
            exists = session.execute(select(User).where(User.username == "demo")).scalar_one_or_none()
            if not exists:
                session.add(User(username="demo", password_hash=hash_password("demo123"), role="user"))
                session.commit()
            else:
                from app.services.auth_service import verify_password

                if not verify_password("demo123", exists.password_hash):
                    exists.password_hash = hash_password("demo123")
                    session.commit()
    except Exception as exc:
        logger.warning(f"预置 demo 用户失败: {exc}")


def themes_from_db() -> List[Dict[str, Any]]:
    """DB 优先，失败回退 JSON。"""
    try:
        session_factory = _ensure_engine()
        with session_factory() as session:
            themes = session.execute(select(GuideTheme).order_by(GuideTheme.id)).scalars().all()
            if themes:
                return [_theme_meta(t) for t in themes]
    except Exception:
        pass
    return [
        {
            "id": t["id"],
            "name": t["name"],
            "icon": t.get("icon"),
            "description": t.get("description"),
            "category": t.get("category"),
            "keywords": t.get("keywords", []),
            "estimated_days": t.get("estimated_days", 0),
        }
        for t in _load_seed().get("themes", [])
    ]


def roadmap_from_db(theme_id: str) -> Optional[Dict[str, Any]]:
    """完整路线图：主题 + steps。"""
    session_factory = _ensure_engine()
    try:
        with session_factory() as session:
            theme = session.get(GuideTheme, theme_id)
            if not theme:
                return None
            steps = session.execute(
                select(GuideStep).where(GuideStep.theme_id == theme_id).order_by(GuideStep.step_order)
            ).scalars().all()
            return {"theme": _theme_full(theme), "steps": [_step_full(s) for s in steps]}
    except Exception:
        pass
    seed = next((t for t in _load_seed().get("themes", []) if t["id"] == theme_id), None)
    if not seed:
        return None
    return {
        "theme": {
            "id": seed["id"],
            "name": seed["name"],
            "icon": seed.get("icon"),
            "description": seed.get("description"),
            "category": seed.get("category"),
            "estimated_days": seed.get("estimated_days", 0),
        },
        "steps": seed.get("steps", []),
    }


def _theme_meta(t: GuideTheme) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "icon": t.icon,
        "category": t.category,
        "estimated_days": t.estimated_days,
    }


def _theme_full(t: GuideTheme) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "icon": t.icon,
        "description": t.description,
        "category": t.category,
        "estimated_days": t.estimated_days,
    }


def _step_full(s: GuideStep) -> dict:
    return {
        "id": s.id,
        "step_order": s.step_order,
        "name": s.name,
        "department": s.department,
        "duration_days": s.duration_days,
        "channel": s.channel,
        "channel_detail": s.channel_detail,
        "materials": s.materials or [],
        "prerequisites": s.prerequisites or [],
        "fee": s.fee,
        "notes": s.notes,
    }


def create_user(username: str, password_hash: str) -> dict:
    session_factory = _ensure_engine()
    with session_factory() as session:
        user = User(username=username, password_hash=password_hash, role="user")
        session.add(user)
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise
        session.refresh(user)
        return _user_dict(user)


def get_user_by_username(username: str) -> Optional[dict]:
    session_factory = _ensure_engine()
    with session_factory() as session:
        user = session.execute(select(User).where(User.username == username)).scalar_one_or_none()
        return _user_dict(user) if user else None


def get_user(user_id: int) -> Optional[dict]:
    session_factory = _ensure_engine()
    with session_factory() as session:
        user = session.get(User, user_id)
        return _user_dict(user) if user else None


def _user_dict(u: User) -> dict:
    return {"id": u.id, "username": u.username, "role": u.role}


def get_progress(user_id: int, theme_id: str) -> dict:
    session_factory = _ensure_engine()
    with session_factory() as session:
        rows = session.execute(
            select(GuideUserProgress).where(
                GuideUserProgress.user_id == user_id,
                GuideUserProgress.theme_id == theme_id,
            )
        ).scalars().all()
        return {r.step_id: r.status for r in rows}


def set_progress(user_id: int, theme_id: str, step_id: str, status: str) -> dict:
    status = status if status in ("pending", "done") else "pending"
    session_factory = _ensure_engine()
    with session_factory() as session:
        row = session.execute(
            select(GuideUserProgress).where(
                GuideUserProgress.user_id == user_id,
                GuideUserProgress.theme_id == theme_id,
                GuideUserProgress.step_id == step_id,
            )
        ).scalar_one_or_none()
        if row:
            row.status = status
            row.updated_at = datetime.now(timezone.utc)
        else:
            session.add(
                GuideUserProgress(user_id=user_id, theme_id=theme_id, step_id=step_id, status=status)
            )
        session.commit()
        return {"theme_id": theme_id, "step_id": step_id, "status": status}
