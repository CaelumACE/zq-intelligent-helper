import { useEffect, useRef, useState } from 'react'
import { API_BASE, apiFetch, authHeaders } from '../utils/api'
import DiffViewer from './DiffViewer'
import type { CompareResult, KnowledgeItem } from '../types'

interface CompareHomeProps {
  token: string | null
  onRequireLogin: () => void
}

async function downloadDocx(id: string) {
  const res = await apiFetch(`${API_BASE}/compare/export/${id}`, { headers: authHeaders() })
  if (!res.ok) throw new Error('导出失败')
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `diff_report_${id}.docx`
  a.click()
  URL.revokeObjectURL(url)
}

export default function CompareHome({ token, onRequireLogin }: CompareHomeProps) {
  const [aTitle, setATitle] = useState('')
  const [aContent, setAContent] = useState('')
  const [bTitle, setBTitle] = useState('')
  const [bContent, setBContent] = useState('')
  const [items, setItems] = useState<KnowledgeItem[]>([])
  const [aid, setAid] = useState(0)
  const [bid, setBid] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<CompareResult | null>(null)
  const fileARef = useRef<File | null>(null)
  const fileBRef = useRef<File | null>(null)

  useEffect(() => {
    apiFetch(`${API_BASE}/knowledge/items`, { headers: authHeaders() })
      .then((r) => r.json())
      .then((d) => setItems(d.items || []))
      .catch(() => setItems([]))
  }, [])

  const requireToken = () => {
    if (!token) {
      onRequireLogin()
      return false
    }
    return true
  }

  const run = async (body: unknown) => {
    if (!requireToken()) return
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const res = await apiFetch(`${API_BASE}/compare`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '比对失败')
      setResult(data)
    } catch (e) {
      setError(e instanceof Error ? e.message : '比对失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  const submitText = () => run({ doc_a: { title: aTitle || '旧版', content: aContent }, doc_b: { title: bTitle || '新版', content: bContent } })
  const submitIds = () => run({ item_a_id: aid, item_b_id: bid })

  const upload = async () => {
    if (!requireToken()) return
    if (!fileARef.current || !fileBRef.current) {
      setError('请同时选择旧版和新版两个文件')
      return
    }
    if (fileARef.current.size > 5 * 1024 * 1024 || fileBRef.current.size > 5 * 1024 * 1024) {
      setError('文件不能超过 5MB')
      return
    }
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const fd = new FormData()
      fd.append('doc_a', fileARef.current)
      fd.append('doc_b', fileBRef.current)
      const res = await apiFetch(`${API_BASE}/compare/upload`, { method: 'POST', headers: authHeaders(), body: fd })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '上传比对失败')
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传比对失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="compare-home">
      <div className="compare-section-title">从知识库选择</div>
      <div className="compare-grid">
        <div className="compare-input">
          <div className="compare-input-label">旧版</div>
          <select value={aid} onChange={(e) => setAid(Number(e.target.value))}>
            <option value={0}>请选择文档</option>
            {items.map((it) => <option key={it.id} value={it.id}>{it.title}</option>)}
          </select>
        </div>
        <div className="compare-input">
          <div className="compare-input-label">新版</div>
          <select value={bid} onChange={(e) => setBid(Number(e.target.value))}>
            <option value={0}>请选择文档</option>
            {items.map((it) => <option key={it.id} value={it.id}>{it.title}</option>)}
          </select>
        </div>
      </div>
      <button className="compare-run" disabled={!aid || !bid || loading} onClick={submitIds}>{loading ? '比对中…' : '开始比对'}</button>

      <div className="compare-divider" />
      <div className="compare-section-title">直接粘贴文本</div>
      <div className="compare-grid">
        <div className="compare-input">
          <div className="compare-input-label">旧版标题</div>
          <input value={aTitle} onChange={(e) => setATitle(e.target.value)} placeholder="旧版标题" />
          <div className="compare-input-label" style={{ marginTop: 8 }}>旧版正文</div>
          <textarea value={aContent} onChange={(e) => setAContent(e.target.value)} placeholder="粘贴旧版政策内容" />
        </div>
        <div className="compare-input">
          <div className="compare-input-label">新版标题</div>
          <input value={bTitle} onChange={(e) => setBTitle(e.target.value)} placeholder="新版标题" />
          <div className="compare-input-label" style={{ marginTop: 8 }}>新版正文</div>
          <textarea value={bContent} onChange={(e) => setBContent(e.target.value)} placeholder="粘贴新版政策内容" />
        </div>
      </div>
      <button className="compare-run" disabled={(!aContent.trim() && !bContent.trim()) || loading} onClick={submitText}>{loading ? '比对中…' : '开始比对'}</button>

      <div className="compare-divider" />
      <div className="compare-section-title">上传文件比对</div>
      <div className="compare-grid">
        <div className="compare-input">
          <div className="compare-input-label">旧版文件</div>
          <input type="file" accept=".txt,.docx,.pdf" onChange={(e) => { fileARef.current = e.target.files?.[0] || null }} />
        </div>
        <div className="compare-input">
          <div className="compare-input-label">新版文件</div>
          <input type="file" accept=".txt,.docx,.pdf" onChange={(e) => { fileBRef.current = e.target.files?.[0] || null }} />
        </div>
      </div>
      <button className="compare-run" disabled={loading} onClick={upload}>{loading ? '上传比对中…' : '上传并比对'}</button>

      {error && <div className="compare-error">{error}</div>}
      {loading && <div className="compare-loading">正在语义比对，预计 15 秒内完成…</div>}
      {result && <DiffViewer result={result} onExport={() => downloadDocx(result.task_id)} />}
    </div>
  )
}
