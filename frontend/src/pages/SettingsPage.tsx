import { useCallback, useEffect, useState } from 'react'
import { getSystemStatus, selectAsrBackend } from '../api/system'
import type { SystemStatus } from '../api/types'
import { formatApiError } from '../lib/apiError'
import './SettingsPage.css'

export function SettingsPage() {
  const [status, setStatus] = useState<SystemStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [selecting, setSelecting] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const data = await getSystemStatus()
      setStatus(data)
    } catch (err) {
      setError(formatApiError(err, '加载系统状态失败'))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const handleSelect = async (backend: string) => {
    setSelecting(backend)
    setError('')
    setSuccess('')
    try {
      const result = await selectAsrBackend(backend)
      setStatus(result.status)
      setSuccess(result.message)
    } catch (err) {
      setError(formatApiError(err, '切换模型失败'))
    } finally {
      setSelecting(null)
    }
  }

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
          MemoFlow 使用 MOSS / VibeVoice 本地 ASR + 远程 LLM / Embedding / Rerank API。在下方选择
          ASR 模型即可<strong>即时切换</strong>，无需重启服务；选择会保存到{' '}
          <code>data/runtime_preferences.json</code>。
        </p>
        {error && <p className="settings-error">{error}</p>}
        {success && <p className="settings-success">{success}</p>}
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

            <h3>ASR 模型选择</h3>
            <p className="settings-desc">
              已选择: <code>{status.configured_asr_backend || 'auto'}</code> · 当前运行:{' '}
              <code>{status.active_asr_backend}</code>
            </p>
            <div className="asr-options">
              {status.asr_options.map((opt) => (
                <div
                  key={opt.backend}
                  className={`asr-option ${opt.active ? 'active' : ''} ${opt.ready ? 'ready' : 'missing'}`}
                >
                  <div className="asr-option-top">
                    <div>
                      <strong>{opt.label}</strong>
                      {opt.configured && <span className="badge neutral">已选择</span>}
                      {opt.active && <span className="badge ok">运行中</span>}
                      <p className="muted">{opt.model_id}</p>
                      <p className="muted">路径: {opt.model_path}</p>
                      <p className="muted">{opt.hint}</p>
                    </div>
                    <div className="asr-option-actions">
                      <span className={`badge ${opt.ready ? 'ok' : 'warn'}`}>
                        {opt.ready ? '权重就绪' : '未下载'}
                      </span>
                      {opt.ready && !opt.active && (
                        <button
                          type="button"
                          className="select-btn"
                          disabled={selecting !== null}
                          onClick={() => void handleSelect(opt.backend)}
                        >
                          {selecting === opt.backend ? '切换中…' : '使用此模型'}
                        </button>
                      )}
                      {opt.active && (
                        <span className="badge ok selected-badge">当前使用</span>
                      )}
                    </div>
                  </div>
                  {!opt.ready && <pre className="download-hint">{opt.download_command}</pre>}
                </div>
              ))}
            </div>

            <h3>当前 ASR 实例</h3>
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
              </div>
            ))}
          </>
        )}
      </section>

      <section className="settings-card">
        <h2>配置说明</h2>
        <ul className="help-list">
          <li>
            <strong>模型切换</strong>: 在上方点击「使用此模型」；偏好保存在{' '}
            <code>data/runtime_preferences.json</code>
          </li>
          <li>
            <strong>统一下载</strong>: <code>./scripts/download_asr_model.sh</code>（moss_hf /
            vibevoice 默认 ModelScope；Mac mlx_moss 走 HF 镜像）
          </li>
          <li>
            <strong>MOSS MLX</strong>: <code>pip install -e &quot;.[mlx-moss-asr]&quot;</code>
          </li>
          <li>
            <strong>MOSS HF</strong>: <code>pip install -e &quot;.[moss-asr]&quot;</code>
          </li>
          <li>
            <strong>ffmpeg</strong>: <code>brew install ffmpeg</code>
          </li>
          <li>
            <strong>API</strong>: 配置 <code>BOSCH_AIGC_API_KEY</code> 可统一覆盖 LLM /
            Embedding / Rerank
          </li>
        </ul>
      </section>
    </div>
  )
}
