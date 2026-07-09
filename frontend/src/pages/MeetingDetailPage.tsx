import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { getMeeting, retryMeeting } from '../api/meetings'
import { getSummary } from '../api/summaries'
import { getTranscript } from '../api/transcripts'
import type { Meeting, Summary, Transcript } from '../api/types'
import { KnowledgeSearch } from '../components/KnowledgeSearch'
import { ProcessingProgress } from '../components/ProcessingProgress'
import { SummaryView } from '../components/SummaryView'
import { TranscriptView } from '../components/TranscriptView'
import { isTerminalStatus } from '../lib/status'
import './MeetingDetailPage.css'

type TabKey = 'summary' | 'transcript' | 'knowledge'

const POLL_MS = 2000

export function MeetingDetailPage() {
  const { meetingId = '' } = useParams()
  const [meeting, setMeeting] = useState<Meeting | null>(null)
  const [meetingError, setMeetingError] = useState('')
  const [tab, setTab] = useState<TabKey>('summary')
  const [summary, setSummary] = useState<Summary | null>(null)
  const [summaryError, setSummaryError] = useState('')
  const [summaryLoading, setSummaryLoading] = useState(false)
  const [transcript, setTranscript] = useState<Transcript | null>(null)
  const [transcriptError, setTranscriptError] = useState('')
  const [transcriptLoading, setTranscriptLoading] = useState(false)
  const [retrying, setRetrying] = useState(false)

  const loadMeeting = useCallback(async () => {
    if (!meetingId) return null
    try {
      const data = await getMeeting(meetingId)
      setMeeting(data)
      setMeetingError('')
      return data
    } catch (err) {
      setMeetingError(err instanceof Error ? err.message : String(err))
      return null
    }
  }, [meetingId])

  const loadTranscript = useCallback(async () => {
    if (!meetingId) return
    setTranscriptLoading(true)
    setTranscriptError('')
    try {
      const data = await getTranscript(meetingId)
      setTranscript(data)
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setTranscript(null)
        setTranscriptError('')
      } else {
        setTranscriptError(err instanceof Error ? err.message : String(err))
      }
    } finally {
      setTranscriptLoading(false)
    }
  }, [meetingId])

  const loadSummary = useCallback(async () => {
    if (!meetingId) return
    setSummaryLoading(true)
    setSummaryError('')
    try {
      const data = await getSummary(meetingId)
      setSummary(data)
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setSummary(null)
        setSummaryError('')
      } else {
        setSummaryError(err instanceof Error ? err.message : String(err))
      }
    } finally {
      setSummaryLoading(false)
    }
  }, [meetingId])

  useEffect(() => {
    void loadMeeting().then((data) => {
      if (!data) return
      if (data.transcript_id) void loadTranscript()
      if (data.status === 'completed') void loadSummary()
    })
  }, [loadMeeting, loadTranscript, loadSummary])

  useEffect(() => {
    if (!meeting || isTerminalStatus(meeting.status)) return

    const timer = window.setInterval(() => {
      void loadMeeting().then((data) => {
        if (!data) return
        if (data.transcript_id) void loadTranscript()
        if (data.status === 'completed') void loadSummary()
      })
    }, POLL_MS)

    return () => window.clearInterval(timer)
  }, [meeting?.status, meeting?.id, loadMeeting, loadTranscript, loadSummary])

  async function handleRetry() {
    if (!meetingId) return
    setRetrying(true)
    try {
      const data = await retryMeeting(meetingId)
      setMeeting(data)
      setSummary(null)
    } catch (err) {
      setMeetingError(err instanceof Error ? err.message : String(err))
    } finally {
      setRetrying(false)
    }
  }

  if (meetingError && !meeting) {
    return (
      <div className="detail">
        <Link to="/" className="back-link">
          ← 返回列表
        </Link>
        <p className="panel-error">{meetingError}</p>
      </div>
    )
  }

  if (!meeting) {
    return (
      <div className="detail">
        <p className="panel-muted">加载中…</p>
      </div>
    )
  }

  return (
    <div className="detail">
      <Link to="/" className="back-link">
        ← 返回列表
      </Link>
      <ProcessingProgress meeting={meeting} onRetry={() => void handleRetry()} retrying={retrying} />

      <div className="tabs">
        <button
          type="button"
          className={tab === 'summary' ? 'active' : ''}
          onClick={() => setTab('summary')}
        >
          摘要 / 决策 / 行动项
        </button>
        <button
          type="button"
          className={tab === 'transcript' ? 'active' : ''}
          onClick={() => setTab('transcript')}
        >
          转写文本
        </button>
        <button
          type="button"
          className={tab === 'knowledge' ? 'active' : ''}
          onClick={() => setTab('knowledge')}
        >
          知识库检索
        </button>
      </div>

      <div className="tab-panel">
        {tab === 'summary' && (
          <SummaryView summary={summary} loading={summaryLoading} error={summaryError} />
        )}
        {tab === 'transcript' && (
          <TranscriptView
            transcript={transcript}
            loading={transcriptLoading}
            error={transcriptError}
          />
        )}
        {tab === 'knowledge' && <KnowledgeSearch meetingId={meetingId} />}
      </div>
    </div>
  )
}
