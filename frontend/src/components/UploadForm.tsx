import { useRef, useState, type FormEvent } from 'react'
import { uploadMeeting } from '../api/meetings'
import type { Meeting } from '../api/types'
import './UploadForm.css'

const ACCEPT = '.mp3,.wav,.m4a,.flac,.ogg,audio/*'

interface UploadFormProps {
  onUploaded: (meeting: Meeting) => void
}

export function UploadForm({ onUploaded }: UploadFormProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [title, setTitle] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [percent, setPercent] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    if (!file || uploading) return

    setUploading(true)
    setError('')
    setPercent(0)
    setStatus('正在上传…')

    try {
      const meeting = await uploadMeeting(file, title, (progress) => {
        setPercent(progress.percent)
      })
      setStatus('上传成功，正在跳转…')
      setPercent(100)
      setFile(null)
      setTitle('')
      if (inputRef.current) inputRef.current.value = ''
      onUploaded(meeting)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setStatus('')
    } finally {
      setUploading(false)
    }
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      <h2>上传会议录音</h2>
      <label className="field">
        <span>标题（可选）</span>
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder="留空则使用文件名"
          disabled={uploading}
        />
      </label>
      <label className="field">
        <span>音频文件</span>
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPT}
          disabled={uploading}
          onChange={(e) => {
            setFile(e.target.files?.[0] ?? null)
            setError('')
            setStatus('')
            setPercent(0)
          }}
        />
      </label>
      {file && <p className="file-meta">{file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB</p>}
      {(uploading || percent > 0) && (
        <div className="progress-wrap">
          <div className="progress-bar" style={{ width: `${percent}%` }} />
          <span className="progress-label">{percent}%</span>
        </div>
      )}
      {status && <p className="status ok">{status}</p>}
      {error && <p className="status err">{error}</p>}
      <button type="submit" disabled={!file || uploading}>
        {uploading ? '上传中…' : '开始上传'}
      </button>
    </form>
  )
}
