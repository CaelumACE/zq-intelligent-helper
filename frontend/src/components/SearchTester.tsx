import { useState } from 'react'
import { API_BASE, apiFetch, authHeaders } from '../utils/api'
import Icon from './Icons'

interface SearchResult {
  id: string
  title: string
  snippet: string
  source?: string
  score: number
  category?: string
}

export default function SearchTester() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [hasSearched, setHasSearched] = useState(false)
  const [topK, setTopK] = useState(8)

  const search = async () => {
    if (!query.trim()) return
    setLoading(true)
    setError('')
    setResults([])
    setHasSearched(true)
    try {
      const res = await apiFetch(`${API_BASE}/knowledge/test-search?query=${encodeURIComponent(query)}&top_k=${topK}`, {
        method: 'POST',
        headers: authHeaders(),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '检索失败')
      setResults(data.results || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : '检索失败')
    } finally {
      setLoading(false)
    }
  }

  const scoreColor = (score: number): string => {
    if (score >= 70) return '#16a34a'
    if (score >= 40) return '#d97706'
    return '#94a3b8'
  }

  return (
    <div className="st-panel">
      <div className="st-card">
        <div className="st-card-head">
          <Icon name="search" size={16} />
          <span>检索测试面板</span>
        </div>
        <p className="st-desc">输入问题，测试知识库召回效果与引用相关性。评分越高表示与问题越相关。</p>
        <div className="st-bar">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="输入问题测试召回效果，如：异地就医怎么备案？"
            className="st-input"
            onKeyDown={(e) => { if (e.key === 'Enter' && query.trim() && !loading) search() }}
          />
          <select className="st-topk" value={topK} onChange={(e) => setTopK(Number(e.target.value))}>
            {[5, 8, 10, 15, 20].map(n => <option key={n} value={n}>Top {n}</option>)}
          </select>
          <button className="st-btn" disabled={loading || !query.trim()} onClick={search}>
            {loading ? (
              <><span className="st-spinner" /> 检索中…</>
            ) : (
              <><Icon name="search" size={14} /> 检索</>
            )}
          </button>
        </div>
      </div>

      {error && <div className="compare-error">{error}</div>}

      {hasSearched && !loading && results.length === 0 && !error && (
        <div className="st-empty">
          <Icon name="search" size={32} />
          <p>未召回任何结果</p>
          <span>尝试更换关键词或检查知识库是否有相关条目</span>
        </div>
      )}

      {!hasSearched && (
        <div className="st-hint">
          <Icon name="help-circle" size={20} />
          <div>
            <p>使用说明</p>
            <span>输入任意政务相关问题，系统将从知识库中检索最相关的片段，展示标题、来源、内容摘要和相关性评分。</span>
          </div>
        </div>
      )}

      {results.length > 0 && (
        <div className="st-results">
          <div className="st-results-head">
            <span>召回结果</span>
            <span className="st-results-count">{results.length} 条</span>
          </div>
          {results.map((r, idx) => (
            <div key={r.id || idx} className="st-item">
              <div className="st-item-head">
                <div className="st-item-rank" style={{ background: scoreColor(r.score) }}>{idx + 1}</div>
                <div className="st-item-title-wrap">
                  <span className="st-item-title">{r.title}</span>
                  {r.source && <span className="st-item-source">{r.source}</span>}
                </div>
                <div className="st-score" style={{ color: scoreColor(r.score) }}>
                  {r.score.toFixed(1)}%
                </div>
              </div>
              {r.snippet && (
                <div className="st-item-snippet">{r.snippet}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
