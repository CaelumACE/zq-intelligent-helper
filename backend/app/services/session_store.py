"""会话存储 - 支持 SQLite / PostgreSQL，自动回退 JSON 文件。

存储后端选择：
- PostgreSQL URL：优先用 `chat_sessions` 表，JSON 列保存完整会话。
- SQLite URL：优先用本地 SQLite，避免每次全量读文件。
- 其它 / 失败：回退 data/conversations.json，保证零基础设施演示可用。

多账号隔离：
- 会话记录写入 user_id，读/列/删都按 user_id 过滤。
- 兼容历史无 user_id 数据（仅能通过内部直读访问，不向账号接口暴露）。
"""
import json
import time
import uuid
from pathlib import Path
from typing import Optional

from app.core.config import settings
from app.core.logger import logger
from sqlalchemy import create_engine, text

_JSON_MESSAGE_FIELDS = ("id", "role", "content", "references", "model", "timestamp", "status", "structured_answer")


class SessionStore:
    """会话存储服务"""

    def __init__(self, data_dir: Path | None = None, filename: str = "conversations.json"):
        self._data_dir = data_dir or settings.DATA_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._path = self._data_dir / filename
        self._sessions: dict = {}
        self._engine = None
        self._sql_ready = False
        self._backend = self._detect_backend()
        self._load()

    # ------------------------------------------------------------------ init
    def _detect_backend(self) -> str:
        url = (settings.DATABASE_URL or "").strip()
        if url.startswith("sqlite:"):
            return "sqlite"
        if url.startswith("postgresql") or url.startswith("postgres+"):
            return "postgres"
        return "json"

    def _ensure_engine(self):
        if self._engine is not None:
            return self._engine
        url = settings.DATABASE_URL
        if self._backend == "sqlite":
            db_path = settings.DATA_DIR / "gov_assistant.db"
            self._engine = create_engine(
                f"sqlite:///{db_path}",
                connect_args={"check_same_thread": False},
            )
        else:
            self._engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_recycle=300,
                connect_args={"connect_timeout": 3},
            )
        return self._engine

    def _init_sql(self) -> bool:
        if self._backend == "json":
            return False
        try:
            with self._ensure_engine().begin() as conn:
                conn.execute(
                    text(
                        """
                        CREATE TABLE IF NOT EXISTS chat_sessions (
                            id TEXT PRIMARY KEY,
                            title TEXT,
                            payload JSON NOT NULL,
                            user_id TEXT,
                            created_at BIGINT NOT NULL,
                            updated_at BIGINT NOT NULL
                        )
                        """
                    )
                )
            self._ensure_user_id_column()
            self._sql_ready = True
            return True
        except Exception as exc:
            logger.warning(f"数据库会话表初始化失败，回退 JSON: {exc}")
            self._backend = "json"
            self._sql_ready = False
            return False

    def _ensure_user_id_column(self):
        """为旧库兼容补 user_id 列；无此列的服务端调用全部回退 JSON。"""
        try:
            with self._ensure_engine().begin() as conn:
                try:
                    conn.execute(text("ALTER TABLE chat_sessions ADD COLUMN user_id TEXT"))
                except Exception:
                    # 已存在该列或数据库不支持 ADD COLUMN，忽略
                    pass
        except Exception as exc:
            logger.warning(f"会话表 user_id 列初始化失败: {exc}")

    def _load(self):
        if self._backend != "json" and self._init_sql():
            self._maybe_migrate_json()
            return
        if self._path.exists():
            try:
                self._sessions = json.loads(self._path.read_text(encoding="utf-8"))
                logger.info(f"会话数据加载完成: {len(self._sessions)} 个会话")
            except Exception as exc:
                logger.warning(f"会话数据加载失败，使用空数据: {exc}")
                self._sessions = {}

    def _maybe_migrate_json(self):
        """首次从 JSON 切换到 SQLite 时，导入既有会话。"""
        if self._backend != "sqlite" or not self._path.exists():
            return
        try:
            with self._ensure_engine().connect() as conn:
                count = conn.execute(text("SELECT COUNT(*) FROM chat_sessions")).scalar() or 0
            if count:
                return
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for session_id, session in raw.items():
                session.setdefault("id", session_id)
                self._sql_upsert(session_id, session)
            if raw:
                logger.info(f"已迁移 JSON 会话到 SQLite: {len(raw)} 条")
        except Exception as exc:
            logger.warning(f"JSON 会话迁移失败，忽略: {exc}")

    # ------------------------------------------------------------------ json
    def _save_json(self):
        try:
            self._path.write_text(
                json.dumps(self._sessions, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.error(f"会话数据保存失败: {exc}")

    # ------------------------------------------------------------------ sql
    def _sql_upsert(self, session_id: str, session: dict):
        with self._ensure_engine().begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO chat_sessions (id, title, payload, user_id, created_at, updated_at)
                    VALUES (:id, :title, :payload, :user_id, :created_at, :updated_at)
                    ON CONFLICT (id) DO UPDATE SET
                        title = EXCLUDED.title,
                        payload = EXCLUDED.payload,
                        user_id = EXCLUDED.user_id,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                {
                    "id": session_id,
                    "title": session.get("title") or "新对话",
                    "payload": json.dumps(session, ensure_ascii=False),
                    "user_id": self._user_id_label(session.get("user_id")),
                    "created_at": session.get("createdAt", 0),
                    "updated_at": session.get("updatedAt", 0),
                },
            )

    def _sql_get(self, session_id: str) -> dict | None:
        with self._ensure_engine().connect() as conn:
            row = conn.execute(
                text("SELECT payload FROM chat_sessions WHERE id = :id"),
                {"id": session_id},
            ).mappings().first()
        if not row:
            return None
        payload = row["payload"]
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except Exception:
                logger.warning(f"会话 payload 解析失败: {session_id}")
                return None
        return payload

    def _sql_get_history(self, session_id: str, limit: int = 10, user_id=None) -> list:
        session = self._sql_get(session_id)
        if not self._owned(session, user_id):
            return []
        if not session:
            return []
        cleaned = []
        for raw in session.get("messages", []):
            if not isinstance(raw, dict):
                continue
            msg = {k: raw.get(k) for k in _JSON_MESSAGE_FIELDS if k in raw}
            if "references" in msg and msg["references"] is not None and not isinstance(msg["references"], list):
                msg["references"] = list(msg["references"])
            cleaned.append(msg)
        return cleaned[-limit:]

    def _sql_list(self, user_id=None) -> list:
        with self._ensure_engine().connect() as conn:
            if user_id is not None:
                rows = conn.execute(
                    text(
                        """
                        SELECT payload FROM chat_sessions
                        WHERE user_id = :user_id
                        ORDER BY updated_at DESC
                        """
                    ),
                    {"user_id": self._user_id_label(user_id)},
                ).mappings().all()
            else:
                rows = conn.execute(
                    text("SELECT payload FROM chat_sessions ORDER BY updated_at DESC")
                ).mappings().all()
        sessions: list = []
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                try:
                    sessions.append(json.loads(payload))
                except Exception:
                    continue
            else:
                sessions.append(payload)
        return sessions

    def _sql_delete(self, session_id: str, user_id=None) -> bool:
        if user_id is not None:
            session = self._sql_get(session_id)
            if not self._owned(session, user_id):
                return False
        with self._ensure_engine().begin() as conn:
            result = conn.execute(text("DELETE FROM chat_sessions WHERE id = :id"), {"id": session_id})
            return bool(result.rowcount)

    @staticmethod
    def _owned(session: Optional[dict], user_id) -> bool:
        if user_id is None:
            return True
        if not session:
            return False
        return session.get("user_id") == user_id

    @staticmethod
    def _user_id_label(user_id) -> str | None:
        return None if user_id is None else str(user_id)

    # ------------------------------------------------------------ public api
    def create(self, title: str = "新对话", session_id: str | None = None, user_id=None) -> dict:
        session_id = session_id or str(uuid.uuid4())
        if self.get(session_id):
            raise ValueError(f"会话已存在: {session_id}")
        now = int(time.time() * 1000)
        session = {
            "id": session_id,
            "title": title,
            "messages": [],
            "user_id": user_id,
            "createdAt": now,
            "updatedAt": now,
        }
        if self._sql_ready:
            self._sql_upsert(session_id, session)
        else:
            self._sessions[session_id] = session
            self._save_json()
        return dict(session)

    def get(self, session_id: str, user_id=None) -> dict | None:
        if self._sql_ready:
            session = self._sql_get(session_id)
        else:
            session = self._sessions.get(session_id)
        if not session or not self._owned(session, user_id):
            return None
        return dict(session)

    def list(self, user_id=None) -> list:
        sessions = (
            self._sql_list(user_id)
            if self._sql_ready
            else [dict(s) for s in self._sessions.values() if self._owned(s, user_id)]
        )
        sessions.sort(key=lambda x: x.get("updatedAt", 0), reverse=True)
        return sessions

    def add_messages(self, session_id: str, messages: list, user_id=None) -> dict | None:
        session = self.get(session_id, user_id=user_id)
        if not session:
            return None
        session["messages"].extend(messages)
        session["updatedAt"] = int(time.time() * 1000)
        if session.get("title") == "新对话" and messages:
            first_user = next((m for m in messages if m.get("role") == "user"), None)
            if first_user:
                content = first_user.get("content", "")
                session["title"] = content[:20] + ("…" if len(content) > 20 else "")
        if self._sql_ready:
            self._sql_upsert(session_id, session)
        else:
            self._sessions[session_id] = session
            self._save_json()
        return dict(session)

    def get_history(self, session_id: str, limit: int = 10, user_id=None) -> list:
        if self._sql_ready:
            return self._sql_get_history(session_id, limit, user_id=user_id)
        session = self._sessions.get(session_id)
        if not self._owned(session, user_id) or not session:
            return []
        return session.get("messages", [])[-limit:]

    def get_message(self, session_id: str, message_id: str, user_id=None) -> dict | None:
        """按 message_id 读取会话中的某条消息（跨 SQL/JSON 后端）。"""
        if not message_id:
            return None
        for msg in self.get_history(session_id, limit=1000, user_id=user_id):
            if isinstance(msg, dict) and msg.get("id") == message_id:
                return msg
        return None

    def delete(self, session_id: str, user_id=None) -> bool:
        if self._sql_ready:
            return self._sql_delete(session_id, user_id=user_id)
        if not self._owned(self._sessions.get(session_id), user_id):
            return False
        if session_id in self._sessions:
            del self._sessions[session_id]
            self._save_json()
            return True
        return False

    def delete_by_user(self, user_id) -> int:
        """删除指定用户的全部会话，返回删除条数。"""
        uid = self._user_id_label(user_id)
        if uid is None:
            return 0
        if self._sql_ready:
            try:
                with self._ensure_engine().begin() as conn:
                    result = conn.execute(
                        text("DELETE FROM chat_sessions WHERE user_id = :uid"),
                        {"uid": uid},
                    )
                    return int(result.rowcount or 0)
            except Exception as exc:
                logger.warning(f"按用户删除会话失败: {exc}")
                return 0
        # JSON 回退模式
        before = len(self._sessions)
        self._sessions = {
            sid: s for sid, s in self._sessions.items()
            if s.get("user_id") != uid
        }
        removed = before - len(self._sessions)
        if removed:
            self._save_json()
        return removed


session_store = SessionStore()
