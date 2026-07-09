#!/usr/bin/env bash
# 下载 VibeVoice-ASR（兼容旧命令，内部调用 download_asr_model.sh）
set -euo pipefail
export MEMOFLOW_ASR_BACKEND=vibevoice
exec "$(cd "$(dirname "$0")" && pwd)/download_asr_model.sh" "${1:-./models/VibeVoice-ASR}"
