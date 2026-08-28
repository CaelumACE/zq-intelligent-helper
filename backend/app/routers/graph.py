"""知识图谱查询 API（S06 Phase1：精确匹配 + 别名扩展 + BFS）。"""
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator

from app.routers.auth import current_user
from app.services.graph_store import graph_store

router = APIRouter()


class GraphQueryRequest(BaseModel):
    query: str
    entity_hints: Optional[List[str]] = None
    depth: int = 2
    entity_types: Optional[List[str]] = None

    @field_validator('depth')
    @classmethod
    def check_depth(cls, v):
        return min(max(int(v), 1), 3)


@router.post("/query")
async def graph_query(body: GraphQueryRequest, user=Depends(current_user)):
    """图谱查询：返回匹配节点、直接关联边与 depth 内子图。"""
    entities = [h.strip() for h in (body.entity_hints or []) if (h or "").strip()]
    if not entities and body.query:
        entities = [body.query]

    matched: List[dict] = []
    for entity in entities:
        for n in graph_store.find_node(entity, entity_types=body.entity_types):
            if n["id"] not in {m["id"] for m in matched}:
                matched.append(n)

    subgraph = graph_store.get_subgraph([n["name"] for n in matched], depth=body.depth)

    edges = []
    edge_seen = set()
    relation_order = {"contains": 0, "requires": 1, "belongs_to": 2, "precedes": 3}
    for e in subgraph["edges"]:
        key = (e["source_id"], e["target_id"], e["relation_type"])
        if key in edge_seen:
            continue
        edge_seen.add(key)
        source_name = next((n["name"] for n in subgraph["nodes"] if n["id"] == e["source_id"]), str(e["source_id"]))
        target_name = next((n["name"] for n in subgraph["nodes"] if n["id"] == e["target_id"]), str(e["target_id"]))
        edges.append({
            "source_id": e["source_id"],
            "target_id": e["target_id"],
            "source": source_name,
            "target": target_name,
            "relation": e["relation_type"],
            "weight": e.get("weight", 1.0),
            "properties": e.get("properties", {}),
        })
    edges.sort(key=lambda x: relation_order.get(x["relation"], 9))

    return {
        "query": body.query,
        "matched_nodes": matched,
        "edges": edges,
        "subgraph": {
            "nodes": subgraph["nodes"],
            "edges": edges,
        },
        "stats": graph_store.stats(),
    }


@router.get("/health")
async def graph_health(user=Depends(current_user)):
    """图谱表初始化与规模探测。"""
    return {
        "ready": graph_store.ready,
        "mode": "postgres" if graph_store.ready else "memory",
        "stats": graph_store.stats(),
    }
