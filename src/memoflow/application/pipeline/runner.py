"""基于 asyncio 后台任务的流水线调度器实现（适用于本地单机部署）。

生产环境如需水平扩展，可替换为基于 Celery / RQ / Redis Stream 的 `PipelineRunner` 实现，
应用层与接口层代码无需任何改动。
"""
from __future__ import annotations

import asyncio

from loguru import logger

from memoflow.application.pipeline.processing_pipeline import MeetingProcessingPipeline
from memoflow.application.ports.pipeline_runner import PipelineRunner


class AsyncioPipelineRunner(PipelineRunner):
    def __init__(self, pipeline: MeetingProcessingPipeline) -> None:
        self._pipeline = pipeline
        self._tasks: set[asyncio.Task[None]] = set()

    async def schedule(self, meeting_id: str) -> None:
        task = asyncio.create_task(self._run_safely(meeting_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_safely(self, meeting_id: str) -> None:
        try:
            await self._pipeline.run(meeting_id)
        except Exception:  # noqa: BLE001 - 后台任务顶层兜底，防止未捕获异常被吞掉后无日志
            logger.exception(f"[{meeting_id}] 后台流水线任务异常退出")
