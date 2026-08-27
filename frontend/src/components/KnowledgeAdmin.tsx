import { useEffect, useState, useMemo } from 'react'
import { API_BASE, apiFetch, authHeaders } from '../utils/api'
import Icon from './Icons'

interface SeedDoc {
  id: string
  title: string
  category: string
  summary: string
  source: 'seed'
}

interface AdminItem {
  id: number
  title: string
  content: string
  category: string
  source?: string
  status?: string
  metadata?: Record<string, unknown>
  created_at?: string
  updated_at?: string
  source_type: 'admin'
}

type CombinedItem = SeedDoc | AdminItem

interface KnowledgeAdminProps {
  userRole: string | undefined
}

const CATEGORY_LABEL: Record<string, string> = {
  policy: '政策',
  regulation: '法规',
  law: '法律',
  guide: '办事指南',
  faq: '常见问题',
  knowledge: '政务知识',
  template: '公文模板',
  service: '办事',
  '公文模板': '公文模板',
}

const CATEGORY_OPTIONS = [
  { value: 'policy', label: '政策' },
  { value: 'regulation', label: '法规' },
  { value: 'law', label: '法律' },
  { value: 'guide', label: '办事指南' },
  { value: 'faq', label: '常见问题' },
  { value: 'knowledge', label: '政务知识' },
  { value: 'template', label: '公文模板' },
]

function isSeed(item: CombinedItem): item is SeedDoc {
  return item.source === 'seed'
}

function isAdmin(item: CombinedItem): item is AdminItem {
  return (item as AdminItem).source_type === 'admin'
}

export default function KnowledgeAdmin({ userRole }: KnowledgeAdminProps) {
  const [seedDocs, setSeedDocs] = useState<SeedDoc[]>([])
  const [adminItems, setAdminItems] = useState<AdminItem[]>([])
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [category, setCategory] = useState('policy')
  const [source, setSource] = useState('')
  const [editing, setEditing] = useState<AdminItem | null>(null)
  const [filterCat, setFilterCat] = useState('all')
  const [search, setSearch] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [view, setView] = useState<'list' | 'add'>('list')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const [seedRes, adminRes] = await Promise.all([
        apiFetch(`${API_BASE}/knowledge/documents`, { headers: authHeaders() }),
        apiFetch(`${API_BASE}/knowledge/items/all`, { headers: authHeaders() }),
      ])
      if (seedRes.ok) {
        const docs = await seedRes.json()
        setSeedDocs((docs || []).map((d: SeedDoc) => ({ ...d, source: 'seed' as const })))
      }
      if (adminRes.ok) {
        const data = await adminRes.json()
        setAdminItems((data.items || []).map((i: AdminItem) => ({ ...i, source_type: 'admin' as const })))
      } else {
        const d = await adminRes.json().catch(() => ({}))
        setError(d.detail || '加载管理条目失败')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [])

  const isAdminRole = userRole === 'admin' || userRole === 'super_admin'
  if (!isAdminRole) return <div className="kb-empty">后台管理仅管理员可用，当前账号无权限。</div>

  const resetForm = () => { setTitle(''); setContent(''); setCategory('policy'); setSource(''); setEditing(null); setView('list') }

  const submit = async () => {
    setError('')
    if (!title.trim() || !content.trim()) { setError('标题和内容不能为空'); return }
    setSubmitting(true)
    try {
      const body: Record<string, string> = { title, content, category, source: source || '后台录入' }
      const res = await apiFetch(editing ? `${API_BASE}/knowledge/items/${editing.id}` : `${API_BASE}/knowledge/items`, {
        method: editing ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(editing ? { ...body, source: body.source || editing.source || '后台录入' } : body),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '保存失败')
      resetForm()
      load()
    } catch (e) {
      setError(e instanceof Error ? e.message : '保存失败')
    } finally {
      setSubmitting(false)
    }
  }

  const toggle = async (item: AdminItem) => {
    await apiFetch(`${API_BASE}/knowledge/items/${item.id}/toggle`, { method: 'POST', headers: authHeaders() })
    load()
  }

  const remove = async (item: AdminItem) => {
    if (!window.confirm(`确认删除「${item.title}」？此操作不可恢复。`)) return
    const res = await apiFetch(`${API_BASE}/knowledge/items/${item.id}`, { method: 'DELETE', headers: authHeaders() })
    if (res.ok) load()
  }

  const startEdit = (item: AdminItem) => {
    setEditing(item)
    setTitle(item.title)
    setContent(item.content)
    setCategory(item.category)
    setSource(item.source || '')
    setView('add')
  }

  const allItems = useMemo<CombinedItem[]>(() => {
    return [...seedDocs, ...adminItems]
  }, [seedDocs, adminItems])

  const filtered = useMemo(() => {
    return allItems.filter(item => {
      const cat = isSeed(item) ? item.category : item.category
      if (filterCat !== 'all' && cat !== filterCat) return false
      if (search.trim()) {
        const q = search.toLowerCase()
        const t = (isSeed(item) ? item.title : item.title).toLowerCase()
        const s = (isAdmin(item) ? (item.source || '') : '').toLowerCase()
        return t.includes(q) || s.includes(q)
      }
      return true
    })
  }, [allItems, filterCat, search])

  const catCount = useMemo(() => {
    const m: Record<string, number> = {}
    allItems.forEach(i => {
      const c = isSeed(i) ? i.category : i.category
      m[c] = (m[c] || 0) + 1
    })
    return m
  }, [allItems])

  const filterOptions = useMemo(() => {
    return CATEGORY_OPTIONS.filter(o => (catCount[o.value] || 0) > 0)
  }, [catCount])

  const getItemTitle = (item: CombinedItem) => isSeed(item) ? item.title : item.title
  const getItemCategory = (item: CombinedItem) => {
    const c = isSeed(item) ? item.category : item.category
    return CATEGORY_LABEL[c] || c
  }
  const getItemSummary = (item: CombinedItem) => {
    if (isSeed(item)) return item.summary
    return item.content ? item.content.slice(0, 120) + (item.content.length > 120 ? '...' : '') : ''
  }

  return (
    <div className="kb-admin-v2">
      {error && <div className="compare-error">{error}</div>}

      {/* 工具栏 */}
      <div className="kb-toolbar">
        <div className="kb-filter-chips">
          <button
            className={`kb-chip ${filterCat === 'all' ? 'active' : ''}`}
            onClick={() => setFilterCat('all')}
          >
            全部 <span className="kb-chip-count">{allItems.length}</span>
          </button>
          {filterOptions.map(o => (
            <button
              key={o.value}
              className={`kb-chip ${filterCat === o.value ? 'active' : ''}`}
              onClick={() => setFilterCat(o.value)}
            >
              {o.label} <span className="kb-chip-count">{catCount[o.value]}</span>
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="kb-search-input"
            placeholder="搜索标题或来源..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button
            className="kb-btn"
            onClick={() => { resetForm(); setView(view === 'add' ? 'list' : 'add') }}
          >
            {view === 'add' ? '返回列表' : '+ 新增条目'}
          </button>
        </div>
      </div>

      {/* 新增/编辑表单 */}
      {view === 'add' && (
        <div className="kb-card">
          <div className="kb-card-head">
            <Icon name="edit" size={16} />
            <span>{editing ? '编辑条目' : '新增条目'}</span>
          </div>
          <div className="kb-form-row">
            <div className="kb-form-group" style={{ flex: 2 }}>
              <label className="kb-label">标题 <span className="kb-required">*</span></label>
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="请输入条目标题" className="kb-input" />
            </div>
            <div className="kb-form-group">
              <label className="kb-label">知识类型</label>
              <select value={category} onChange={(e) => setCategory(e.target.value)} className="kb-input">
                {CATEGORY_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
          </div>
          <div className="kb-form-group">
            <label className="kb-label">来源</label>
            <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="如：市政府官网、XX文件..." className="kb-input" />
          </div>
          <div className="kb-form-group">
            <label className="kb-label">正文内容 <span className="kb-required">*</span></label>
            <textarea value={content} onChange={(e) => setContent(e.target.value)} placeholder="粘贴或输入正文内容" className="kb-textarea" style={{ minHeight: 160 }} />
          </div>
          <div className="kb-form-actions">
            <button className="kb-btn" disabled={submitting} onClick={submit}>
              {submitting ? '保存中…' : (editing ? '保存修改' : '+ 新增条目')}
            </button>
            <button className="kb-btn ghost" onClick={resetForm}>取消</button>
          </div>
        </div>
      )}

      {/* 条目列表 */}
      <div className="kb-list-header">
        <span>知识库条目</span>
        <span className="kb-list-count">种子 {seedDocs.length} 条 · 录入 {adminItems.length} 条 · 共 {allItems.length} 条</span>
      </div>

      {loading ? (
        <div className="kb-empty">加载中…</div>
      ) : filtered.length === 0 ? (
        <div className="kb-empty">暂无条目，新增或迁入后可在此管理。</div>
      ) : (
        <div className="kb-list-v2">
          {filtered.map((item) => {
            const seed = isSeed(item)
            const admin = isAdmin(item)
            const isDisabled = admin && item.status === 'inactive'
            const key = seed ? `seed-${item.id}` : `admin-${(item as AdminItem).id}`
            return (
              <div key={key} className={`kb-item-v2 ${isDisabled ? 'is-disabled' : ''}`}>
                <div className="kb-item-main">
                  <div className="kb-item-title">
                    {getItemTitle(item)}
                    {seed && <span className="kb-item-tag seed-tag">种子数据</span>}
                    {isDisabled && <span className="kb-item-tag">已下架</span>}
                  </div>
                  <div className="kb-item-meta">
                    <span className="kb-item-cat">{getItemCategory(item)}</span>
                    {!seed && (
                      <>
                        <span className="kb-item-dot">·</span>
                        <span>{(item as AdminItem).source || '—'}</span>
                        {admin && item.metadata?.vectorized && (
                          <>
                            <span className="kb-item-dot">·</span>
                            <span className="kb-item-vec">已向量化</span>
                          </>
                        )}
                      </>
                    )}
                  </div>
                  {getItemSummary(item) && (
                    <div className="kb-item-preview">{getItemSummary(item)}</div>
                  )}
                </div>
                {admin && (
                  <div className="kb-item-actions">
                    <button className="kb-btn small" onClick={() => startEdit(item)}>
                      <Icon name="edit" size={12} /> 编辑
                    </button>
                    <button className="kb-btn small ghost" onClick={() => toggle(item)}>
                      {isDisabled ? '上架' : '下架'}
                    </button>
                    <button className="kb-btn small danger" onClick={() => remove(item)}>删除</button>
                  </div>
                )}
                {seed && (
                  <div className="kb-item-actions">
                    <span className="kb-seed-hint">只读</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
