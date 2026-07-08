"""系统状态 API：运行时依赖与本地模型就绪情况。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from memoflow.application.system_service import SystemStatusService
from memoflow.interfaces.api.deps import get_system_service
from memoflow.interfaces.api.schemas import (
    DependencyStatusResponse,
    ModelStatusResponse,
    SystemStatusResponse,
)

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/status", response_model=SystemStatusResponse, summary="系统与模型状态")
async def get_system_status(
    service: SystemStatusService = Depends(get_system_service),
) -> SystemStatusResponse:
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
                role=m.role,
                model_id=m.model_id,
                loaded=m.loaded,
                ready=m.ready,
                status=m.status,
                hint=m.hint,
            )
            for m in status.models
        ],
    )
