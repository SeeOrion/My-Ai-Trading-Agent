"""Use cases for discovering and validating the factor library."""

from __future__ import annotations

from ai_trading_agent.domain.ability.factors import (
    DEFAULT_FACTOR_REGISTRY,
    FactorMetadata,
    FactorRegistry,
)


class ListFactorsHandler:
    def __init__(self, registry: FactorRegistry = DEFAULT_FACTOR_REGISTRY) -> None:
        self._registry = registry

    def handle(self) -> tuple[FactorMetadata, ...]:
        return self._registry.list()


class GetFactorHandler:
    def __init__(self, registry: FactorRegistry = DEFAULT_FACTOR_REGISTRY) -> None:
        self._registry = registry

    def handle(self, identifier: str) -> FactorMetadata:
        return self._registry.get(identifier)
