"""领域层异常。基础设施 / 应用层异常不应放在此处。"""
from __future__ import annotations


class DomainError(Exception):
    """所有领域异常的基类。"""


class InvariantViolationError(DomainError):
    """违反聚合内不变量时抛出。"""


class EntityNotFoundError(DomainError):
    """按 ID 查找实体但未找到时抛出（由仓储实现转译并抛出）。"""

    def __init__(self, entity_name: str, entity_id: str) -> None:
        super().__init__(f"{entity_name} 未找到: id={entity_id}")
        self.entity_name = entity_name
        self.entity_id = entity_id


class InvalidStateTransitionError(DomainError):
    """状态机非法迁移时抛出，例如对未完成转写的会议生成摘要。"""

    def __init__(self, entity_name: str, current_state: str, action: str) -> None:
        super().__init__(f"{entity_name} 处于 [{current_state}] 状态，不能执行操作 [{action}]")
