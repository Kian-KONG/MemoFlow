import { apiPostJson } from './client'
import type { KnowledgeHit } from './types'

export function searchKnowledge(
  query: string,
  meetingId?: string,
  topK = 5,
): Promise<KnowledgeHit[]> {
  return apiPostJson('/api/knowledge/search', {
    query,
    meeting_id: meetingId ?? null,
    top_k: topK,
  })
}
