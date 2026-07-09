import { apiGet, apiPostJson } from './client'
import type { Meeting } from './types'

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
      let detail = `HTTP ${xhr.status}`
      try {
        const data = JSON.parse(xhr.responseText) as Meeting & { detail?: string }
        if (xhr.status >= 200 && xhr.status < 300) {
          onProgress?.({ loaded: 1, total: 1, percent: 100 })
          resolve(data)
          return
        }
        if (typeof data.detail === 'string') detail = data.detail
      } catch {
        /* use default detail */
      }
      reject(new Error(detail))
    }

    xhr.onerror = () => reject(new Error('网络错误，上传失败'))
    xhr.onabort = () => reject(new Error('上传已取消'))
    xhr.send(form)
  })
}
