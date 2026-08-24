import { useEffect, useState } from 'react'
import { API_BASE } from '../utils/api'
import Icon from './Icons'
import type { GuideTheme } from '../types'

interface GuideHomeProps {
  onOpenTheme: (theme: GuideTheme) => void
}

export default function GuideHome({ onOpenTheme }: GuideHomeProps) {
  const [themes, setThemes] = useState<GuideTheme[]>([])
  const [loading, setLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const [candidates, setCandidates] = useState<{ id: string; name: string; score: number }[]>([])
  const [message, setMessage] = useState('')

  useEffect(() => {
    fetch(`${API_BASE}/guide/themes`)
      .then((r) => r.json())
      .then((d) => setThemes(d.themes || []))
      .catch(() => setThemes([]))
      .finally(() => setLoading(false))
  }, [])

  const search = async (q: string) => {
    setSearching(true)
    setCandidates([])
    setMessage('')
    try {
      const res = await fetch(`${API_BASE}/guide/match`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q }),
      })
      const data = await res.json()
      if (data.matched) {
        onOpenTheme(data.theme)
      } else {
        setCandidates(data.candidates || [])
        setMessage(data.message || '未找到匹配主题')
      }
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="guide-home">
      <div className="guide-search-card">
        <div className="guide-search-ic"><Icon name="search" size={20} /></div>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && query.trim()) search(query.trim())
          }}
          placeholder="输入您要办的事，如“我要开饭店”"
          className="guide-search-input"
        />
        <button className="guide-search-btn" disabled={searching || !query.trim()} onClick={() => search(query.trim())}>
          {searching ? '匹配中…' : '查询'}
        </button>
      </div>

      {candidates.length > 0 && (
        <div className="guide-candidates">
          <div className="guide-candidate-title">您可能想办的是：</div>
          {candidates.map((c) => (
            <button
              key={c.id}
              className="guide-candidate"
              onClick={() =>
                onOpenTheme(themes.find((t) => t.id === c.id) || ({ id: c.id, name: c.name, estimated_days: 0 } as GuideTheme))
              }
            >
              <span>{c.name}</span>
              <span className="guide-candidate-score">{Math.round(c.score * 100)}%</span>
            </button>
          ))}
        </div>
      )}
      {message && !candidates.length && <div className="guide-no-match">{message}</div>}

      <div className="guide-section-title">高频办事场景</div>
      {loading ? (
        <div className="guide-loading">正在加载导办场景…</div>
      ) : (
        <div className="guide-grid">
          {themes.map((t) => (
            <button key={t.id} className="guide-theme-card" onClick={() => onOpenTheme(t)}>
              <div className="guide-theme-icon">{t.icon || '📋'}</div>
              <div className="guide-theme-name">{t.name}</div>
              <div className="guide-theme-days">预计 {t.estimated_days} 天</div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
