# AI Trading Agent

一个以研究和模拟交易为优先、遵循领域驱动设计（DDD）的量化交易智能体。

## 当前状态

项目刚初始化。第一个交付目标是建立可测试的市场数据领域模型与端口，随后按独立功能逐步接入行情、新闻、基本面、情绪、资金流、期权、因子、策略、文档/OCR 和交易日志分析。

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

## 目录

```text
src/ai_trading_agent/
├── domain/          # 业务规则、实体、值对象与领域服务
├── application/     # 用例编排和入站/出站端口
├── infrastructure/  # 数据源、持久化与配置适配器
└── presentation/    # API、CLI 等交付适配器
```

完整的边界和增量路线见 [docs/architecture.md](docs/architecture.md)。
