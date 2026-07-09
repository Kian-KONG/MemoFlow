#!/usr/bin/env bash
# 按 MEMOFLOW_ASR_BACKEND 下载对应 ASR 模型（真实断点续传，跳过已完整文件）
#
# Usage:
#   ./scripts/download_asr_model.sh [target_dir]
#   MEMOFLOW_ASR_BACKEND=moss_hf ./scripts/download_asr_model.sh
#
# Mac Apple Silicon 默认下载 MLX 版 MOSS（~1.8GB）:
#   vanch007/mlx-MOSS-Transcribe-Diarize
#
# 依赖: pip install -U "huggingface_hub[cli]"

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKEND="${MEMOFLOW_ASR_BACKEND:-}"
if [[ -z "$BACKEND" ]]; then
  if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" == "arm64" ]]; then
    BACKEND="mlx_moss"
  else
    BACKEND="vibevoice"
  fi
fi

case "$BACKEND" in
  mlx_moss)
    REPO_ID="${MEMOFLOW_ASR_MODEL_ID:-vanch007/mlx-MOSS-Transcribe-Diarize}"
    TARGET="${1:-./models/mlx-MOSS-Transcribe-Diarize}"
    ;;
  moss_hf)
    REPO_ID="${MEMOFLOW_ASR_MODEL_ID:-OpenMOSS-Team/MOSS-Transcribe-Diarize}"
    TARGET="${1:-./models/MOSS-Transcribe-Diarize}"
    ;;
  vibevoice)
    REPO_ID="${MEMOFLOW_ASR_MODEL_ID:-microsoft/VibeVoice-ASR-HF}"
    TARGET="${1:-./models/VibeVoice-ASR}"
    ;;
  *)
    echo "未知 MEMOFLOW_ASR_BACKEND=$BACKEND（可选: mlx_moss | moss_hf | vibevoice）" >&2
    exit 1
    ;;
esac

MIRROR="${HF_MIRROR:-https://hf-mirror.com}"
MAX_WORKERS="${HF_MAX_WORKERS:-4}"
# 默认走镜像；若镜像 HEAD 校验失败可设 USE_HF_OFFICIAL=1 直连 huggingface.co
USE_OFFICIAL="${USE_HF_OFFICIAL:-0}"

if [[ "${KEEP_PROXY:-0}" != "1" ]]; then
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
fi

if [[ "$USE_OFFICIAL" == "1" ]]; then
  unset HF_ENDPOINT HUGGINGFACE_HUB_ENDPOINT
  ENDPOINT_LABEL="https://huggingface.co (official)"
else
  export HF_ENDPOINT="$MIRROR"
  export HUGGINGFACE_HUB_ENDPOINT="$MIRROR"
  ENDPOINT_LABEL="$MIRROR"
fi
export HF_HUB_DISABLE_XET=1
export HF_HUB_ENABLE_HF_TRANSFER=0

if ! python3 -c "import huggingface_hub" 2>/dev/null; then
  echo "Error: 未安装 huggingface_hub。请运行:" >&2
  echo "  pip install -U \"huggingface_hub[cli]\"" >&2
  exit 1
fi

mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

echo "Backend:  $BACKEND"
echo "Repo:     $REPO_ID"
echo "Target:   $TARGET"
echo "Endpoint: $ENDPOINT_LABEL"
echo ""

set +e
python3 scripts/download_hf_model.py "$REPO_ID" \
  --local-dir "$TARGET" \
  --max-workers "$MAX_WORKERS" \
  --mirror "$MIRROR" \
  "${HF_DOWNLOAD_METHOD:+--method $HF_DOWNLOAD_METHOD}"
status=$?
set -e

# 镜像 huggingface_hub 失败时，回退官方源
if [[ $status -ne 0 && "$USE_OFFICIAL" != "1" ]]; then
  echo ""
  echo "镜像下载失败，回退 huggingface.co 官方源重试..."
  unset HF_ENDPOINT HUGGINGFACE_HUB_ENDPOINT
  set +e
  python3 scripts/download_hf_model.py "$REPO_ID" \
    --local-dir "$TARGET" \
    --max-workers "$MAX_WORKERS" \
    --method hub
  status=$?
  set -e
fi

if [[ $status -eq 0 ]]; then
  echo "Done. Model saved to: $TARGET"
elif [[ $status -eq 2 ]]; then
  echo "部分文件未完成，可重新运行本脚本续传: $0" >&2
  exit 2
else
  exit "$status"
fi
