/** 解析 API 返回的时间字符串（后端为 UTC，SQLite 可能去掉时区后缀）。 */
export function parseApiDate(value: string): Date {
  const trimmed = value.trim()
  if (!trimmed) return new Date(NaN)

  // 已带时区：Z / +08:00 等
  if (/[zZ]$/.test(trimmed) || /[+-]\d{2}:\d{2}$/.test(trimmed)) {
    return new Date(trimmed)
  }

  // 无时区后缀 → 按 UTC 解析（避免在东八区被当成本地时间少算 8 小时）
  const normalized = trimmed.includes('T') ? trimmed : trimmed.replace(' ', 'T')
  return new Date(`${normalized}Z`)
}

export function formatElapsed(since: string, nowMs: number = Date.now()): string {
  const started = parseApiDate(since)
  const startedMs = started.getTime()
  if (Number.isNaN(startedMs)) return '—'

  const seconds = Math.max(0, Math.floor((nowMs - startedMs) / 1000))
  if (seconds < 60) return `${seconds} 秒`
  const minutes = Math.floor(seconds / 60)
  const secs = seconds % 60
  if (minutes < 60) return `${minutes} 分 ${secs} 秒`
  const hours = Math.floor(minutes / 60)
  return `${hours} 小时 ${minutes % 60} 分`
}
