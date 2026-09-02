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

## 首选数据提供方

| 范围 | 主适配器 | 作用 | 凭证/限制 |
| --- | --- | --- | --- |
| A 股 / ETF | Tushare Pro | 日线、基本面、资金流、中文财经快讯 | API token；部分接口按权限/积分开放 |
| A / 港 / 美股、ETF、期权 | Futu OpenAPI | 实时快照、K 线、盘口、期权与统一代码格式 | OpenD、账户及相应行情权限 |
| 新闻 | Tushare News（中文）+ 可替换新闻端口 | 最新财经快讯 | Tushare 新闻权限；未来可按许可增加全球新闻源 |

所有供应商都经由端口访问，业务代码不会绑定任何单一数据源。对于同一查询，应用层可配置优先级与降级策略；任何数据结果都携带来源和采集时间，避免把延迟行情误作实时行情。

## 安全边界

- 研究、数据采集与回测默认只读。
- API 密钥只来自环境变量或外部秘密管理系统，绝不写入 Git。
- 未来订单必须通过独立的 `Execution` 上下文和风险闸门；研究模块没有下单端口。
- 所有市场数据以时区明确的 UTC 时间戳表示，展示层再转换为交易所时区。
