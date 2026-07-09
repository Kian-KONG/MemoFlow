import { useState, type FormEvent } from 'react'
import { searchKnowledge } from '../api/knowledge'
import type { KnowledgeHit } from '../api/types'
import './Panel.css'
import './KnowledgeSearch.css'

interface KnowledgeSearchProps {
  meetingId: string
}

export function KnowledgeSearch({ meetingId }: KnowledgeSearchProps) {
  const [query, setQuery] = useState('')
  const [hits, setHits] = useState<KnowledgeHit[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSearch(event: FormEvent) {
    event.preventDefault()
    if (!query.trim()) return
    setLoading(true)
    setError('')
    try {
      const results = await searchKnowledge(query.trim(), meetingId, 5)
      setHits(results)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setHits(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="knowledge">
      <form className="knowledge-form" onSubmit={handleSearch}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="输入问题以检索本会议相关内容"
        />
        <button type="submit" disabled={loading || !query.trim()}>
          {loading ? '检索中…' : '检索'}
        </button>
      </form>
      {error && <p className="panel-error">{error}</p>}
      {hits && hits.length === 0 && <p className="panel-muted">未找到相关内容</p>}
      {hits && hits.length > 0 && (
        <ul className="hit-list">
          {hits.map((hit) => (
            <li key={hit.chunk_id} className="hit-card">
              <span className="hit-score">相关度: {hit.score.toFixed(2)}</span>
              <p>{hit.text}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
