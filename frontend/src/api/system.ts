import { apiGet } from './client'
import type { SystemStatus } from './types'

export function getSystemStatus(): Promise<SystemStatus> {
  return apiGet('/api/system/status')
}
