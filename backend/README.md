# Backend

The Python DDD source remains in `../src/ai_trading_agent`; this folder owns container delivery only.

The API is served at `/api/v1`. Database migrations are in `../migrations` and must receive a
PostgreSQL URL at deployment time. No credentials are committed in this repository.
