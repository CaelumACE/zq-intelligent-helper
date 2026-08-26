# 版本变更记录（CHANGELOG）

本项目按 3 天 Sprint 迭代，每个 Sprint 结束打 tag 并记录。版本号规则：`v1.0-sXX`（Sprint 版本）。

---

## v1.0-s05-p0 — 2026-08-27（P0 安全加固热修复）

> tag：`v1.0-s05-p0`（基于 commit `eb1beba`）
> 性质：S04 验收后代码审查发现 5 项 P0 一票否决项的紧急安全热修复，不新增功能。
> QA：S03 安全回归 45 passed + 1 skipped，P0 五项全通过，无回归。

### 安全修复（P0，5 项）
| 编号 | 问题 | 修复 |
|---|---|---|
| S1 | 知识库后台接口未授权访问 | `/api/knowledge/*` 管理端点（reindex 等）加鉴权，未登录返回 401，普通用户返回 404（不泄露资源存在性） |
| S2 | 超管口令弱/硬编码 | 强密码策略，`SUPER_ADMIN_PASSWORD` 改为环境变量必填，CI 补测试环境变量，旧硬编码口令失效 |
| S3 | 前端 XSS（marked 渲染未净化） | 引入 DOMPurify，marked 输出经 sanitize 后再渲染 |
| S4 | nginx 无上传大小/安全头限制 | `client_max_body_size 12m`，增加 CSP / X-Frame-Options:DENY / X-Content-Type-Options / Referrer-Policy 安全响应头 |
| M2 | backend 8000 端口直接暴露公网 | docker-compose 改 `expose: 8000`（仅容器内），不映射宿主机；统一由 nginx 80 端口入口；新增 `/health` 反代 |

### 工程/部署
- nginx 新增 `location /health` 反代到 backend:8000，M2 后宿主机通过 80 端口做健康检查。
- cpolar 隧道改为转发 nginx **80 端口**（不再转发 8000），backend 完全不暴露公网。
- CI `backend-check` job 补 `SUPER_ADMIN_PASSWORD` / `JWT_SECRET` 环境变量，修复 S2 加固后 import 阶段失败。
- 放宽 CSP `connect-src/img-src`，兼容公网跨域 API 部署（commit `c50bbb8`）。

### 已知限制（非本次范围，入 S05）
- cpolar 免费版隧道 URL 每次重启可能变化，URL 变了需更新前端 `VITE_API_BASE` 重新部署 Cloudflare Pages。S05 评估固定域名或前端运行时配置 API 地址。
- 单点登录 `ALLOW_MULTI_SESSION=false` 保持不变（浩哥决定暂不开启多端登录）。

### 部署/更新命令（VM 标准流程）
```bash
cd /home/wzh/gov-assistant && \
git fetch origin && \
git reset --hard origin/main && \
docker compose build && \
docker compose up -d && \
sed -i 's/addr: 8000/addr: 80/' ~/.cpolar/cpolar.yml && \
pkill -f cpolar; sleep 2; \
nohup cpolar start-all --config /home/wzh/.cpolar/cpolar.yml > /home/wzh/cpolar.log 2>&1 & disown && \
sleep 5 && \
docker compose ps && \
curl -s http://127.0.0.1/health && \
echo "" && \
grep -o 'https://[a-z0-9]*\.[a-z0-9]*\.cpolar\.[a-z]*' /home/wzh/cpolar.log | head -1
```
要点：用 `up -d` 不用 `restart`（restart 不重读 .env）；不加 `--no-cache`；health 走 80 端口；末行若输出的 cpolar URL 与当前不一致需通知小赵更新前端 CI。

---

## v1.0-s04 — 2026-08-26（公文对话式生成）

> tag：`v1.0-s04`（commit `133664b`）
> 浩哥验收通过。

### 新增功能
- 公文对话式生成：多轮对话修改公文内容。
- 8 种公文类型支持。
- docx 国标格式导出。
- 工具栏 + 满意度反馈。
- 公文预览排版。

### 关键修复
- `cb0cef4`：修复 service 问答流式无回复——stream_provider 嵌套 async generator 导致 delta 丢失。
- `133664b`：修复普通知识问答/办事导引 500——`_build_messages` 在非 writing 分支遗漏 `user_query` 赋值。
- `ca208c4`：review 修复——docx 导出改 Response 防损坏、反馈接口加归属校验 + 幂等去重、字体扫描加 lru_cache。
- `bb20f60`：has_feedback 查重改用 JSONB 取值，修复 LIKE pattern 类型不匹配。

---

## v1.0-s03 — 2026-08-25（政策比对 + 安全加固）

> tag：`v1.0-s03`（commit `1729245`）

- 政策文件比对功能。
- 安全加固基线（S03 安全回归 45 项）。

---

## v1.0-s02 / s01
- S02：政策比对能力初版。
- S01：一件事导办。

## MVP — 2026-08-24
- 政企智能助手 MVP 交付。

---

## 历史 tag
| tag | 含义 |
|---|---|
| `v0.1.0` | 早期版本 |
| `v1.0.0-stable` | 首个稳定基线 |
| `v1.0-s03` | Sprint 3 版本 |
| `v1.0-s04` | Sprint 4 版本 |
| `v1.0-s05-p0` | P0 安全热修复（本次） |
