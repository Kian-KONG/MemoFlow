#!/usr/bin/env bash
# 按 MEMOFLOW_ASR_BACKEND 下载对应 ASR 模型（真实断点续传，跳过已完整文件）
#
# Usage:
#   ./scripts/download_asr_model.sh [target_dir]
#   ./scripts/download_asr_model.sh --check-only [target_dir]
#   MEMOFLOW_ASR_BACKEND=moss_hf ./scripts/download_asr_model.sh
#
# 默认优先 ModelScope（国内更稳定）；mlx_moss 仅 HF 镜像可用。
#
# 环境变量:
#   USE_MODELSCOPE=1          优先 ModelScope（默认开启）
#   USE_MODELSCOPE=0          禁用 ModelScope，仅走 HF 镜像/官方
#   USE_HF_OFFICIAL=1         强制 HF 官方源
#   HF_MIRROR=https://hf-mirror.com
#   KEEP_PROXY=1              保留终端代理（默认会 unset）
#
# 依赖:
#   pip install -e ".[download]"   # modelscope + huggingface_hub

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

read -r HF_REPO_ID MODELSCOPE_REPO_ID DEFAULT_TARGET <<< "$(
  python3 -c "
from memoflow.infrastructure.ai.asr_model_sources import get_source
import os
s = get_source('${BACKEND}')
hf = os.environ.get('MEMOFLOW_ASR_MODEL_ID') or s.hf_repo_id
ms = s.modelscope_repo_id or ''
print(hf, ms, s.default_local_dir)
"
)"

CHECK_ONLY=0
TARGET="$DEFAULT_TARGET"
if [[ "${1:-}" == "--check" || "${1:-}" == "--check-only" ]]; then
  CHECK_ONLY=1
  TARGET="${2:-$DEFAULT_TARGET}"
elif [[ -n "${1:-}" ]]; then
  TARGET="$1"
fi
USE_MODELSCOPE="${USE_MODELSCOPE:-1}"
MIRROR="${HF_MIRROR:-https://hf-mirror.com}"
MAX_WORKERS="${HF_MAX_WORKERS:-4}"
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

echo "Backend:       $BACKEND"
echo "HF Repo:       $HF_REPO_ID"
echo "ModelScope:    ${MODELSCOPE_REPO_ID:-（无，走 HF）}"
echo "Target:        $TARGET"
echo "USE_MODELSCOPE: $USE_MODELSCOPE"
echo "HF Endpoint:   $ENDPOINT_LABEL"
echo ""

mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

download_hf() {
  if [[ -n "${HF_DOWNLOAD_METHOD:-}" && "$CHECK_ONLY" == "1" ]]; then
    python3 scripts/download_hf_model.py "$HF_REPO_ID" \
      --local-dir "$TARGET" \
      --max-workers "$MAX_WORKERS" \
      --mirror "$MIRROR" \
      --method "$HF_DOWNLOAD_METHOD" \
      --check-only
  elif [[ -n "${HF_DOWNLOAD_METHOD:-}" ]]; then
    python3 scripts/download_hf_model.py "$HF_REPO_ID" \
      --local-dir "$TARGET" \
      --max-workers "$MAX_WORKERS" \
      --mirror "$MIRROR" \
      --method "$HF_DOWNLOAD_METHOD"
  elif [[ "$CHECK_ONLY" == "1" ]]; then
    python3 scripts/download_hf_model.py "$HF_REPO_ID" \
      --local-dir "$TARGET" \
      --max-workers "$MAX_WORKERS" \
      --mirror "$MIRROR" \
      --check-only
  else
    python3 scripts/download_hf_model.py "$HF_REPO_ID" \
      --local-dir "$TARGET" \
      --max-workers "$MAX_WORKERS" \
      --mirror "$MIRROR"
  fi
}

download_hf_official() {
  echo ""
  echo "HF 镜像下载失败，回退 huggingface.co 官方源重试..."
  unset HF_ENDPOINT HUGGINGFACE_HUB_ENDPOINT
  python3 scripts/download_hf_model.py "$HF_REPO_ID" \
    --local-dir "$TARGET" \
    --max-workers "$MAX_WORKERS" \
    --method hub
}

download_modelscope() {
  if [[ "$CHECK_ONLY" == "1" ]]; then
    python3 scripts/download_modelscope_model.py "$MODELSCOPE_REPO_ID" \
      --local-dir "$TARGET" \
      --max-workers "$MAX_WORKERS" \
      --check-only
  else
    python3 scripts/download_modelscope_model.py "$MODELSCOPE_REPO_ID" \
      --local-dir "$TARGET" \
      --max-workers "$MAX_WORKERS"
  fi
}

# mlx_moss 或禁用 ModelScope 时仅走 HF
if [[ "$BACKEND" == "mlx_moss" || "$USE_MODELSCOPE" != "1" || -z "$MODELSCOPE_REPO_ID" ]]; then
  if [[ "$BACKEND" == "mlx_moss" ]]; then
    echo "mlx_moss 模型仅 Hugging Face 可用，使用 HF 镜像下载..."
  fi
  if ! python3 -c "import huggingface_hub" 2>/dev/null; then
    echo "Error: 未安装 huggingface_hub。请运行:" >&2
    echo "  pip install -e \".[download]\"" >&2
    exit 1
  fi
  set +e
  download_hf
  status=$?
  set -e
  if [[ $status -ne 0 && "$USE_OFFICIAL" != "1" ]]; then
    set +e
    download_hf_official
    status=$?
    set -e
  fi
else
  if ! python3 -c "import modelscope" 2>/dev/null; then
    echo "Warning: 未安装 modelscope，回退 HF 镜像下载。" >&2
    USE_MODELSCOPE=0
  fi
  if [[ "$USE_MODELSCOPE" == "1" ]]; then
    set +e
    download_modelscope
    status=$?
    set -e
    if [[ "$CHECK_ONLY" == "1" ]]; then
      : # check-only：0=完整，2=缺失，1=API 错误；不因 2 回退 HF
    elif [[ $status -ne 0 ]]; then
      echo ""
      echo "ModelScope 下载失败，回退 HF 镜像..."
      if ! python3 -c "import huggingface_hub" 2>/dev/null; then
        echo "Error: 未安装 huggingface_hub。请运行:" >&2
        echo "  pip install -e \".[download]\"" >&2
        exit 1
      fi
      set +e
      download_hf
      status=$?
      set -e
      if [[ $status -ne 0 && "$USE_OFFICIAL" != "1" ]]; then
        set +e
        download_hf_official
        status=$?
        set -e
      fi
    fi
    # check-only 且 ModelScope API 失败时，尝试 HF 检测
    if [[ "$CHECK_ONLY" == "1" && $status -eq 1 ]]; then
      echo ""
      echo "ModelScope 检测失败，尝试 HF 镜像检测..."
      if python3 -c "import huggingface_hub" 2>/dev/null; then
        set +e
        download_hf
        status=$?
        set -e
      fi
    fi
  else
    if ! python3 -c "import huggingface_hub" 2>/dev/null; then
      echo "Error: 未安装 huggingface_hub。请运行:" >&2
      echo "  pip install -e \".[download]\"" >&2
      exit 1
    fi
    set +e
    download_hf
    status=$?
    set -e
    if [[ $status -ne 0 && "$USE_OFFICIAL" != "1" ]]; then
      set +e
      download_hf_official
      status=$?
      set -e
    fi
  fi
fi

if [[ "$CHECK_ONLY" == "1" ]]; then
  if [[ $status -eq 0 ]]; then
    echo "检测通过：模型文件已完整。"
  else
    echo "检测未通过：仍有文件缺失或不完整，运行 $0 下载。" >&2
  fi
  exit "$status"
fi

if [[ $status -eq 0 ]]; then
  echo "Done. Model saved to: $TARGET"
elif [[ $status -eq 2 ]]; then
  echo "部分文件未完成，可重新运行本脚本续传: $0" >&2
  exit 2
else
  exit "$status"
fi
