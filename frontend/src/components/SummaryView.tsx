import type { Summary } from '../api/types'
import './Panel.css'

interface SummaryViewProps {
  summary: Summary | null
  loading: boolean
  error: string
}

export function SummaryView({ summary, loading, error }: SummaryViewProps) {
  if (loading) return <p className="panel-muted">加载摘要中…</p>
  if (error) return <p className="panel-error">{error}</p>
  if (!summary) return <p className="panel-muted">摘要尚未生成，处理完成后会自动显示。</p>

  return (
    <div className="panel">
      <h3>会议概览</h3>
      <p>{summary.overview}</p>

      <h3>关键要点</h3>
      {summary.key_points.length === 0 ? (
        <p className="panel-muted">无</p>
      ) : (
        <ul>
          {summary.key_points.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      )}

      <h3>决策</h3>
      {summary.decisions.length === 0 ? (
        <p className="panel-muted">无</p>
      ) : (
        <ul>
          {summary.decisions.map((d) => (
            <li key={d.id}>{d.description}</li>
          ))}
        </ul>
      )}

      <h3>行动项</h3>
      {summary.action_items.length === 0 ? (
        <p className="panel-muted">无</p>
      ) : (
        <ul>
          {summary.action_items.map((item) => (
            <li key={item.id}>
              [{item.status}] {item.description}（负责人: {item.owner || '未指定'}）
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
