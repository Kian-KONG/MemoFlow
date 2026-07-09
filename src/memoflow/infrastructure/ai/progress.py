"""模型下载进度回调类型。"""
from __future__ import annotations

from collections.abc import Callable

ProgressCallback = Callable[[float, str], None] | None


def report_progress(
    on_progress: ProgressCallback,
    percent: float,
    message: str,
    *,
    progress_range: tuple[float, float] = (0, 100),
) -> None:
    if on_progress is None:
        return
    start, end = progress_range
    scaled = start + (end - start) * (percent / 100.0)
    on_progress(min(100.0, max(0.0, scaled)), message)
