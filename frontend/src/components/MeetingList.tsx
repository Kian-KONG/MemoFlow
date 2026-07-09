import { Link } from 'react-router-dom'
import type { Meeting } from '../api/types'
import { STATUS_LABELS } from '../lib/status'
import './MeetingList.css'

interface MeetingListProps {
  meetings: Meeting[]
  loading: boolean
  error: string
  onRefresh: () => void
}

function statusClass(status: string): string {
  if (status === 'completed') return 'status-completed'
  if (status === 'failed') return 'status-failed'
  if (status === 'uploaded') return 'status-queued'
  return 'status-active'
}

export function MeetingList({ meetings, loading, error, onRefresh }: MeetingListProps) {
  return (
    <section className="meeting-list">
      <div className="meeting-list-header">
        <h2>会议列表</h2>
        <button type="button" onClick={onRefresh} disabled={loading}>
          {loading ? '刷新中…' : '刷新'}
        </button>
      </div>
      {error && (
        <pre className="list-error" role="alert">
          {error}
        </pre>
      )}
      {!error && meetings.length === 0 && !loading && (
        <p className="list-empty">暂无会议，请先上传录音。</p>
      )}
      <ul>
        {meetings.map((meeting) => (
          <li key={meeting.id}>
            <Link to={`/meetings/${meeting.id}`} className="meeting-row">
              <div className="meeting-meta">
                <span className="meeting-title">{meeting.title}</span>
                {meeting.status === 'failed' && meeting.error_message && (
                  <span className="meeting-error">{meeting.error_message}</span>
                )}
              </div>
              <span className={`meeting-status ${statusClass(meeting.status)}`}>
                {STATUS_LABELS[meeting.status] ?? meeting.status}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
