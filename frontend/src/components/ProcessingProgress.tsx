import { useEffect, useState } from 'react'
import type { Meeting } from '../api/types'
import { STAGE_HINTS, STAGE_LABELS, STAGE_STEPS, isTerminalStatus } from '../lib/status'
import { formatElapsed } from '../lib/time'
import './ProcessingProgress.css'

interface ProcessingProgressProps {
  meeting: Meeting
  onRetry?: () => void
  retrying?: boolean
}

export function ProcessingProgress({ meeting, onRetry, retrying }: ProcessingProgressProps) {
  const status = meeting.status
  const [nowMs, setNowMs] = useState(() => Date.now())

  useEffect(() => {
    if (isTerminalStatus(status)) return
    const timer = window.setInterval(() => setNowMs(Date.now()), 1000)
    return () => window.clearInterval(timer)
  }, [status])

  const stageIndex = STAGE_STEPS.includes(status as (typeof STAGE_STEPS)[number])
    ? STAGE_STEPS.indexOf(status as (typeof STAGE_STEPS)[number])
    : 0
  const progress = status === 'failed' ? 0 : (stageIndex + 1) / STAGE_STEPS.length

  return (
    <section className="processing">
      <div className="processing-header">
        <h1>{meeting.title}</h1>
        <span className="filename">{meeting.original_filename}</span>
      </div>

      {!isTerminalStatus(status) && (
        <>
          <p className="stage-label active">{STAGE_LABELS[status] ?? status}</p>
          <div className="stage-bar">
            <div className="stage-fill" style={{ width: `${progress * 100}%` }} />
          </div>
          <p className="hint">已耗时: {formatElapsed(meeting.updated_at, nowMs)}</p>
          <p className="hint">{STAGE_HINTS[status] ?? '处理中，页面会自动更新进度。'}</p>
          {meeting.transcript_id && (
            <p className="hint ok">转写文本已部分生成，可切换到「转写文本」查看。</p>
          )}
        </>
      )}

      {status === 'completed' && (
        <p className="stage-label completed">处理完成，可在下方查看结果</p>
      )}

      {status === 'failed' && (
        <div className="failed-block">
          <p className="stage-label failed">处理失败</p>
          {meeting.error_message && <p className="error-msg">{meeting.error_message}</p>}
          <p className="hint">重试将从上次成功的阶段继续，已完成的转写/摘要不会重新生成。</p>
          {onRetry && (
            <button type="button" onClick={onRetry} disabled={retrying}>
              {retrying ? '重试中…' : '重试处理'}
            </button>
          )}
        </div>
      )}
    </section>
  )
}
