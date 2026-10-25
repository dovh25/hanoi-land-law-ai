"""Lightweight application factory. No model or external service startup."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from backend.api.v1.auth import router as auth_router
from backend.api.v1.chat import router as chat_router
from backend.api.v1.demo import router as demo_router
from backend.api.v1.lookup import router as lookup_router
from backend.api.v1.sessions import router as sessions_router
from backend.core.config import Config, get_settings
from backend.core.database import create_database
from backend.core.logging import setup_logging
from backend.services.chat_service import ChatService
from backend.services.lookup_service import LawDocumentService
from backend.services.llm import LLMUnavailable
from backend.services.pipelines.mvp_rag_pipeline import MvpRagPipeline
from backend.services.rate_limit import DemoRateLimiter

logger = logging.getLogger(__name__)


def create_app(
    settings: Config | None = None, *, pipeline=None, lookup_service=None, mvp_pipeline=None
):
    # Settings validate at app creation, without model initialization.
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app):
        setup_logging(settings.LOG_LEVEL)
        engine, factory = create_database(settings.DATABASE_URL)
        app.state.session_factory = factory
        app.state.database_ready = True
        if app.state.mvp_pipeline is not None:
            try:
                app.state.mvp_pipeline.startup()
            except FileNotFoundError:
                logger.error("MVP demo corpus artifact is missing; demo endpoints will return 503")
        try:
            yield
        finally:
            app.state.database_ready = False
            engine.dispose()

    app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)
    app.state.settings = settings
    app.state.database_ready = False
    app.state.chat_service = ChatService(settings, pipeline=pipeline)
    app.state.lookup_service = lookup_service or LawDocumentService(str(settings.DOCS_ROOT))
    app.state.mvp_pipeline = mvp_pipeline
    if app.state.mvp_pipeline is None and settings.MVP_ENABLED:
        app.state.mvp_pipeline = MvpRagPipeline(settings.MVP_DEMO_CORPUS_PATH)
    app.state.demo_limiter = DemoRateLimiter(
        settings.MVP_RATE_LIMIT_PER_MINUTE, settings.MVP_RATE_LIMIT_PER_DAY
    )
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.CORS_ORIGINS,
        allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(LLMUnavailable)
    async def llm_unavailable(request: Request, exc: LLMUnavailable):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        return JSONResponse(status_code=500, content={"detail": "Database operation failed"})

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        return JSONResponse(status_code=500, content={"detail": "Request failed"})

    @app.get("/healthz")
    async def liveness():
        return {"status": "ok"}

    @app.get("/readyz")
    async def readiness():
        chat = app.state.chat_service
        ready = app.state.database_ready and chat.is_ready
        demo = app.state.mvp_pipeline
        return JSONResponse(status_code=200 if ready else 503, content={
            "status": "ready" if ready else "not_ready",
            "database": app.state.database_ready,
            "rag": chat.is_ready, "live_llm_enabled": settings.ENABLE_LIVE_LLM,
            "demo_rag": bool(demo and demo.is_initialized),
        })

    @app.get("/demo/readyz")
    async def demo_readiness():
        demo = app.state.mvp_pipeline
        ready = app.state.database_ready and bool(demo and demo.is_initialized)
        return JSONResponse(status_code=200 if ready else 503, content={
            "status": "ready" if ready else "not_ready",
            "demo_rag": bool(demo and demo.is_initialized),
            "live_llm_enabled": settings.ENABLE_LIVE_LLM,
        })

    for router in (auth_router, sessions_router, chat_router, lookup_router, demo_router):
        app.include_router(router, prefix=settings.API_STR)
    return app


app = create_app()


def main():
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
