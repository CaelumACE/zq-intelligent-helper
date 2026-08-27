"""Sprint 02 知识库运营后台 API。"""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.routers.auth import current_user
from app.services import kb_admin_store as store
from app.services.document_parser import extract_text, safe_filename
from app.services.vector_store import vector_store

router = APIRouter()

_SEARCH_PATTERN = "%%s%"  # 仅标记占位，实际使用参数化 LIKE


class ItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    category: str = Field(default="policy", max_length=50)
    doc_type: str = Field(default="policy", max_length=50)
    source: str = ""
    aliases: list[str] = Field(default_factory=list)


class ItemUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    doc_type: str | None = None
    source: str | None = None
    metadata: dict | None = None
    aliases: list[str] | None = None


def _require_admin(user) -> None:
    if getattr(user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="需要管理员权限")


@router.get("/knowledge/items")
async def list_items(category: str | None = None, search: str | None = None, doc_type: str | None = None, user=Depends(current_user)):
    return {"items": store.list_items(category=category, status="active", search=search, doc_type=doc_type)}


@router.get("/knowledge/items/all")
async def list_all_items(user=Depends(current_user)):
    _require_admin(user)
    return {"items": store.list_items()}


@router.get("/knowledge/items/{item_id}")
async def get_item(item_id: int, user=Depends(current_user)):
    item = store.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="条目不存在")
    return {"item": item}


@router.post("/knowledge/items")
async def create_item(body: ItemCreate, user=Depends(current_user)):
    _require_admin(user)
    try:
        item = store.create_item(
            body.title, body.content, body.category, body.source,
            metadata={"aliases": list(body.aliases or [])},
            doc_type=body.doc_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"item": item}


@router.put("/knowledge/items/{item_id}")
async def update_item(item_id: int, body: ItemUpdate, user=Depends(current_user)):
    _require_admin(user)
    if body.aliases is not None and body.metadata is None:
        body.metadata = {"aliases": list(body.aliases)}
    elif body.aliases is not None and isinstance(body.metadata, dict):
        body.metadata["aliases"] = list(body.aliases)
    item = store.update_item(
        item_id, body.title, body.content, body.category, body.source, body.metadata, body.doc_type,
    )
    if not item:
        raise HTTPException(status_code=404, detail="条目不存在")
    return {"item": item}


@router.delete("/knowledge/items/{item_id}")
async def delete_item(item_id: int, user=Depends(current_user)):
    _require_admin(user)
    if not store.delete_item(item_id):
        raise HTTPException(status_code=404, detail="条目不存在")
    return {"ok": True}


@router.post("/knowledge/items/{item_id}/toggle")
async def toggle_item(item_id: int, user=Depends(current_user)):
    _require_admin(user)
    item = store.toggle_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="条目不存在")
    return {"item": item}


@router.post("/knowledge/upload")
async def upload_and_embed(file: UploadFile = File(...), user=Depends(current_user)):
    _require_admin(user)
    if file.size > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 10MB")
    title = safe_filename(file.filename or "upload")
    try:
        text = extract_text(file.filename or "", await file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not text.strip():
        raise HTTPException(status_code=400, detail="未解析到文本内容")
    try:
        item = store.create_item(title=title, content=text, category="policy", source=file.filename or "文件上传", doc_type="policy")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

    vectorized = sync_item_vector(item, text, replace=True)
    return {"item": item, "vectorized": vectorized}


def sync_item_vector(item: dict, text: str, replace: bool = False) -> bool:
    from app.services.embedding_service import embedding_service

    try:
        chunks = _chunk_text(text)
        vectors = embedding_service.sync_embed_batch(chunks, "kb_upload")
        if not vectors or not vector_store.mode == "postgres":
            return False
        rows = [
            {
                "id": f"kb_item_{item['id']}_{i}",
                "type": "kb_item",
                "title": item["title"],
                "category": item["category"],
                "summary": (chunks[i] or "")[:200],
                "source": item["source"],
                "keywords": chunks[i] or "",
                "embedding": vectors[i],
            }
            for i in range(min(len(chunks), len(vectors)))
        ]
        if vector_store.ensure_ready():
            from sqlalchemy import text as sql_text

            engine = vector_store._ensure_engine()
            with engine.begin() as conn:
                if replace:
                    conn.execute(
                        sql_text("DELETE FROM knowledge_chunks WHERE id LIKE :pattern"),
                        {"pattern": f"kb_item_{item['id']}_%"},
                    )
                for row in rows:
                    conn.execute(
                        sql_text(
                            """
                            INSERT INTO knowledge_chunks
                                (id, type, title, category, summary, source, keywords, embedding)
                            VALUES
                                (:id, :type, :title, :category, :summary, :source, :keywords, :embedding)
                            """
                        ),
                        row,
                    )
            store.update_item(item["id"], None, None, None, None, {"vectorized": True})
            item["is_vectorized"] = True
            return True
        return False
    except Exception as exc:
        item["vectorize_error"] = str(exc)
        return False


@router.post("/knowledge/test-search")
async def test_search(query: str, top_k: int = 8, rerank: bool = True, user=Depends(current_user)):
    from app.services import knowledge_service
    from app.services.rerank_service import rerank_service

    try:
        top_k = min(max(int(top_k), 1), 20)
        pre_rank = await knowledge_service.search_async(query, top_k=max(top_k * 4, 10), apply_rerank=False)
        if rerank:
            candidate_rank = await rerank_service.rerank_async(query, pre_rank)
        else:
            candidate_rank = pre_rank
        final = candidate_rank[:top_k]

        def _normalize(items):
            if not items:
                return {}
            scores = [float(r.get("score", 0)) for r in items]
            lo, hi = min(scores), max(scores)
            rng = (hi - lo) if hi > lo else 1.0
            return {r.get("id"): round((float(r.get("score", 0)) - lo) / rng * 100, 1) for r in items}

        norm_map = _normalize(final)
        pre_ids = {r.get("id"): i + 1 for i, r in enumerate(pre_rank)}
        results = []
        for rank, r in enumerate(final, 1):
            rid = r.get("id")
            results.append({
                "rank": rank,
                "id": rid,
                "type": r.get("type"),
                "title": r.get("title"),
                "snippet": r.get("snippet") or "",
                "source": r.get("source") or "",
                "score": norm_map.get(rid, 0.0),
                "raw_score": round(float(r.get("score", 0)), 4),
                "pre_rank": pre_ids.get(rid),
            })
        return {
            "query": query,
            "top_k": top_k,
            "rerank_enabled": bool(rerank),
            "rerank_provider": rerank_service.provider if rerank else "offline",
            "results": results,
            "total": len(results),
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


def _chunk_text(text: str, limit: int = 800) -> list:
    text = (text or "").strip()
    if not text:
        return []
    parts = [p.strip() for p in text.split("\n") if p.strip()]
    if not parts:
        return [text]
    result = []
    current = ""
    for p in parts:
        if len(current) + len(p) + 1 > limit and current:
            result.append(current)
            current = p
        else:
            current = f"{current}\n{p}" if current else p
    if current:
        result.append(current)
    return result
