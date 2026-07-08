"""极简的进程内领域事件分发器。

生产环境可替换为基于消息队列（Redis Stream / Kafka）的实现，
只需实现同样的 `publish` / `subscribe` 接口即可，符合"模块可替换"的要求。
"""
from __future__ import annotations

from collections import defaultdict
from typing import Awaitable, Callable, TypeVar

from memoflow.domain.shared.entity import DomainEvent

TEvent = TypeVar("TEvent", bound=DomainEvent)
EventHandler = Callable[[DomainEvent], Awaitable[None]]


class EventDispatcher:
    """一个简单的异步事件总线，按事件类型分发给已注册的处理器。"""

    def __init__(self) -> None:
        self._handlers: dict[type[DomainEvent], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[TEvent], handler: EventHandler) -> None:
        self._handlers[event_type].append(handler)

    async def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers.get(type(event), []):
            await handler(event)

    async def publish_all(self, events: list[DomainEvent]) -> None:
        for event in events:
            await self.publish(event)
