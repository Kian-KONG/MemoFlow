"""音频预处理：用 ffmpeg 将 m4a/mp3 等转为 ASR 可读的 wav。"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

_WAV_SUFFIX = ".wav"
_CONVERTIBLE_SUFFIXES = {".m4a", ".mp3", ".flac", ".ogg", ".aac", ".webm", ".mp4"}


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def needs_ffmpeg_conversion(audio_path: str | Path) -> bool:
    suffix = Path(audio_path).suffix.lower()
    return suffix in _CONVERTIBLE_SUFFIXES


def convert_to_wav(source: str | Path, target: str | Path) -> Path:
    """用 ffmpeg 转为 16kHz 单声道 wav（ASR / librosa 友好格式）。"""
    if not ffmpeg_available():
        raise RuntimeError(
            "缺少 ffmpeg，无法解码 m4a/mp3 等音频。请运行 brew install ffmpeg 后重试。"
        )

    source_path = Path(source)
    target_path = Path(target)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-ar",
        "16000",
        "-ac",
        "1",
        str(target_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        raise RuntimeError(
            f"ffmpeg 无法解码音频 {source_path.name}"
            + (f": {stderr}" if stderr else "")
        ) from exc

    if not target_path.is_file() or target_path.stat().st_size == 0:
        raise RuntimeError(f"ffmpeg 转换失败，未生成有效 wav: {target_path}")
    return target_path


def prepare_audio_for_asr(audio_path: str | Path) -> tuple[Path, Callable[[], None] | None]:
    """返回可供 ASR 使用的 wav 路径；非 wav 时创建临时文件并返回清理回调。"""
    path = Path(audio_path)
    if not path.is_file():
        raise FileNotFoundError(f"音频文件不存在: {path}")

    if path.suffix.lower() == _WAV_SUFFIX:
        return path, None

    if not needs_ffmpeg_conversion(path):
        return path, None

    fd, temp_name = tempfile.mkstemp(suffix=_WAV_SUFFIX, prefix="memoflow_asr_")
    import os

    os.close(fd)
    temp_path = Path(temp_name)
    convert_to_wav(path, temp_path)

    def cleanup() -> None:
        temp_path.unlink(missing_ok=True)

    return temp_path, cleanup
