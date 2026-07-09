"""ModelScope 模型下载工具（带文件级进度回调）。"""
from __future__ import annotations

from loguru import logger

from memoflow.infrastructure.ai.progress import ProgressCallback, report_progress

_VAD_MODELSCOPE_ID = "iic/speech_fsmn_vad_zh-cn-16k-common-pytorch"


def sensevoice_model_ids(asr_model: str) -> list[str]:
    """SenseVoice ASR 依赖的 ModelScope 模型列表。"""
    return [asr_model, _VAD_MODELSCOPE_ID]


def snapshot_download_with_progress(
    model_id: str,
    on_progress: ProgressCallback = None,
    *,
    progress_range: tuple[float, float] = (5, 95),
    label: str | None = None,
) -> str:
    """从 ModelScope 下载模型快照，并按文件汇报进度。"""
    display = label or model_id
    report_progress(on_progress, 0, f"连接 ModelScope · {display}", progress_range=progress_range)

    try:
        return _download_files_with_progress(model_id, on_progress, progress_range, display)
    except Exception as exc:  # noqa: BLE001 - 回退到整包下载
        logger.warning(f"ModelScope 分文件下载失败，回退整包下载: {exc}")
        report_progress(on_progress, 30, f"批量下载 {display}...", progress_range=progress_range)
        from modelscope import snapshot_download

        local_dir = snapshot_download(model_id)
        report_progress(on_progress, 100, f"{display} 下载完成", progress_range=progress_range)
        return local_dir


def _download_files_with_progress(
    model_id: str,
    on_progress: ProgressCallback,
    progress_range: tuple[float, float],
    display: str,
) -> str:
    from modelscope.hub.api import HubApi
    from modelscope.hub.file_download import model_file_download

    api = HubApi()
    files = api.get_model_files(model_id, recursive=True)
    blobs = [item for item in files if item.get("Type") == "blob"]
    if not blobs:
        from modelscope import snapshot_download

        local_dir = snapshot_download(model_id)
        report_progress(on_progress, 100, f"{display} 下载完成", progress_range=progress_range)
        return local_dir

    total = len(blobs)
    local_dir: str | None = None
    for index, file_info in enumerate(blobs, start=1):
        path = file_info["Path"]
        file_percent = index / total * 100
        report_progress(
            on_progress,
            file_percent,
            f"下载 {display} ({index}/{total}): {path}",
            progress_range=progress_range,
        )
        local_dir = model_file_download(model_id=model_id, file_path=path)

    assert local_dir is not None
    report_progress(on_progress, 100, f"{display} 下载完成", progress_range=progress_range)
    return local_dir
