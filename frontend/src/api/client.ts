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

function previewBody(text: string, max = 200): string {
  const trimmed = text.trim()
  if (!trimmed) return ''
  return trimmed.length > max ? `${trimmed.slice(0, max)}…` : trimmed
}

async function readResponseBody(response: Response): Promise<string> {
  try {
    return await response.text()
  } catch {
    return ''
  }
}

async function parseError(response: Response, bodyText: string): Promise<string> {
  const trimmed = bodyText.trim()
  const contentType = response.headers.get('content-type') ?? ''

  if (contentType.includes('application/json') && trimmed) {
    try {
      const data = JSON.parse(trimmed) as { detail?: unknown }
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

  if (contentType.includes('text/html') || trimmed.startsWith('<!')) {
    if (response.status === 502) {
      return 'Cloudflare 无法连接本机后端（502）。请确认 uvicorn 正在运行且隧道未断开。'
    }
    if (response.status === 524) {
      return 'Cloudflare 上传超时（524）。隧道对大文件/慢网络约 100 秒限制，请改在本机上传或缩小文件。'
    }
    return `服务器返回 HTML 而非 JSON（HTTP ${response.status}），多为 Cloudflare 网关错误页。`
  }

  if (trimmed) return previewBody(trimmed)
  return response.statusText || `HTTP ${response.status}`
}

async function requestJson<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (err) {
    throw err instanceof TypeError
      ? err
      : new Error(err instanceof Error ? err.message : '网络请求失败')
  }

  if (!response.ok) {
    const bodyText = await readResponseBody(response)
    const message = await parseError(response, bodyText)
    throw new ApiError(response.status, message, previewBody(bodyText))
  }

  return (await response.json()) as T
}

export async function apiGet<T>(path: string): Promise<T> {
  return requestJson<T>('GET', path)
}

export async function apiPostJson<T>(path: string, body?: unknown): Promise<T> {
  return requestJson<T>('POST', path, body)
}

export async function apiPutJson<T>(path: string, body: unknown): Promise<T> {
  return requestJson<T>('PUT', path, body)
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
