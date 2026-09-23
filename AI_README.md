# AI 协作说明：My AI Trading Agent

> 这是一份给下次接手项目的 AI/开发者的“工作地图”。开始任何改动前，先读本文件，再按需要阅读 [`README.md`](README.md) 与 [`docs/architecture.md`](docs/architecture.md)。
>
> 项目目标是**研究优先的个人投资跟踪与模拟交易工具**：围绕用户手动选择的股票、ETF 和场外基金做深度跟踪、解释和模拟，不是自动实盘下单系统，也不是默认扫描全市场的交易机器人。

## 1. 30 秒了解项目

| 项目项 | 约定 |
| --- | --- |
| 项目名 | My AI Trading Agent |
| 前端 | `frontend/`：React 19 + TypeScript + Vite |
| 后端 | `backend/`：Python 3.12+、FastAPI、uv、SQLAlchemy、Alembic |
| 架构 | DDD + 六边形（端口/适配器），前后端完全分离 |
| 数据库 | 私有 PostgreSQL；业务 schema 是 `trading_agent` |
| 核心范围 | A 股、港股、美股、场内 ETF、场外公募基金；自选跟踪、研究分析、个人策略/纪律、手动模拟持仓、AI 模拟持仓 |
| 不做什么 | 不保存券商交易密钥、不连接真实下单链路、不把研究结论伪装成确定投资建议 |

最重要的业务原则：

1. **先自选，后研究。** 默认定时任务只刷新用户的自选标的，不启动全市场扫描。
2. **数据源可降级、每份数据可追溯。** 返回值应保留 `source` 与时间；日终数据不能被标成实时数据。
3. **个人纪律是可选硬约束。** 未配置适用纪律时，AI 模拟交易按策略、因子与风险预算判断；配置并启用后，必须满足纪律买入条件才允许模拟建仓。
4. **缺失因子不是不利因子。** 数据缺口只提示；已观测因子风险占优、风险预算、仓位上限或纪律不满足才会阻止 AI 模拟建仓。
5. **场外基金与股票不同。** 只展示净值与定期披露资料；没有真实 OHLCV 时，不能虚构 K 线、成交量、资金流或技术因子。

## 2. 首次接手时的检查清单

1. 在仓库根目录确认当前分支和未提交改动：`git status --short`。
2. **不要读取、打印、提交或重写**根目录 `.env`、`backend/.env`、系统凭据文件或任何 API Key。
3. 阅读本文件中与任务相关的“快速定位”表，而不是跨层复制已有逻辑。
4. 若改 Python：在 `backend/` 用 `uv run pytest` 和 `uv run ruff check src tests` 验证。
5. 若改前端：在 `frontend/` 执行 `npm run build`。
6. 新增持久化实体时：新增 Alembic migration，更新 SQLAlchemy model、repository、领域模型和测试；不要手工改线上 schema。
7. 新增供应商时：先定义/复用 application port，再在 `infrastructure/rpc/` 写适配器；不要从 `domain` 或 React 直接调用第三方 SDK/API。

## 3. 启动、测试与部署

### 本地开发

后端依赖由 `uv` 管理，虚拟环境为 `backend/.venv`。不需要手动激活；`uv run` 会自动使用它。

```bash
# 终端 1：后端
cd backend
uv sync --all-extras
uv run alembic upgrade head
uv run uvicorn ai_trading_agent.interfaces.api.app:app --app-dir src --reload --port 8000

# 终端 2：前端
cd frontend
npm install
npm run dev
```

- 前端开发地址：`http://127.0.0.1:5173`
- 后端健康检查：`http://127.0.0.1:8000/healthz`
- FastAPI 交互文档：`http://127.0.0.1:8000/docs`
- Vite 已将 `/api` 和 `/healthz` 代理至端口 `8000`。

### 验证命令

```bash
cd backend
uv run pytest
uv run ruff check src tests

cd ../frontend
npm run build
```

### 私有部署

[`docker-compose.yml`](docker-compose.yml) 包含五项独立服务：

```text
Browser ── HTTPS / reverse proxy ── React/Nginx ── FastAPI ── PostgreSQL
                                                └── 外部行情、资讯、LLM 服务
```

- Docker 默认只把前端绑定为 `127.0.0.1:8090`（可用 `FRONTEND_PORT` 覆盖）；公网暴露应由宿主机反向代理和 TLS 负责。
- `credential-init` 在首次启动时把随机 PostgreSQL 密码写入 `postgres_credentials` 命名卷；`postgres`、`migrate`、`backend` 只通过只读文件使用，不把密码写入 Git 或项目 `.env`。
- 本机完整部署叠加 `docker-compose.hithink.yml`，把用户级同花顺凭据文件只读挂载到后端；凭据值不进入镜像、Compose 文件或项目 `.env`。
- Docker Desktop 中的后端用 `host.docker.internal` 访问 Mac 上的 Futu OpenD；不要把容器内 `127.0.0.1` 当作宿主机。
- 多个后端副本时，只允许一个副本启用定时任务，避免重复抓取与重复模拟交易。

## 4. 完整目录地图

```text
AI-Trading-Agent/
├── AI_README.md                    # 本文件：AI 接手说明
├── README.md                       # 面向使用者的概览与启动说明
├── docs/architecture.md            # 设计原则、数据源和安全边界
├── docker-compose.yml              # 私有部署拓扑
├── backend/
│   ├── .env.example                # 仅非敏感配置示例；绝不放真实密钥
│   ├── pyproject.toml              # Python/uv 依赖与质量工具配置
│   ├── alembic.ini                 # Alembic 配置
│   ├── migrations/versions/        # 按日期编号的 PostgreSQL 迁移
│   ├── src/ai_trading_agent/
│   │   ├── domain/                 # 纯业务规则；不依赖 FastAPI/SQLAlchemy/SDK
│   │   ├── application/            # 用例、端口和流程编排
│   │   ├── infrastructure/         # 数据库、配置、外部数据源适配器
│   │   └── interfaces/             # HTTP、DTO、组装层、定时任务
│   └── tests/                      # 与源代码层级相对应的 pytest 测试
└── frontend/
    ├── src/App.tsx                 # 单页 UI、页面工作区与展示组件
    ├── src/api.ts                  # 所有 HTTP DTO 与请求函数的唯一入口
    ├── src/styles.css              # 全局样式（浅色、紧凑 UI）
    ├── src/main.tsx                # React 启动入口
    ├── vite.config.ts              # 开发服务器与 API 代理
    └── nginx.conf                  # 生产环境同源 API 反向代理
```

## 5. 后端分层：职责与依赖方向

依赖方向必须保持如下形态：

```text
interfaces (HTTP / facade / DTO / scheduler)
                      ↓
              application (use cases / ports)
                      ↓
                  domain (rules / models)
                      ↑
infrastructure (DB / external API / configuration adapters)
```

### `domain/`：业务真相，保持纯净

| 子目录 | 含义 | 典型文件 |
| --- | --- | --- |
| `aggregate/` | 有边界和不变式的业务对象 | `market.py`、`watchlist.py`、`ai_simulation.py`、`discipline.py` |
| `ability/` | 可复用领域能力 | `factors.py`：10 个声明式因子及防前视诊断 |
| `enums/` | 市场、标的、候选、研究等受控枚举 | `market.py`、`candidates.py` |
| `service/` | 跨聚合的纯业务决策 | `ai_simulation.py`、`discipline_entry.py`、`factor_analysis.py`、`position_metrics.py` |
| `event/` / `query/` | 预留的事件与查询扩展边界 | 当前不应塞入重复业务实现 |

禁止在 `domain/` 中：读取环境变量、发 HTTP、导入 FastAPI/SQLAlchemy、调用 pandas/第三方金融 SDK、直接写数据库。

### `application/`：用例和端口

| 文件/方向 | 负责什么 |
| --- | --- |
| `ports.py` | 供应商无关的市场数据、候选、基金研究等 Protocol；新增外部能力先考虑这里 |
| `market_data.py` / `a_share_quote_failover.py` | 获取行情与 A 股多源降级策略 |
| `research.py` / `technical.py` / `funds.py` | 基本面、资金流、情绪、K 线技术与基金研究用例 |
| `factors.py` | 因子注册表查询用例 |
| `portfolio.py` / `watchlist_analysis.py` | 自选、手动模拟持仓与分析快照的用例 |
| `strategies.py` / `disciplines.py` | 版本化策略与个人纪律的保存/查询用例 |
| `market_scans.py` / `candidates.py` | 有界研究样本、扫描记录与 7 天清理 |

`application` 可以依赖 `domain`，并只通过 `ports` 表达对数据库或供应商的需要；它不能反向 import 具体 `infrastructure/rpc` 实现。

### `infrastructure/`：可替换的技术实现

| 子目录 | 含义 | 快速入口 |
| --- | --- | --- |
| `config/` | 在组合层读取配置并做范围校验 | `providers.py`、`news.py` |
| `repo/` | SQLAlchemy ORM 与 repository 实现 | `models.py`、`database.py`、`portfolio.py`、`ai_simulation.py` |
| `rpc/` | 每个外部系统一个适配器 | `hithink_*.py`、`futu_*.py`、`tushare_*.py`、`tencent_market.py`、`akshare_news.py`、`llm_*.py` |
| `common/` | 仅放真正共享的基础技术工具 | 不应放业务规则 |

外部 API 的异常必须在适配器侧转换成可理解的 provider error；上层应把可选数据的失败变成 `notices`，不要因为一项辅助数据失败让整个自选页面崩溃。

### `interfaces/`：交付与组合层

| 子目录 | 含义 | 快速入口 |
| --- | --- | --- |
| `api/` | FastAPI 路由和应用生命周期 | `api/app.py` |
| `model/` | HTTP request/response DTO；不直接暴露 domain object | `model/http.py` |
| `facade/` | 将 use case、repository、provider 组合为完整页面/API 行为 | `research_workspace.py`、`watchlist_analysis.py`、`ai_simulation.py` |
| `adapter/` | 将环境/运行时输入适配入应用 | `adapter/environment.py` |
| `task/` | 无状态、可取消的循环定时任务 | `task/market_scans.py` |
| `mq/` | 未来消息队列扩展边界 | 当前不放重复实现 |

`interfaces/facade/` 是“选什么 provider、如何降级、哪些可选信息可失败”的组合位置。不要把这些编排散落到 FastAPI 路由或 React。

## 6. 关键业务能力与快速定位

| 需要修改的功能 | 先看哪里 | 关联位置 |
| --- | --- | --- |
| 证券代码/市场/币种规范化 | `domain/aggregate/market.py` | 所有请求都经 `research_workspace.instrument_from_query()` 构造 `Instrument` |
| 自选添加、删除、列表 | `interfaces/facade/portfolio.py`、`application/portfolio.py` | 表：`watchlist_items`；前端：`WatchlistWorkspace` |
| 自选的标签与 AI 解读 | `interfaces/facade/watchlist_analysis.py` | 表：`watchlist_analysis_snapshots`；定时任务从 `api/app.py` lifespan 启动 |
| 自选详情/K 线/Volume Profile | `application/technical.py`、`domain/aggregate/technical.py` | 前端：`WatchlistDetail`、`TechnicalStudyView`、`CandlestickChart` |
| A 股财务、估值、现金流、催化剂 | `infrastructure/rpc/hithink_watchlist_detail.py` | API：`/watchlist/{id}/deep-dive` |
| 基金/ETF 资料与净值 | `infrastructure/rpc/hithink_funds.py` | 前端：`FundWorkspace`、`FundWatchlistDetail` |
| 研究：基本面/情绪/资金流/期权/因子 | `application/research.py`、`domain/aggregate/research.py`、`domain/service/factor_analysis.py` | HTTP：`POST /api/v1/research` |
| 10 因子定义 | `domain/ability/factors.py` | API：`GET /api/v1/factors`；因子是声明式元数据，不执行用户代码 |
| 个人策略 | `domain/aggregate/strategy.py`、`application/strategies.py` | 表：`strategy_profiles`；前端：`StrategyWorkspace` |
| 个人纪律 | `domain/aggregate/discipline.py`、`domain/service/discipline_entry.py` | 表：`trading_disciplines`；前端：`DisciplineWorkspace` |
| 手动模拟持仓/盈亏 | `domain/service/position_metrics.py`、`interfaces/facade/portfolio.py` | 表：`paper_positions`；前端：`ManualPaperPortfolioWorkspace` |
| AI 模拟选股与交易 | `interfaces/facade/ai_simulation.py`、`domain/service/ai_simulation.py`、`domain/service/simulated_execution.py` | 表：`ai_simulation_*`；前端：`AiSimulationWorkspace` |
| AI 市场问答 | `interfaces/facade/market_assistant.py`、`infrastructure/rpc/llm_advisor.py` | 前端：`MarketAssistant` |
| 盘后快报、指数与板块轮动 | `interfaces/facade/market_brief.py`、`infrastructure/rpc/hithink_market_brief.py` | 前端：`Dashboard` |
| 财经资讯与情绪 | `application/news.py`、`infrastructure/rpc/akshare_news.py`、`infrastructure/rpc/llm_news.py` | 前端总览：`OverviewNews` |
| 数据保留/全市场扫描 | `application/market_scans.py`、`infrastructure/repo/market_scans.py` | 默认只保留 7 天扫描快照 |
| 文档 OCR / 交易日志 | `repo/models.py` 的 `DocumentRecord` / `TradeJournalRecord` | UI 和表结构已预留，上传/OCR/导入用例尚未完成 |

## 7. API 地图

所有浏览器请求必须集中在 [`frontend/src/api.ts`](frontend/src/api.ts)；前端组件不得自行 `fetch`。

| 范围 | 主要接口 |
| --- | --- |
| 系统 | `GET /healthz` |
| 因子 | `GET /api/v1/factors`、`GET /api/v1/factors/{identifier}` |
| 行情/名称 | `POST /api/v1/market/quote`、`POST /api/v1/instruments/resolve` |
| 总览 | `GET /api/v1/market/post-market-brief`、`POST /api/v1/assistant/market-question`、`GET /api/v1/news` |
| 候选/扫描 | `GET /api/v1/market/candidates`、`POST /api/v1/market/scans/{market}`、`GET /api/v1/market/scans/{market}/latest` |
| 研究 | `POST /api/v1/research`、`POST /api/v1/funds/research`、`POST /api/v1/technical/study` |
| 自选 | `GET/POST /api/v1/watchlist`、`DELETE /api/v1/watchlist/{id}`、`GET /api/v1/watchlist/analyses`、`POST /api/v1/watchlist/{id}/analysis/refresh`、`GET /api/v1/watchlist/{id}/deep-dive` |
| 手动模拟持仓 | `GET/POST /api/v1/paper-positions`、`DELETE /api/v1/paper-positions/{id}`、`GET /api/v1/paper-positions/valuations`、`GET /api/v1/paper-positions/overview` |
| AI 模拟交易 | `GET /api/v1/ai-simulation/overview`、`GET /api/v1/ai-simulation/runs`、`POST /api/v1/ai-simulation/run`、`PUT /api/v1/ai-simulation/settings` |
| 策略 / 纪律 | `GET/POST /api/v1/strategies`、`PUT /api/v1/strategies/{id}`、`GET/POST /api/v1/disciplines`、`PUT /api/v1/disciplines/{id}` |

请求和响应的权威结构在 `interfaces/model/http.py` 与 `frontend/src/api.ts`；新增字段时两边同步修改，并添加 API 测试。

## 8. 数据源、能力和降级顺序

### 数据提供方矩阵

| 数据源 | 主要用途 | 凭据 | 适用与限制 |
| --- | --- | --- | --- |
| Futu OpenD | A/港/美行情、K 线、盘口、期权、分批快照 | 本机 OpenD + 账户行情权限 | 优先实时来源；市场权限取决于账户 |
| Hithink Finance | A 股快照/日 K/财务/估值、指数、板块、ETF、场外基金 | **hithink-finance Skill 的系统级私密凭据** | 场内 ETF 有真实行情与日线；场外基金是净值与定期披露 |
| Tushare Pro | A 股日线、`daily_basic`、财务、资金流、扫描 | `TUSHARE_TOKEN` | 部分接口需积分/权限；日线不是盘中实时价 |
| 腾讯公开行情 | A 股免费末级报价降级 | 不需 key | 实验性公开源，只作研究/展示，不作执行价格 |
| AKShare | 公开财经资讯采集 | 不需 key | 上游网页可能变化/限流；由东方财富优先、Sina 降级、短时缓存处理 |
| LLM（兼容 Chat Completions） | AI 问答、资讯摘要、自选解读 | `LLM_API_KEY` 等 | 只能解释已有、明确标记来源的数据；不能绕过数据缺口编造事实 |

### A 股行情降级链路

```text
Futu OpenD
  ↓ 失败、超时或权限不足（有冷却期）
Hithink Finance
  ↓
腾讯公开行情
  ↓
Tushare 日线（明确标记为日终/非实时）
```

实现位置：`interfaces/facade/research_workspace.py` + `application/a_share_quote_failover.py`。

### 基金/ETF 代码与数据语义（高频踩坑）

| 类型 | UI 市场 | `instrument_type` | 合法/规范化代码例 | 数据语义 |
| --- | --- | --- | --- | --- |
| 场内 ETF | `a_share` | `etf` | `159995.SZ`、`510300.SH` | 有场内快照、日 K、真实 OHLCV，可做技术研究 |
| 场外公募基金 | `fund` | `fund` | `002010.OF` | 净值、收益/回撤、定期披露的持仓和配置；没有盘中成交量 |
| A 股股票 | `a_share` | `equity` | `600519.SH`、`000001.SZ` | 行情、K 线、基本面、估值；资金流依 Tushare 权限 |

`domain/aggregate/market.py` 会将明确类别的裸六码自动规范为同花顺所需 `thscode`：ETF 加 `.SH/.SZ`，场外基金加 `.OF`。不要删除或绕过这一步，否则同花顺基金接口会返回“无数据”。

## 9. 研究、因子、策略、纪律和 AI 的关系

```text
自选标的 / 候选样本
       │
       ├─ 行情、K 线、基本面、估值、资金流、新闻情绪
       ├─ 10 个内置因子（可用 / 支持 / 不利 / 缺失）
       ├─ 选中的个人策略（研究筛选条件与最严格仓位上限）
       └─ 适用的启用个人纪律（硬性买入/加仓/止盈/清仓门槛）
                               │
                               ▼
             可解释标签 + LLM 解读 + 人工复核动作
                               │
                    仅 AI 模拟账户可写入模拟交易记录
```

### 内置 10 因子

1. `momentum_20d`：20 日动量
2. `volatility_20d`：20 日波动率
3. `short_reversal_5d`：5 日短期反转
4. `rsi_14`：14 日 RSI
5. `moving_average_trend`：20/60 日均线趋势
6. `relative_volume_20d`：相对成交量
7. `earnings_yield`：盈利收益率
8. `book_to_price`：账面市值比
9. `return_on_equity`：ROE
10. `news_sentiment`：新闻情绪

因子元数据是可审计的声明，不是用户可执行脚本。回测/诊断必须使用 `(as_of, realized_for)` 的时间边界，`realized_for` 必须晚于 `as_of`，以避免前视偏差。

### AI 模拟交易的硬规则

- 只在预设的高流动性**研究样本**中选择，非全市场，也从不下真实订单。
- 支持多选启用策略；仅参考所有选中策略的因子，仓位上限取最严格值。
- 建仓评分阈值为 65；若存在已观测因子，至少需 2 项支持，且支持项必须多于逆风项。缺失因子只在决策报告和通知中提示，不能单独否决。
- 仓位先受剩余槽位和所选策略最严格单标的上限约束，再按评分及因子证据强度缩放；不会因为刚好达标就满仓。
- 模拟买卖使用统一成交估算：参考价加/减 5bp 不利滑点，并计入 5bp 成本估算；这不是券商成交、真实税费或投资建议。
- 已启用个人纪律的止盈/清仓条件优先于新的选股；取得可验证行情后才会全量平掉相应模拟仓位。加仓条件当前只生成复核提示，避免每十分钟重复加仓，直到引入版本化加仓计划。
- 每次手动或定时运行均写入 `ai_simulation_runs`，便于日后审计。
- AI 模拟账户目前仅支持 `a_share`、`hong_kong`、`united_states`；不接受 `fund` 市场。

## 10. 定时任务与数据保留

应用在 `interfaces/api/app.py` 的 lifespan 中创建任务，通用循环实现位于 `interfaces/task/market_scans.py`。

| 任务 | 默认 | 配置 | 行为 |
| --- | --- | --- | --- |
| 自选分析刷新 | 每 900 秒 | `WATCHLIST_ANALYSIS_*` | 顺序刷新最多 30 个自选，存标签和 AI 摘要；不会全市场扫描 |
| AI 模拟交易 | 每 600 秒；仅工作日各市场常规开市时段 | `AI_SIMULATION_*` | 只运行已创建的 AI 模拟账户，并保存结果/失败记录；任务对齐到每小时的 00/10/20/… 分钟 |
| 全市场扫描 | 默认关闭 | `MARKET_SCAN_*` | 仅手动或显式开启；批次上限 400 |
| 扫描快照清理 | 与扫描流程关联 | 代码中的保留策略 | `market_snapshots` 只保留 7 天 |

本机 macOS 开发环境使用 `backend/deploy/macos/com.seeorion.my-ai-trading-agent.backend.plist` 与 `frontend/deploy/macos/com.seeorion.my-ai-trading-agent.frontend.plist` 安装两项 `launchd` 用户服务，使 FastAPI 与生产构建后的前端在登录后持续运行并在异常退出后自动重启。服务是否常驻与模拟任务是否执行是两回事：后者仍由 `AI_SIMULATION_*` 和交易时段门控严格限制。

调试时，如果页面数据未变，先确认：后端进程是否是最新代码、对应 scheduler 是否开启、数据库连接是否有效、分析快照是否还在缓存窗口内。手动“更新解读”可强制刷新一只自选标的。

## 11. PostgreSQL 与迁移

- 连接串只在私有 `.env` 或部署环境设置：`DATABASE_URL`。
- ORM 权威定义：`backend/src/ai_trading_agent/infrastructure/repo/models.py`。
- 迁移权威目录：`backend/migrations/versions/`。
- 运行迁移：`cd backend && uv run alembic upgrade head`。
- 主要表：`watchlist_items`、`watchlist_analysis_snapshots`、`paper_positions`、`strategy_profiles`、`trading_disciplines`、`ai_simulation_portfolios`、`ai_simulation_positions`、`ai_simulation_trades`、`ai_simulation_runs`、`market_scan_runs`、`market_snapshots`。
- `documents`、`trade_journal_records`、`strategy_runs` 的结构已预留；相应上传/OCR、日志导入、回测用例并未完成，不能宣称已上线。

## 12. 安全和隐私（不可突破）

1. `.env`、`backend/.env`、`credentials.env`、真实 token、数据库密码与 LLM key 绝不可读取、输出、提交或放入前端。
2. 同花顺 key 不属于项目 `.env`：由 `hithink-finance` Skill 的系统级私密凭据管理。项目仅保留 `HITHINK_FINANCE_TIMEOUT_SECONDS` 等非敏感配置。
3. `frontend/` 不得出现 `TUSHARE_TOKEN`、`LLM_API_KEY`、PostgreSQL 连接串或任何 `HITHINK_FINANCE_API_KEY`。
4. 记录 API 故障时只记录安全的错误摘要，不能记录 `Authorization`、请求头或响应中可能出现的敏感字段。
5. 永远保持研究/模拟与真实执行隔离。若未来接券商下单，必须是新的 `Execution` 限界上下文、单独权限、显式用户确认和风险闸门，不能复用研究 API 直接下单。

## 13. 常见问题与正确排查路径

| 现象 | 先检查 | 正确处理 |
| --- | --- | --- |
| ETF/场外基金显示无数据 | `Instrument` 是否为完整 `thscode` | ETF 使用 `.SH/.SZ`，场外基金用 `.OF`；由 `market.py` 统一规范化 |
| A 股实时价不可用 | `research_workspace.latest_quote()` 的降级错误 | 检查 Futu OpenD/权限，再核对同花顺私密凭据，最后确认腾讯/Tushare 降级标识 |
| 场外基金没有 K 线/成交量 | `HithinkFundHistoricalBarsProvider` 的限制 | 正确显示“净值/定期披露”，不要补造 OHLCV 或资金流 |
| 自选显示 `partial` | `watchlist_analysis.py` 的 `notices` | `partial` 往往表示核心数据成功、可选披露/技术项受限；只有 `failed` 才是整个分析失败 |
| 前端黑屏/页面异常 | 浏览器控制台、`frontend/src/App.tsx`、`api.ts` | 保持 API DTO 和 UI 类型同步；先运行 `npm run build` |
| API 500/503 | 后端日志、`interfaces/facade/` 组合层 | 区分配置错误、上游权限、暂时网络失败；对可选数据降级为 notices |
| AI 模拟未买入 | `decision_reports.blockers` | 明确展示不利因子、预算、持仓上限或纪律哪一项阻止；不要把数据缺失写成“不合格” |
| 数据库没有表/页面无历史 | `DATABASE_URL`、Alembic head | 验证连接后运行 `alembic upgrade head`，不要手工建表冒充迁移 |

## 14. 开发规范与提交方式

- 后端新业务逻辑先落在 `domain` 或 `application`，再由 `infrastructure` 和 `interfaces` 接入；不要把计算公式写进路由或 React。
- UI 只消费 `api.ts` 暴露的请求函数与类型；避免页面之间复制同一请求、金额格式化或错误处理。
- 价格、金额、份额在后端使用 `Decimal`，不以 `float` 做财务计算；时间使用带时区 UTC。
- 新数据源需要说明市场覆盖、时效、授权与限制；失败时提供可读 notice。
- 新功能至少包含对应层级单测；改 HTTP 行为加 `tests/interfaces/api/` 测试。
- 提交按意图拆分，例如：`feat(watchlist): ...`、`fix(funds): ...`、`refactor(domain): ...`、`test(api): ...`、`docs(ai): ...`。不要把无关格式化、依赖升级和业务功能混在同一提交。
- 保留用户既有未提交变更；不使用破坏性 Git 命令。

## 15. 推荐的接手提示词

下次导入项目时，可以把下面这句话连同本文件提供给 AI：

> 请先完整阅读仓库根目录 `AI_README.md`、`README.md` 和与本任务有关的文件。遵循 DDD/六边形分层，不读取或输出 `.env`、同花顺 Skill 凭据或任何密钥；先检查现有实现避免重复代码，改动后运行相应测试并按功能拆分提交。

---

最后更新：2026-09-20。此文件描述的是当前已实现状态；新增功能时请同时更新本文件的目录、能力、数据源、API、迁移和限制说明。
