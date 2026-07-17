#!/usr/bin/env bash
# 启动 MemoFlow 并通过 Cloudflare Quick Tunnel 临时暴露给外网访问。
#
# Usage: ./scripts/start_with_cloudflare_tunnel.sh
#
# 依赖:
#   brew install cloudflared
#   pip install -e ".[dev]"
#   cd frontend && npm install && npm run build
#
# 另一台设备用终端输出的 https://xxxx.trycloudflare.com 访问。
# Ctrl+C 停止隧道和应用。

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HOST="${MEMOFLOW_HOST:-127.0.0.1}"
PORT="${MEMOFLOW_PORT:-8000}"
LOG_FILE="${ROOT}/data/uvicorn.log"

if [[ ! -d frontend/dist ]]; then
  echo "Error: 未找到 frontend/dist。请先构建前端:" >&2
  echo "  cd frontend && npm install && npm run build" >&2
  exit 1
fi

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  port_line=$(grep -E '^MEMOFLOW_PORT=' .env | tail -1 || true)
  if [[ -n "$port_line" ]]; then
    PORT="${port_line#MEMOFLOW_PORT=}"
    PORT="${PORT%%#*}"
    PORT="$(echo "$PORT" | xargs)"
  fi
  host_line=$(grep -E '^MEMOFLOW_HOST=' .env | tail -1 || true)
  if [[ -n "$host_line" ]]; then
    HOST="${host_line#MEMOFLOW_HOST=}"
    HOST="${HOST%%#*}"
    HOST="$(echo "$HOST" | xargs)"
  fi
  set +a
fi

APP_URL="http://${HOST}:${PORT}"

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "Error: 未找到 cloudflared。请安装: brew install cloudflared" >&2
  exit 1
fi

if ! command -v uvicorn >/dev/null 2>&1; then
  echo "Error: 未找到 uvicorn。请先: pip install -e \".[dev]\"" >&2
  exit 1
fi

mkdir -p "${ROOT}/data"

UVICORN_PID=""
cleanup() {
  if [[ -n "$UVICORN_PID" ]] && kill -0 "$UVICORN_PID" 2>/dev/null; then
    echo ""
    echo "正在停止 MemoFlow (pid=$UVICORN_PID)..."
    kill "$UVICORN_PID" 2>/dev/null || true
    wait "$UVICORN_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

echo "启动 MemoFlow: $APP_URL"
echo "日志: $LOG_FILE"
PYTHONPATH="${ROOT}/src" uvicorn memoflow.main:app --host "$HOST" --port "$PORT" >>"$LOG_FILE" 2>&1 &
UVICORN_PID=$!

echo -n "等待服务就绪"
ready=0
for _ in $(seq 1 90); do
  if curl -fsS "$APP_URL/health" >/dev/null 2>&1 && curl -fsS "$APP_URL/api/meetings" >/dev/null 2>&1; then
    echo " OK"
    ready=1
    break
  fi
  if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
    echo " FAIL (进程已退出)"
    echo "--- uvicorn 日志 (最后 40 行) ---" >&2
    tail -40 "$LOG_FILE" >&2 || true
    exit 1
  fi
  echo -n "."
  sleep 1
done

if [[ "$ready" -ne 1 ]]; then
  echo "" >&2
  echo "Error: MemoFlow 未在 $APP_URL 就绪。" >&2
  echo "请检查日志: $LOG_FILE" >&2
  tail -40 "$LOG_FILE" >&2 || true
  exit 1
fi

echo ""
echo "本地访问: $APP_URL"
echo "本地测试: ./scripts/smoke_test.sh $APP_URL"
echo "正在创建 Cloudflare Quick Tunnel（下方会输出公网 URL）..."
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  安全警告 — Cloudflare 公网 URL 无任何身份认证               ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  任何拿到链接的人都可以：                                    ║"
echo "║    • 上传 / 列出 / 查看会议录音与元数据                      ║"
echo "║    • 调用管理类 API（如切换 ASR 后端等设置）                 ║"
echo "║  仅限临时调试 / 演示。请勿长期对外暴露。                     ║"
echo "║  建议：私有网络（Tailscale/VPN）或反向代理鉴权后再公开。     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "提示: 链接是临时的；Ctrl+C 关闭隧道与应用。"
echo "若外网 502，请确认本脚本终端未关闭，并查看 $LOG_FILE"
echo "大文件上传易 524 超时：请在本机 $APP_URL 上传，或压缩音频后再经隧道传"
echo ""

cloudflared tunnel --url "$APP_URL"
