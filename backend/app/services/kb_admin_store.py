"""Sprint 02 知识库运营后台：knowledge_items 表 CRUD。"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import settings
from app.core.logger import logger


class Base(DeclarativeBase):
    pass


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="policy", nullable=False)
    source: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    meta: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    is_vectorized: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


_engine = None
_factory = None
_ready: Optional[bool] = None


def _ensure():
    global _engine, _factory
    if _factory is not None:
        return _factory
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        db_path = settings.DATA_DIR / "gov_assistant.db"
        _engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    else:
        _engine = create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 3})
    _factory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _factory


def init_kb_db() -> bool:
    global _ready
    try:
        factory = _ensure()
        Base.metadata.create_all(_engine)
        _ready = True
        return True
    except Exception as exc:
        logger.warning(f"knowledge_items 初始化失败: {exc}")
        _ready = False
        return False


def db_ready() -> bool:
    return _ready is True


def _dict(k: KnowledgeItem) -> dict:
    return {
        "id": k.id,
        "title": k.title,
        "category": k.category,
        "source": k.source or "",
        "status": k.status,
        "metadata": k.meta or {},
        "is_vectorized": k.is_vectorized,
        "content": k.content,
    }


def list_items(category: str | None = None, status: str | None = None, search: str | None = None) -> List[dict]:
    factory = _ensure()
    with factory() as session:
        stmt = select(KnowledgeItem).order_by(KnowledgeItem.id.desc())
        if category:
            stmt = stmt.where(KnowledgeItem.category == category)
        if status:
            stmt = stmt.where(KnowledgeItem.status == status)
        if search and search.strip():
            like = f"%{search.strip()}%"
            stmt = stmt.where(KnowledgeItem.title.like(like))
        rows = session.execute(stmt).scalars().all()
        return [_dict(k) for k in rows]


def get_item(item_id: int) -> Optional[dict]:
    factory = _ensure()
    with factory() as session:
        row = session.get(KnowledgeItem, item_id)
        return _dict(row) if row else None


def create_item(title: str, content: str, category: str = "policy", source: str = "", metadata: dict | None = None) -> dict:
    factory = _ensure()
    with factory() as session:
        row = session.execute(select(KnowledgeItem).where(KnowledgeItem.title == title)).scalar_one_or_none()
        if row:
            raise ValueError("相同标题的条目已存在")
        item = KnowledgeItem(
            title=title,
            content=content,
            category=category,
            source=source,
            status="active",
            meta=metadata or {},
        )
        session.add(item)
        session.commit()
        session.refresh(item)
        return _dict(item)


def update_item(item_id: int, title: str | None, content: str | None, category: str | None = None, source: str | None = None, metadata: dict | None = None) -> Optional[dict]:
    factory = _ensure()
    with factory() as session:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return None
        if title is not None:
            item.title = title
        if content is not None:
            item.content = content
        if category is not None:
            item.category = category
        if source is not None:
            item.source = source
        if metadata is not None:
            item.meta = metadata
        session.commit()
        session.refresh(item)
        return _dict(item)


def delete_item(item_id: int) -> bool:
    factory = _ensure()
    with factory() as session:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return False
        session.delete(item)
        session.commit()
        return True


def toggle_item(item_id: int) -> Optional[dict]:
    factory = _ensure()
    with factory() as session:
        item = session.get(KnowledgeItem, item_id)
        if not item:
            return None
        item.status = "archived" if item.status == "active" else "active"
        session.commit()
        session.refresh(item)
        return _dict(item)


def list_active_for_compare() -> List[dict]:
    return list_items(status="active")
