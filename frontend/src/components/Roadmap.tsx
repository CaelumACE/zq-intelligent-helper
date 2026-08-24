import { useEffect, useMemo, useState } from 'react'
import { API_BASE, authHeaders } from '../utils/api'
import type { GuideStep } from '../types'

interface RoadmapProps {
  themeId: string
  themeName?: string
  icon?: string
  totalDays?: number
  token?: string | null
  onBack: () => void
  onRequireLogin: () => void
}

const CHANNEL_LABEL: Record<string, string> = {
  online: '线上办理',
  offline: '线下办理',
  both: '线上/线下均可',
}

export default function Roadmap({ themeId, themeName, icon, totalDays, token, onBack, onRequireLogin }: RoadmapProps) {
  const [steps, setSteps] = useState<GuideStep[]>([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [progress, setProgress] = useState<Record<string, string>>({})
  const [progressDirty, setProgressDirty] = useState(false)

  useEffect(() => {
    fetch(`${API_BASE}/guide/theme/${themeId}/roadmap`)
      .then((r) => r.json())
      .then((d) => setSteps(d.steps || []))
      .catch(() => setSteps([]))
      .finally(() => setLoading(false))
  }, [themeId])

  useEffect(() => {
    if (!token) return
    fetch(`${API_BASE}/guide/progress/${themeId}`, { headers: authHeaders() })
      .then((r) => (r.ok ? r.json() : { progress: {} }))
      .then((d) => setProgress(d.progress || {}))
      .catch(() => setProgress({}))
  }, [themeId, token])

  const doneCount = useMemo(() => steps.filter((s) => progress[s.id] === 'done').length, [steps, progress])
  const pct = steps.length ? Math.round((doneCount / steps.length) * 100) : 0

  const toggle = async (stepId: string) => {
    const isDone = progress[stepId] === 'done'
    if (!token) {
      onRequireLogin()
      return
    }
    const next = { ...progress, [stepId]: isDone ? 'pending' : 'done' }
    setProgress(next)
    setProgressDirty(true)
    try {
      await fetch(`${API_BASE}/guide/progress/${themeId}/${stepId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ status: isDone ? 'pending' : 'done' }),
      })
    } catch {
      // 本地已更新；失败下次刷新可重新加载
    }
  }

  return (
    <div className="roadmap">
      <button className="roadmap-back" onClick={onBack}>← 返回导办首页</button>
      <div className="roadmap-head">
        <div className="roadmap-head-icon">{icon || '📋'}</div>
        <div className="roadmap-head-meta">
          <h2 className="roadmap-title">{themeName || '办事指南'}</h2>
          <div className="roadmap-sub">总预估 {totalDays ?? 0} 天 · 已完成 {doneCount}/{steps.length} 步</div>
        </div>
      </div>
      <div className="roadmap-progress"><div className="roadmap-progress-fill" style={{ width: `${pct}%` }} /></div>

      {loading ? (
        <div className="guide-loading">正在加载路线图…</div>
      ) : (
        <div className="roadmap-timeline">
          {steps.map((step, idx) => {
            const isDone = progress[step.id] === 'done'
            const isOpen = expanded === step.id
            return (
              <div key={step.id} className={`roadmap-step ${isDone ? 'done' : ''}`}>
                <div className="roadmap-step-marker">
                  <button
                    className={`roadmap-check ${isDone ? 'checked' : ''}`}
                    onClick={() => toggle(step.id)}
                    aria-label={isDone ? '标记为待办' : '标记为已完成'}
                  >
                    {isDone ? '✓' : ''}
                  </button>
                  {idx < steps.length - 1 && <div className="roadmap-line" />}
                </div>
                <div className="roadmap-step-body">
                  <button className="roadmap-step-head" onClick={() => setExpanded(isOpen ? null : step.id)}>
                    <div className="roadmap-step-order">{idx + 1}</div>
                    <div className="roadmap-step-main">
                      <div className="roadmap-step-name">{step.name}</div>
                      <div className="roadmap-step-meta">
                        {step.department} · {step.duration_days} 个工作日 · {CHANNEL_LABEL[step.channel] || '办理'} · {step.fee || '免费'}
                      </div>
                    </div>
                    <span className="roadmap-chevron">{isOpen ? '▴' : '▾'}</span>
                  </button>
                  {isOpen && (
                    <div className="roadmap-detail">
                      <div className="roadmap-detail-row">
                        <span className="roadmap-detail-label">办理渠道</span>
                        <span className="roadmap-detail-val">{step.channel_detail || CHANNEL_LABEL[step.channel] || '—'}</span>
                      </div>
                      {step.materials.length > 0 && (
                        <div className="roadmap-materials">
                          <div className="roadmap-materials-title">所需材料</div>
                          {step.materials.map((m) => (
                            <div key={m.name} className="roadmap-material">
                              <span className="roadmap-material-name">
                                {m.name} {m.copies && m.copies > 1 ? `×${m.copies}` : ''}
                              </span>
                              <span className={`roadmap-material-tag ${m.required === false ? 'optional' : ''}`}>
                                {m.required === false ? '容缺' : '必要'}
                              </span>
                              {m.notes && <span className="roadmap-material-note">{m.notes}</span>}
                            </div>
                          ))}
                        </div>
                      )}
                      {step.notes && (
                        <div className="roadmap-note">⚠️ {step.notes}</div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
      {progressDirty && <div className="roadmap-save-hint">进度已保存</div>}
    </div>
  )
}
