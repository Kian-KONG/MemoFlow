#!/usr/bin/env bash
# 本地冒烟测试：验证后端 API 与前端静态资源是否可用。
#
# Usage:
#   ./scripts/smoke_test.sh
#   ./scripts/smoke_test.sh http://127.0.0.1:8000
#
# 通过 Cloudflare 隧道测试（将 URL 换成终端输出的 trycloudflare 地址）：
#   ./scripts/smoke_test.sh https://xxxx.trycloudflare.com

set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
BASE="${BASE%/}"

echo "=== MemoFlow Smoke Test ==="
echo "Target: $BASE"
echo ""

fail() {
  echo "FAIL: $1" >&2
  exit 1
}

check() {
  local name="$1"
  local url="$2"
  local expect="${3:-200}"
  local code
  code=$(curl -sS -o /tmp/memoflow_smoke_body.txt -w "%{http_code}" "$url" || echo "000")
  if [[ "$code" != "$expect" ]]; then
    echo "--- response body (first 500 chars) ---"
    head -c 500 /tmp/memoflow_smoke_body.txt 2>/dev/null || true
    echo ""
    fail "$name → HTTP $code (expected $expect) [$url]"
  fi
  echo "OK   $name (HTTP $code)"
}

[[ -d frontend/dist ]] || fail "frontend/dist 不存在，请先: cd frontend && npm run build"

check "health" "$BASE/health"
check "meetings API" "$BASE/api/meetings"
check "system status" "$BASE/api/system/status"
check "SPA index" "$BASE/"

if [[ "$BASE" == http://127.0.0.1:* ]] || [[ "$BASE" == http://localhost:* ]]; then
  echo ""
  echo "提示: 本地 UI → $BASE/"
  echo "      API 文档 → $BASE/docs"
fi

echo ""
echo "=== 全部通过 ==="
