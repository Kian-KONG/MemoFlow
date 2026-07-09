import { apiGet, apiPostJson, ApiError } from './client'
import type { Meeting } from './types'
import { statusHint } from '../lib/apiError'

export function listMeetings(limit = 100): Promise<Meeting[]> {
  return apiGet(`/api/meetings?limit=${limit}`)
}

export function getMeeting(id: string): Promise<Meeting> {
  return apiGet(`/api/meetings/${id}`)
}

export function retryMeeting(id: string): Promise<Meeting> {
  return apiPostJson(`/api/meetings/${id}/retry`)
}

export interface UploadProgress {
  loaded: number
  total: number
  percent: number
}

function parseXhrError(status: number, responseText: string): string {
  if (responseText.trim().startsWith('<!')) {
    if (status === 502) {
      return 'Cloudflare 无法连接本机后端（502）。请确认 uvicorn 正在运行且隧道未断开。'
    }
    if (status === 524) {
      return 'Cloudflare 上传超时（524）。隧道对大文件/慢网络约 100 秒限制，请改在本机上传或缩小文件。'
    }
    return `服务器返回 HTML 而非 JSON（HTTP ${status}），多为 Cloudflare 网关错误页。`
  }

  try {
    const data = JSON.parse(responseText) as { detail?: string }
    if (typeof data.detail === 'string') return data.detail
  } catch {
    /* ignore */
  }

  const hint = statusHint(status)
  const base = responseText.trim() || `HTTP ${status}`
  return hint ? `${base}\n${hint}` : base
}

/** 使用 XHR 上传，以便拿到真实字节进度；仅在 2xx 且解析 JSON 后 resolve。 */
export function uploadMeeting(
  file: File,
  title: string,
  onProgress?: (progress: UploadProgress) => void,
): Promise<Meeting> {
  return new Promise((resolve, reject) => {
    const form = new FormData()
    form.append('file', file)
    if (title.trim()) {
      form.append('title', title.trim())
    }

    const xhr = new XMLHttpRequest()
    xhr.open('POST', '/api/meetings')

    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable || !onProgress) return
      const percent = Math.min(100, Math.round((event.loaded / event.total) * 100))
      onProgress({ loaded: event.loaded, total: event.total, percent })
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          const data = JSON.parse(xhr.responseText) as Meeting
          onProgress?.({ loaded: 1, total: 1, percent: 100 })
          resolve(data)
          return
        } catch {
          reject(new Error('上传成功但响应不是有效 JSON'))
          return
        }
      }
      reject(new ApiError(xhr.status, parseXhrError(xhr.status, xhr.responseText), xhr.responseText))
    }

    xhr.onerror = () =>
      reject(
        new Error(
          '网络错误：无法连接后端。请确认 uvicorn 已启动；通过 Cloudflare 访问时隧道脚本需保持运行。',
        ),
      )
    xhr.onabort = () => reject(new Error('上传已取消'))
    xhr.send(form)
  })
}
