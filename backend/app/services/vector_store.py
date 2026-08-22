"""PostgreSQL + pgvector 向量存储（可选启用）

回退策略：
- 配置为 postgresql+psycopg2 时，优先走 pgvector；
- PG 不可用 / 未建索引时自动回退到现有内存向量检索；
- 当前沙盒无 Docker/PG 时使用 SQLite + 内存路径，不影响本地开发。
"""
import time
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logger import logger
from sqlalchemy import create_engine, text


class VectorStore:
    """pgvector 索引管理 + 向量召回，仅承载检索能力，不处理业务语义。"""

    def __init__(self):
        self._engine = None
        self._ready = None
        self.mode = self._resolve_mode()

    def _resolve_mode(self) -> str:
        url = (settings.DATABASE_URL or "").strip().lower()
        if url.startswith("postgresql") or url.startswith("postgres+"):
            return "postgres"
        return "memory"

    def _ensure_engine(self):
        if self._engine is None and self.mode == "postgres":
            self._engine = create_engine(
                settings.DATABASE_URL,
                pool_pre_ping=True,
                pool_recycle=300,
                connect_args={"connect_timeout": 3},
            )
        return self._engine

    @property
    def initialized(self) -> bool:
        return self._ready is True

    def initialize_database(self) -> bool:
        """建扩展与表结构；失败时返回 False 不阻塞主服务。"""
        if self.mode != "postgres":
            return False
        engine = self._ensure_engine()
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                dim = max(1, int(getattr(settings, "EMBEDDING_DIMENSION", 1536)))
                conn.execute(
                    text(
                        f"""
                        CREATE TABLE IF NOT EXISTS knowledge_chunks (
                            id TEXT PRIMARY KEY,
                            type TEXT NOT NULL,
                            title TEXT NOT NULL,
                            category TEXT,
                            summary TEXT,
                            source TEXT,
                            keywords TEXT,
                            embedding vector({dim})
                        )
                        """
                    )
                )
            self._ready = True
            logger.info("PostgreSQL + pgvector 已就绪")
            return True
        except Exception as exc:
            self._ready = False
            logger.warning(f"PostgreSQL + pgvector 初始化失败，回退内存检索: {exc}")
            return False

    def ensure_ready(self) -> bool:
        if self.mode != "postgres":
            return False
        if self._ready is not None:
            return self._ready
        return self.initialize_database()

    def rebuild_from_corpus(self, chunks: List[Dict[str, Any]], vectors: List[List[float]]) -> bool:
        """用当前块与本地 embedding 缓存重建向量表。"""
        if not self.ensure_ready():
            return False
        if len(chunks) != len(vectors):
            logger.warning("向量数不一致，跳过 pgvector 重建")
            return False
        if not chunks:
            return False
        engine = self._ensure_engine()
        rows = []
        for chunk, vector in zip(chunks, vectors):
            text_content = f"{chunk.get('title','')} {chunk.get('summary','')} {chunk.get('keywords','')}"
            rows.append(
                {
                    "id": chunk.get("id", ""),
                    "type": chunk.get("type", ""),
                    "title": chunk.get("title", ""),
                    "category": chunk.get("category", ""),
                    "summary": chunk.get("summary", ""),
                    "source": chunk.get("source", ""),
                    "keywords": chunk.get("keywords", "") or text_content,
                    "embedding": vector,
                }
            )
        try:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM knowledge_chunks"))
                for row in rows:
                    conn.execute(
                        text(
                            """
                            INSERT INTO knowledge_chunks
                                (id, type, title, category, summary, source, keywords, embedding)
                            VALUES
                                (:id, :type, :title, :category, :summary, :source, :keywords, :embedding)
                            """
                        ),
                        row,
                    )
            logger.info(f"pgvector 索引重建完成: {len(rows)} 条")
            self._ready = True
            return True
        except Exception as exc:
            logger.warning(f"pgvector 索引重建失败，使用内存召回: {exc}")
            return False

    def search_sync(self, query_vector: List[float], top_k: int = 10) -> Optional[List[Dict[str, Any]]]:
        """向量召回，返回候选块快照。"""
        if not query_vector or not self.ensure_ready():
            return None
        engine = self._ensure_engine()
        try:
            limit = max(5, min(int(top_k), 50))
            with engine.connect() as conn:
                rows = conn.execute(
                    text(
                        """
                        SELECT id, type, title, category, summary, source,
                               1 - (embedding <=> CAST(:query AS vector)) AS semantic_score
                        FROM knowledge_chunks
                        WHERE embedding IS NOT NULL
                        ORDER BY embedding <=> CAST(:query AS vector)
                        LIMIT :limit
                        """
                    ),
                    {"query": query_vector, "limit": limit},
                ).mappings().all()
                return [dict(row) for row in rows]
        except Exception as exc:
            logger.warning(f"pgvector 向量召回失败，降级关键词检索: {exc}")
            return None

    def status(self) -> Dict[str, Any]:
        health = self._ready or False
        if self.mode == "postgres":
            try:
                count = 0
                if self.ensure_ready():
                    with self._ensure_engine().connect() as conn:
                        count = conn.execute(text("SELECT COUNT(*) FROM knowledge_chunks")).scalar() or 0
                return {
                    "engine": "pgvector",
                    "ready": bool(health),
                    "indexed_chunks": int(count),
                }
            except Exception as exc:
                return {"engine": "pgvector", "ready": False, "error": str(exc)}
        return {"engine": "memory", "ready": True, "indexed_chunks": None}


vector_store = VectorStore()
