import { ApiError } from '../api/client'

const STATUS_HINTS: Record<number, string> = {
  502: '网关错误 (502)：后端未响应。请确认 uvicorn 已启动且 Cloudflare 隧道指向正确端口。',
  503: '服务不可用 (503)：后端可能正在启动或已崩溃，请查看终端日志。',
  504: '网关超时 (504)：请求耗时过长，长音频处理时可能出现。',
}

export function statusHint(status: number): string {
  return STATUS_HINTS[status] ?? ''
}

/** 将 API / 网络错误格式化为用户可读说明（含排查建议）。 */
export function formatApiError(err: unknown, context?: string): string {
  const prefix = context ? `${context}：` : ''

  if (err instanceof ApiError) {
    const hint = statusHint(err.status)
    const base = `${prefix}HTTP ${err.status} — ${err.message}`
    return hint ? `${base}\n${hint}` : base
  }

  if (err instanceof TypeError) {
    return (
      `${prefix}无法连接后端。\n` +
      '请确认：\n' +
      '1. 已运行 PYTHONPATH=src uvicorn memoflow.main:app --host 127.0.0.1 --port 8000\n' +
      '2. 生产模式已执行 cd frontend && npm run build\n' +
      '3. Cloudflare 隧道脚本在本机终端保持运行'
    )
  }

  if (err instanceof Error) {
    return `${prefix}${err.message}`
  }

  return `${prefix}${String(err)}`
}
