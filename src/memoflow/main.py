"""应用入口：装配 FastAPI + NiceGUI，注册路由、异常处理与生命周期钩子。"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger
from nicegui import ui

from memoflow.config import get_settings
from memoflow.container import AppContainer, build_container
from memoflow.domain.shared.exceptions import (
    DomainError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    InvariantViolationError,
)
from memoflow.infrastructure.persistence.db import init_models
from memoflow.interfaces.api.router import api_router
from memoflow.interfaces.ui.app import register_ui


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    container = build_container(settings)
    await init_models(container.engine)
    app.state.container = container
    logger.info(f"{settings.app_name} 启动完成 (env={settings.env})")
    yield
    await container.engine.dispose()
    logger.info(f"{settings.app_name} 已关闭")


def create_app() -> FastAPI:
    app = FastAPI(
        title="MemoFlow API",
        description="本地部署的 AI 会议助手：转写 / 说话人识别 / 摘要 / 决策与行动项 / 知识库检索",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.include_router(api_router)

    @app.exception_handler(EntityNotFoundError)
    async def handle_not_found(request: Request, exc: EntityNotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(InvalidStateTransitionError)
    @app.exception_handler(InvariantViolationError)
    async def handle_bad_request(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(DomainError)
    async def handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()


def _register_ui_once() -> None:
    """NiceGUI 页面需要在 `ui.run_with` 之前注册，但页面内部会通过 `app.state.container` 懒获取依赖。"""

    class _LazyContainer:
        def __getattr__(self, name: str):  # noqa: ANN001, ANN204
            return getattr(app.state.container, name)

    register_ui(_LazyContainer())  # type: ignore[arg-type]


_register_ui_once()
ui.run_with(app, title="MemoFlow", storage_secret=get_settings().secret_key)


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("memoflow.main:app", host=settings.host, port=settings.port, reload=False)
