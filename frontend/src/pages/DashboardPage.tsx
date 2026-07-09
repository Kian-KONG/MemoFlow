import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listMeetings } from '../api/meetings'
import type { Meeting } from '../api/types'
import { BackendStatus } from '../components/BackendStatus'
import { MeetingList } from '../components/MeetingList'
import { UploadForm } from '../components/UploadForm'
import { formatApiError } from '../lib/apiError'
import './DashboardPage.css'

export function DashboardPage() {
  const navigate = useNavigate()
  const [meetings, setMeetings] = useState<Meeting[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await listMeetings(100)
      setMeetings(data)
    } catch (err) {
      setError(formatApiError(err, '加载会议列表失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return (
    <div className="dashboard">
      <BackendStatus />
      <UploadForm
        onUploaded={(meeting) => {
          setMeetings((prev) => [meeting, ...prev.filter((m) => m.id !== meeting.id)])
          navigate(`/meetings/${meeting.id}`)
        }}
      />
      <MeetingList meetings={meetings} loading={loading} error={error} onRefresh={() => void refresh()} />
    </div>
  )
}
