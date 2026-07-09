import { apiGet } from './client'
import type { Transcript } from './types'

export function getTranscript(meetingId: string): Promise<Transcript> {
  return apiGet(`/api/meetings/${meetingId}/transcript`)
}
