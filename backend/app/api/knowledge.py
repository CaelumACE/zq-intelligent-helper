"""知识库 API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.core.config import settings
from app.core.logger import logger
from app.services.knowledge_service import knowledge_service
from app.services.vector_store import vector_store
from app.routers.auth import current_user
from app.routers.admin import admin_required

router = APIRouter()


class Document(BaseModel):
    id: str
    title: str
    category: str
    summary: str


class KnowledgeStats(BaseModel):
    total_documents: int
    categories: dict
    total_chunks: int


@router.get("/documents", response_model=List[Document])
async def list_documents(user = Depends(current_user)):
    """获取知识库文档列表"""
    try:
        all_docs = []
        for policy in knowledge_service.documents.get('policies', []):
            all_docs.append(Document(
                id=policy.get('id', ''),
                title=policy.get('title', ''),
                category=policy.get('category', '未分类'),
                summary=policy.get('summary', '')[:200],
            ))
        for service in knowledge_service.documents.get('services', []):
            all_docs.append(Document(
                id=service.get('id', ''),
                title=service.get('item_name', ''),
                category=service.get('category', '未分类'),
                summary=service.get('description', '')[:200],
            ))
        for tpl in knowledge_service.documents.get('templates', []):
            all_docs.append(Document(
                id=tpl.get('id', ''),
                title=tpl.get('type_name', ''),
                category='公文模板',
                summary=tpl.get('doc_type', '')[:200],
            ))
        for item in knowledge_service.documents.get('knowledge', []):
            all_docs.append(Document(
                id=item.get('id', ''),
                title=item.get('title', ''),
                category=item.get('category', '公文知识'),
                summary=item.get('summary', '')[:200],
            ))
        return all_docs
    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats", response_model=KnowledgeStats)
async def get_stats(user = Depends(current_user)):
    """获取知识库统计"""
    try:
        policies = knowledge_service.documents.get('policies', [])
        services = knowledge_service.documents.get('services', [])
        templates = knowledge_service.documents.get('templates', [])
        knowledge = knowledge_service.documents.get('knowledge', [])

        categories = {}
        for doc in policies + knowledge:
            cat = doc.get('category', '未分类')
            categories[cat] = categories.get(cat, 0) + 1
        for s in services:
            cat = s.get('category', '未分类')
            categories[cat] = categories.get(cat, 0) + 1
        categories['公文模板'] = len(templates)

        return KnowledgeStats(
            total_documents=len(policies) + len(services) + len(templates) + len(knowledge),
            categories=categories,
            total_chunks=len(knowledge_service.chunks),
        )
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rag/status")
async def rag_status(user = Depends(current_user)):
    """RAG 存储与向量池状态探测。"""
    try:
        vector_status = vector_store.status()
        embedding_ready = knowledge_service._corpus_ready
        return {
            "vector_store": vector_status,
            "memory_embedding_ready": embedding_ready,
            "embedding_dimension": settings.EMBEDDING_DIMENSION,
            "chunks_total": len(knowledge_service.chunks),
        }
    except Exception as e:
        logger.error(f"RAG status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_knowledge(query: str, top_k: int = 5, user = Depends(current_user)):
    """搜索知识库（复用统一检索服务）"""
    try:
        results = knowledge_service.search(query, top_k=min(top_k, 20))
        return {
            "results": [
                {
                    "id": r['id'],
                    "title": r['title'],
                    "snippet": r['snippet'],
                    "source": r['source'],
                    "score": round(r['score'], 3),
                }
                for r in results if r['snippet']
            ],
            "total": len(results),
        }
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reindex")
async def reindex(user = Depends(admin_required)):
    """强制重建语义向量索引并同步到 pgvector（首次部署或数据更新后调用）。"""
    try:
        knowledge_service._corpus_ready = False
        knowledge_service._corpus_embeddings = []
        knowledge_service._pg_synced = False
        knowledge_service._ensure_corpus_embeddings()
        vs = vector_store.status()
        return {
            "status": "ok",
            "chunks_total": len(knowledge_service.chunks),
            "corpus_ready": knowledge_service._corpus_ready,
            "vector_store": vs,
        }
    except Exception as e:
        logger.error(f"Reindex error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
