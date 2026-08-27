#!/bin/bash
# ============================================================
# 政企智能助手 - 虚拟机一键部署脚本
# 适用：Ubuntu 24.04 + Docker + Docker Compose
# 用法：bash deploy_vm.sh
# ============================================================
set -e

PROJECT_DIR="${GOV_PROJECT_DIR:-$HOME/gov-assistant}"
REPO_URL="https://github.com/CaelumACE/zq-intelligent-helper.git"
GIT_BRANCH="${1:-main}"

echo "============================================"
echo "  政企智能助手 - 虚拟机部署"
echo "============================================"

# 1. 检查Docker
echo ""
echo "[1/6] 检查Docker环境..."
docker --version
docker compose version
docker info > /dev/null 2>&1 && echo "Docker daemon: 运行中" || { echo "❌ Docker daemon未启动，请先运行: sudo systemctl start docker"; exit 1; }

# 2. 检查端口冲突
echo ""
echo "[2/6] 检查端口占用..."
for port in 80; do
    if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
        echo "⚠️  端口 ${port} 已被占用："
        ss -tlnp | grep ":${port} "
    else
        echo "✅ 端口 ${port} 空闲"
    fi
done

# 3. Clone或更新项目
echo ""
echo "[3/6] 获取项目代码..."
if [ -d "$PROJECT_DIR" ]; then
    echo "项目目录已存在，拉取最新代码..."
    cd "$PROJECT_DIR"
    git fetch origin
    git checkout "$GIT_BRANCH" 2>/dev/null || git checkout -b "$GIT_BRANCH" "origin/$GIT_BRANCH"
    git pull origin "$GIT_BRANCH"
else
    echo "克隆项目到 $PROJECT_DIR ..."
    cd "$HOME"
    git clone -b "$GIT_BRANCH" "$REPO_URL" "$PROJECT_DIR" 2>/dev/null || git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    git fetch origin
    git checkout "$GIT_BRANCH" 2>/dev/null || git checkout -b "$GIT_BRANCH" "origin/$GIT_BRANCH"
fi
echo "当前版本: $(git log --oneline -1)"

# 4. 配置.env
echo ""
echo "[4/6] 配置环境变量..."
if [ -f .env ]; then
    echo "✅ .env 已存在，跳过创建（如需重置请先手动删除）"
else
    echo "请输入以下配置（直接回车使用默认值）："
    echo ""
    read -p "DeepSeek API Key [必填]: " DEEPSEEK_KEY
    if [ -z "$DEEPSEEK_KEY" ]; then echo "❌ DeepSeek Key不能为空"; exit 1; fi
    read -p "MiniMax API Key [必填]: " MINIMAX_KEY
    if [ -z "$MINIMAX_KEY" ]; then echo "❌ MiniMax Key不能为空"; exit 1; fi
    read -p "PostgreSQL密码 [默认Gov2026]: " PG_PASS
    PG_PASS=${PG_PASS:-Gov2026}

    cat > .env << ENVEOF
# ===== 大模型配置 =====
LLM_PROVIDER=deepseek
LLM_FALLBACK_PROVIDER=minimax
MINIMAX_API_KEY=$MINIMAX_KEY
MINIMAX_MODEL=MiniMax-Text-01
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
DEEPSEEK_API_KEY=$DEEPSEEK_KEY
DEEPSEEK_MODEL=deepseek-chat
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1

# ===== Embedding配置 =====
EMBEDDING_PROVIDER=minimax
EMBEDDING_MODEL=embo-01
EMBEDDING_DIMENSION=1536

# ===== Rerank（Demo 期可用 SiliconFlow；默认 offline） =====
RERANK_PROVIDER=offline
RERANK_MODEL=n-gram-offline
RERANK_BASE_URL=
RERANK_API_KEY=

# ===== 安全密钥 =====
JWT_SECRET=
ADMIN_PASSWORD=
SUPER_ADMIN_USERNAME=super_admin
SUPER_ADMIN_PASSWORD=

# ===== 数据库配置 =====
POSTGRES_PASSWORD=$PG_PASS
DATABASE_URL=postgresql+psycopg2://gov:$PG_PASS@postgres:5432/gov_assistant
ENVEOF
    echo "✅ .env 已创建"
fi

# 5. 构建并启动
echo ""
echo "[5/6] 构建Docker镜像并启动服务（首次需要5-10分钟）..."
docker compose build
docker compose up -d

# 6. 等待健康检查
echo ""
echo "[6/6] 等待服务启动..."
sleep 10
for i in $(seq 1 30); do
    HEALTH=$(curl -s http://localhost/health 2>/dev/null || echo "")
    if echo "$HEALTH" | grep -q "ok"; then
        echo ""
        echo "============================================"
        echo "  ✅ 部署成功！"
        echo "============================================"
        echo "后端状态: $HEALTH"
        echo ""
        VM_IP=$(hostname -I | awk '{print $1}')
        echo "访问地址："
        echo "  前端/API同源: http://${VM_IP}"
        echo "  健康检查: http://${VM_IP}/health"
        echo "  （M2 修复后 8000 端口不再对外，仅 nginx 80 反代访问）"
        echo ""
        RAG=$(curl -s http://localhost/health 2>/dev/null)
        echo "服务状态: $RAG"
        echo ""
        echo "日志: docker compose logs -f"
        echo "停止: docker compose down"
        exit 0
    fi
    echo "  等待中... ($i/30)"
    sleep 5
done

echo "⚠️ 启动超时，请检查: docker compose logs"
exit 1
