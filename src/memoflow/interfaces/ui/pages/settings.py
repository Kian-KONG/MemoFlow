"""设置页面：模型下载与管理（与会议处理流水线解耦）。"""
from __future__ import annotations

import asyncio

from nicegui import ui

from memoflow.application.system_service import ModelKey
from memoflow.container import AppContainer

_POLL_INTERVAL_SECONDS = 1.0


def register_settings_page(container: AppContainer) -> None:
    @ui.refreshable
    def models_panel() -> None:
        model_service = container.system_service
        status = model_service.get_status()

        with ui.row().classes("w-full items-center justify-between mb-2"):
            ui.label(f"运行环境: {status.platform}").classes("text-xs text-gray-500")
            if status.all_ready:
                ui.badge("全部就绪", color="green")
            else:
                ui.badge("尚未就绪", color="orange")

        for dep in status.dependencies:
            color = "text-green-600" if dep.available else "text-red-600"
            with ui.row().classes("w-full items-center gap-2 mb-2"):
                ui.icon("check_circle" if dep.available else "error").classes(color)
                ui.label(f"{dep.name}: {dep.hint}").classes(f"text-sm {color}")

        ui.separator().classes("my-3")

        for model in status.models:
            if model.loaded:
                badge_color, badge_text = "green", "已就绪"
            elif model.downloading:
                badge_color, badge_text = "blue", "下载中"
            elif model.ready:
                badge_color, badge_text = "grey", "未下载"
            else:
                badge_color, badge_text = "orange", "不可用"

            with ui.card().classes("w-full mb-2"):
                with ui.row().classes("w-full items-start justify-between gap-2"):
                    with ui.column().classes("gap-0 flex-grow"):
                        ui.label(model.role).classes("font-medium")
                        ui.label(model.model_id).classes("text-xs text-gray-400")
                        ui.label(f"来源: {model.source}").classes("text-xs text-gray-400")
                        ui.label(model.hint).classes("text-xs text-gray-500 mt-1")
                    ui.badge(badge_text, color=badge_color)

                if model.downloading or model.progress_percent > 0:
                    progress_value = max(0.0, min(1.0, model.progress_percent / 100.0))
                    ui.linear_progress(value=progress_value).classes("w-full mt-2")
                    ui.label(
                        model.progress_message or f"进度: {model.progress_percent:.0f}%"
                    ).classes("text-xs text-blue-600 mt-1")
                    if model.recent_logs:
                        with ui.column().classes("gap-0 mt-1"):
                            for line in model.recent_logs[-4:]:
                                ui.label(f"· {line}").classes("text-xs text-gray-500")

                if model.ready and not model.loaded:
                    if model.downloading:
                        with ui.row().classes("items-center gap-2 mt-2"):
                            ui.spinner(size="sm")
                            ui.label("下载中，请保持页面打开…").classes("text-sm text-blue-600")
                    else:
                        ui.button(
                            "下载模型",
                            on_click=lambda k=model.key: _start_download(container, k, models_panel),
                        ).props("outline color=primary").classes("mt-2")

        if not status.all_ready:
            ui.button(
                "下载全部可用模型",
                on_click=lambda: _start_download_all(container, models_panel),
            ).props("color=primary").classes("mt-2")

    @ui.page("/settings")
    async def settings_page() -> None:
        ui.page_title("MemoFlow - 设置")

        with ui.header().classes("items-center"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat color=white")
            ui.label("模型设置").classes("text-xl font-bold")

        with ui.column().classes("w-full max-w-3xl mx-auto p-4 gap-4"):
            with ui.card().classes("w-full"):
                ui.label("本地 AI 模型").classes("text-lg font-semibold")
                ui.label(
                    "请在此预先下载模型。会议处理不会自动下载模型，未下载时上传后将处理失败。"
                ).classes("text-sm text-gray-500 mb-3")
                models_panel()

            with ui.card().classes("w-full"):
                ui.label("配置说明").classes("text-lg font-semibold")
                ui.markdown(
                    """
- **ffmpeg**: 终端运行 `brew install ffmpeg`（处理 m4a/mp3 必需）
- **说话人识别**: 在 `.env` 中设置 `MEMOFLOW_HF_TOKEN`（只读 Token 即可），并在 HuggingFace 接受 pyannote 模型协议
- **摘要 LLM**: 需要 Apple Silicon Mac（MLX）
- 模型下载可能耗时数分钟，下载期间请保持本页面打开；若连接中断可刷新后重试
                    """
                )

        ui.timer(_POLL_INTERVAL_SECONDS, models_panel.refresh)


def _start_download(container: AppContainer, key: ModelKey, panel) -> None:  # noqa: ANN001
    ui.notify(f"开始下载 {key.value} 模型，请稍候…", type="info")

    async def _run() -> None:
        try:
            await container.system_service.download_model(key)
            ui.notify(f"{key.value} 模型下载完成", type="positive")
        except Exception as exc:  # noqa: BLE001
            ui.notify(f"下载失败: {exc}", type="negative")
        finally:
            panel.refresh()

    asyncio.create_task(_run())
    panel.refresh()


def _start_download_all(container: AppContainer, panel) -> None:  # noqa: ANN001
    ui.notify("开始下载全部可用模型，请稍候…", type="info")

    async def _run() -> None:
        try:
            await container.system_service.download_all()
            ui.notify("全部可用模型已下载完成", type="positive")
        except Exception as exc:  # noqa: BLE001
            ui.notify(f"下载失败: {exc}", type="negative")
        finally:
            panel.refresh()

    asyncio.create_task(_run())
    panel.refresh()
