#!/usr/bin/env bash
# 云环境自动部署轮询：监听 origin/main 新提交，自动更新并重载服务。
# 用法：nohup bash scripts/auto_deploy.sh >> /tmp/auto_deploy.log 2>&1 &
set -uo pipefail

REPO_DIR="/root/.coze/agents/7676786338666037539/workspace/gov-assistant"
SLEEP_SECONDS="${AUTO_DEPLOY_INTERVAL:-20}"

log() {
  echo "[$(date '+%F %T')] $*"
}

log "自动部署守护启动，仓库: $REPO_DIR，轮询间隔 ${SLEEP_SECONDS}s"

while true; do
  if [ ! -d "$REPO_DIR/.git" ]; then
    log "仓库目录不存在: $REPO_DIR，等待重试"
    sleep "$SLEEP_SECONDS"
    continue
  fi

  cd "$REPO_DIR" || {
    log "进入仓库失败"
    sleep "$SLEEP_SECONDS"
    continue
  }

  # 拉取远端引用
  if ! git fetch origin main >/dev/null 2>&1; then
    log "git fetch 失败（网络抖动），下轮重试"
    sleep "$SLEEP_SECONDS"
    continue
  fi

  LOCAL="$(git rev-parse HEAD)"
  REMOTE="$(git rev-parse origin/main 2>/dev/null || echo '')"

  if [ -z "$REMOTE" ]; then
    sleep "$SLEEP_SECONDS"
    continue
  fi

  if [ "$LOCAL" != "$REMOTE" ]; then
    log "检测到新提交 ${REMOTE:0:8}，开始自动部署"
    if git pull --ff-only origin main >> /tmp/auto_deploy.log 2>&1; then
      log "代码更新成功，后端 --reload 自动重启，前端 Vite 自动 HMR"
    else
      log "git pull 失败，尝试 reset 到远端（保留 gitignore 的 .env 等本地文件）"
      git reset --hard origin/main >> /tmp/auto_deploy.log 2>&1 || log "reset 失败，需人工处理"
    fi
  fi

  sleep "$SLEEP_SECONDS"
done
