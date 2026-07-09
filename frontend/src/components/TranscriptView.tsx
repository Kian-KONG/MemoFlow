import type { Transcript } from '../api/types'
import './Panel.css'

interface TranscriptViewProps {
  transcript: Transcript | null
  loading: boolean
  error: string
}

export function TranscriptView({ transcript, loading, error }: TranscriptViewProps) {
  if (loading) return <p className="panel-muted">加载转写中…</p>
  if (error) return <p className="panel-error">{error}</p>
  if (!transcript) return <p className="panel-muted">转写尚未完成，处理中会自动显示。</p>

  return (
    <div className="panel">
      <p className="panel-muted">共 {transcript.utterances.length} 条话语</p>
      <ul className="utterance-list">
        {transcript.utterances.map((u) => {
          const speaker = u.speaker?.display_name || u.speaker?.label || '未知说话人'
          return (
            <li key={u.id}>
              <span className="utt-meta">
                [{u.start.toFixed(1)}s] {speaker}:
              </span>{' '}
              {u.text}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
