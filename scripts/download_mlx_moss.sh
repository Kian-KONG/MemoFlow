#!/usr/bin/env bash
# 下载 MLX 版 MOSS（Mac M 系列推荐，~1.8GB）
# ModelScope 无 MLX 转换版，委托统一下载脚本走 HF 镜像。
#
# Usage:
#   ./scripts/download_mlx_moss.sh [target_dir]
#   ./scripts/download_mlx_moss.sh --check-only [target_dir]

set -euo pipefail

export MEMOFLOW_ASR_BACKEND=mlx_moss
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/scripts/download_asr_model.sh" "$@"
