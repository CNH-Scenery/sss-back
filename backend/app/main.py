import os
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.requests import Request

from app.api import api_router
from app.db import initialize_database

DEFAULT_CORS_ALLOWED_ORIGINS = ",".join(
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    initialize_database()
    yield


app = FastAPI(title="CoinTwin API", lifespan=lifespan)
allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ALLOWED_ORIGINS).split(",")
    if origin.strip()
]
# Allow any localhost / 127.0.0.1 port in dev so the frontend port can change
# without editing CORS config. Override with CORS_ALLOWED_ORIGIN_REGEX in prod.
allowed_origin_regex = os.getenv(
    "CORS_ALLOWED_ORIGIN_REGEX",
    r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=allowed_origin_regex,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def normalize_duplicate_slashes(request: Request, call_next):
    normalized_path = re.sub(r"/{2,}", "/", request.scope["path"])
    if normalized_path != request.scope["path"]:
        request.scope["path"] = normalized_path
    return await call_next(request)


app.include_router(api_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "CoinTwin API",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "scenarios": "/api/scenarios",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
