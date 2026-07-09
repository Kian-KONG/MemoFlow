import { useCallback, useEffect, useState } from 'react'
import { getSystemStatus } from '../api/system'
import type { SystemStatus } from '../api/types'
import './SettingsPage.css'

const DOWNLOAD_SCRIPT = './scripts/download_vibevoice_asr.sh'

export function SettingsPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getSystemStatus()
      setStatus(data)
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
    <div className="settings">
      <section className="settings-card">
        <div className="settings-header">
          <h2>AI 栈状态</h2>
          <button type="button" onClick={() => void refresh()} disabled={loading}>
            {loading ? '刷新中…' : '刷新'}
          </button>
        </div>
        <p className="settings-desc">
          MemoFlow 使用 VibeVoice 本地 ASR + 远程 LLM / Embedding / Rerank API。请确保模型权重与
          API 密钥均已就绪后再处理会议。
        </p>
        {error && <p className="settings-error">{error}</p>}
        {status && (
          <>
            <div className="status-row">
              <span className="platform">运行环境: {status.platform}</span>
              <span className={status.all_ready ? 'badge ok' : 'badge warn'}>
                {status.all_ready ? '全部就绪' : '尚未就绪'}
              </span>
            </div>

            <h3>系统依赖</h3>
            <ul className="dep-list">
              {status.dependencies.map((dep) => (
                <li key={dep.name} className={dep.available ? 'ok' : 'bad'}>
                  {dep.available ? '✓' : '✗'} {dep.name}: {dep.hint}
                </li>
              ))}
            </ul>

            <h3>本地模型</h3>
            {status.models.map((model) => (
              <div key={model.key} className="model-card">
                <div className="model-top">
                  <div>
                    <strong>{model.role}</strong>
                    <p className="muted">{model.model_id}</p>
                    <p className="muted">来源: {model.source}</p>
                    <p className="muted">{model.hint}</p>
                  </div>
                  <span className={`badge ${model.loaded ? 'ok' : model.ready ? 'neutral' : 'warn'}`}>
                    {model.loaded ? '已就绪' : model.ready ? '未加载' : '未找到'}
                  </span>
                </div>
                {!model.ready && (
                  <pre className="download-hint">{`chmod +x ${DOWNLOAD_SCRIPT}\n${DOWNLOAD_SCRIPT}`}</pre>
                )}
              </div>
            ))}
          </>
        )}
      </section>

      <section className="settings-card">
        <h2>配置说明</h2>
        <ul className="help-list">
          <li>
            <strong>ffmpeg</strong>: 终端运行 <code>brew install ffmpeg</code>（处理 m4a/mp3 必需）
          </li>
          <li>
            <strong>VibeVoice ASR</strong>: 运行 <code>{DOWNLOAD_SCRIPT}</code> 下载本地权重
          </li>
          <li>
            <strong>Bosch AIGC</strong>: 在 <code>.env</code> 中设置 <code>BOSCH_AIGC_API_KEY</code>{' '}
            与各 API URL
          </li>
          <li>
            或分别配置 <code>MEMOFLOW_DEEPSEEK_API_KEY</code> / <code>MEMOFLOW_OPENAI_API_KEY</code> /{' '}
            <code>MEMOFLOW_RERANK_API_KEY</code>
          </li>
        </ul>
      </section>
    </div>
  )
}
