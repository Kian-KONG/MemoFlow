"""仪表盘页面：上传会议录音 + 会议列表（自动轮询刷新处理状态）。"""
from __future__ import annotations

from nicegui import events, ui

from memoflow.container import AppContainer
from memoflow.domain.meeting.services import AudioValidationPolicy

_STATUS_LABELS = {
    "uploaded": "排队等待处理",
    "transcribing": "转写中",
    "diarizing": "说话人识别中",
    "summarizing": "生成摘要中",
    "completed": "已完成",
    "failed": "处理失败",
}

_STATUS_COLORS = {
    "uploaded": "text-gray-500",
    "transcribing": "text-blue-600",
    "diarizing": "text-blue-600",
    "summarizing": "text-blue-600",
    "completed": "text-green-600",
    "failed": "text-red-600",
}

_POLL_INTERVAL_SECONDS = 2.0


def register_dashboard_page(container: AppContainer) -> None:
    @ui.refreshable
    async def meetings_list() -> None:
        dtos = await container.meeting_service.list_meetings(limit=100)
        if not dtos:
            ui.label("暂无会议，请先上传录音。").classes("text-gray-500")
            return
        for dto in dtos:
            with ui.row().classes(
                "w-full items-center justify-between border rounded p-2 cursor-pointer hover:bg-gray-50"
            ).on("click", lambda _, mid=dto.id: ui.navigate.to(f"/meetings/{mid}")):
                with ui.column().classes("gap-0 flex-grow"):
                    ui.label(dto.title).classes("font-medium")
                    if dto.status.value == "failed" and dto.error_message:
                        ui.label(dto.error_message).classes("text-xs text-red-500 truncate max-w-md")
                with ui.row().classes("items-center gap-2 shrink-0"):
                    if dto.status.value not in ("completed", "failed"):
                        ui.spinner(size="1em")
                    ui.label(_STATUS_LABELS.get(dto.status.value, dto.status.value)).classes(
                        f"text-sm {_STATUS_COLORS.get(dto.status.value, 'text-gray-500')}"
                    )

    @ui.refreshable
    def readiness_banner() -> None:
        status = container.system_service.get_status()
        if status.all_ready:
            return
        missing = container.system_service.get_missing_for_processing()
        with ui.row().classes("w-full items-center justify-between p-3 bg-orange-50 rounded"):
            if missing:
                ui.label(f"模型未就绪：{'、'.join(missing)}。请先在设置页下载模型。").classes(
                    "text-sm text-orange-700"
                )
            else:
                ui.label("部分系统依赖未就绪，请查看设置页。").classes("text-sm text-orange-700")
            ui.button("前往设置", on_click=lambda: ui.navigate.to("/settings")).props(
                "outline color=orange"
            )

    @ui.page("/")
    async def dashboard() -> None:
        ui.page_title("MemoFlow - 会议列表")

        with ui.header().classes("items-center justify-between"):
            ui.label("MemoFlow 本地 AI 会议助手").classes("text-xl font-bold")
            ui.button(icon="settings", on_click=lambda: ui.navigate.to("/settings")).props(
                "flat color=white"
            ).tooltip("模型设置")

        with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-4"):
            readiness_banner()

            with ui.card().classes("w-full"):
                ui.label("上传会议录音").classes("text-lg font-semibold")
                ui.label("上传前请确保已在设置页下载全部模型。").classes("text-xs text-gray-500 mb-2")
                title_input = ui.input("会议标题（可选）").classes("w-full")
                upload_status = ui.label("").classes("text-sm text-gray-500")

                async def handle_upload(e: events.UploadEventArguments) -> None:
                    content = e.content.read()
                    upload_status.set_text("上传中，请稍候...")
                    try:
                        missing = container.system_service.get_missing_for_processing()
                        if missing:
                            upload_status.set_text(
                                f"无法上传：{'、'.join(missing)} 尚未下载，请前往设置页下载。"
                            )
                            return
                        normalized_type = AudioValidationPolicy.normalize_content_type(
                            e.type or "application/octet-stream", e.name
                        )
                        dto = await container.meeting_service.upload_meeting(
                            title=title_input.value,
                            filename=e.name,
                            content_type=normalized_type,
                            content=content,
                        )
                        upload_status.set_text(f"上传成功：{dto.title}，正在跳转到处理进度页面...")
                        title_input.set_value("")
                        await meetings_list.refresh()
                        ui.navigate.to(f"/meetings/{dto.id}")
                    except Exception as exc:  # noqa: BLE001 - 展示给用户的顶层错误兜底
                        upload_status.set_text(f"上传失败：{exc}")

                ui.upload(on_upload=handle_upload, auto_upload=True).props(
                    "accept=.mp3,.wav,.m4a,.flac,.ogg"
                ).classes("w-full")

            with ui.card().classes("w-full"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label("会议列表").classes("text-lg font-semibold")
                    ui.label("每 2 秒自动刷新处理状态").classes("text-xs text-gray-400")
                await meetings_list()

        async def poll() -> None:
            await meetings_list.refresh()
            readiness_banner.refresh()

        ui.timer(_POLL_INTERVAL_SECONDS, poll)
