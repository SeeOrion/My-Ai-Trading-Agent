# AI Trading Agent

一个以研究和模拟交易为优先、遵循领域驱动设计（DDD）的量化交易智能体。

## 当前状态

已实现供应商无关的行情、财经快讯采集与新闻情绪分析，以及基本面、资金流、期权到期损益分析。因子库现提供严格的声明式注册表和 HTTP 查询 API。策略注入、文档/OCR、交易日志的私有 PostgreSQL 数据模型与前端入口已就绪，业务用例将在下一阶段接入。

系统默认**不连接券商、不下单**。任何未来实盘能力都必须是显式配置、独立授权并经过风险约束的可选模块。

## 使用 uv

后端由 `backend/` 内的 `uv` 项目管理依赖和 `.venv`。首次进入项目或依赖变更后执行：

```bash
cd backend
uv sync --all-extras
```

不需要手动 `source .venv/bin/activate`。所有 `uv run` 命令都会自动发现并在
`backend/.venv` 中运行；例如：

```bash
cd backend
uv run pytest
uv run ruff check .
```

## 前后端与私有部署

`backend/src/ai_trading_agent` 是 Python 后端（DDD 核心与 FastAPI 交付层），`frontend/` 是独立的
React/Vite 工作区。前端只访问 `/api/v1`，不会保存或读取任何数据源、LLM、数据库密钥。

本地开发可分别启动：

```bash
# 终端一：后端
cd backend
uv run uvicorn ai_trading_agent.interfaces.api.app:app --app-dir src --reload --port 8000

# 终端二：前端
cd frontend
npm run dev
```

`docker-compose.yml` 为未来私人服务器准备了 PostgreSQL、迁移、后端和静态前端四个独立服务。
部署时在宿主机的秘密管理或私有环境变量中设置 `POSTGRES_PASSWORD`；不应把它写入仓库或前端构建变量。

## 已配置服务如何进入 UI

本机后端在真正收到行情、资讯、研究或 AI 对话请求时，才从项目根目录的私有 `.env` 装载
`TUSHARE_TOKEN`、Futu OpenD 地址、LLM 配置和可选的 `DATABASE_URL`。同花顺配置在
[`backend/.env.example`](backend/.env.example) 中保留超时等非敏感参数；其 API Key 由
`hithink-finance` Skill 的系统级私密凭据保存。后端会按 Skill 的安全优先级读取运行时 Key，
但项目 `.env`、前端、Git 提交和日志都不应出现 `HITHINK_FINANCE_API_KEY`。免费腾讯公开行情与
AKShare 公开资讯不需要密钥；这些值绝不返回给前端。
当前 UI 已接通行情、财经资讯、研究分析、个人策略编辑/版本保存，以及首页 AI 研究对话；文档/OCR
和交易日志仍是下一阶段模块。

## 目录

```text
backend/
├── src/ai_trading_agent/  # Python DDD 后端
├── tests/                 # 后端测试
├── migrations/            # PostgreSQL Alembic 迁移
├── pyproject.toml         # uv 后端依赖定义
└── Dockerfile              # 后端/迁移镜像
frontend/                   # 独立 React 用户界面
```

完整的边界和增量路线见 [docs/architecture.md](docs/architecture.md)。
