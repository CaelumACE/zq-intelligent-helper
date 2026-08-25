import { useState } from 'react'
import { API_BASE, apiFetch, authHeaders } from '../utils/api'

export default function SearchTester() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Array<{ id: string; title: string; snippet: string; score: number }>>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const search = async () => {
    setLoading(true)
    setError('')
    setResults([])
    try {
      const res = await apiFetch(`${API_BASE}/knowledge/test-search?query=${encodeURIComponent(query)}&top_k=8`, { method: 'POST', headers: authHeaders() })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '检索失败')
      setResults(data.results || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : '检索失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="search-tester">
      <div className="kb-form-title">检索测试面板</div>
      <div className="search-tester-bar">
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="输入问题测试召回效果" className="search-tester-input" onKeyDown={(e) => { if (e.key === 'Enter' && query.trim()) search() }} />
        <button className="kb-btn" disabled={loading || !query.trim()} onClick={search}>{loading ? '检索中…' : '检索'}</button>
      </div>
      {error && <div className="compare-error">{error}</div>}
      {results.map((r) => (
        <div key={r.id} className="search-tester-item">
          <div className="search-tester-head"><span>{r.title}</span><span className="search-tester-score">{(r.score * 100).toFixed(1)}%</span></div>
          <div className="search-tester-snippet">{r.snippet}</div>
        </div>
      ))}
    </div>
  )
}
