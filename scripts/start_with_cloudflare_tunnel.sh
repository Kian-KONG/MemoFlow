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

if [[ ! -d frontend/dist ]]; then
  echo "Error: 未找到 frontend/dist。请先构建前端:" >&2
  echo "  cd frontend && npm install && npm run build" >&2
  exit 1
fi

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a
  # 只读取端口，避免 source 整份 .env 带入注释等问题
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
uvicorn memoflow.main:app --host "$HOST" --port "$PORT" &
UVICORN_PID=$!

echo -n "等待服务就绪"
for _ in $(seq 1 60); do
  if curl -fsS "$APP_URL/health" >/dev/null 2>&1; then
    echo " OK"
    break
  fi
  echo -n "."
  sleep 1
done

if ! curl -fsS "$APP_URL/health" >/dev/null 2>&1; then
  echo "" >&2
  echo "Error: MemoFlow 未在 $APP_URL 就绪，请检查日志。" >&2
  exit 1
fi

echo ""
echo "本地访问: $APP_URL"
echo "正在创建 Cloudflare Quick Tunnel（下方会输出公网 URL）..."
echo "提示: 链接是临时的，任何拿到 URL 的人都能访问。Ctrl+C 关闭。"
echo ""

cloudflared tunnel --url "$APP_URL"
