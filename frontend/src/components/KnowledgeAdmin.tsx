import { useEffect, useState } from 'react'
import { API_BASE, apiFetch, authHeaders } from '../utils/api'
import type { KnowledgeItem } from '../types'

interface KnowledgeAdminProps {
  userRole: string | undefined
}

export default function KnowledgeAdmin({ userRole }: KnowledgeAdminProps) {
  const [items, setItems] = useState<KnowledgeItem[]>([])
  const [error, setError] = useState('')
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [category, setCategory] = useState('policy')
  const [editing, setEditing] = useState<KnowledgeItem | null>(null)

  const load = async () => {
    try {
      const res = await apiFetch(`${API_BASE}/knowledge/items`, { headers: authHeaders() })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '加载失败')
      setItems(data.items || [])
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    }
  }

  useEffect(() => { load() }, [])

  const isAdmin = userRole === 'admin' || userRole === 'super_admin'
  if (!isAdmin) return <div className="kb-empty">后台管理仅管理员可用，当前账号无权限。</div>

  const resetForm = () => { setTitle(''); setContent(''); setCategory('policy'); setEditing(null) }

  const submit = async () => {
    setError('')
    if (!title.trim() || !content.trim()) { setError('标题和内容不能为空'); return }
    try {
      const res = await apiFetch(editing ? `${API_BASE}/knowledge/items/${editing.id}` : `${API_BASE}/knowledge/items`, {
        method: editing ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(editing ? { title, content, category } : { title, content, category, source: '后台录入' }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '保存失败')
      resetForm()
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    }
  }

  const toggle = async (item: KnowledgeItem) => {
    await apiFetch(`${API_BASE}/knowledge/items/${item.id}/toggle`, { method: 'POST', headers: authHeaders() })
    load()
  }

  const remove = async (item: KnowledgeItem) => {
    if (!window.confirm(`确认删除「${item.title}」？`)) return
    await apiFetch(`${API_BASE}/knowledge/items/${item.id}`, { method: 'DELETE', headers: authHeaders() })
    load()
  }

  return (
    <div className="kb-admin">
      <div className="kb-form">
        <div className="kb-form-title">{editing ? '编辑条目' : '新增条目'}</div>
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="标题" className="kb-input" />
        <select value={category} onChange={(e) => setCategory(e.target.value)} className="kb-input">
          <option value="policy">policy 政策</option>
          <option value="regulation">regulation 法规</option>
          <option value="law">law 法律</option>
          <option value="guide">guide 办事指南</option>
          <option value="faq">faq 常见问题</option>
        </select>
        <textarea value={content} onChange={(e) => setContent(e.target.value)} placeholder="正文内容" className="kb-textarea" />
        <div className="kb-form-actions">
          <button className="kb-btn" onClick={submit}>{editing ? '保存修改' : '新增条目'}</button>
          {editing && <button className="kb-btn ghost" onClick={resetForm}>取消编辑</button>}
        </div>
      </div>

      {error && <div className="compare-error">{error}</div>}

      <div className="kb-list-title">知识库条目（{items.length}）</div>
      <div className="kb-list">
        {items.map((item) => (
          <div key={item.id} className="kb-item">
            <div className="kb-item-main">
              <div className="kb-item-title">{item.title}</div>
              <div className="kb-item-meta">{item.category} · {item.source || '—'}</div>
            </div>
            <div className="kb-item-actions">
              <button className="kb-btn small" onClick={() => { setEditing(item); setTitle(item.title); setContent(item.content); setCategory(item.category) }}>编辑</button>
              <button className="kb-btn small ghost" onClick={() => toggle(item)}>下架</button>
              <button className="kb-btn small danger" onClick={() => remove(item)}>删除</button>
            </div>
          </div>
        ))}
        {items.length === 0 && <div className="kb-empty">暂无条目，迁入或新增后可在此管理。</div>}
      </div>
    </div>
  )
}
