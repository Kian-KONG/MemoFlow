import { apiGet } from './client'
import type { Summary } from './types'

export function getSummary(meetingId: string): Promise<Summary> {
  return apiGet(`/api/meetings/${meetingId}/summary`)
}
