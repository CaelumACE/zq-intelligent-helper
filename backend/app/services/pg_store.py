"""PG 统一存储：知识库文档元数据、别名配置、检索日志、反馈日志。

PG 可用时读写同一个 gov_assistant 库；PG 不可用时上层回退到 JSON/JSONL，
沙盒开发与零基础设施演示不受影响。
"""
import json
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.core.logger import logger

_RETENTION_DAYS = 7

_SCHEMA = """
CREATE TABLE IF NOT EXISTS retrieval_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT,
    raw_query TEXT,
    intent TEXT,
    payload TEXT NOT NULL,
    created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id TEXT,
    message_id TEXT,
    rating TEXT,
    payload TEXT NOT NULL DEFAULT '{}',
    created_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_documents (
    doc_type TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at BIGINT NOT NULL
);
CREATE TABLE IF NOT EXISTS knowledge_aliases (
    key TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at BIGINT NOT NULL
);
"""


class PGStore:
    """统一 PostgreSQL 业务数据存取；非 PG 环境自动禁用。"""

    def __init__(self):
        self._engine = None
        self._ready: bool | None = None
        self._url = (settings.DATABASE_URL or "").strip()

    @property
    def _is_pg(self) -> bool:
        return self._url.startswith("postgresql") or self._url.startswith("postgres+")

    @property
    def ready(self) -> bool:
        return self._ready is True

    def _ensure_engine(self):
        if self._engine is None:
            self._engine = create_engine(
                self._url,
                pool_pre_ping=True,
                pool_recycle=300,
                connect_args={"connect_timeout": 3},
            )
        return self._engine

    def ensure_schema(self) -> bool:
        if self._ready is True:
            return True
        if not self._is_pg:
            self._ready = False
            return False
        try:
            with self._ensure_engine().begin() as conn:
                conn.execute(text(_SCHEMA))
                cutoff = int((time.time() - _RETENTION_DAYS * 86400) * 1000)
                conn.execute(
                    text("DELETE FROM retrieval_logs WHERE created_at < :cutoff"),
                    {"cutoff": cutoff},
                )
            self._ready = True
            return True
        except Exception as exc:  # pragma: no cover - PG 不可用时静默降级
            logger.warning(f"PG 业务表初始化失败，回退文件存储: {exc}")
            self._ready = False
            return False

    def _run_insert(self, sql: str, params: dict) -> bool:
        if not self.ensure_schema():
            return False
        try:
            with self._ensure_engine().begin() as conn:
                conn.execute(text(sql), params)
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning(f"PG 写失败，回退文件存储: {exc}")
            return False

    def insert_retrieval_log(self, record: Dict[str, Any]) -> bool:
        return self._run_insert(
            "INSERT INTO retrieval_logs (session_id, raw_query, intent, payload, created_at) "
            "VALUES (:session_id, :raw_query, :intent, :payload, :created_at)",
            {
                "session_id": record.get("session_id"),
                "raw_query": record.get("raw_query"),
                "intent": record.get("intent"),
                "payload": json.dumps(record, ensure_ascii=False),
                "created_at": int(time.time() * 1000),
            },
        )

    def insert_feedback(self, session_id: str, message_id: str, rating: str = "", payload: Optional[Dict[str, Any]] = None) -> bool:
        return self._run_insert(
            "INSERT INTO feedback_logs (session_id, message_id, rating, payload, created_at) "
            "VALUES (:session_id, :message_id, :rating, :payload, :created_at)",
            {
                "session_id": session_id,
                "message_id": message_id,
                "rating": rating,
                "payload": json.dumps(payload or {}, ensure_ascii=False),
                "created_at": int(time.time() * 1000),
            },
        )

    def has_feedback(self, session_id: str, message_id: str, user_id: str) -> bool:
        """检查同一 session+message+user 是否已提交过反馈（幂等用）。PG 不可用时返回 False（不阻断）。"""
        if not self.ensure_schema():
            return False
        try:
            with self._ensure_engine().begin() as conn:
                row = conn.execute(
                    text(
                        "SELECT 1 FROM feedback_logs "
                        "WHERE session_id = :session_id AND message_id = :message_id "
                        "AND payload::text LIKE :user_pattern LIMIT 1"
                    ),
                    {
                        "session_id": session_id,
                        "message_id": message_id,
                        "user_pattern": f'%"user_id": "{user_id}"%',
                    },
                ).fetchone()
                return row is not None
        except Exception as exc:
            logger.warning(f"反馈查重查询失败（降级为不拦截）: {exc}")
            return False

    def save_documents(self, documents: Dict[str, List[Any]]) -> bool:
        if not self.ensure_schema():
            return False
        now = int(time.time() * 1000)
        ok = True
        for doc_type, items in documents.items():
            if not isinstance(items, list):
                continue
            ok = self._run_insert(
                "INSERT INTO knowledge_documents (doc_type, payload, updated_at) "
                "VALUES (:doc_type, :payload, :updated_at) "
                "ON CONFLICT (doc_type) DO UPDATE SET payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at",
                {
                    "doc_type": doc_type,
                    "payload": json.dumps(items, ensure_ascii=False),
                    "updated_at": now,
                },
            ) and ok
        return ok

    def load_documents(self) -> Optional[Dict[str, List[Any]]]:
        if not self.ensure_schema():
            return None
        try:
            with self._ensure_engine().connect() as conn:
                rows = conn.execute(text("SELECT doc_type, payload FROM knowledge_documents")).mappings().all()
            if not rows:
                return None
            result: Dict[str, List[Any]] = {}
            for row in rows:
                result[row["doc_type"]] = json.loads(row["payload"])
            return result
        except Exception as exc:  # pragma: no cover
            logger.warning(f"PG 读取知识库文档失败: {exc}")
            return None

    def save_aliases(self, data: Dict[str, Any]) -> bool:
        return self._run_insert(
            "INSERT INTO knowledge_aliases (key, payload, updated_at) "
            "VALUES ('aliases_config', :payload, :updated_at) "
            "ON CONFLICT (key) DO UPDATE SET payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at",
            {
                "payload": json.dumps(data, ensure_ascii=False),
                "updated_at": int(time.time() * 1000),
            },
        )

    def load_aliases(self) -> Optional[Dict[str, Any]]:
        if not self.ensure_schema():
            return None
        try:
            with self._ensure_engine().connect() as conn:
                row = conn.execute(
                    text("SELECT payload FROM knowledge_aliases WHERE key = 'aliases_config'")
                ).mappings().first()
            if not row:
                return None
            return json.loads(row["payload"])
        except Exception as exc:  # pragma: no cover
            logger.warning(f"PG 读取别名配置失败: {exc}")
            return None


pg_store = PGStore()
