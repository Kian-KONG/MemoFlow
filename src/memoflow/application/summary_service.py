"""摘要应用服务：编排 LLM 生成会议摘要 / 决策 / 行动项。"""
from __future__ import annotations

import json

from loguru import logger
from pydantic import BaseModel, Field, ValidationError

from memoflow.application.dto import SummaryDTO
from memoflow.application.ports.llm_port import LLMPort
from memoflow.application.ports.unit_of_work import UnitOfWorkFactory
from memoflow.domain.meeting.value_objects import MeetingId
from memoflow.domain.shared.exceptions import EntityNotFoundError
from memoflow.domain.summary.entities import ActionItem, Decision, Summary
from memoflow.domain.summary.value_objects import ActionItemId, DecisionId
from memoflow.domain.transcript.value_objects import TranscriptId

_SYSTEM_PROMPT = (
    "你是一名专业的会议记录助手。请仔细阅读会议转写文本，"
    "只依据转写内容提炼信息，不要编造未出现的信息。"
    "严格按照要求的 JSON 格式输出，不要输出任何多余文字。"
)

_USER_PROMPT_TEMPLATE = """请阅读以下会议转写内容，输出 JSON，字段要求：
- overview: 200 字以内的会议纪要总览
- key_points: 关键要点列表（字符串数组）
- decisions: 会议中做出的决策列表（字符串数组）
- action_items: 行动项列表，每项包含 description（任务描述）、owner（负责人，若未提及为 null）

只输出 JSON，不要包含 Markdown 代码块标记。

会议转写内容：
---
{transcript_text}
---
"""


class _ActionItemPayload(BaseModel):
    description: str
    owner: str | None = None


class _SummaryPayload(BaseModel):
    overview: str
    key_points: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[_ActionItemPayload] = Field(default_factory=list)


class SummaryApplicationService:
    def __init__(
        self,
        uow_factory: UnitOfWorkFactory,
        llm: LLMPort,
        llm_model_name: str,
    ) -> None:
        self._uow_factory = uow_factory
        self._llm = llm
        self._llm_model_name = llm_model_name

    async def summarize_meeting(self, meeting_id: str) -> SummaryDTO:
        async with self._uow_factory() as uow:
            meeting = await uow.meetings.get(MeetingId(meeting_id))
            if meeting is None:
                raise EntityNotFoundError("Meeting", meeting_id)
            if meeting.transcript_id is None:
                raise EntityNotFoundError("Transcript", "(meeting has no transcript yet)")
            transcript = await uow.transcripts.get(TranscriptId(meeting.transcript_id))
            if transcript is None:
                raise EntityNotFoundError("Transcript", meeting.transcript_id)

        logger.info(f"[{meeting_id}] 开始生成摘要（Qwen3-14B / MLX）...")
        prompt = _USER_PROMPT_TEMPLATE.format(transcript_text=transcript.full_text)
        raw_output = await self._llm.generate(prompt=prompt, system_prompt=_SYSTEM_PROMPT)
        payload = self._parse_llm_output(raw_output)

        summary = Summary.create(
            meeting_id=meeting_id,
            overview=payload.overview,
            key_points=payload.key_points,
            decisions=[Decision(DecisionId.new(), description=d) for d in payload.decisions],
            action_items=[
                ActionItem(ActionItemId.new(), description=a.description, owner=a.owner)
                for a in payload.action_items
            ],
            generated_by_model=self._llm_model_name,
        )

        async with self._uow_factory() as uow:
            meeting = await uow.meetings.get(MeetingId(meeting_id))
            if meeting is None:
                raise EntityNotFoundError("Meeting", meeting_id)
            await uow.summaries.add(summary)
            meeting.complete_summarization(str(summary.id))
            await uow.meetings.save(meeting)
            await uow.commit()

        logger.info(f"[{meeting_id}] 摘要生成完成: {len(summary.action_items)} 个行动项")
        return SummaryDTO.from_domain(summary)

    async def get_summary(self, meeting_id: str) -> SummaryDTO:
        async with self._uow_factory() as uow:
            summary = await uow.summaries.get_by_meeting_id(meeting_id)
        if summary is None:
            raise EntityNotFoundError("Summary", f"(meeting_id={meeting_id})")
        return SummaryDTO.from_domain(summary)

    @staticmethod
    def _parse_llm_output(raw_output: str) -> _SummaryPayload:
        text = raw_output.strip()
        # 兼容模型偶尔输出 ```json ... ``` 代码块的情况
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:]
            text = text.strip()
        try:
            data = json.loads(text)
            return _SummaryPayload.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            logger.warning(f"LLM 输出解析失败，使用降级摘要: {exc}")
            return _SummaryPayload(overview=raw_output[:500], key_points=[], decisions=[], action_items=[])
