"""政企智能助手后端服务"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.logger import logger
from app.services.vector_store import vector_store
from app.api import chat, knowledge


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时初始化 PG + pgvector（失败不阻塞，自动降级内存检索）
    if vector_store.mode == "postgres":
        ok = vector_store.initialize_database()
        logger.info(f"pgvector 初始化: {'成功' if ok else '失败/降级内存'}")
    yield


app = FastAPI(
    title="政企智能助手 API",
    description="基于 RAG 的政企智能问答系统",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(chat.router, prefix="/api/chat", tags=["对话"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识库"])


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_provider": settings.LLM_PROVIDER,
        "rag_engine": "pgvector" if vector_store.mode == "postgres" else "memory",
    }


# 生产部署：托管前端静态文件
_dist = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend", "dist")
if not os.path.exists(_dist):
    # Docker 镜像内前端构建产物位于 /app/frontend/dist
    _dist = "/app/frontend/dist"
if os.path.exists(_dist):
    app.mount("/", StaticFiles(directory=_dist, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
