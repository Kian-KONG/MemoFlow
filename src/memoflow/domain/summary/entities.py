"""摘要（Summary）聚合根：Summary / Decision / ActionItem。"""
from __future__ import annotations

from datetime import date, datetime

from memoflow.domain.shared.entity import AggregateRoot, Entity, utcnow
from memoflow.domain.shared.exceptions import EntityNotFoundError, InvariantViolationError
from memoflow.domain.summary.value_objects import (
    ActionItemId,
    ActionItemStatus,
    DecisionId,
    SummaryId,
)


class Decision(Entity[DecisionId]):
    """会议中作出的一项决策。"""

    def __init__(
        self,
        decision_id: DecisionId,
        description: str,
        related_utterance_ids: list[str] | None = None,
    ) -> None:
        super().__init__(decision_id)
        if not description.strip():
            raise InvariantViolationError("决策描述不能为空")
        self.description = description
        self.related_utterance_ids = related_utterance_ids or []


class ActionItem(Entity[ActionItemId]):
    """会议产生的一项行动项（任务）。"""

    def __init__(
        self,
        action_item_id: ActionItemId,
        description: str,
        owner: str | None = None,
        due_date: date | None = None,
        status: ActionItemStatus = ActionItemStatus.OPEN,
        related_utterance_ids: list[str] | None = None,
    ) -> None:
        super().__init__(action_item_id)
        if not description.strip():
            raise InvariantViolationError("行动项描述不能为空")
        self.description = description
        self.owner = owner
        self.due_date = due_date
        self.status = status
        self.related_utterance_ids = related_utterance_ids or []

    def reassign(self, owner: str) -> None:
        self.owner = owner

    def mark_in_progress(self) -> None:
        self.status = ActionItemStatus.IN_PROGRESS

    def mark_done(self) -> None:
        self.status = ActionItemStatus.DONE


class Summary(AggregateRoot[SummaryId]):
    """摘要聚合根：一次会议的摘要、关键决策与行动项集合。"""

    def __init__(
        self,
        summary_id: SummaryId,
        meeting_id: str,
        overview: str,
        key_points: list[str],
        decisions: list[Decision],
        action_items: list[ActionItem],
        generated_by_model: str,
        generated_at: datetime,
    ) -> None:
        super().__init__(summary_id)
        self.meeting_id = meeting_id
        self.overview = overview
        self.key_points = key_points
        self.decisions = decisions
        self.action_items = action_items
        self.generated_by_model = generated_by_model
        self.generated_at = generated_at

    @classmethod
    def create(
        cls,
        meeting_id: str,
        overview: str,
        key_points: list[str],
        decisions: list[Decision],
        action_items: list[ActionItem],
        generated_by_model: str,
    ) -> "Summary":
        return cls(
            summary_id=SummaryId.new(),
            meeting_id=meeting_id,
            overview=overview,
            key_points=key_points,
            decisions=decisions,
            action_items=action_items,
            generated_by_model=generated_by_model,
            generated_at=utcnow(),
        )

    def complete_action_item(self, action_item_id: ActionItemId) -> None:
        self._find_action_item(action_item_id).mark_done()

    def reassign_action_item(self, action_item_id: ActionItemId, owner: str) -> None:
        self._find_action_item(action_item_id).reassign(owner)

    def _find_action_item(self, action_item_id: ActionItemId) -> ActionItem:
        for item in self.action_items:
            if item.id == action_item_id:
                return item
        raise EntityNotFoundError("ActionItem", str(action_item_id))
