export class ApiError extends Error {
  status: number
  bodyPreview: string

  constructor(status: number, message: string, bodyPreview = '') {
    super(message)
    this.status = status
    this.name = 'ApiError'
    this.bodyPreview = bodyPreview
  }
}

async function readBodyPreview(response: Response): Promise<string> {
  try {
    const text = await response.text()
    const trimmed = text.trim()
    if (!trimmed) return ''
    return trimmed.length > 200 ? `${trimmed.slice(0, 200)}…` : trimmed
  } catch {
    return ''
  }
}

async function parseError(response: Response, bodyPreview: string): Promise<string> {
  const contentType = response.headers.get('content-type') ?? ''

  if (contentType.includes('application/json') && bodyPreview) {
    try {
      const data = JSON.parse(bodyPreview) as { detail?: unknown }
      if (typeof data.detail === 'string') return data.detail
      if (Array.isArray(data.detail)) {
        return data.detail
          .map((item) =>
            typeof item === 'object' && item && 'msg' in item ? String(item.msg) : String(item),
          )
          .join('; ')
      }
    } catch {
      /* fall through */
    }
  }

  if (contentType.includes('text/html') || bodyPreview.startsWith('<!')) {
    if (response.status === 502) {
      return 'Cloudflare 无法连接本机后端（502）。请确认 uvicorn 正在运行且隧道未断开。'
    }
    return `服务器返回 HTML 而非 JSON（HTTP ${response.status}），可能未正确代理到 API。`
  }

  if (bodyPreview) return bodyPreview
  return response.statusText || `HTTP ${response.status}`
}

export async function apiGet<T>(path: string): Promise<T> {
  let response: Response
  try {
    response = await fetch(path)
  } catch (err) {
    throw err instanceof TypeError
      ? err
      : new Error(err instanceof Error ? err.message : '网络请求失败')
  }

  if (!response.ok) {
    const bodyPreview = await readBodyPreview(response)
    const message = await parseError(response, bodyPreview)
    throw new ApiError(response.status, message, bodyPreview)
  }
  return (await response.json()) as T
}

export async function apiPostJson<T>(path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method: 'POST',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (err) {
    throw err instanceof TypeError
      ? err
      : new Error(err instanceof Error ? err.message : '网络请求失败')
  }

  if (!response.ok) {
    const bodyPreview = await readBodyPreview(response)
    const message = await parseError(response, bodyPreview)
    throw new ApiError(response.status, message, bodyPreview)
  }
  return (await response.json()) as T
}

/** 探测后端是否可达（用于页面顶部状态条）。 */
export async function probeBackend(): Promise<{ ok: boolean; detail: string }> {
  try {
    const health = await fetch('/health')
    if (!health.ok) {
      return { ok: false, detail: `健康检查失败 (HTTP ${health.status})` }
    }
    const meetings = await fetch('/api/meetings?limit=1')
    if (!meetings.ok) {
      const text = await meetings.text()
      return {
        ok: false,
        detail: `API 不可用 (HTTP ${meetings.status})${text ? `: ${text.slice(0, 120)}` : ''}`,
      }
    }
    return { ok: true, detail: '后端连接正常' }
  } catch {
    return { ok: false, detail: '无法连接后端，请确认服务已启动' }
  }
}
