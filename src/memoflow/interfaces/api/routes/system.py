"""系统状态与模型下载 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from memoflow.application.system_service import ModelKey, ModelService
from memoflow.interfaces.api.deps import get_system_service
from memoflow.interfaces.api.schemas import (
    DependencyStatusResponse,
    ModelDownloadResponse,
    ModelStatusResponse,
    SystemStatusResponse,
)

router = APIRouter(prefix="/api/system", tags=["system"])


def _to_response(service: ModelService) -> SystemStatusResponse:
    status = service.get_status()
    return SystemStatusResponse(
        platform=status.platform,
        all_ready=status.all_ready,
        dependencies=[
            DependencyStatusResponse(name=d.name, available=d.available, hint=d.hint)
            for d in status.dependencies
        ],
        models=[
            ModelStatusResponse(
                key=m.key.value,
                role=m.role,
                model_id=m.model_id,
                loaded=m.loaded,
                ready=m.ready,
                downloading=m.downloading,
                source=m.source,
                progress_percent=m.progress_percent,
                progress_message=m.progress_message,
                recent_logs=m.recent_logs,
                status=m.status,
                hint=m.hint,
            )
            for m in status.models
        ],
    )


@router.get("/status", response_model=SystemStatusResponse, summary="系统与模型状态")
async def get_system_status(
    service: ModelService = Depends(get_system_service),
) -> SystemStatusResponse:
    return _to_response(service)


@router.post(
    "/models/{model_key}/download",
    response_model=ModelDownloadResponse,
    summary="下载并加载指定模型",
)
async def download_model(
    model_key: ModelKey,
    service: ModelService = Depends(get_system_service),
) -> ModelDownloadResponse:
    await service.download_model(model_key)
    return ModelDownloadResponse(key=model_key.value, message="模型下载完成")


@router.post("/models/download-all", response_model=SystemStatusResponse, summary="下载全部可用模型")
async def download_all_models(
    service: ModelService = Depends(get_system_service),
) -> SystemStatusResponse:
    await service.download_all()
    return _to_response(service)
