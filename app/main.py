from fastapi import FastAPI

from app.api.routes import health as health_routes
from app.api.routes import inbound as inbound_routes
from app.core.config import settings


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(title=settings.app_name, version=settings.version)

    app.include_router(health_routes.router, prefix="/health", tags=["health"])
    app.include_router(inbound_routes.router, prefix="/v1/chatbot", tags=["chatbot"])

    return app


app = create_app()

