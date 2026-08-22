"""政企智能助手后端服务"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logger import logger
from app.api import chat, knowledge

app = FastAPI(
    title="政企智能助手 API",
    description="基于 RAG 的政企智能问答系统",
    version="1.0.0"
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

@app.get("/")
async def root():
    return {"message": "政企智能助手 API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "ok", "llm_provider": settings.LLM_PROVIDER}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
