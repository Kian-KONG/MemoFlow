import { apiGet, apiPutJson } from './client'
import type { SelectAsrBackendResponse, SystemStatus } from './types'

export function getSystemStatus(): Promise<SystemStatus> {
  return apiGet('/api/system/status')
}

export function selectAsrBackend(backend: string): Promise<SelectAsrBackendResponse> {
  return apiPutJson('/api/system/asr-backend', { backend })
}
