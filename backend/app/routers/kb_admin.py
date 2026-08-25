"""Sprint 02 知识库运营后台 API。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.routers.auth import current_user
from app.services import kb_admin_store as store

router = APIRouter()


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
