"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from devflow_api.adapters.registry import registry
from devflow_api.middleware.error_handler import add_error_handlers
from devflow_api.middleware.logging import RequestLoggingMiddleware
from devflow_api.routers.approvals import router as approvals_router
from devflow_api.routers.health import router as health_router
from devflow_api.routers.integrations import router as integrations_router
from devflow_api.routers.learning import router as learning_router
from devflow_api.routers.projects import router as projects_router
from devflow_api.routers.workflows import router as workflows_router
from devflow_core.config import Settings, get_settings
from devflow_core.logging import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings if settings is not None else get_settings()
    configure_logging(config.LOG_LEVEL, config.LOG_FORMAT)
    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION,
        description="Local-first AI development and learning orchestrator.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.ALLOWED_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)
    add_error_handlers(app)
    app.state.adapter_registry = registry
    app.include_router(health_router)
    app.include_router(projects_router)
    app.include_router(learning_router)
    app.include_router(integrations_router)
    app.include_router(workflows_router)
    app.include_router(approvals_router)
    return app


app = create_app()
