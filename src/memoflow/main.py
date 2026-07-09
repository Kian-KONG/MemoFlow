"""应用入口：装配 FastAPI，注册路由、CORS、静态前端与生命周期钩子。"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from memoflow.config import get_settings
from memoflow.container import build_container
from memoflow.domain.shared.exceptions import (
    DomainError,
    EntityNotFoundError,
    InvalidStateTransitionError,
    InvariantViolationError,
)
from memoflow.infrastructure.persistence.db import init_models
from memoflow.interfaces.api.router import api_router

_FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


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

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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

    _mount_frontend(app)

    return app


def _mount_frontend(app: FastAPI) -> None:
    """生产模式：若 frontend/dist 存在，托管静态资源并以 SPA fallback 回 index.html。"""
    if not _FRONTEND_DIST.is_dir():
        logger.warning(
            f"未找到前端构建产物 {_FRONTEND_DIST}；"
            "开发时请单独运行 frontend (npm run dev)，生产请先 npm run build。"
        )
        return

    assets_dir = _FRONTEND_DIST / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    index_html = _FRONTEND_DIST / "index.html"

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str) -> FileResponse:
        # FastAPI 已先匹配 /api、/health、/docs 等；此处仅作兜底
        if full_path.startswith(("api/", "health", "docs", "openapi.json", "redoc")):
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        candidate = (_FRONTEND_DIST / full_path).resolve()
        if full_path and candidate.is_file() and _FRONTEND_DIST in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(index_html)


app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("memoflow.main:app", host=settings.host, port=settings.port, reload=False)
