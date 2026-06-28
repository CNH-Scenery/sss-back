from fastapi import APIRouter

from app.api import (
    auth,
    backtests,
    codegen,
    feedbacks,
    responses,
    scenarios,
    signals,
    strategies,
    twin_contexts,
    watchlists,
)

api_router = APIRouter(prefix="/api")
api_router.include_router(auth.router)
api_router.include_router(scenarios.router)
api_router.include_router(responses.router)
api_router.include_router(twin_contexts.router)
api_router.include_router(strategies.router)
api_router.include_router(backtests.router)
api_router.include_router(feedbacks.router)
api_router.include_router(watchlists.router)
api_router.include_router(signals.router)
api_router.include_router(codegen.router)
