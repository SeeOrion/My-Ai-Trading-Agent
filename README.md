# AI Trading Agent

一个以研究和模拟交易为优先、遵循领域驱动设计（DDD）的量化交易智能体。

接手开发或导入新的 AI 对话时，请先阅读 [AI_README.md](AI_README.md)。其中包含完整的项目地图、DDD 分层、数据源与降级逻辑、关键文件索引、安全边界和验证方式。

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

`docker-compose.yml` 提供凭据初始化、PostgreSQL、一次性数据库迁移、后端和静态前端五个独立服务。
后端从仓库根目录私有 `.env` 读取 Tushare、LLM 和定时任务设置；Compose 会用容器内连接串覆盖
`DATABASE_URL`。首次启动时，`credential-init` 会自动生成数据库密码并只保存在
`postgres_credentials` 私有 Docker 卷中；密码不会进入项目 `.env`、镜像、Git 或前端。

本机 Docker 部署（包含同花顺系统级私密凭据的只读挂载）：

```bash
HITHINK_CREDENTIALS_FILE="/Users/你的用户名/Library/Application Support/hithink-finance/credentials.env" \
docker compose -f docker-compose.yml -f docker-compose.hithink.yml up -d --build

docker compose -f docker-compose.yml -f docker-compose.hithink.yml ps
```

部署完成后访问 `http://127.0.0.1:8090`。如需其他端口，可在启动命令前设置 `FRONTEND_PORT`。
`credential-init` 和 `migrate` 成功退出是正常状态；
`postgres`、`backend`、`frontend` 应保持 `healthy`。Futu OpenD 继续运行在 Mac 宿主机，容器通过
`host.docker.internal:11111` 访问。停止服务使用相同的两个 `-f` 参数执行 `docker compose down`；
不要追加 `-v`，否则会删除 PostgreSQL 数据卷。

从原生 macOS PostgreSQL 迁移旧数据到 Docker 时，运行：

```bash
backend/.venv/bin/python backend/deploy/migrate_local_postgres_to_docker.py
```

工具会先在 `.runtime/backups/` 中生成源库和 Docker 库的私有备份，然后以主键去重的方式合并；
已存在的 Docker 记录优先，不会删除旧库。该目录已被 Git 忽略。

需要使用 pgAdmin 查看 Docker 数据库时，运行：

```bash
backend/.venv/bin/python backend/deploy/configure_pgadmin_access.py
```

数据库只会绑定到本机 `127.0.0.1:55433`，脚本会创建一个只读 pgAdmin 账号，并把完整连接参数
保存到本机私有文件 `.runtime/pgadmin.env`。请由用户自行打开该文件并将参数填入 pgAdmin；
密码不会被输出到终端或提交到 Git。

本机 macOS 开发环境已准备两项 `launchd` 用户服务：后端服务和生产构建后的前端预览服务均会在登录后自动启动、异常退出后自动重启。前端固定提供于 `http://127.0.0.1:5173`，并将 `/api` 请求代理到本机后端。前端源码改动后，先执行 `cd frontend && npm run build`，再重启前端服务以加载新页面。

## 已配置服务如何进入 UI

本机后端在真正收到行情、资讯、研究或 AI 对话请求时，才从项目根目录的私有 `.env` 装载
`TUSHARE_TOKEN`、Futu OpenD 地址、LLM 配置和可选的 `DATABASE_URL`。同花顺配置在
[`backend/.env.example`](backend/.env.example) 中保留超时等非敏感参数；其 API Key 由
`hithink-finance` Skill 的系统级私密凭据保存。后端会按 Skill 的安全优先级读取运行时 Key，
但项目 `.env`、前端、Git 提交和日志都不应出现 `HITHINK_FINANCE_API_KEY`。免费腾讯公开行情与
AKShare 公开资讯不需要密钥；这些值绝不返回给前端。
当前 UI 已接通行情、财经资讯、研究分析、个人策略编辑/版本保存，以及首页 AI 研究对话；文档/OCR
和交易日志仍是下一阶段模块。

“自选跟踪”只分析你手动加入的标的：后台默认每 15 分钟按顺序更新至多 30 个自选标的，并将行情、
情绪、基本面、资金流、技术面和个人纪律生成可解释标签，再保存最多 300 字的 AI 研究摘要。点击
自选项会展开当日行情与成交量、同花顺历史 K 线和 Volume Profile。对于 A 股股票，还会读取同花顺
最近披露的利润表、资产负债表、现金流量表、五项估值快照及历史除权除息事件；这些“时间催化剂”只展示
已披露事实，不预测未来事件。基金/ETF 则使用同花顺的基本资料、场内行情/日线、重仓与资产配置、收益
回撤、财务指标和资讯列表，并明确区分定期披露数据与实时数据。系统不会扫描全市场、不会创建委托。生产环境
如运行多个后端副本，只能让一个副本设置 `WATCHLIST_ANALYSIS_SCHEDULER_ENABLED=true`；若不希望
自动调用数据源与 LLM，可设置为 `false` 并在界面手动点击“更新解读”。

AI 模拟选股只会对已创建的模拟账户运行：默认在各交易所的实际交易日和常规开市时段，每 10 分钟于
`00/10/20/…` 分钟对齐执行一次，并把每轮结论（包括失败原因）保存到 PostgreSQL。A 股按
北京时间 `09:30–11:30、13:00–15:00`，港股按香港时间 `09:30–12:00、13:00–16:00`，美股按纽约
时间 `09:30–16:00`（自动处理夏令时）。这项规则由根目录私有 `.env` 的
`AI_SIMULATION_*` 配置控制。交易日判断使用独立的 A 股、港股和纽交所日历，会跳过节假日、午休和收市后时段，并处理半日市与美股夏令时。手动执行不受交易时段限制。

AI 模拟持仓的卖出复核使用可审计的 `classic_v1` 规则：已启用的个人纪律始终优先；无适用纪律时，
成本下方 8% 触发全量风险退出，盈利达到 20% 后先按有效交易单位兑现约一半，剩余仓位改用 2×ATR
移动保护（回撤距离限制为 5%–12%）。现价跌破 20 日均线且至少两项所选技术因子转弱时也会退出；
因子或 K 线缺失不会被当作卖出信号。该规则只服务模拟账户，不会创建真实委托，也不保证收益。

候选股研究使用预设的有界高流动性样本池，不扫描整个交易所。腾讯公开行情发生短时网络错误时
会使用有上限的指数退避自动重试；多次失败后，A 股降级到同花顺、再降级到 Futu，港股/美股降级到 Futu。
返回结果保留实际 `source`，不会把备用源伪装成腾讯数据。

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
