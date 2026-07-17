"""上传流式读取与大小限制单元测试。"""
from __future__ import annotations

from typing import Any

import pytest

from memoflow.interfaces.api.upload_stream import UploadTooLargeError, read_upload_limited


class _FakeUpload:
    def __init__(self, data: bytes, *, size: int | None = None) -> None:
        self._data = data
        self._pos = 0
        self.filename = "meeting.wav"
        self.content_type = "audio/wav"
        self.size = len(data) if size is None else size

    async def read(self, size: int = -1) -> bytes:
        if self._pos >= len(self._data):
            return b""
        if size < 0:
            size = len(self._data) - self._pos
        chunk = self._data[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk


@pytest.mark.asyncio
async def test_read_upload_limited_streams_exact_content() -> None:
    payload = b"abc" * 1000
    upload: Any = _FakeUpload(payload)

    content = await read_upload_limited(upload, max_bytes=10_000, chunk_size=64)

    assert content == payload


@pytest.mark.asyncio
async def test_read_upload_limited_rejects_when_known_size_exceeds() -> None:
    upload: Any = _FakeUpload(b"tiny", size=5000)

    with pytest.raises(UploadTooLargeError) as exc_info:
        await read_upload_limited(upload, max_bytes=100)

    assert exc_info.value.max_bytes == 100
    assert upload._pos == 0  # 未开始读 body


@pytest.mark.asyncio
async def test_read_upload_limited_rejects_during_stream() -> None:
    payload = b"x" * 250
    upload: Any = _FakeUpload(payload, size=None)

    with pytest.raises(UploadTooLargeError) as exc_info:
        await read_upload_limited(upload, max_bytes=100, chunk_size=32)

    assert exc_info.value.max_bytes == 100
    assert exc_info.value.received_bytes is not None
    assert exc_info.value.received_bytes > 100
