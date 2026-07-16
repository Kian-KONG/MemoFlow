#!/usr/bin/env python3
"""从 ModelScope 下载模型，跳过已完整文件，支持断点续传。

Usage:
  python scripts/download_modelscope_model.py OpenMOSS/MOSS-Transcribe-Diarize --local-dir ./models/foo
  python scripts/download_modelscope_model.py REPO_ID --local-dir ./models/foo --check-only

与 huggingface_hub 不同，本脚本对接 ModelScope Hub API 做本地完整性校验。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path


def human_bytes(num: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(num)
    for unit in units:
        if value < 1000 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)}{unit}"
            return f"{value:.2f}{unit}"
        value /= 1000
    return f"{value:.2f}TB"


def local_file_size(path: Path) -> int:
    if not path.is_file():
        return 0
    return path.stat().st_size


def iter_local_bytes(root: Path) -> int:
    total = 0
    if not root.is_dir():
        return 0
    for file_path in root.rglob("*"):
        if not file_path.is_file():
            continue
        if file_path.name.endswith(".incomplete"):
            continue
        if "._____temp" in file_path.parts or ".cache" in file_path.parts:
            continue
        total += file_path.stat().st_size
    return total


def list_remote_files(model_id: str) -> list[dict]:
    from modelscope.hub.api import HubApi

    api = HubApi()
    return api.get_model_files(model_id, recursive=True)


def analyze_repo(model_id: str, local_dir: Path) -> tuple[
    list[tuple[str, int]],
    list[tuple[str, int]],
    int,
    int,
]:
    remote_files = list_remote_files(model_id)
    complete: list[tuple[str, int]] = []
    pending: list[tuple[str, int]] = []
    have = 0
    need = 0
    for item in remote_files:
        name = item.get("Path")
        size = item.get("Size")
        if not name or size is None:
            continue
        if name in {".gitignore", ".gitattributes"}:
            continue
        size = int(size)
        need += size
        local_path = local_dir / name
        if local_file_size(local_path) == size:
            complete.append((name, size))
            have += size
        else:
            pending.append((name, size))
    return pending, complete, have, need


def marker_files_complete(model_id: str, local_dir: Path) -> bool:
    """关键权重文件存在时视为可能完整（用于 API 不可用时的兜底）。"""
    markers = ("config.json", "model.safetensors", "model-00000-of-00001.safetensors")
    return any((local_dir / name).is_file() for name in markers)


def main() -> int:
    parser = argparse.ArgumentParser(description="Download ModelScope model with resume")
    parser.add_argument("model_id", help="e.g. OpenMOSS/MOSS-Transcribe-Diarize")
    parser.add_argument("--local-dir", required=True, help="Local directory for model files")
    parser.add_argument(
        "--revision",
        default=None,
        help="Model revision (default: ModelScope master)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        help="Parallel download workers",
    )
    parser.add_argument("--check-only", action="store_true", help="Only check local vs remote, do not download")
    args = parser.parse_args()

    local_dir = Path(args.local_dir).expanduser().resolve()
    local_dir.mkdir(parents=True, exist_ok=True)

    print("========================================")
    print(f"ModelScope:  {args.model_id}")
    print(f"Target:      {local_dir}")
    print(f"Revision:    {args.revision or 'master'}")
    print(f"Workers:     {args.max_workers}")
    print("========================================")

    try:
        pending, complete, have, need = analyze_repo(args.model_id, local_dir)
    except Exception as exc:
        print(f"无法获取 ModelScope 仓库文件列表: {exc}", file=sys.stderr)
        if args.check_only and marker_files_complete(args.model_id, local_dir):
            print("API 不可用，但检测到关键 marker 文件，视为可能完整。")
            return 0
        return 1

    pending_bytes = sum(size for _, size in pending)
    print(f"远程总大小: {human_bytes(need)}")
    print(f"已完整文件: {human_bytes(have)} ({len(complete)} 个)")
    print(f"待下载:     {human_bytes(pending_bytes)} ({len(pending)} 个文件)")
    if pending:
        for name, size in pending[:8]:
            print(f"  - {name} ({human_bytes(size)})")
        if len(pending) > 8:
            print(f"  ... 另有 {len(pending) - 8} 个文件")

    if not pending:
        print("\n所有文件已完整，跳过下载。")
        return 0

    if args.check_only:
        print("\n[--check-only] 仅检测，未下载。")
        return 2

    before_bytes = iter_local_bytes(local_dir)
    started = time.time()

    from modelscope.hub.snapshot_download import snapshot_download

    print("\n开始 snapshot_download（已存在文件会自动跳过，支持断点续传）...")
    snapshot_download(
        model_id=args.model_id,
        revision=args.revision,
        local_dir=str(local_dir),
        max_workers=args.max_workers,
    )

    after_bytes = iter_local_bytes(local_dir)
    delta = max(0, after_bytes - before_bytes)
    elapsed = max(time.time() - started, 0.001)

    pending2, _complete2, have2, need2 = analyze_repo(args.model_id, local_dir)
    print("\n========================================")
    print(f"本次新增本地数据: {human_bytes(delta)}")
    print(f"平均速度:         {human_bytes(int(delta / elapsed))}/s")
    print(f"最终进度:         {human_bytes(have2)} / {human_bytes(need2)}")
    if pending2:
        print(f"仍有未完成:       {len(pending2)} 个文件 ({human_bytes(sum(s for _, s in pending2))})")
        print("可重新运行本命令续传。")
        return 2
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
