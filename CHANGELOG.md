# 版本变更记录（CHANGELOG）

本项目按 3 天 Sprint 迭代，每个 Sprint 结束打 tag 并记录。版本号规则：
- `v1.0-sXX`：Sprint 版本
- `v1.0-sXX-p0`：该 Sprint 之上的 P0 热修复
- `v1.0.0-stable`：里程碑稳定基线

记录顺序：新版本在前。

---

## v1.0-s05-p0 — 2026-08-27（P0 安全加固热修复）

> tag：`v1.0-s05-p0`（基于 commit `eb1beba`，小孙打 tag）
> 性质：S04 验收后代码审查发现 5 项 P0 一票否决项的紧急安全热修复，不新增功能。
> QA：S03 安全回归 45 passed + 1 skipped，P0 五项全通过，无回归。

### 安全修复（P0，5 项）
| 编号 | 问题 | 修复 |
|---|---|---|
| S1 | 知识库后台接口未授权访问 | `/api/knowledge/*` 管理端点（reindex 等）加鉴权，未登录 401，普通用户 404（不泄露资源存在性） |
| S2 | 超管口令弱/硬编码 | 强密码策略，`SUPER_ADMIN_PASSWORD` 改为环境变量必填，旧硬编码口令失效 |
| S3 | 前端 XSS（marked 渲染未净化） | 引入 DOMPurify，marked 输出经 sanitize 后再渲染 |
| S4 | nginx 无上传大小/安全头限制 | `client_max_body_size 12m`；增加 CSP / X-Frame-Options:DENY / X-Content-Type-Options / Referrer-Policy |
| M2 | backend 8000 端口直接暴露公网 | docker-compose 改 `expose: 8000`（仅容器内），不映射宿主机；统一 nginx 80 入口；新增 `/health` 反代 |

### 工程/部署
- nginx 新增 `location /health` 反代 backend:8000（`eb1beba`），M2 后宿主机通过 80 端口健康检查。
- cpolar 隧道改为转发 nginx **80 端口**（不再转发 8000），backend 完全不暴露公网。
- CI `backend-check` 补 `SUPER_ADMIN_PASSWORD` / `JWT_SECRET` 环境变量（`57a10bf`），修复 S2 加固后 import 失败。
- 放宽 CSP `connect-src/img-src`，兼容公网跨域 API 部署（`c50bbb8`）。
- 期间 cpolar URL 三次变更（31cb4970 → 3b6dbdc0 → 2c2aec80），均同步前端 CI 重新部署 Cloudflare Pages。

### 关键 commits
`3fe774c`（P0 五项修复主体）、`c50bbb8`（CSP 放宽）、`57a10bf`（CI 环境变量）、`9be7f6e`（cpolar URL）、`eb1beba`（nginx /health 反代）

### 已知限制（入 S05）
- cpolar 免费版隧道 URL 每次重启可能变化，需更新前端 `VITE_API_BASE` 重新部署。S05 评估固定域名或前端运行时配置 API 地址。
- 单点登录 `ALLOW_MULTI_SESSION=false` 保持不变（暂不开启多端登录）。

---

## v1.0-s04 — 2026-08-26（公文对话式生成）

> tag：`v1.0-s04`（commit `133664b`）
> 浩哥验收通过。

### 新增功能
- 公文对话式生成：多轮对话修改公文内容（`925ea38` 后端、`ec22dd3` 前端）。
- 文种扩充到 **8 种公文类型**。
- **docx 国标格式导出**；工具栏 + 导出按钮 + 公文预览排版。
- **满意度反馈**：反馈 UI、反馈接口加归属校验 + 幂等去重。

### 关键修复
- `cb0cef4`：修复 service 问答流式无回复——stream_provider 嵌套 async generator 导致 delta 丢失。
- `133664b`：修复普通知识问答/办事导引 500——`_build_messages` 非 writing 分支遗漏 `user_query` 赋值。
- `ca208c4`：review 修复——docx 导出改 Response 防损坏、字体扫描加 lru_cache。
- `bb20f60`：has_feedback 查重改用 JSONB 取值，修复 LIKE pattern 类型不匹配永远 false。
- `c50bbb8`：放宽 CSP 兼容公网跨域（后入 s05-p0）。

### P3 技术债（记录入 S05）
- 公文预览折叠截断、历史空会话堆积、`WRITING_REVISE_KEYWORDS` 单字误判。

---

## v1.0-s03 — 2026-08-25（账号安全体系 + 政策比对收尾）

> tag：`v1.0-s03`（commit `0040e96`）
> S03 安全回归基线 45 项。

### 新增功能
- **独立超级管理员账号** `super_admin`，admin 回退为普通管理员（`89a7307`）。
- **用户管理**：用户列表、删除用户（清理聊天记录）、启用/禁用、管理员升降级、改密（`f7b1e8b`、`b52e081`）。
- **权限矩阵**：超管可管理所有账号；普通管理员不可互操作、不可改其他管理员（`146a6ad`、`880f52a`）。
- **单点登录**：`ALLOW_MULTI_SESSION=false`，同账号新登录踢旧会话；sessionStorage 标签页隔离（`dd7692a`）。
- **登录限流**：IP + 用户名粒度加锁（`9a8d15c`）。
- 模型选择器方案 A：从 `/health` 动态读取后端默认 provider（`bc74ef2`）；默认模型切 MiniMax（`a997436`）。
- 侧边栏 UI 优化、改密入口闭环（登录页移除改密，改侧边栏弹窗 `1729245`）。

### 安全修复
- 自保护补全（超管不可删/降自己）、降级/禁用递增 `token_version` 使旧会话失效（`e7b2839`、`d397d3b`）。
- guide 接口补 tv 校验、admin 越权顺序修复、阻止跨账号会话接管（`54e11a9`）。

---

## v1.0-s02 — 2026-08-24（政策智能比对 + 知识库运营后台）

> 未单独打 tag，并入 v1.0.0-stable 之后迭代。核心 commit `01e275f`。

### 新增功能
- **政策智能比对**：双文档上传比对，相同文档确定性返回 0 变更（`c3a6ffc`、`01e275f`）。
- **知识库运营后台**：上传/检索测试接口、预置 admin 账号、补 `python-multipart` 依赖（`c22488b`）。
- 检索测试面板：GET 改 POST 修复 405、相似度分数归一化到 0-100%（`0abf88e`、`8699ab1`、`b5b9a5e`）。
- 账号安全与会话隔离：阻止跨账号会话接管、对话已提供 sid 时不重复建会话（`2bf4814`、`3865835`、`d240d3b`）。
- guide 路由 3 个接口（themes/match/roadmap）补 JWT 认证（`a3df7ea`）。

---

## v1.0-s01 — 2026-08-23（一件事智能导办 + JWT 登录）

> 核心 commit `8901c72`。

- **一件事智能导办**：主题、匹配、路线图全链路（`8901c72`）。
- **JWT 登录认证体系**接入。
- 修复路线图标题/icon/天数丢失（`790daa5`）。
- 新建对话时切回智能问答 Tab（`1d2ba6b`）。

---

## v1.0.0-stable — 2026-08-24（MVP 交付里程碑）

> tag：`v1.0.0-stable`（commit `91c36f6`）
> 政企智能助手 MVP 正式交付浩哥。

### 里程碑能力
- **RAG 语义检索**：向量召回 + Rerank + 意图识别 + 公文知识库（`53cf5f2`）。
- **SSE 流式输出** + 双通道（DeepSeek 主 / MiniMax 兜底）+ 开场白（`df5092d`）。
- **会话历史持久化**：SQLite → 后期统一 PostgreSQL/pgvector（`821e38f`、`8c43100`）。
- **前端 1:1 对齐高保真原型**（v1.2/v1.3）：配色、侧栏、卡片、气泡、引用、模型切换、公文写作面板、流式停止（`4ec09a6`、`8813d75`、`c88e9a2`）。
- **公文写作**：结构化传参与 RAG 低置信召回收口（`2488efa`）。
- **smalltalk 意图识别**：元话语走 LLM 自然回复不检索知识库（`17146c4`、`f99d5de`）。
- related_chips 关联推荐、aliases 配置多版本迭代（`2e2bb69`、`eddd6e8`、`ce976b2`）。
- 10 题评测脚本、双模型同题对比评测（`fb95fa2`、`359e5f8`）。

### 工程与部署
- **Docker 部署配置** + RAG 检索链路验证（`ce1baae`）。
- **Cloudflare Pages 自动化部署流水线**：`ci.yml` + `deploy-cloudflare.yml`，构建注入 `VITE_API_BASE`（`0926171`、`8790fe7`、`caf68f4`、`3942a2a`）。
- 后端切公网 API 到 VM cpolar 隧道（`91c36f6`）。
- VM 一键部署脚本 `deploy_vm.sh`，默认 DeepSeek + fallback（`998a1a4`）。
- 4 类官方知识库数据预置：社保缴费比例/公积金贷款额度/外资企业设立/数字化转型专项资金（`1686bf5`）。
- 后端 PyCompile 语法检查防 f-string SyntaxError 上线（`a43117a`）；SSE [DONE] 主动退出 + 60s 超时防挂起（`c0195eb`）。

---

## v0.1.0 — 2026-08-22（项目初始化 / Day1-Day2）

> tag：`v0.1.0`（commit `8cd35e9`）

### Day1（2026-08-21）
- 项目初始化：前端框架搭建 + 数据文件归档（`7469764`）。
- 后端骨架搭建 + MiniMax API 配置（`7a3e583`）。
- 后端 API 模块完善 + 前端界面改造启动（`1956046`）。
- 前端核心组件 + 后端 RAG 引擎（`986b7fc`）。

### Day2（2026-08-22）
- Docker 部署配置 + RAG 检索链路验证（`ce1baae`）。
- 修复 .env 加载路径与 LLM 配置调用，优化中文检索（`c5f3195`）。
- 增强检索智能体验 + 会话历史持久化（`821e38f`）。
- RAG 语义向量检索 + 意图识别 + 公文知识库（`53cf5f2`）。
- 双模型同题对比评测脚本（`359e5f8`）。
- SSE 流式输出 + 双通道兜底 + 开场白（`df5092d`）。
- `8cd35e9`：记录数据库决策与 Day2 后续计划（打 tag 点）。

---

## tag 索引

| tag | commit | 日期 | 说明 |
|---|---|---|---|
| `v0.1.0` | `8cd35e9` | 2026-08-22 | Day1-Day2 项目初始化 |
| `v1.0.0-stable` | `91c36f6` | 2026-08-24 | MVP 交付里程碑 |
| `v1.0-s03` | `0040e96` | 2026-08-26 | S03 账号安全体系 |
| `v1.0-s04` | `133664b` | 2026-08-26 | S04 公文对话式生成 |
| `v1.0-s05-p0` | `eb1beba` | 2026-08-27 | P0 安全热修复 |
