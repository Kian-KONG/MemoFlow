"""FileStoragePort 的本地磁盘实现。"""
from __future__ import annotations

import os
import uuid
from pathlib import Path

import aiofiles
from loguru import logger

from memoflow.application.ports.file_storage_port import FileStoragePort


class LocalFileStorage(FileStoragePort):
    """将上传的音频文件保存到本地目录。storage_path 为相对于 `base_dir` 的相对路径。"""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, filename: str, content: bytes) -> str:
        safe_name = self._sanitize_filename(filename)
        unique_name = f"{uuid.uuid4().hex}_{safe_name}"
        destination = self._base_dir / unique_name

        async with aiofiles.open(destination, "wb") as f:
            await f.write(content)

        logger.info(f"音频文件已保存: {destination}")
        return unique_name

    async def resolve_path(self, storage_path: str) -> str:
        full_path = (self._base_dir / storage_path).resolve()
        # 防止通过精心构造的 storage_path 进行目录穿越
        if self._base_dir.resolve() not in full_path.parents and full_path != self._base_dir.resolve():
            raise ValueError("非法的存储路径")
        return str(full_path)

    async def delete(self, storage_path: str) -> None:
        full_path = self._base_dir / storage_path
        if full_path.exists():
            os.remove(full_path)

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """仅保留文件名部分（去除任何目录组件），杜绝路径穿越攻击。"""
        return Path(filename).name.replace("..", "_")
