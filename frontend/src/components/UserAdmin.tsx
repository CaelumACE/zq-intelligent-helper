import { useState, useEffect, useCallback } from 'react'
import { apiFetch, API_BASE } from '../utils/api'

interface AdminUser {
  id: number
  username: string
  role: string
  is_active: boolean
  token_version: number
  last_login?: string | null
}

interface UsersResponse {
  items: AdminUser[]
  total: number
  page: number
  page_size: number
}

const ROLE_LABEL: Record<string, string> = {
  super_admin: '超级管理员',
  admin: '管理员',
  user: '普通用户',
}

const ROLE_BADGE: Record<string, string> = {
  super_admin: 'ua-badge-super',
  admin: 'ua-badge-admin',
  user: 'ua-badge-user',
}

export default function UserAdmin({ onClose, currentUserId, currentUserRole }: {
  onClose: () => void
  currentUserId: number | null
  currentUserRole?: string
}) {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [pageSize, setPageSize] = useState(10)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ username: '', password: '', role: 'user' })
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')
  const [resetTarget, setResetTarget] = useState<AdminUser | null>(null)
  const [newPwd, setNewPwd] = useState('')
  const [actionLoading, setActionLoading] = useState<number | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<AdminUser | null>(null)

  const isSuper = currentUserRole === 'super_admin'

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    setError('')
    try {
      const res = await apiFetch(`${API_BASE}/admin/users?page=${page}&page_size=${pageSize}&keyword=${encodeURIComponent(keyword)}`)
      if (res.status === 404) { setError('无权限访问'); return }
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: UsersResponse = await res.json()
      setUsers(data.items || [])
      setTotal(data.total || 0)
    } catch (e) {
      setError(e instanceof Error ? e.message : '加载失败')
    } finally {
      setLoading(false)
    }
  }, [page, pageSize, keyword])

  useEffect(() => { load() }, [load])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  // 切换页大小回到第一页
  useEffect(() => { setPage(1) }, [pageSize])

  const canModify = (u: AdminUser): boolean => {
    if (actionLoading === u.id) return false
    if (u.role === 'super_admin') return false
    if (u.role === 'admin' && !isSuper) return false
    return true
  }

  const handleCreate = async () => {
    setFormError('')
    if (!form.username.trim() || !form.password) { setFormError('请填写用户名和密码'); return }
    setSubmitting(true)
    try {
      const res = await apiFetch(`${API_BASE}/admin/users`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      const data = await res.json()
      if (!res.ok) { setFormError(data.detail || '创建失败'); return }
      setShowCreate(false)
      setForm({ username: '', password: '', role: 'user' })
      setPage(1)
      load(true)
    } catch {
      setFormError('网络异常')
    } finally {
      setSubmitting(false)
    }
  }

  const handleToggleActive = async (u: AdminUser) => {
    if (u.role === 'super_admin' || u.role === 'admin') return
    setActionLoading(u.id)
    try {
      const res = await apiFetch(`${API_BASE}/admin/users/${u.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !u.is_active }),
      })
      if (res.ok) load(true)
    } finally {
      setActionLoading(null)
    }
  }

  const handleToggleRole = async (u: AdminUser) => {
    if (u.role === 'super_admin' || u.role === 'admin') return
    setActionLoading(u.id)
    try {
      const nextRole = u.role === 'admin' ? 'user' : 'admin'
      const res = await apiFetch(`${API_BASE}/admin/users/${u.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: nextRole }),
      })
      if (res.ok) load(true)
    } finally {
      setActionLoading(null)
    }
  }

  const handleResetPwd = async () => {
    if (!resetTarget || newPwd.length < 8) return
    setActionLoading(resetTarget.id)
    try {
      const res = await apiFetch(`${API_BASE}/admin/users/${resetTarget.id}/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_password: newPwd }),
      })
      if (res.ok) { setResetTarget(null); setNewPwd('') }
    } finally {
      setActionLoading(null)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setActionLoading(deleteTarget.id)
    try {
      const res = await apiFetch(`${API_BASE}/admin/users/${deleteTarget.id}`, {
        method: 'DELETE',
      })
      if (res.ok) {
        setDeleteTarget(null)
        load(true)
      }
    } finally {
      setActionLoading(null)
    }
  }

  return (
    <div className="ua-overlay" onClick={onClose}>
      <div className="ua-panel" onClick={(e) => e.stopPropagation()}>
        <div className="ua-header">
          <h2>用户管理</h2>
          <button className="ua-close" onClick={onClose} aria-label="关闭">✕</button>
        </div>

        <div className="ua-toolbar">
          <input
            className="ua-search"
            placeholder="搜索用户名..."
            value={keyword}
            onChange={(e) => { setKeyword(e.target.value); setPage(1) }}
          />
          <button className="ua-btn-primary" onClick={() => setShowCreate(true)}>+ 新建用户</button>
        </div>

        {error && <div className="ua-error">{error}</div>}

        {loading ? (
          <div className="ua-loading">加载中…</div>
        ) : (
          <table className="ua-table">
            <thead>
              <tr>
                <th style={{ width: 50 }}>序号</th>
                <th>用户名</th>
                <th>角色</th>
                <th>状态</th>
                <th>最近登录</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr><td colSpan={6} style={{ textAlign: 'center', color: '#9ca3af', padding: '24px' }}>暂无用户</td></tr>
              ) : users.map((u, idx) => {
                const isSelf = u.id === currentUserId
                const isSuperRow = u.role === 'super_admin'
                const locked = !canModify(u)
                return (
                  <tr key={u.id}>
                    <td style={{ color: '#9ca3af' }}>{(page - 1) * pageSize + idx + 1}</td>
                    <td>
                      {u.username}
                      {isSelf && <span style={{ color: '#2563eb', fontSize: 12, marginLeft: 6 }}>（当前账号）</span>}
                    </td>
                    <td>
                      <span className={`ua-badge ${ROLE_BADGE[u.role] || 'ua-badge-user'}`}>
                        {ROLE_LABEL[u.role] || u.role}
                      </span>
                    </td>
                    <td>
                      <span className={`ua-dot ${u.is_active ? 'ua-dot-on' : 'ua-dot-off'}`} />
                      {u.is_active ? '启用' : '禁用'}
                    </td>
                    <td>{u.last_login ? new Date(u.last_login).toLocaleString('zh-CN') : '—'}</td>
                    <td className="ua-actions">
                      {isSuperRow ? (
                        <span style={{ color: '#d97706', fontSize: 12 }}>🔒 超级管理员受保护</span>
                      ) : u.role === 'admin' && !isSuper ? (
                        <span style={{ color: '#9ca3af', fontSize: 12 }}>🔒 管理员账号不可操作</span>
                      ) : (
                        <>
                          <button className="ua-btn-sm" disabled={locked || isSelf} onClick={() => handleToggleActive(u)}>
                            {u.is_active ? '禁用' : '启用'}
                          </button>
                          <button className="ua-btn-sm" disabled={locked} onClick={() => handleToggleRole(u)}>
                            {u.role === 'admin' ? '降为普通' : '设为管理员'}
                          </button>
                          <button className="ua-btn-sm" disabled={locked} onClick={() => { setResetTarget(u); setNewPwd('') }}>
                            重置密码
                          </button>
                          <button
                            className="ua-btn-sm ua-btn-danger"
                            disabled={locked || isSelf}
                            title={isSelf ? '不能删除当前登录账号' : ''}
                            onClick={() => setDeleteTarget(u)}
                          >
                            删除
                          </button>
                        </>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}

        <div className="ua-pager">
          <span>
            共 <strong>{total}</strong> 个用户，第 {page}/{totalPages} 页
          </span>
          <div className="ua-pager-controls">
            <select
              className="ua-page-size"
              value={pageSize}
              onChange={(e) => setPageSize(Number(e.target.value))}
            >
              {[10, 20, 50, 100].map(n => <option key={n} value={n}>{n}条/页</option>)}
            </select>
            <button className="ua-btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>上一页</button>
            <button className="ua-btn-sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>下一页</button>
          </div>
        </div>

        {showCreate && (
          <div className="ua-modal-mask" onClick={() => setShowCreate(false)}>
            <div className="ua-modal" onClick={(e) => e.stopPropagation()}>
              <h3>新建用户</h3>
              <input className="ua-input" placeholder="用户名（3-32位字母数字下划线）" value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })} />
              <input className="ua-input" type="password" placeholder="密码（至少8位，含字母和数字）" value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })} />
              <select className="ua-input" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
                <option value="user">普通用户</option>
                {isSuper && <option value="admin">管理员</option>}
                {isSuper && <option value="super_admin">超级管理员</option>}
              </select>
              {formError && <div className="ua-error">{formError}</div>}
              <div className="ua-modal-actions">
                <button className="ua-btn-sm" onClick={() => setShowCreate(false)}>取消</button>
                <button className="ua-btn-primary" disabled={submitting} onClick={handleCreate}>
                  {submitting ? '创建中…' : '创建'}
                </button>
              </div>
            </div>
          </div>
        )}

        {resetTarget && (
          <div className="ua-modal-mask" onClick={() => setResetTarget(null)}>
            <div className="ua-modal" onClick={(e) => e.stopPropagation()}>
              <h3>重置「{resetTarget.username}」的密码</h3>
              <input className="ua-input" type="password" placeholder="新密码（至少8位，含字母和数字）" value={newPwd}
                onChange={(e) => setNewPwd(e.target.value)} />
              <div className="ua-modal-actions">
                <button className="ua-btn-sm" onClick={() => setResetTarget(null)}>取消</button>
                <button className="ua-btn-primary" disabled={actionLoading === resetTarget.id || newPwd.length < 8} onClick={handleResetPwd}>
                  确认重置
                </button>
              </div>
            </div>
          </div>
        )}

        {deleteTarget && (
          <div className="ua-modal-mask" onClick={() => setDeleteTarget(null)}>
            <div className="ua-modal" onClick={(e) => e.stopPropagation()}>
              <h3>删除用户</h3>
              <p style={{ margin: '12px 0', color: '#6b7280' }}>
                确定要删除用户「{deleteTarget.username}」吗？此操作不可恢复，该用户的导办进度也会一并清除。
              </p>
              <div className="ua-modal-actions">
                <button className="ua-btn-sm" onClick={() => setDeleteTarget(null)}>取消</button>
                <button className="ua-btn-primary ua-btn-danger-bg" disabled={actionLoading === deleteTarget.id} onClick={handleDelete}>
                  {actionLoading === deleteTarget.id ? '删除中…' : '确认删除'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
