# 政企智能助手

基于 RAG（检索增强生成）的政企智能问答系统，为政企单位提供政策咨询、公文写作、办事指引等服务。

## 技术架构

- 前端：React + TypeScript + Vite + Tailwind CSS
- 后端：FastAPI + Python
- LLM：MiniMax（当前调试）/ DeepSeek（预留，可切换）
- 检索：关键词 n-gram 检索（当前 MVP）+ 后续向量检索升级
- 部署：Docker Compose

## 快速启动

### 本地开发

```bash
# 后端
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm install
npm run dev
```

### Docker 一键部署

```bash
cp .env.example .env
docker compose up -d
```

## 项目结构

```
gov-assistant/
├── frontend/          # React 前端
├── backend/           # FastAPI 后端
├── data/              # 知识库数据 + 设计稿 + 验收文档
├── docker-compose.yml # 一键部署
└── README.md
```
