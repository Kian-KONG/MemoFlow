"""仪表盘页面：上传会议录音 + 会议列表（自动轮询刷新处理状态）。"""
from __future__ import annotations

from nicegui import events, ui

from memoflow.container import AppContainer

_STATUS_LABELS = {
    "uploaded": "待处理",
    "transcribing": "转写中",
    "diarizing": "说话人识别中",
    "summarizing": "生成摘要中",
    "completed": "已完成",
    "failed": "失败",
}

_STATUS_COLORS = {
    "uploaded": "text-gray-500",
    "transcribing": "text-blue-600",
    "diarizing": "text-blue-600",
    "summarizing": "text-blue-600",
    "completed": "text-green-600",
    "failed": "text-red-600",
}

# 轮询间隔（秒）：处理是后台异步进行的，列表需要定期刷新才能看到状态变化
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
                ui.label(dto.title).classes("font-medium")
                with ui.row().classes("items-center gap-2"):
                    if dto.status.value not in ("completed", "failed"):
                        ui.spinner(size="1em")
                    ui.label(_STATUS_LABELS.get(dto.status.value, dto.status.value)).classes(
                        f"text-sm {_STATUS_COLORS.get(dto.status.value, 'text-gray-500')}"
                    )

    @ui.page("/")
    async def dashboard() -> None:
        ui.page_title("MemoFlow - 会议列表")

        with ui.header().classes("items-center justify-between"):
            ui.label("MemoFlow 本地 AI 会议助手").classes("text-xl font-bold")

        with ui.column().classes("w-full max-w-4xl mx-auto p-4 gap-4"):
            with ui.card().classes("w-full"):
                ui.label("上传会议录音").classes("text-lg font-semibold")
                title_input = ui.input("会议标题（可选）").classes("w-full")
                upload_status = ui.label("").classes("text-sm text-gray-500")

                async def handle_upload(e: events.UploadEventArguments) -> None:
                    content = e.content.read()
                    upload_status.set_text("上传中，请稍候...")
                    try:
                        dto = await container.meeting_service.upload_meeting(
                            title=title_input.value,
                            filename=e.name,
                            content_type=e.type or "application/octet-stream",
                            content=content,
                        )
                        upload_status.set_text(f"上传成功：{dto.title}，正在跳转到处理进度页面...")
                        title_input.set_value("")
                        # 上传成功后直接跳转到会议详情页实时查看处理进度，
                        # 避免用户停留在列表页却找不到处理结果在哪里查看
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

        # 页面存在期间每 2 秒自动拉取一次最新状态，无需手动刷新即可看到"转写中 -> 生成摘要中 -> 已完成"的变化
        ui.timer(_POLL_INTERVAL_SECONDS, meetings_list.refresh)
