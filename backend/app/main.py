"""FastAPI application factory for 9Router."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.openapi_ui import openapi_ui_kwargs
from app.middleware.api_prefix import StripApiPrefixMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.static_ui import mount_provider_icons, mount_static_ui
from app.routers import auth as auth_router
from app.routers import api_keys as api_keys_router
from app.routers import chat as chat_router
from app.routers import settings as settings_router
from app.routers import combos as combos_router
from app.routers import providers as providers_router
from app.routers import usage as usage_router
from app.routers import quota as quota_router
from app.routers import mitm as mitm_router
from app.routers import cli_tools as cli_tools_router
from app.routers import proxy_pools as proxy_pools_router
from app.routers import console as console_router
from app.routers import v1_proxy as v1_proxy_router
from app.routers import models as models_router
from app.routers import oauth as oauth_router
from app.routers import media_providers as media_providers_router
from app.routers import usage_stream as usage_stream_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup / shutdown hooks."""
    # Start background token refresh + connection health
    from app.services.connection_health import (
        connection_health_loop,
    )
    from app.services.token_refresh import token_refresh_loop

    refresh_task = asyncio.create_task(token_refresh_loop())
    health_task = asyncio.create_task(connection_health_loop())

    from app.database import async_session, install_quiet_pool_terminate
    from app.services.provider_aliases import refresh_from_db

    install_quiet_pool_terminate()

    try:
        async with async_session() as session:
            await refresh_from_db(session)
    except Exception:
        pass

    yield

    # Shutdown: cancel background tasks and dispose engine
    refresh_task.cancel()
    health_task.cancel()
    for task in (refresh_task, health_task):
        try:
            await task
        except asyncio.CancelledError:
            pass

    from app.database import engine

    await engine.dispose()


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    app = FastAPI(
        title="9Router",
        description="AI model proxy router with web dashboard",
        version="0.1.0",
        lifespan=lifespan,
        **openapi_ui_kwargs(settings.DEBUG),
    )

    # CORS — allow all origins during development
    origins = (
        ["*"] if settings.CORS_ORIGINS in ("*", "")
        else [o.strip() for o in settings.CORS_ORIGINS.split(",")]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(StripApiPrefixMiddleware)
    # Pure ASGI — do not use @app.middleware("http") / BaseHTTPMiddleware
    # (client disconnect cancels DB pool terminate → noisy traceback).
    app.add_middleware(RequestLoggingMiddleware)

    # Provider icons must register before /providers/{conn_id} API routes.
    mount_provider_icons(app)

    # Include routers
    app.include_router(auth_router.router)
    app.include_router(api_keys_router.router)
    app.include_router(chat_router.router)
    app.include_router(settings_router.router)
    app.include_router(providers_router.router)
    app.include_router(combos_router.router)
    app.include_router(usage_router.router)
    # Exact /usage/ws must register before quota's /usage/{connection_id}
    # or a param route can shadow related /usage/* paths.
    app.include_router(usage_stream_router.router)
    app.include_router(quota_router.router)
    app.include_router(mitm_router.router)
    app.include_router(cli_tools_router.router)
    app.include_router(proxy_pools_router.router)
    app.include_router(console_router.router)
    app.include_router(v1_proxy_router.router)
    app.include_router(models_router.router)
    app.include_router(oauth_router.router)
    app.include_router(media_providers_router.router)

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    mount_static_ui(app)

    return app


app = create_app()
