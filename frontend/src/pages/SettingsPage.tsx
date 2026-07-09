import { useCallback, useEffect, useState } from 'react'
import { getSystemStatus } from '../api/system'
import type { SystemStatus } from '../api/types'
import './SettingsPage.css'

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
          MemoFlow 使用 MOSS / VibeVoice 本地 ASR + 远程 LLM / Embedding / Rerank API。ASR
          后端在 <code>.env</code> 中通过 <code>MEMOFLOW_ASR_BACKEND</code> 切换，修改后需重启服务。
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

            <h3>ASR 模型（可选后端）</h3>
            <p className="settings-desc">
              配置: <code>{status.configured_asr_backend || 'auto'}</code> · 当前运行:{' '}
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
                      {opt.configured && <span className="badge neutral">已配置</span>}
                      {opt.active && <span className="badge ok">运行中</span>}
                      <p className="muted">{opt.model_id}</p>
                      <p className="muted">路径: {opt.model_path}</p>
                      <p className="muted">{opt.hint}</p>
                    </div>
                    <span className={`badge ${opt.ready ? 'ok' : 'warn'}`}>
                      {opt.ready ? '权重就绪' : '未下载'}
                    </span>
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
            <strong>ffmpeg</strong>: 终端运行 <code>brew install ffmpeg</code>（处理 m4a/mp3 必需）
          </li>
          <li>
            <strong>MOSS MLX</strong>: <code>MEMOFLOW_ASR_BACKEND=mlx_moss</code> +{' '}
            <code>./scripts/download_mlx_moss.sh</code>
          </li>
          <li>
            <strong>MOSS HF</strong>: <code>MEMOFLOW_ASR_BACKEND=moss_hf</code> +{' '}
            <code>pip install -e &quot;.[moss-asr]&quot;</code> +{' '}
            <code>MEMOFLOW_ASR_BACKEND=moss_hf ./scripts/download_asr_model.sh</code>
          </li>
          <li>
            <strong>VibeVoice</strong>: <code>MEMOFLOW_ASR_BACKEND=vibevoice</code> +{' '}
            <code>./scripts/download_vibevoice_asr.sh</code>
          </li>
          <li>
            MLX 权重已下载时，即使 MLX 运行时未安装，也可设 <code>moss_hf</code> 使用同一目录权重
          </li>
        </ul>
      </section>
    </div>
  )
}
