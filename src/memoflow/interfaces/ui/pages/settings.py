"""设置页面：VibeVoice 本地模型与远程 API 密钥状态。"""
from __future__ import annotations

from nicegui import ui

from memoflow.container import AppContainer

_POLL_INTERVAL_SECONDS = 2.0
_DOWNLOAD_SCRIPT = "./scripts/download_vibevoice_asr.sh"


def register_settings_page(container: AppContainer) -> None:
    @ui.refreshable
    def status_panel() -> None:
        model_service = container.system_service
        status = model_service.get_status()

        with ui.row().classes("w-full items-center justify-between mb-2"):
            ui.label(f"运行环境: {status.platform}").classes("text-xs text-gray-500")
            if status.all_ready:
                ui.badge("全部就绪", color="green")
            else:
                ui.badge("尚未就绪", color="orange")

        ui.label("系统依赖").classes("text-sm font-medium mt-2 mb-1")
        for dep in status.dependencies:
            color = "text-green-600" if dep.available else "text-red-600"
            with ui.row().classes("w-full items-center gap-2 mb-1"):
                ui.icon("check_circle" if dep.available else "error").classes(color)
                ui.label(f"{dep.name}: {dep.hint}").classes(f"text-sm {color}")

        ui.separator().classes("my-3")
        ui.label("本地模型").classes("text-sm font-medium mb-1")

        for model in status.models:
            if model.loaded:
                badge_color, badge_text = "green", "已就绪"
            elif model.ready:
                badge_color, badge_text = "grey", "未加载"
            else:
                badge_color, badge_text = "orange", "未找到"

            with ui.card().classes("w-full mb-2"):
                with ui.row().classes("w-full items-start justify-between gap-2"):
                    with ui.column().classes("gap-0 flex-grow"):
                        ui.label(model.role).classes("font-medium")
                        ui.label(model.model_id).classes("text-xs text-gray-400")
                        ui.label(f"来源: {model.source}").classes("text-xs text-gray-400")
                        ui.label(model.hint).classes("text-xs text-gray-500 mt-1")
                    ui.badge(badge_text, color=badge_color)

                if not model.ready:
                    ui.markdown(
                        f"""
**下载说明：** 在项目根目录运行：

```bash
chmod +x {_DOWNLOAD_SCRIPT}
{_DOWNLOAD_SCRIPT}
```
                        """
                    ).classes("text-xs mt-2")

    @ui.page("/settings")
    async def settings_page() -> None:
        ui.page_title("MemoFlow - 设置")

        with ui.header().classes("items-center"):
            ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat color=white")
            ui.label("系统设置").classes("text-xl font-bold")

        with ui.column().classes("w-full max-w-3xl mx-auto p-4 gap-4"):
            with ui.card().classes("w-full"):
                ui.label("AI 栈状态").classes("text-lg font-semibold")
                ui.label(
                    "MemoFlow 使用 VibeVoice 本地 ASR + DeepSeek / OpenAI / Qwen3 远程 API。"
                    " 请确保模型权重与 API 密钥均已就绪后再处理会议。"
                ).classes("text-sm text-gray-500 mb-3")
                status_panel()

            with ui.card().classes("w-full"):
                ui.label("配置说明").classes("text-lg font-semibold")
                ui.markdown(
                    f"""
- **ffmpeg**: 终端运行 `brew install ffmpeg`（处理 m4a/mp3 必需）
- **VibeVoice ASR**: 运行 `{_DOWNLOAD_SCRIPT}` 下载本地权重到 `./models/VibeVoice-ASR`
- **DeepSeek LLM**: 在 `.env` 中设置 `MEMOFLOW_DEEPSEEK_API_KEY`
- **OpenAI Embedding**: 在 `.env` 中设置 `MEMOFLOW_OPENAI_API_KEY`
- **Qwen3 Reranker**: 在 `.env` 中设置 `MEMOFLOW_RERANK_API_KEY`（DashScope 兼容 API）
                    """
                )

        ui.timer(_POLL_INTERVAL_SECONDS, status_panel.refresh)
