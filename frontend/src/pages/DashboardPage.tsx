import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listMeetings } from '../api/meetings'
import type { Meeting } from '../api/types'
import { MeetingList } from '../components/MeetingList'
import { UploadForm } from '../components/UploadForm'
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
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return (
    <div className="dashboard">
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
