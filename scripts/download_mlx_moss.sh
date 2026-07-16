#!/usr/bin/env bash
# 下载 / 检测 MLX 版 MOSS-Transcribe-Diarize（Mac M 系列推荐，~1.8GB）
#
# 注意：MLX 版权重仅发布在 Hugging Face，ModelScope 无对应模型。
# 也可统一使用: MEMOFLOW_ASR_BACKEND=mlx_moss ./scripts/download_asr_model.sh
# （download_asr_model.sh 会自动识别 mlx_moss 并走 HF 镜像，忽略 USE_MODELSCOPE）
#
# 模型页:
#   https://huggingface.co/vanch007/mlx-MOSS-Transcribe-Diarize
#   https://hf-mirror.com/vanch007/mlx-MOSS-Transcribe-Diarize  （国内镜像，已同步）
#
# Usage:
#   ./scripts/download_mlx_moss.sh              # 下载（默认 hf-mirror + curl 续传）
#   ./scripts/download_mlx_moss.sh --check      # 仅检测本地是否完整
#   ./scripts/download_mlx_moss.sh /path/to/dir # 指定目录
#
# 环境变量:
#   HF_MIRROR=https://hf-mirror.com   镜像地址
#   USE_HF_OFFICIAL=1                 强制官方源（国内可能较慢）
#   KEEP_PROXY=1                      保留终端代理（默认会 unset 坏代理）
#
# 依赖: pip install -U "huggingface_hub[cli]"  （仅用于文件列表与校验）

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REPO_ID="vanch007/mlx-MOSS-Transcribe-Diarize"
TARGET="${1:-./models/mlx-MOSS-Transcribe-Diarize}"
CHECK_ONLY=0

if [[ "${1:-}" == "--check" ]]; then
  CHECK_ONLY=1
  TARGET="${2:-./models/mlx-MOSS-Transcribe-Diarize}"
elif [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  sed -n '2,20p' "$0"
  exit 0
fi

MIRROR="${HF_MIRROR:-https://hf-mirror.com}"
MAX_WORKERS="${HF_MAX_WORKERS:-2}"
USE_OFFICIAL="${USE_HF_OFFICIAL:-0}"

if [[ "${KEEP_PROXY:-0}" != "1" ]]; then
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
fi

export HF_HUB_DISABLE_XET=1
export HF_HUB_ENABLE_HF_TRANSFER=0
export HF_DOWNLOAD_METHOD="${HF_DOWNLOAD_METHOD:-auto}"

if [[ "$USE_OFFICIAL" == "1" ]]; then
  unset HF_ENDPOINT HUGGINGFACE_HUB_ENDPOINT
  export HF_DOWNLOAD_METHOD=hub
  ENDPOINT_LABEL="https://huggingface.co (official)"
else
  export HF_ENDPOINT="$MIRROR"
  export HUGGINGFACE_HUB_ENDPOINT="$MIRROR"
  ENDPOINT_LABEL="$MIRROR (curl 续传大文件)"
fi

if ! python3 -c "import huggingface_hub" 2>/dev/null; then
  echo "请先安装: pip install -U \"huggingface_hub[cli]\"" >&2
  exit 1
fi

mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

echo "========================================"
echo "MLX MOSS 模型下载 / 检测"
echo "Repo:     $REPO_ID"
echo "Target:   $TARGET"
echo "Endpoint: $ENDPOINT_LABEL"
echo "========================================"
echo ""

set +e
if [[ "$CHECK_ONLY" == "1" ]]; then
  python3 scripts/download_hf_model.py "$REPO_ID" \
    --local-dir "$TARGET" \
    --max-workers "$MAX_WORKERS" \
    --mirror "$MIRROR" \
    --check-only
else
  python3 scripts/download_hf_model.py "$REPO_ID" \
    --local-dir "$TARGET" \
    --max-workers "$MAX_WORKERS" \
    --mirror "$MIRROR"
fi
status=$?
set -e

if [[ "$CHECK_ONLY" == "1" ]]; then
  if [[ $status -eq 0 ]]; then
    echo "检测通过：模型文件已完整。"
  else
    echo "检测未通过：仍有文件缺失或不完整，运行 ./scripts/download_mlx_moss.sh 下载。" >&2
  fi
  exit "$status"
fi

if [[ $status -eq 0 ]]; then
  echo ""
  echo "完成。模型目录: $TARGET"
  echo "MemoFlow .env 建议:"
  echo "  MEMOFLOW_ASR_BACKEND=mlx_moss"
  echo "  MEMOFLOW_ASR_MODEL_PATH=$TARGET"
elif [[ $status -eq 2 ]]; then
  echo "部分文件未完成，重新运行本脚本即可续传。" >&2
  exit 2
else
  exit "$status"
fi
