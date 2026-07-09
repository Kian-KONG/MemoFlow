import { useEffect, useState } from 'react'
import { probeBackend } from '../api/client'
import './BackendStatus.css'

export function BackendStatus() {
  const [ok, setOk] = useState<boolean | null>(null)
  const [detail, setDetail] = useState('')

  useEffect(() => {
    let cancelled = false
    void probeBackend().then((result) => {
      if (cancelled) return
      setOk(result.ok)
      setDetail(result.detail)
    })
    return () => {
      cancelled = true
    }
  }, [])

  if (ok === null) return null
  if (ok) return null

  return (
    <div className="backend-status error" role="alert">
      <strong>后端未就绪</strong>
      <p>{detail}</p>
      <ul>
        <li>本地测试：运行 <code>./scripts/smoke_test.sh</code></li>
        <li>
          启动服务：<code>PYTHONPATH=src uvicorn memoflow.main:app --host 127.0.0.1 --port 8000</code>
        </li>
        <li>Cloudflare：先 <code>cd frontend && npm run build</code>，再运行隧道脚本</li>
      </ul>
    </div>
  )
}
