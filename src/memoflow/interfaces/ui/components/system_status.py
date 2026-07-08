"""系统状态面板：展示运行时依赖与本地 AI 模型就绪情况。"""
from __future__ import annotations

from nicegui import ui

from memoflow.application.system_service import SystemStatusService


def render_system_status_panel(service: SystemStatusService) -> None:
    """渲染系统依赖与模型状态卡片（可在仪表盘等页面复用）。"""

    status = service.get_status()

    with ui.row().classes("w-full items-center justify-between"):
        ui.label("系统与模型状态").classes("text-lg font-semibold")
        ui.label(status.platform).classes("text-xs text-gray-400")

    for dep in status.dependencies:
        color = "text-green-600" if dep.available else "text-red-600"
        icon = "check_circle" if dep.available else "error"
        with ui.row().classes("w-full items-start gap-2 mt-2"):
            ui.icon(icon).classes(f"{color} shrink-0 mt-0.5")
            with ui.column().classes("gap-0"):
                ui.label(f"依赖: {dep.name}").classes("text-sm font-medium")
                ui.label(dep.hint).classes(f"text-xs {color}")

    ui.separator().classes("my-3")

    for model in status.models:
        if model.loaded:
            color, icon = "text-green-600", "memory"
        elif model.ready:
            color, icon = "text-blue-600", "cloud_download"
        else:
            color, icon = "text-orange-600", "warning"

        with ui.row().classes("w-full items-start gap-2 mt-2"):
            ui.icon(icon).classes(f"{color} shrink-0 mt-0.5")
            with ui.column().classes("gap-0 flex-grow"):
                ui.label(model.role).classes("text-sm font-medium")
                ui.label(model.model_id).classes("text-xs text-gray-400")
                ui.label(f"{model.status} — {model.hint}").classes(f"text-xs {color}")

    if not status.all_ready:
        ui.label(
            "部分依赖或模型尚未就绪，上传后处理可能失败。请根据上方提示完成配置后重试。"
        ).classes("text-sm text-orange-600 mt-3 p-2 bg-orange-50 rounded")
