"""Sprint 02 政策智能比对 API。"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.routers.auth import current_user
from app.services.compare_service import compare_documents
from app.services.document_parser import extract_text
from app.services.docx_exporter import build_diff_docx
from app.services.kb_admin_store import get_item

router = APIRouter()

_RESULTS: dict[str, dict] = {}


class Doc(BaseModel):
    title: str = ""
    content: str = ""


class CompareRequest(BaseModel):
    doc_a: Optional[Doc] = None
    doc_b: Optional[Doc] = None
    item_a_id: Optional[int] = None
    item_b_id: Optional[int] = None


@router.post("/compare")
async def compare(body: CompareRequest, user=Depends(current_user)):
    if body.item_a_id and body.item_b_id:
        a = get_item(body.item_a_id)
        b = get_item(body.item_b_id)
        if not a or not b:
            raise HTTPException(status_code=404, detail="知识库条目不存在")
        doc_a = {"title": a["title"], "content": a["content"]}
        doc_b = {"title": b["title"], "content": b["content"]}
    elif body.doc_a and body.doc_b:
        if not body.doc_a.content.strip() and not body.doc_b.content.strip():
            raise HTTPException(status_code=400, detail="两份文档内容不能都为空")
        doc_a = {"title": body.doc_a.title or "旧版", "content": body.doc_a.content}
        doc_b = {"title": body.doc_b.title or "新版", "content": body.doc_b.content}
    else:
        raise HTTPException(status_code=422, detail="请提供两份文档，或两个知识库条目ID")

    result = await compare_documents(doc_a, doc_b)
    task_id = str(uuid.uuid4())
    _RESULTS[task_id] = {"doc_a_title": doc_a["title"], "doc_b_title": doc_b["title"], "result": result}
    return {"task_id": task_id, **result}


@router.post("/compare/upload")
async def compare_upload(
    doc_a: UploadFile = File(...),
    doc_b: UploadFile = File(...),
    user=Depends(current_user),
):
    if doc_a.size > 5 * 1024 * 1024 or doc_b.size > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="文件不能超过 5MB")
    a_text = extract_text(doc_a.filename or "", await doc_a.read())
    b_text = extract_text(doc_b.filename or "", await doc_b.read())
    if not a_text.strip() and not b_text.strip():
        raise HTTPException(status_code=400, detail="两份文件均未提取到文本")

    result = await compare_documents(
        {"title": doc_a.filename or "旧版", "content": a_text},
        {"title": doc_b.filename or "新版", "content": b_text},
    )
    task_id = str(uuid.uuid4())
    _RESULTS[task_id] = {
        "doc_a_title": doc_a.filename or "旧版",
        "doc_b_title": doc_b.filename or "新版",
        "result": result,
    }
    return {"task_id": task_id, **result}


@router.get("/compare/export/{task_id}")
async def export_compare(task_id: str, user=Depends(current_user)):
    record = _RESULTS.get(task_id)
    if not record:
        raise HTTPException(status_code=404, detail="比对结果不存在或已过期")
    payload = build_diff_docx(record["doc_a_title"], record["doc_b_title"], record["result"])
    filename = f"diff_report_{task_id[:8]}.docx"
    return Response(
        content=payload,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
