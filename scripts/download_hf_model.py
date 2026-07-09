#!/usr/bin/env python3
"""从 Hugging Face（或 hf-mirror）下载模型，跳过已完整文件，支持断点续传。

Usage:
  python scripts/download_hf_model.py REPO_ID --local-dir ./models/foo
  HF_ENDPOINT=https://hf-mirror.com python scripts/download_hf_model.py ...

与 `hf download` 不同，本脚本会先统计「已完整 / 待下载」字节，下载后再汇报实际新增流量。
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# 国内镜像 + 禁用 Xet（与 shell 脚本一致）
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")


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
        if ".cache" in file_path.parts:
            continue
        total += file_path.stat().st_size
    return total


def analyze_repo(
    repo_id: str, local_dir: Path, endpoint: str | None
) -> tuple[list[tuple[str, int]], list[tuple[str, int]], int, int]:
    from huggingface_hub import HfApi

    api = HfApi(endpoint=endpoint)
    info = api.repo_info(repo_id, repo_type="model", files_metadata=True)
    complete: list[tuple[str, int]] = []
    pending: list[tuple[str, int]] = []
    have = 0
    need = 0
    for sibling in info.siblings or []:
        if sibling.rfilename is None or sibling.size is None:
            continue
        name = sibling.rfilename
        size = int(sibling.size)
        need += size
        local_path = local_dir / name
        if local_file_size(local_path) == size:
            complete.append((name, size))
            have += size
        else:
            pending.append((name, size))
    return pending, complete, have, need


def download_file_curl(url: str, dest: Path, *, retries: int = 20) -> None:
    import subprocess

    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")
    if dest.is_file() and not tmp.is_file():
        tmp = dest  # continue in-place if partial naming differs
    cmd = [
        "curl",
        "-L",
        "--http1.1",
        "--fail",
        "--retry",
        str(retries),
        "--retry-delay",
        "3",
        "--retry-all-errors",
        "-C",
        "-",
        "-o",
        str(tmp if tmp != dest else dest),
        url,
    ]
    env = os.environ.copy()
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        env.pop(key, None)
    print(f"  curl → {dest.name}")
    subprocess.run(cmd, check=True, env=env)
    if tmp != dest and tmp.is_file():
        tmp.rename(dest)


def mirror_resolve_url(repo_id: str, filename: str, mirror: str) -> str:
    return f"{mirror.rstrip('/')}/{repo_id}/resolve/main/{filename}"


def download_pending_curl(
    repo_id: str,
    local_dir: Path,
    pending: list[tuple[str, int]],
    *,
    mirror: str,
) -> list[tuple[str, int]]:
    still_pending: list[tuple[str, int]] = []
    for name, size in pending:
        dest = local_dir / name
        if local_file_size(dest) == size:
            continue
        url = mirror_resolve_url(repo_id, name, mirror)
        try:
            download_file_curl(url, dest)
        except Exception as exc:
            print(f"  下载失败 {name}: {exc}", file=sys.stderr)
            still_pending.append((name, size))
            continue
        if local_file_size(dest) != size:
            print(f"  大小不匹配 {name}: 本地 {local_file_size(dest)} != 远程 {size}", file=sys.stderr)
            still_pending.append((name, size))
    return still_pending


def main() -> int:
    parser = argparse.ArgumentParser(description="Download HF model with resume")
    parser.add_argument("repo_id", help="e.g. vanch007/mlx-MOSS-Transcribe-Diarize")
    parser.add_argument("--local-dir", required=True, help="Local directory for model files")
    parser.add_argument("--max-workers", type=int, default=int(os.environ.get("HF_MAX_WORKERS", "4")))
    parser.add_argument("--force", action="store_true", help="Re-download even if file size matches")
    parser.add_argument("--check-only", action="store_true", help="Only check local vs remote, do not download")
    parser.add_argument(
        "--method",
        choices=("auto", "hub", "curl"),
        default=os.environ.get("HF_DOWNLOAD_METHOD", "auto"),
        help="auto: curl on hf-mirror then hub fallback; hub: huggingface_hub only; curl: curl only",
    )
    parser.add_argument(
        "--mirror",
        default=os.environ.get("HF_MIRROR", "https://hf-mirror.com"),
        help="Mirror base URL for curl downloads",
    )
    args = parser.parse_args()

    local_dir = Path(args.local_dir).expanduser().resolve()
    local_dir.mkdir(parents=True, exist_ok=True)
    endpoint = os.environ.get("HF_ENDPOINT") or os.environ.get("HUGGINGFACE_HUB_ENDPOINT")

    print("========================================")
    print(f"Repo:        {args.repo_id}")
    print(f"Target:      {local_dir}")
    print(f"Endpoint:    {endpoint or 'https://huggingface.co'}")
    print(f"Xet CDN:     disabled (HF_HUB_DISABLE_XET=1)")
    print(f"Workers:     {args.max_workers}")
    print("========================================")

    try:
        pending, complete, have, need = analyze_repo(args.repo_id, local_dir, endpoint)
    except Exception as exc:
        print(f"无法获取仓库文件列表: {exc}", file=sys.stderr)
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

    if not pending and not args.force:
        print("\n所有文件已完整，跳过下载。")
        return 0

    if args.check_only:
        print("\n[--check-only] 仅检测，未下载。")
        return 2 if pending else 0

    before_bytes = iter_local_bytes(local_dir)
    started = time.time()
    pending2: list[tuple[str, int]] = list(pending)

    use_curl = args.method in {"auto", "curl"} and (
        args.method == "curl" or (endpoint and "hf-mirror" in endpoint)
    )
    if use_curl and pending2:
        print(f"\n使用 curl 从镜像续传（{args.mirror}，禁用代理）...")
        pending2 = download_pending_curl(args.repo_id, local_dir, pending2, mirror=args.mirror)

    if pending2 and args.method in {"auto", "hub"}:
        from huggingface_hub import snapshot_download

        hub_endpoint = endpoint
        if args.method == "auto" and pending2:
            print("\n镜像未下完，回退 huggingface_hub（官方源）...")
            hub_endpoint = None

        print("开始 snapshot_download（已存在且大小匹配的文件会自动跳过）...")
        snapshot_download(
            repo_id=args.repo_id,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False,
            max_workers=args.max_workers,
            force_download=args.force,
            endpoint=hub_endpoint,
        )
        pending2, _, _, _ = analyze_repo(args.repo_id, local_dir, hub_endpoint or endpoint)
    after_bytes = iter_local_bytes(local_dir)
    delta = max(0, after_bytes - before_bytes)
    elapsed = max(time.time() - started, 0.001)

    pending2, _complete2, have2, need2 = analyze_repo(args.repo_id, local_dir, endpoint)
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
