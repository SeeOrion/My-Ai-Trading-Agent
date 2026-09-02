# 架构与数据源决策

## 架构原则

项目采用 DDD 与六边形架构。`domain` 不依赖框架、HTTP 客户端、数据库或第三方金融 SDK；`application` 只依赖领域模型和端口；`infrastructure` 实现端口；`presentation` 仅负责 HTTP/CLI 输入输出。

```text
Presentation → Application → Domain
                   ↓
              Ports (interfaces)
                   ↓
       Infrastructure adapters
```

浏览器是独立交付层：`frontend/`（React/Vite）只能调用版本化 `/api/v1` HTTP 接口；Python
后端位于 `src/ai_trading_agent`。浏览器不包含数据供应商、LLM 或数据库的密钥。生产环境通过
Nginx 反向代理同源访问 API，默认不开启跨域；若未来需要不同域名，必须显式配置精确的允许来源。

领域按业务能力拆分：

| 限界上下文 | 职责 | 初始优先级 |
| --- | --- | --- |
| Market Data | 行情、交易日、证券主数据与 ETF | 1 |
| News Intelligence | 财经新闻采集、去重、标的映射 | 2 |
| Research | 基本面、情绪、资金流、期权与因子 | 3 |
| Strategy Lab | 策略生成、回测、验证和风险报告 | 4 |
| Document Intelligence | 文档解析、OCR 与结构化抽取 | 5 |
| Journal Analytics | 交易日志导入、归因和行为分析 | 6 |
| Execution | 模拟账户、风控和可选券商执行 | 最后，默认关闭 |

## 因子库

因子定义是不可执行的声明式元数据：稳定 ID、版本、主题、公式说明、显式输入列、预热期、持有期与说明。
`FactorRegistry` 拒绝未知输入列；基本面输入必须使用 `fund:` 前缀，避免计算器在不知情时读取隐式字段。

验证记录采用 `(as_of, realized_for)`：`realized_for` 必须晚于因子时点，IC 以每个交易日的横截面
Spearman 相关系数计算，样本少于 5 个标的不纳入统计。这样与 Vibe-Trading 的防前视原则一致；后续
分层回测也必须沿用同一时点边界，不可使用未来财报或未来成分股。

当前内置动量、波动率、盈利收益率、ROE 和新闻情绪五个因子，可通过 `GET /api/v1/factors` 查询。

## 个人策略、文档/OCR 与交易日志设计

| 模块 | 写入模型 | 关键约束 | 下一步用例 |
| --- | --- | --- | --- |
| Strategy Lab | `strategy_profiles`、`strategy_runs` | 用户策略保存为版本化 JSON 声明；不执行任意 Python 文本 | 校验因子引用、回测、风险报告 |
| Document Intelligence | `documents` | 原文件以 `storage_key` 引用；SHA-256 去重；提取文本可审计 | 上传、病毒扫描、PDF/OCR、证据定位 |
| Journal Analytics | `trade_journal_records` | 数量、价格、费用按原始精度保存；导入时间与成交日分离 | CSV 列映射、成交匹配、PnL/行为归因 |

上述表由 `migrations/` 的 Alembic 脚本创建在 PostgreSQL 的 `trading_agent` schema。迁移只能由部署者
显式执行；本阶段未连接、未创建或修改任何本地 pgAdmin4 数据库。

## 私有服务器拓扑

```text
Browser ──HTTPS──> Nginx / React ──same-origin──> FastAPI ──> PostgreSQL
                                                   │
                                                   ├── Futu OpenD (private network)
                                                   ├── Tushare / licensed news APIs
                                                   └── optional LLM gateway
```

`docker-compose.yml` 使这些服务可独立替换或扩展。数据库仅暴露在 Docker 私网；默认只将 Web UI
绑定到 `127.0.0.1:8080`，生产服务器应再由已配置 TLS 的反向代理公开访问。迁移服务使用部署时提供的
`DATABASE_URL`，不会读取本地 `.env` 文件。

## 当前研究能力

- **基本面**：将最新已公告的财务指标映射为供应商无关的快照，并用公开、可解释的质量规则计算分数。分数不是买卖建议。
- **情绪**：内置中英文财经词典基线，返回分数、标签和触发词；后续可用模型实现替换，不改变领域接口。
- **资金流**：保存总净流入与大/特大单净流入，统一为 CNY，再分别给出资金和大单方向。
- **期权**：支持多腿策略的到期损益、盈亏平衡点及有限/无限最大盈亏分析；尚未接入实时期权链。

当前 Tushare Research 适配器只服务 A 股：`fina_indicator` 提供已公告的财务指标，`moneyflow` 提供基于主动买卖单的个股资金流。港股和美股将通过后续的同一端口增加具备相应授权的数据源。

## 首选数据提供方

| 范围 | 主适配器 | 作用 | 凭证/限制 |
| --- | --- | --- | --- |
| A 股 / ETF | Tushare Pro | 日线、基本面、资金流、中文财经快讯 | API token；部分接口按权限/积分开放 |
| A / 港 / 美股、ETF、期权 | Futu OpenAPI | 实时快照、K 线、盘口、期权与统一代码格式 | OpenD、账户及相应行情权限 |
| 新闻 | Tushare News（中文）+ 可替换新闻端口 | 最新财经快讯 | Tushare 新闻权限；未来可按许可增加全球新闻源 |

所有供应商都经由端口访问，业务代码不会绑定任何单一数据源。对于同一查询，应用层可配置优先级与降级策略；任何数据结果都携带来源和采集时间，避免把延迟行情误作实时行情。

当前实现中，Tushare 的 `daily` 适配器明确标记为日终数据（以上海收盘时间戳返回）；它不会被默认 15 分钟的“最新报价”时效策略误认为实时数据。Futu 适配器经由本地 OpenD，先订阅 `QUOTE` 再读取一次快照并关闭连接；实时权限仍由 Futu 账户决定。

## 安全边界

- 研究、数据采集与回测默认只读。
- API 密钥只来自环境变量或外部秘密管理系统，绝不写入 Git。
- `.env` 被 Git 忽略且权限应仅限其所有者；自动化与本助手都不读取其中内容。
- 未来订单必须通过独立的 `Execution` 上下文和风险闸门；研究模块没有下单端口。
- 所有市场数据以时区明确的 UTC 时间戳表示，展示层再转换为交易所时区。
