"""音频文件存储端口。

生产实现：`memoflow.infrastructure.storage.file_storage.LocalFileStorage`（本地磁盘）。
可替换为 S3 / MinIO 等对象存储实现。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class FileStoragePort(ABC):
    @abstractmethod
    async def save(self, filename: str, content: bytes) -> str:
        """保存文件内容，返回可用于后续读取的存储路径（storage_path）。"""

    @abstractmethod
    async def resolve_path(self, storage_path: str) -> str:
        """将存储路径解析为本地文件系统绝对路径，供 AI 模型读取。"""

    @abstractmethod
    async def delete(self, storage_path: str) -> None: ...
