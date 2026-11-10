"""Integration checks restricted to a disposable named PostgreSQL database.

Run seed after migrating to 20261029_01; run check after upgrading to head.
No external data/model calls and no access to production accounts.
"""

import asyncio
import os
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D
from unittest.mock import AsyncMock, patch
from uuid import UUID

import httpx
from sqlalchemy import select, func
from sqlalchemy.engine import make_url
from ai_trading_agent.infrastructure.repo.database import (
    create_database_engine,
    create_session_factory,
)
from ai_trading_agent.infrastructure.repo.ai_simulation import SqlAlchemyAiSimulationRepository
from ai_trading_agent.infrastructure.repo.agent import AgentRepository
from ai_trading_agent.infrastructure.repo.models import AiSimulationTradeRecord
from ai_trading_agent.domain.aggregate.ai_simulation import AiSimulationPortfolio
from ai_trading_agent.domain.aggregate.market import Instrument, Quote
from ai_trading_agent.domain.aggregate.candidate import CandidateObservation, RankedCandidate
from ai_trading_agent.domain.enums.market import Market
from ai_trading_agent.domain.service.ai_simulation import AiSimulationCandidate
from ai_trading_agent.interfaces.api.app import create_app
from ai_trading_agent.interfaces.model.agent import AgentSettings
from ai_trading_agent.interfaces.facade import research_agents as agents


async def main():
    url = os.environ["DATABASE_URL"]
    if make_url(url).database != "trading_agent_research_test_20261110":
        raise RuntimeError("verification is restricted to the dedicated test database")
    engine = create_database_engine(url)
    sessions = create_session_factory(engine)
    repo, audits = SqlAlchemyAiSimulationRepository(sessions), AgentRepository(sessions)
    a, b = UUID(int=1001), UUID(int=1002)
    try:
        if sys.argv[-1] == "seed":
            for identifier in (a, b):
                await repo.save_portfolio(
                    AiSimulationPortfolio(identifier, "a_share", "CNY", D(100000), D(100000), 3)
                )
            print("legacy accounts seeded")
            return
        assert (await audits.config(a)) == (1, {})
        app = create_app()
        app.state.private_sessions = sessions
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://test"
        ) as client:
            route = f"/api/v1/ai-simulation/accounts/{a}/agent-settings"
            response = await client.get(route)
            assert (
                response.status_code == 200 and not response.json()["settings"]["position_enabled"]
            )
            config = AgentSettings(position_enabled=True)
            response = await client.put(route, json=config.model_dump(mode="json"))
            assert response.status_code == 200 and response.json()["generation"] == 2
            bad = {**config.model_dump(mode="json"), "research_weight": "0.8"}
            assert (await client.put(route, json=bad)).status_code == 422
            assert not AgentSettings.model_validate((await audits.config(b))[1]).position_enabled
        now = datetime.now(UTC)
        instrument = Instrument("600737.SH", Market.A_SHARE)
        candidate = RankedCandidate(
            CandidateObservation(
                instrument, "测试", D(10), D(1), D(10000), D(11), D(9), now, "fixture"
            ),
            D(80),
            ("基础分",),
        )
        report = {
            "score": "90",
            "recommendation": "buy",
            "price_min": "9",
            "price_max": "11",
            "thesis": {"text": "测试买入假设", "evidence_ids": ["0"]},
        }
        payload = {
            "generation": 2,
            "status": "completed",
            "started_at": now.isoformat(),
            "report": report,
            "rule_review": {"combined_score": "84"},
            "trace": [],
        }
        identifier = await audits.audit(a, instrument.symbol, "buy", payload)
        simulated = AiSimulationCandidate(
            instrument.symbol,
            "测试",
            D(84),
            D(10),
            2,
            0,
            ("a", "b"),
            (),
            (f"研究审计：{identifier}",),
        )
        quote = Quote(instrument, D(10), now, "fixture")
        with (
            patch(
                "ai_trading_agent.interfaces.facade.research_workspace.latest_quote",
                AsyncMock(return_value=quote),
            ),
            patch(
                "ai_trading_agent.interfaces.facade.ai_simulation._discipline_entry_blockers",
                AsyncMock(return_value=()),
            ),
        ):
            portfolio, position, blockers = await agents.execute_buy(
                app, candidate, await repo.get(a), (), simulated
            )
            assert position and not blockers and portfolio.cash_balance < 100000
            assert (await audits.history(a, position.position_id))[0]["report"]["thesis"][
                "text"
            ] == "测试买入假设"
            await repo.save_position(replace(position, status="closed"))
            before = (await repo.get(a)).cash_balance
            new_id = await audits.audit(a, instrument.symbol, "buy", payload)
            with patch.object(
                SqlAlchemyAiSimulationRepository,
                "save_trade",
                AsyncMock(side_effect=RuntimeError("injected failure")),
            ):
                try:
                    await agents.execute_buy(
                        app,
                        candidate,
                        await repo.get(a),
                        (),
                        replace(simulated, rationale=(f"研究审计：{new_id}",)),
                    )
                except RuntimeError:
                    pass
                else:
                    raise AssertionError("expected injected failure")
            assert (
                await repo.get(a)
            ).cash_balance == before and not await repo.list_open_positions(a)
            await audits.save_config(a, AgentSettings().model_dump(mode="json"))
            _, new_position, blockers = await agents.execute_buy(
                app,
                candidate,
                await repo.get(a),
                (),
                replace(simulated, rationale=(f"研究审计：{new_id}",)),
            )
            assert new_position is None and blockers
        position = await repo.save_position(
            replace(position, status="open", opened_at=now - timedelta(days=2))
        )
        mock_research = AsyncMock()
        with patch.object(agents, "run_research", mock_research):
            result = await agents.review_positions(app, repo, await repo.get(a), [position], ())
            assert result[1] == [position]
            mock_research.assert_not_called()
        # Disable after research completed but before the final transactional gate.
        generation = await audits.save_config(
            a, AgentSettings(position_enabled=True).model_dump(mode="json")
        )
        holding_report = {
            "recommendation": "exit",
            "thesis_state": "invalidated",
            "thesis": {"text": "测试假设失效"},
            "risks": [{"severity": "major", "text": "测试证据"}],
        }
        holding_payload = {**payload, "generation": generation, "report": holding_report}
        holding_id = await audits.audit(
            a, instrument.symbol, "position", holding_payload, position.position_id
        )

        async def disable_on_quote(*args):
            await audits.save_config(a, AgentSettings().model_dump(mode="json"))
            return quote

        with (
            patch.object(
                agents,
                "run_research",
                AsyncMock(
                    return_value=(holding_id, holding_payload, AgentSettings(position_enabled=True))
                ),
            ),
            patch(
                "ai_trading_agent.interfaces.facade.research_workspace.latest_quote",
                disable_on_quote,
            ),
            patch(
                "ai_trading_agent.interfaces.facade.disciplines.evaluate_active_disciplines",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await agents.review_positions(app, repo, await repo.get(a), [position], ())
            assert result[1] == [position]
            assert (await audits.history(a))[0]["rule_review"]["action"] == "hold"
        # The same validated advice may sell only with the current enabled generation.
        generation = await audits.save_config(
            a, AgentSettings(position_enabled=True).model_dump(mode="json")
        )
        holding_payload = {**holding_payload, "generation": generation}
        holding_id = await audits.audit(
            a, instrument.symbol, "position", holding_payload, position.position_id
        )
        with (
            patch.object(
                agents,
                "run_research",
                AsyncMock(
                    return_value=(holding_id, holding_payload, AgentSettings(position_enabled=True))
                ),
            ),
            patch(
                "ai_trading_agent.interfaces.facade.research_workspace.latest_quote",
                AsyncMock(return_value=quote),
            ),
            patch(
                "ai_trading_agent.interfaces.facade.disciplines.evaluate_active_disciplines",
                AsyncMock(return_value=[]),
            ),
        ):
            result = await agents.review_positions(app, repo, await repo.get(a), [position], ())
            assert result[1] == []
        async with sessions() as session:
            assert (
                await session.scalar(select(func.count()).select_from(AiSimulationTradeRecord)) == 2
            )
        assert (await repo.get(b)).cash_balance == D(100000)
        print(
            "PASS: legacy migration, isolated settings/API, weighted buy audit/thesis, atomic rollback, stale generation rejection, disabled no calls, disable-before-apply, enabled exit, isolated ledgers"
        )
    finally:
        await engine.dispose()


asyncio.run(main())
