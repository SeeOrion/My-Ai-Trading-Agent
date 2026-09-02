# AI Trading Agent

一个以研究和模拟交易为优先、遵循领域驱动设计（DDD）的量化交易智能体。

## 当前状态

已实现供应商无关的行情、财经快讯采集与新闻情绪分析，以及基本面、资金流、期权到期损益分析。因子库现提供严格的声明式注册表和 HTTP 查询 API。策略注入、文档/OCR、交易日志的私有 PostgreSQL 数据模型与前端入口已就绪，业务用例将在下一阶段接入。

系统默认**不连接券商、不下单**。任何未来实盘能力都必须是显式配置、独立授权并经过风险约束的可选模块。

## 使用 uv

本项目由 `uv` 管理依赖和 `.venv`。首次进入项目或依赖变更后执行：

```bash
uv sync --all-extras
```

不需要手动 `source .venv/bin/activate`。所有 `uv run` 命令都会自动发现并在
项目的 `.venv` 中运行；例如：

```bash
uv run pytest
uv run ruff check .
```

## 前后端与私有部署

`src/ai_trading_agent` 是 Python 后端（DDD 核心与 FastAPI 交付层），`frontend/` 是独立的
React/Vite 工作区。前端只访问 `/api/v1`，不会保存或读取任何数据源、LLM、数据库密钥。

本地开发可分别启动：

```bash
# 终端一：后端
uv run uvicorn ai_trading_agent.presentation.http.app:app --reload --port 8000

# 终端二：前端
cd frontend
npm run dev
```

`docker-compose.yml` 为未来私人服务器准备了 PostgreSQL、迁移、后端和静态前端四个独立服务。
部署时在宿主机的秘密管理或私有环境变量中设置 `POSTGRES_PASSWORD`；不应把它写入仓库或前端构建变量。

## 目录

```text
src/ai_trading_agent/
├── domain/          # 业务规则、实体、值对象与领域服务
├── application/     # 用例编排和入站/出站端口
├── infrastructure/  # 数据源、持久化与配置适配器
└── presentation/    # API、CLI 等交付适配器
frontend/             # 独立 React 用户界面
backend/              # 后端容器交付文件
migrations/           # PostgreSQL Alembic 迁移
```

完整的边界和增量路线见 [docs/architecture.md](docs/architecture.md)。
