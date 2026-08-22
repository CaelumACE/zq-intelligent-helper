# 政企智能助手

> Government Enterprise AI Assistant

## 项目简介
政企智能助手是一个基于 RAG（检索增强生成）的智能问答系统，为政企单位提供政策咨询、公文写作、办事指引等服务。

## 技术架构
- **前端**: React + TypeScript + Vite + Tailwind CSS
- **后端**: FastAPI + Python
- **数据库**: PostgreSQL + pgvector
- **LLM**: DeepSeek API（云端）/ Ollama（私有化）
- **部署**: Docker Compose

## 快速启动
```bash
# 克隆项目
git clone <repo-url>
cd gov-assistant

# 启动服务
docker-compose up -d
```

## 开发计划
- Day 1: 基础框架搭建 + 核心对话链路
- Day 2: 知识库接入 + 功能完善  
- Day 3: 联调测试 + 部署验收

## 团队
- 产品经理：小赵
- 界面设计：界面设计
- 工程师：小孙
- 验收：浩哥

