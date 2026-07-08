"""流水线调度端口：将“会议处理流水线”的执行调度出去（后台任务 / 队列）。"""
from __future__ import annotations

from abc import ABC, abstractmethod


class PipelineRunner(ABC):
    @abstractmethod
    async def schedule(self, meeting_id: str) -> None:
        """调度对指定会议执行完整的处理流水线（转写 -> 说话人识别 -> 摘要 -> 知识库索引）。

        该调用应立即返回（非阻塞），实际处理在后台执行。
        """
