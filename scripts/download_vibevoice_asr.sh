#!/usr/bin/env bash
# 通过 hf-mirror 国内镜像下载 microsoft/VibeVoice-ASR-HF（全程不走海外 Xet CDN）
#
# Usage: ./scripts/download_vibevoice_asr.sh [target_dir]
# Default target: ./models/VibeVoice-ASR
#
# 依赖:
#   pip install -U "huggingface_hub[cli]"
#   命令行工具: hf
#
# 原理:
#   - HF_ENDPOINT=https://hf-mirror.com  → API / 元数据走国内镜像
#   - HF_HUB_DISABLE_XET=1               → 禁用 Xet，避免 302 到 us.aws.cdn.hf.co
#   - 不使用 hfd/aria2（大文件会被重定向到海外 CDN，国内无梯子常 0 速）

set -euo pipefail

REPO_ID="microsoft/VibeVoice-ASR-HF"
TARGET="${1:-./models/VibeVoice-ASR}"
MAX_WORKERS="${HF_MAX_WORKERS:-4}"
MIRROR="https://hf-mirror.com"

# 国内镜像下载：默认清除终端代理（坏代理会导致 SSL/403）
if [[ "${KEEP_PROXY:-0}" != "1" ]]; then
  unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
fi

# 强制全程走镜像 + 经典 LFS 下载路径
export HF_ENDPOINT="$MIRROR"
export HUGGINGFACE_HUB_ENDPOINT="$MIRROR"
export HF_HUB_DISABLE_XET=1
export HF_HUB_ENABLE_HF_TRANSFER=0
export HF_HUB_DISABLE_PROGRESS_BARS=1
export TQDM_DISABLE=1

if ! command -v hf >/dev/null 2>&1; then
  echo "Error: 未找到 hf 命令。请安装:" >&2
  echo "  pip install -U \"huggingface_hub[cli]\"" >&2
  exit 1
fi

mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

human_bytes() {
  awk -v b="${1:-0}" 'BEGIN{
    u="B KB MB GB TB"; n=split(u,a," "); i=1;
    while (b>=1000 && i<n) { b/=1000; i++ }
    printf (i==1?"%d%s":"%.2f%s"), b, a[i]
  }'
}

calc_local_bytes() {
  python3 - "$TARGET" <<'PY'
import sys
from pathlib import Path
root = Path(sys.argv[1])
total = 0
for p in root.rglob("*"):
    if p.is_file() and ".hfd" not in p.parts and not p.name.endswith(".aria2"):
        total += p.stat().st_size
print(total)
PY
}

print_status() {
  python3 - "$TARGET" <<'PY' 2>/dev/null || true
import sys
from pathlib import Path
root = Path(sys.argv[1])
manifest = root / ".hfd" / "manifest"
need = 16673547108  # fallback total ~16.67GB
if manifest.exists():
    need = sum(int(l.split("\t",1)[0]) for l in manifest.read_text().splitlines() if l.strip())
have = 0
for p in root.rglob("*"):
    if p.is_file() and ".hfd" not in p.parts and not p.name.endswith(".aria2"):
        have += p.stat().st_size
pct = 100.0 * have / need if need else 0
print(f"本地已有: {have/1e9:.2f} / {need/1e9:.2f} GB ({pct:.1f}%)")
PY
}

echo "========================================"
echo "Repo:        $REPO_ID"
echo "Target:      $TARGET"
echo "Mirror:      $MIRROR"
echo "Xet CDN:     disabled (HF_HUB_DISABLE_XET=1)"
echo "Workers:     $MAX_WORKERS"
echo "Proxy:       HTTP_PROXY=${HTTP_PROXY:-<empty>} HTTPS_PROXY=${HTTPS_PROXY:-<empty>}"
echo "========================================"
print_status

# 单行进度：总已下载字节 / 速度
monitor_progress() {
  local prev_bytes prev_ts
  prev_bytes=$(calc_local_bytes)
  prev_ts=$(date +%s)
  while true; do
    sleep 2
    local now_bytes now_ts dt delta speed
    now_bytes=$(calc_local_bytes)
    now_ts=$(date +%s)
    dt=$((now_ts - prev_ts)); (( dt < 1 )) && dt=1
    delta=$((now_bytes - prev_bytes)); (( delta < 0 )) && delta=0
    speed=$((delta / dt))
    printf '\r[下载中] 已下载 %s | 速度 %s/s   ' "$(human_bytes "$now_bytes")" "$(human_bytes "$speed")"
    prev_bytes=$now_bytes
    prev_ts=$now_ts
  done
}

cleanup() {
  kill "$MON_PID" 2>/dev/null || true
  wait "$MON_PID" 2>/dev/null || true
  printf '\n'
}
trap cleanup EXIT INT TERM

echo "开始/续传（hf + hf-mirror，单行进度如下）..."
monitor_progress &
MON_PID=$!

set +e
hf download "$REPO_ID" \
  --local-dir "$TARGET" \
  --max-workers "$MAX_WORKERS"
status=$?
set -e

if [[ $status -ne 0 ]]; then
  echo "" >&2
  echo "下载失败 (exit=$status)。" >&2
  echo "请确认:" >&2
  echo "  1) 已安装: pip install -U \"huggingface_hub[cli]\"" >&2
  echo "  2) 未开干扰代理（或 KEEP_PROXY=1 并配置正确端口）" >&2
  echo "  3) 可重跑续传，勿删除 $TARGET" >&2
  exit "$status"
fi

print_status
echo "Done. Model saved to: $TARGET"
