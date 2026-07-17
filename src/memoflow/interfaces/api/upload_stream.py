"""会议录音上传：分块流式读取并强制大小上限。

避免 `UploadFile.read()` 一次性把整个文件缓冲进内存；
先按块写入临时文件，再交给下游（当前仍需 bytes 的存储接口）。
"""
from __future__ import annotations

import tempfile
from pathlib import Path

import aiofiles
from fastapi import UploadFile

DEFAULT_CHUNK_SIZE = 1024 * 1024  # 1 MiB


class UploadTooLargeError(Exception):
    """上传内容超过配置的最大字节数。"""

    def __init__(self, max_bytes: int, received_bytes: int | None = None) -> None:
        self.max_bytes = max_bytes
        self.received_bytes = received_bytes
        detail = f"上传文件超过大小限制（最大 {max_bytes} 字节）"
        if received_bytes is not None:
            detail = f"{detail}，已接收约 {received_bytes} 字节"
        super().__init__(detail)


async def read_upload_limited(
    upload: UploadFile,
    *,
    max_bytes: int,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> bytes:
    """分块读取上传流，写入临时文件并校验大小，返回完整内容。

    - 接收阶段峰值内存约为 ``chunk_size``，而非整文件。
    - 若 ``upload.size`` 已知且已超限，立即拒绝（不读 body）。
    - 返回的 ``bytes`` 供现有 ``FileStoragePort.save`` 使用（仍会有一次整文件内存占用）。
    """
    if max_bytes <= 0:
        raise ValueError("max_bytes 必须为正数")
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须为正数")

    known_size = getattr(upload, "size", None)
    if isinstance(known_size, int) and known_size > max_bytes:
        raise UploadTooLargeError(max_bytes, received_bytes=known_size)

    total = 0
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".upload") as tmp:
            tmp_path = Path(tmp.name)

        async with aiofiles.open(tmp_path, "wb") as out:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise UploadTooLargeError(max_bytes, received_bytes=total)
                await out.write(chunk)

        async with aiofiles.open(tmp_path, "rb") as f:
            return await f.read()
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)
