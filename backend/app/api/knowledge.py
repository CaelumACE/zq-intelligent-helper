"""知识库 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from app.core.config import settings
from app.core.logger import logger
import json

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
async def list_documents():
    """获取知识库文档列表"""
    try:
        # 读取政策知识库数据
        with open(settings.DATA_DIR / '政策知识库.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        documents = [
            Document(
                id=doc['id'],
                title=doc['title'],
                category=doc.get('category', '未分类'),
                summary=doc.get('summary', '')[:200]
            )
            for doc in data
        ]
        return documents
    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats", response_model=KnowledgeStats)
async def get_stats():
    """获取知识库统计"""
    try:
        with open(settings.DATA_DIR / '政策知识库.json', 'r', encoding='utf-8') as f:
            policies = json.load(f)
        
        with open(settings.DATA_DIR / '办事事项.json', 'r', encoding='utf-8') as f:
            services = json.load(f)
        
        with open(settings.DATA_DIR / '公文模板.json', 'r', encoding='utf-8') as f:
            templates = json.load(f)
        
        # 统计分类
        categories = {}
        for doc in policies:
            cat = doc.get('category', '未分类')
            categories[cat] = categories.get(cat, 0) + 1
        
        return KnowledgeStats(
            total_documents=len(policies) + len(services) + len(templates),
            categories=categories,
            total_chunks=len(policies) + len(services) + len(templates)  # TODO: 实际分块数
        )
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/search")
async def search_knowledge(query: str, top_k: int = 5):
    """搜索知识库"""
    try:
        # TODO: 实现向量检索
        # 临时返回简单匹配
        with open(settings.DATA_DIR / '政策知识库.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        results = []
        for doc in data:
            if query in doc.get('title', '') or query in doc.get('summary', ''):
                results.append({
                    "id": doc['id'],
                    "title": doc['title'],
                    "snippet": doc.get('summary', '')[:200],
                    "score": 0.8
                })
                if len(results) >= top_k:
                    break
        
        return {"results": results, "total": len(results)}
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
