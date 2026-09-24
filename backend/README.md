# My AI Trading Agent Backend

## macOS 常驻本机服务

本项目在 macOS 上使用 `launchd` 保持后端常驻，而不是依赖临时终端。服务在登录后自动启动，意外退出会自动重启；AI 模拟任务本身仍只会在工作日各市场常规开市时段每 10 分钟运行。

已提交的模板为 `deploy/macos/com.seeorion.my-ai-trading-agent.backend.plist`。模板中的路径对应当前这台 Mac；如将项目移动到其他位置，先更新三个项目绝对路径后再安装。运行日志保存于 `/private/tmp/my-ai-trading-agent-backend.log` 与 `/private/tmp/my-ai-trading-agent-backend-error.log`，不写入仓库。

This directory is the complete Python backend workspace: DDD source, tests, Alembic migrations,
`uv` dependency definition and Docker image.

Run local development commands from here:

```bash
uv sync --all-extras
uv run uvicorn ai_trading_agent.interfaces.api.app:app --app-dir src --reload --port 8000
```

The API is served under `/api/v1`. Migrations are in `migrations/` and must receive a PostgreSQL
URL at deployment time. No credentials are committed in this repository.

For A-share intraday quotes, the runtime prefers Futu OpenD and automatically
degrades to the Hithink Finance private REST credential configured by its skill,
then Tencent's experimental public page feed and Tushare daily data. The Hithink
key is kept in its user-level private credential store outside this repository;
never add it to this project `.env` or a deployment manifest. Tencent and
AKShare are research/display sources only and are never execution prices.

The bounded candidate screen retries transient Tencent transport failures with
configured exponential backoff. If Tencent still fails, A shares fall back to
Hithink Finance and then Futu; Hong Kong and US candidates fall back to Futu.
This is a fixed research universe rather than an exchange-wide scan, and the
API reports the provider that actually supplied the observations.

`HITHINK_FINANCE_TIMEOUT_SECONDS` is the only Hithink setting shown in
`.env.example`. Configure the API Key through the `hithink-finance` Skill's
system-level private credential flow, not through a project file or Git.

Hithink Finance also powers the selected-fund workspace: exchange-traded ETFs
receive true snapshots and daily OHLCV, while OTC funds receive their published
NAV, returns, disclosed holdings, allocation, drawdowns, diagnostics and fund
news metadata. OTC NAV is never presented as real-time traded volume.
