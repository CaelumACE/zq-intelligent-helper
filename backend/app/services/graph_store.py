"""知识图谱存储层：PostgreSQL 邻接表（memory 回退）。

Phase1 不引入 Neo4j 等中间件，用 nodes + edges 两张表承载：
- 5 类实体：policy / service / material / department / process_node
- 4 类关系：contains / requires / belongs_to / precedes

PG 不可用时回退到进程内内存图，接口保持一致，方便本地开发与测试。
"""
import json
import time
from collections import defaultdict, deque
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text

from app.core.config import settings
from app.core.logger import logger

_SCHEMA = """
CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
    id BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    aliases JSONB NOT NULL DEFAULT '[]',
    properties JSONB NOT NULL DEFAULT '{}',
    source_ref TEXT NOT NULL DEFAULT '',
    created_at BIGINT NOT NULL,
    CONSTRAINT uq_node_type_name UNIQUE (entity_type, name)
);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_type ON knowledge_graph_nodes(entity_type);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_name ON knowledge_graph_nodes(name);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_aliases ON knowledge_graph_nodes USING gin(aliases);
CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
    target_id BIGINT NOT NULL REFERENCES knowledge_graph_nodes(id) ON DELETE CASCADE,
    relation_type TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    properties JSONB NOT NULL DEFAULT '{}',
    created_at BIGINT NOT NULL,
    CONSTRAINT uq_graph_edge UNIQUE (source_id, target_id, relation_type)
);
CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON knowledge_graph_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON knowledge_graph_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_relation ON knowledge_graph_edges(relation_type);
"""


class GraphStore:
    """政务知识图谱存储与查询；PG 不可用时回退内存。"""

    def __init__(self):
        self._engine = None
        self._ready: bool | None = None
        self._url = (settings.DATABASE_URL or "").strip()
        # memory fallback
        self._mem_nodes: Dict[int, dict] = {}
        self._mem_edges: List[dict] = []
        self._mem_name_index: Dict[str, int] = {}
        self._mem_next_id = 1

    @property
    def _is_pg(self) -> bool:
        return self._url.startswith("postgresql") or self._url.startswith("postgres+")

    @property
    def ready(self) -> bool:
        return self._ready is True

    def _ensure_engine(self):
        if self._engine is None and self._is_pg:
            self._engine = create_engine(
                self._url,
                pool_pre_ping=True,
                pool_recycle=300,
                connect_args={"connect_timeout": 3},
            )
        return self._engine

    # ------------------------------------------------------------------
    # 内存回退
    # ------------------------------------------------------------------
    def _ensure_memory(self):
        if self._ready is None:
            self._ready = False

    def _mem_upsert_node(self, entity_type: str, name: str, aliases: List[str], properties: Dict[str, Any], source_ref: str) -> int:
        key = f"{entity_type}\0{name}"
        node_id = self._mem_name_index.get(key)
        if node_id is None:
            node_id = self._mem_next_id
            self._mem_next_id += 1
            self._mem_name_index[key] = node_id
            self._mem_nodes[node_id] = {
                "id": node_id,
                "entity_type": entity_type,
                "name": name,
                "aliases": [],
                "properties": {},
                "source_ref": "",
            }
        node = self._mem_nodes[node_id]
        node["aliases"] = list(dict.fromkeys(aliases or []))
        node["properties"] = dict(properties or {})
        node["source_ref"] = source_ref or ""
        return node_id

    def _mem_upsert_edge(self, source_name: str, target_name: str, relation_type: str, weight: float, properties: Dict[str, Any]) -> bool:
        # 内存图不要求 source/target 同 entity_type，按 name 查找已存在节点
        source_id = next((nid for nid, n in self._mem_nodes.items() if n["name"] == source_name), None)
        target_id = next((nid for nid, n in self._mem_nodes.items() if n["name"] == target_name), None)
        if source_id is None or target_id is None:
            return False
        for e in self._mem_edges:
            if e["source_id"] == source_id and e["target_id"] == target_id and e["relation_type"] == relation_type:
                e["weight"] = float(weight)
                e["properties"] = dict(properties or {})
                return True
        self._mem_edges.append({
            "source_id": source_id,
            "target_id": target_id,
            "relation_type": relation_type,
            "weight": float(weight),
            "properties": dict(properties or {}),
        })
        return True

    def _mem_all_nodes(self) -> List[dict]:
        return [dict(n) for n in self._mem_nodes.values()]

    def _mem_all_edges(self) -> List[dict]:
        return [dict(e) for e in self._mem_edges]

    def _mem_clear(self):
        self._mem_nodes = {}
        self._mem_edges = []
        self._mem_name_index = {}
        self._mem_next_id = 1

    # ------------------------------------------------------------------
    # PG 持久化
    # ------------------------------------------------------------------
    def ensure_schema(self) -> bool:
        if self._ready is True:
            return True
        if not self._is_pg:
            self._ensure_memory()
            return False
        try:
            with self._ensure_engine().begin() as conn:
                conn.execute(text(_SCHEMA))
            self._ready = True
            logger.info("知识图谱 PG 表已就绪")
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning(f"知识图谱 PG 表初始化失败，回退内存: {exc}")
            self._ensure_memory()
            self._ready = False
            return False

    def _pg_all_nodes(self) -> List[dict]:
        with self._ensure_engine().connect() as conn:
            rows = conn.execute(text(
                "SELECT id, entity_type, name, aliases, properties, source_ref FROM knowledge_graph_nodes"
            )).mappings().all()
        return [
            {
                "id": row["id"],
                "entity_type": row["entity_type"],
                "name": row["name"],
                "aliases": json.loads(row["aliases"] or "[]") if isinstance(row["aliases"], str) else (row["aliases"] or []),
                "properties": json.loads(row["properties"] or "{}") if isinstance(row["properties"], str) else (row["properties"] or {}),
                "source_ref": row["source_ref"] or "",
            }
            for row in rows
        ]

    def _pg_all_edges(self) -> List[dict]:
        with self._ensure_engine().connect() as conn:
            rows = conn.execute(text(
                "SELECT source_id, target_id, relation_type, weight, properties FROM knowledge_graph_edges"
            )).mappings().all()
        return [
            {
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "relation_type": row["relation_type"],
                "weight": float(row["weight"] or 1.0),
                "properties": json.loads(row["properties"] or "{}") if isinstance(row["properties"], str) else (row["properties"] or {}),
            }
            for row in rows
        ]

    def upsert_node(self, entity_type: str, name: str, aliases: Optional[List[str]] = None, properties: Optional[Dict[str, Any]] = None, source_ref: str = "") -> int:
        name = (name or "").strip()
        if not name or not entity_type:
            raise ValueError("entity_type 和 name 不能为空")
        aliases = [a.strip() for a in (aliases or []) if (a or "").strip()]
        properties = properties or {}

        if not self.ensure_schema():
            return self._mem_upsert_node(entity_type, name, aliases, properties, source_ref)

        sql = """
            INSERT INTO knowledge_graph_nodes (entity_type, name, aliases, properties, source_ref, created_at)
            VALUES (:entity_type, :name, CAST(:aliases AS jsonb), CAST(:properties AS jsonb), :source_ref, :created_at)
            ON CONFLICT (entity_type, name)
            DO UPDATE SET aliases = EXCLUDED.aliases, properties = EXCLUDED.properties, source_ref = EXCLUDED.source_ref
            RETURNING id
        """
        with self._ensure_engine().begin() as conn:
            row = conn.execute(text(sql), {
                "entity_type": entity_type,
                "name": name,
                "aliases": json.dumps(aliases, ensure_ascii=False),
                "properties": json.dumps(properties, ensure_ascii=False),
                "source_ref": source_ref or "",
                "created_at": int(time.time() * 1000),
            }).mappings().first()
        return int(row["id"])

    def upsert_edge(self, source_name: str, target_name: str, relation_type: str, weight: float = 1.0, properties: Optional[Dict[str, Any]] = None) -> bool:
        source_name = (source_name or "").strip()
        target_name = (target_name or "").strip()
        relation_type = (relation_type or "").strip()
        if not source_name or not target_name or not relation_type:
            return False
        properties = properties or {}

        if not self.ensure_schema():
            return self._mem_upsert_edge(source_name, target_name, relation_type, weight, properties)

        try:
            with self._ensure_engine().begin() as conn:
                conn.execute(text("""
                    INSERT INTO knowledge_graph_edges (source_id, target_id, relation_type, weight, properties, created_at)
                    SELECT s.id, t.id, :relation_type, :weight, CAST(:properties AS jsonb), :created_at
                    FROM knowledge_graph_nodes s, knowledge_graph_nodes t
                    WHERE s.name = :source_name AND t.name = :target_name
                    ON CONFLICT (source_id, target_id, relation_type)
                    DO UPDATE SET weight = EXCLUDED.weight, properties = EXCLUDED.properties
                """), {
                    "relation_type": relation_type,
                    "weight": float(weight),
                    "properties": json.dumps(properties, ensure_ascii=False),
                    "created_at": int(time.time() * 1000),
                    "source_name": source_name,
                    "target_name": target_name,
                })
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning(f"图谱边写入失败: {exc}")
            return False

    def clear_all(self) -> bool:
        if not self.ensure_schema():
            self._mem_clear()
            return True
        try:
            with self._ensure_engine().begin() as conn:
                conn.execute(text("DELETE FROM knowledge_graph_edges"))
                conn.execute(text("DELETE FROM knowledge_graph_nodes"))
            return True
        except Exception as exc:  # pragma: no cover
            logger.warning(f"图谱清空失败: {exc}")
            return False

    def all_nodes(self) -> List[dict]:
        if not self.ensure_schema():
            return self._mem_all_nodes()
        return self._pg_all_nodes()

    def all_edges(self) -> List[dict]:
        if not self.ensure_schema():
            return self._mem_all_edges()
        return self._pg_all_edges()

    def stats(self) -> Dict[str, int]:
        return {"nodes": len(self.all_nodes()), "edges": len(self.all_edges())}

    # ------------------------------------------------------------------
    # 查询语义
    # ------------------------------------------------------------------
    def find_node(self, query: str, entity_types: Optional[List[str]] = None) -> List[dict]:
        """按 name 精确、别名精确、前缀匹配三档查找实体。"""
        query = (query or "").strip()
        if not query:
            return []
        nodes = []
        for n in self.all_nodes():
            if entity_types and n["entity_type"] not in entity_types:
                continue
            aliases = {str(a).strip() for a in n.get("aliases", []) if str(a).strip()}
            if n["name"] == query:
                n = {**n, "match_reason": "name"}
                nodes.append(n)
            elif query in aliases:
                n = {**n, "match_reason": "alias:" + query}
                nodes.append(n)
            elif n["name"].startswith(query) or any(a.startswith(query) for a in aliases):
                n = {**n, "match_reason": "prefix"}
                nodes.append(n)
        # 排序：精确 name > alias > prefix
        order = {"name": 0, "alias": 1, "prefix": 2}
        nodes.sort(key=lambda x: order.get(str(x.get("match_reason", "")).split(":", 1)[0], 3) if x.get("match_reason") != "name" else order["name"])
        return nodes

    def _resolve_nodes(self, names: List[str], entity_types: Optional[List[str]] = None) -> List[dict]:
        nodes = self.all_nodes()
        found = []
        for name in names:
            name = (name or "").strip()
            if not name:
                continue
            for n in nodes:
                if entity_types and n["entity_type"] not in entity_types:
                    continue
                if n["name"] == name:
                    found.append(n)
                    break
        return found

    def get_neighbors(self, node_id: int, relation_type: Optional[str] = None, depth: int = 1) -> Dict[str, Any]:
        nodes = self.all_nodes()
        edges = self.all_edges()
        node_by_id = {n["id"]: n for n in nodes}
        depth = max(1, min(int(depth), 3))

        seen_nodes: Dict[int, str] = {}
        seen_edges: Dict[tuple, dict] = {}
        if node_id in node_by_id:
            seen_nodes[node_id] = "root"

        frontier = [node_id]
        for _ in range(depth):
            next_frontier = []
            for nid in frontier:
                for e in edges:
                    if relation_type and e["relation_type"] != relation_type:
                        continue
                    if e["source_id"] == nid or e["target_id"] == nid:
                        other = e["source_id"] if e["target_id"] == nid else e["target_id"]
                        key = (min(e["source_id"], e["target_id"]), max(e["source_id"], e["target_id"]), e["relation_type"])
                        seen_edges[key] = e
                        if other not in seen_nodes:
                            seen_nodes[other] = "level"
                            next_frontier.append(other)
            frontier = next_frontier
            if not frontier:
                break

        return {
            "nodes": [node_by_id[nid] for nid in seen_nodes if nid in node_by_id],
            "edges": list(seen_edges.values()),
            "depth": depth,
        }

    def get_subgraph(self, entity_names: List[str], depth: int = 2, relation_type: Optional[str] = None) -> Dict[str, Any]:
        depth = max(1, min(int(depth), 3))
        roots = self._resolve_nodes(entity_names)
        node_ids = []
        for r in roots:
            if r["id"] not in node_ids:
                node_ids.append(r["id"])

        all_nodes = {}
        all_edges = {}
        for root_id in node_ids:
            part = self.get_neighbors(root_id, relation_type=relation_type, depth=depth)
            for n in part["nodes"]:
                all_nodes[n["id"]] = n
            for e in part["edges"]:
                key = (e["source_id"], e["target_id"], e["relation_type"])
                all_edges[key] = e
        return {"nodes": list(all_nodes.values()), "edges": list(all_edges.values()), "roots": roots}


graph_store = GraphStore()
