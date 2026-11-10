"""Account-scoped agent settings; defaults are experimental, not return probabilities."""

from decimal import Decimal
from pydantic import BaseModel, Field, model_validator


class AgentSettings(BaseModel):
    model_config = {"extra": "forbid"}
    position_enabled: bool = False
    workflow_weight: Decimal = Field(default=Decimal("0.6"), ge=0, le=1)
    research_weight: Decimal = Field(default=Decimal("0.4"), ge=0, le=1)
    entry_threshold: Decimal = Field(default=Decimal("70"), ge=0, le=100)
    holding_days: int = Field(default=20, ge=1, le=3650)
    validity_seconds: int = Field(default=300, ge=30, le=1800)
    max_price_move: Decimal = Field(default=Decimal("0.02"), ge=0, le=Decimal("0.1"))
    rounds: int = Field(default=5, ge=2, le=10)
    tokens: int = Field(default=16000, ge=1000, le=20000)
    timeout_seconds: int = Field(default=45, ge=5, le=90)
    repeated_queries: int = Field(default=1, ge=1, le=2)

    @model_validator(mode="after")
    def weights(self):
        if self.workflow_weight + self.research_weight != 1:
            raise ValueError("两项权重之和必须为 1")
        return self
