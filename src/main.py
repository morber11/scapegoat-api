import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import chat, health
from api.middleware import RateLimitMiddleware
from core.config import get_settings

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and fill in the value."
        )
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Scapegoat API",
        description="because we all need someone to blame",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
    )

    origins = settings.allowed_origins
    if not origins and not settings.is_production:
        origins = ["*"]

    logging.info("CORS allowed origins: %s", origins)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_private_network=True,
    )

    app.add_middleware(RateLimitMiddleware)

    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(health.router)

    return app


app = create_app()
