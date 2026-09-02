"""Versioned HTTP API composition root.

Keep framework objects here: DDD application and domain modules do not import FastAPI.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from ai_trading_agent.application.factors import GetFactorHandler, ListFactorsHandler
from ai_trading_agent.domain.factors import FactorMetadata


class FactorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    identifier: str
    name: str
    theme: str
    formula: str
    columns_required: tuple[str, ...]
    warmup_bars: int
    horizon_days: int
    description: str
    version: str

    @classmethod
    def from_domain(cls, factor: FactorMetadata) -> FactorResponse:
        return cls.model_validate(factor)


def create_app(*, cors_origins: tuple[str, ...] = ()) -> FastAPI:
    """Build an API safe for private-server deployment.

    No cross-origin browser access is enabled until explicit frontend origins are supplied.
    """
    app = FastAPI(title="My AI Trading Agent API", version="0.1.0")
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )

    list_factors = ListFactorsHandler()
    get_factor = GetFactorHandler()

    @app.get("/healthz", tags=["system"])
    def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/v1/factors", response_model=list[FactorResponse], tags=["factors"])
    def list_factor_library() -> list[FactorResponse]:
        return [FactorResponse.from_domain(item) for item in list_factors.handle()]

    @app.get("/api/v1/factors/{identifier}", response_model=FactorResponse, tags=["factors"])
    def get_factor_definition(identifier: str) -> FactorResponse:
        try:
            return FactorResponse.from_domain(get_factor.handle(identifier))
        except KeyError as error:
            raise HTTPException(status_code=404, detail="factor not found") from error

    return app


app = create_app()
