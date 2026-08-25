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
    source: str = ""


class ItemUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    category: str | None = None
    source: str | None = None
    metadata: dict | None = None


def _require_admin(user) -> None:
    if getattr(user, "role", None) != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")


@router.get("/knowledge/items")
async def list_items(category: str | None = None, search: str | None = None, user=Depends(current_user)):
    return {"items": store.list_items(category=category, status="active", search=search)}


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
        item = store.create_item(body.title, body.content, body.category, body.source)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"item": item}


@router.put("/knowledge/items/{item_id}")
async def update_item(item_id: int, body: ItemUpdate, user=Depends(current_user)):
    _require_admin(user)
    item = store.update_item(item_id, body.title, body.content, body.category, body.source, body.metadata)
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
        item = store.create_item(title=title, content=text, category="policy", source=file.filename or "文件上传")
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
            return True
        return False
    except Exception as exc:
        item["vectorize_error"] = str(exc)
        return False


@router.post("/knowledge/test-search")
async def test_search(query: str, top_k: int = 8, user=Depends(current_user)):
    from app.services import knowledge_service

    try:
        results = knowledge_service.search(query, top_k=min(top_k, 20))
        if results:
            max_score = max(float(r.get("score", 0)) for r in results)
            min_score = min(float(r.get("score", 0)) for r in results)
            score_range = max_score - min_score if max_score > min_score else 1.0
        else:
            max_score = min_score = score_range = 1.0
        return {
            "results": [
                {
                    "id": r.get("id"),
                    "title": r.get("title"),
                    "snippet": r.get("snippet") or "",
                    "source": r.get("source") or "",
                    "score": round((float(r.get("score", 0)) - min_score) / score_range * 100, 1),
                }
                for r in results
                if r.get("snippet")
            ],
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
