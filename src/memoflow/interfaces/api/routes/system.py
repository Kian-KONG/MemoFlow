"""系统状态与模型下载 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from memoflow.application.system_service import ModelKey, ModelNotReadyError, ModelService
from memoflow.container import AppContainer
from memoflow.interfaces.api.deps import get_container, get_system_service
from memoflow.interfaces.api.schemas import (
    AsrOptionStatusResponse,
    DependencyStatusResponse,
    ModelDownloadResponse,
    ModelStatusResponse,
    SelectAsrBackendRequest,
    SelectAsrBackendResponse,
    SystemStatusResponse,
)

router = APIRouter(prefix="/api/system", tags=["system"])

_DOWNLOAD_MESSAGE = "模型下载已改为脚本方式，请运行: ./scripts/download_asr_model.sh"


def _to_response(service: ModelService) -> SystemStatusResponse:
    status = service.get_status()
    return SystemStatusResponse(
        platform=status.platform,
        all_ready=status.all_ready,
        configured_asr_backend=status.configured_asr_backend,
        active_asr_backend=status.active_asr_backend,
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
        asr_options=[
            AsrOptionStatusResponse(
                backend=o.backend,
                label=o.label,
                model_id=o.model_id,
                model_path=o.model_path,
                ready=o.ready,
                source=o.source,
                configured=o.configured,
                active=o.active,
                download_command=o.download_command,
                hint=o.hint,
            )
            for o in status.asr_options
        ],
    )


@router.get("/status", response_model=SystemStatusResponse, summary="系统与模型状态")
async def get_system_status(
    service: ModelService = Depends(get_system_service),
) -> SystemStatusResponse:
    return _to_response(service)


@router.put("/asr-backend", response_model=SelectAsrBackendResponse, summary="选择 ASR 模型后端")
async def select_asr_backend(
    body: SelectAsrBackendRequest,
    service: ModelService = Depends(get_system_service),
    container: AppContainer = Depends(get_container),
) -> SelectAsrBackendResponse:
    backend = body.backend.strip().lower()
    try:
        active = container.switch_asr_backend(backend)
    except ModelNotReadyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    status = _to_response(service)
    spec = next((o for o in status.asr_options if o.backend == backend), None)
    label = spec.label if spec else backend
    return SelectAsrBackendResponse(
        backend=backend,
        active_asr_backend=active,
        message=f"已切换至 {label}",
        status=status,
    )


@router.post(
    "/models/{model_key}/download",
    response_model=ModelDownloadResponse,
    summary="（已弃用）下载并加载指定模型",
    deprecated=True,
)
async def download_model(
    model_key: ModelKey,  # noqa: ARG001
    service: ModelService = Depends(get_system_service),  # noqa: ARG001
) -> ModelDownloadResponse:
    raise HTTPException(status_code=400, detail=_DOWNLOAD_MESSAGE)


@router.post(
    "/models/download-all",
    response_model=SystemStatusResponse,
    summary="（已弃用）下载全部可用模型",
    deprecated=True,
)
async def download_all_models(
    service: ModelService = Depends(get_system_service),  # noqa: ARG001
) -> SystemStatusResponse:
    raise HTTPException(status_code=400, detail=_DOWNLOAD_MESSAGE)
