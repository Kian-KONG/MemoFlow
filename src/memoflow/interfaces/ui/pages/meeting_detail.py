"""会议详情页面：转写文本、说话人、摘要、决策、行动项、知识库检索。

处理是后台异步流水线，本页面通过 `ui.timer` 定时轮询会议状态，
处理中显示实时进度，完成后自动刷新摘要 / 转写内容，无需用户手动刷新浏览器。
"""
from __future__ import annotations

from datetime import datetime, timezone

from nicegui import ui

from memoflow.container import AppContainer
from memoflow.domain.shared.exceptions import EntityNotFoundError

_STAGE_STEPS = ["uploaded", "transcribing", "diarizing", "summarizing", "completed"]
_STAGE_LABELS = {
    "uploaded": "排队等待处理",
    "transcribing": "正在转写语音（VibeVoice）",
    "diarizing": "正在识别说话人（VibeVoice）",
    "summarizing": "正在生成摘要（DeepSeek）",
    "completed": "处理完成",
    "failed": "处理失败",
}
_STAGE_HINTS = {
    "uploaded": "后台任务即将启动，请稍候…",
    "transcribing": "正在用 VibeVoice 模型转写语音并标注说话人，长音频可能需要较长时间。",
    "diarizing": "VibeVoice 已在转写阶段标注说话人，正在推进处理状态。",
    "summarizing": "正在通过 DeepSeek API 生成会议摘要。",
}

_POLL_INTERVAL_SECONDS = 2.0


def _format_elapsed(started_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)
    seconds = int((now - started_at).total_seconds())
    if seconds < 60:
        return f"{seconds} 秒"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes} 分 {secs} 秒"
    hours, minutes = divmod(minutes, 60)
    return f"{hours} 小时 {minutes} 分"


def _copy_button(text_getter) -> None:  # noqa: ANN001
    """生成一个"复制到剪贴板"按钮，`text_getter` 是获取最新文本的回调（避免闭包捕获旧值）。"""

    def do_copy() -> None:
        ui.clipboard.write(text_getter())
        ui.notify("已复制到剪贴板", type="positive")

    ui.button(icon="content_copy", on_click=do_copy).props("flat dense round").tooltip("复制")


def register_meeting_detail_page(container: AppContainer) -> None:
    @ui.refreshable
    async def status_panel(meeting_id: str) -> str:
        """渲染处理进度，返回当前状态字符串，供轮询逻辑判断是否需要继续/停止。"""
        try:
            meeting = await container.meeting_service.get_meeting(meeting_id)
        except EntityNotFoundError:
            ui.label("会议不存在").classes("text-red-500")
            return "not_found"

        status = meeting.status.value
        with ui.row().classes("w-full items-center justify-between"):
            ui.label(meeting.title).classes("text-lg font-semibold")
            ui.label(f"上传文件: {meeting.original_filename}").classes("text-xs text-gray-400")

        if status not in ("completed", "failed"):
            current_index = _STAGE_STEPS.index(status) if status in _STAGE_STEPS else 0
            with ui.row().classes("items-center gap-2 mt-2"):
                ui.spinner(size="1.2em", color="primary")
                ui.label(_STAGE_LABELS.get(status, status)).classes("text-blue-600 font-medium")
            ui.linear_progress(value=(current_index + 1) / len(_STAGE_STEPS)).props("instant-feedback")
            ui.label(f"已耗时: {_format_elapsed(meeting.updated_at)}").classes("text-xs text-gray-500 mt-1")
            ui.label(_STAGE_HINTS.get(status, "处理完全在本地进行，页面会每 2 秒自动刷新进度。")).classes(
                "text-xs text-gray-400 mt-1"
            )
            if meeting.transcript_id:
                ui.label("转写文本已部分生成，可切换到「转写文本」标签页查看。").classes(
                    "text-xs text-green-600 mt-1"
                )
        elif status == "completed":
            with ui.row().classes("items-center gap-2 mt-2"):
                ui.icon("check_circle", color="green").classes("text-xl")
                ui.label("处理完成，可在下方查看结果").classes("text-green-600 font-medium")
        else:  # failed
            with ui.row().classes("items-center gap-2 mt-2"):
                ui.icon("error", color="red").classes("text-xl")
                ui.label("处理失败").classes("text-red-600 font-medium")
            if meeting.error_message:
                ui.label(f"错误信息: {meeting.error_message}").classes("text-sm text-red-500 mt-1")
                if meeting.status.value == "failed":
                    ui.label("重试将从上次成功的阶段继续，已完成的转写/摘要不要重新生成。").classes(
                        "text-xs text-blue-600 mt-1"
                    )
                if "ffmpeg" in meeting.error_message.lower():
                    ui.label("提示: 请安装 ffmpeg（brew install ffmpeg）后点击重试。").classes(
                        "text-sm text-orange-600 mt-1"
                    )
            ui.button(
                "重试处理", on_click=lambda: _retry(container, meeting_id)
            ).props("outline color=red").classes("mt-2")

        return status

    @ui.refreshable
    async def summary_panel(meeting_id: str) -> None:
        try:
            summary = await container.summary_service.get_summary(meeting_id)
        except EntityNotFoundError:
            ui.label("摘要尚未生成，处理完成后会自动显示。").classes("text-gray-500")
            return

        def full_summary_text() -> str:
            lines = [f"会议概览：{summary.overview}", "", "关键要点："]
            lines += [f"- {p}" for p in summary.key_points] or ["（无）"]
            lines += ["", "决策："]
            lines += [f"- {d.description}" for d in summary.decisions] or ["（无）"]
            lines += ["", "行动项："]
            lines += [
                f"- [{a.status.value}] {a.description}（负责人: {a.owner or '未指定'}）"
                for a in summary.action_items
            ] or ["（无）"]
            return "\n".join(lines)

        with ui.row().classes("w-full items-center justify-between"):
            ui.label("会议概览").classes("font-semibold mt-2")
            _copy_button(full_summary_text)
        ui.label(summary.overview)

        ui.label("关键要点").classes("font-semibold mt-4")
        if not summary.key_points:
            ui.label("无").classes("text-gray-500")
        for point in summary.key_points:
            ui.label(f"• {point}")

        ui.label("决策").classes("font-semibold mt-4")
        if not summary.decisions:
            ui.label("无").classes("text-gray-500")
        for decision in summary.decisions:
            ui.label(f"• {decision.description}")

        ui.label("行动项").classes("font-semibold mt-4")
        if not summary.action_items:
            ui.label("无").classes("text-gray-500")
        for item in summary.action_items:
            owner = item.owner or "未指定"
            ui.label(f"[{item.status.value}] {item.description}（负责人: {owner}）")

    @ui.refreshable
    async def transcript_panel(meeting_id: str) -> None:
        try:
            transcript = await container.transcription_service.get_transcript(meeting_id)
        except EntityNotFoundError:
            ui.label("转写尚未完成，处理中会自动显示。").classes("text-gray-500")
            return

        def full_transcript_text() -> str:
            lines = []
            for u in transcript.utterances:
                speaker_name = (u.speaker.display_name or u.speaker.label) if u.speaker else "未知说话人"
                lines.append(f"[{u.start:.1f}s] {speaker_name}: {u.text}")
            return "\n".join(lines)

        with ui.row().classes("w-full items-center justify-between"):
            ui.label(f"共 {len(transcript.utterances)} 条话语").classes("text-sm text-gray-500")
            _copy_button(full_transcript_text)

        for utterance in transcript.utterances:
            speaker_name = (
                (utterance.speaker.display_name or utterance.speaker.label)
                if utterance.speaker
                else "未知说话人"
            )
            with ui.row().classes("w-full gap-2"):
                ui.label(f"[{utterance.start:.1f}s] {speaker_name}:").classes(
                    "font-medium text-blue-600 shrink-0"
                )
                ui.label(utterance.text)

    @ui.page("/meetings/{meeting_id}")
    async def meeting_detail(meeting_id: str) -> None:
        ui.page_title("MemoFlow - 会议详情")

        with ui.header().classes("items-center justify-between"):
            with ui.row().classes("items-center"):
                ui.button(icon="arrow_back", on_click=lambda: ui.navigate.to("/")).props("flat color=white")
                ui.label("会议详情").classes("text-xl font-bold")
            ui.button(icon="settings", on_click=lambda: ui.navigate.to("/settings")).props(
                "flat color=white"
            ).tooltip("模型设置")

        with ui.column().classes("w-full max-w-3xl mx-auto p-4 gap-4"):
            with ui.card().classes("w-full"):
                await status_panel(meeting_id)

            with ui.tabs().classes("w-full") as tabs:
                tab_summary = ui.tab("摘要 / 决策 / 行动项")
                tab_transcript = ui.tab("转写文本")
                tab_knowledge = ui.tab("知识库检索")

            with ui.tab_panels(tabs, value=tab_summary).classes("w-full"):
                with ui.tab_panel(tab_summary):
                    await summary_panel(meeting_id)
                with ui.tab_panel(tab_transcript):
                    await transcript_panel(meeting_id)
                with ui.tab_panel(tab_knowledge):
                    _render_knowledge_search(container, meeting_id)

        async def poll() -> None:
            await status_panel.refresh(meeting_id)
            meeting = await container.meeting_service.get_meeting(meeting_id)
            if meeting.transcript_id is not None:
                await transcript_panel.refresh(meeting_id)
            if meeting.status.value == "completed":
                await summary_panel.refresh(meeting_id)
                poll_timer.active = False
            elif meeting.status.value == "failed":
                poll_timer.active = False

        poll_timer = ui.timer(_POLL_INTERVAL_SECONDS, poll)


async def _retry(container: AppContainer, meeting_id: str) -> None:
    await container.meeting_service.retry_meeting(meeting_id)
    ui.navigate.to(f"/meetings/{meeting_id}")


def _render_knowledge_search(container: AppContainer, meeting_id: str) -> None:
    query_input = ui.input("输入问题以检索本会议相关内容").classes("w-full")
    results_container = ui.column().classes("w-full gap-2 mt-2")

    async def do_search() -> None:
        results_container.clear()
        hits = await container.knowledge_service.search(
            query=query_input.value, meeting_id=meeting_id, top_k=5
        )
        with results_container:
            if not hits:
                ui.label("未找到相关内容").classes("text-gray-500")
            for hit in hits:
                with ui.card().classes("w-full"):
                    with ui.row().classes("w-full items-center justify-between"):
                        ui.label(f"相关度: {hit.score:.2f}").classes("text-xs text-gray-400")
                        _copy_button(lambda t=hit.text: t)
                    ui.label(hit.text)

    ui.button("检索", on_click=do_search)
