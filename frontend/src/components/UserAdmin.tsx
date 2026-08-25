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

export default function UserAdmin({ onClose }: { onClose: () => void }) {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ username: '', password: '', role: 'user' })
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')
  const [resetTarget, setResetTarget] = useState<AdminUser | null>(null)
  const [newPwd, setNewPwd] = useState('')
  const [actionLoading, setActionLoading] = useState<number | null>(null)

  const pageSize = 20

  const load = useCallback(async () => {
    setLoading(true)
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
  }, [page, keyword])

  useEffect(() => { load() }, [load])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

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
      load()
    } catch {
      setFormError('网络异常')
    } finally {
      setSubmitting(false)
    }
  }

  const handleToggleActive = async (u: AdminUser) => {
    setActionLoading(u.id)
    try {
      const res = await apiFetch(`${API_BASE}/admin/users/${u.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !u.is_active }),
      })
      if (res.ok) load()
    } finally {
      setActionLoading(null)
    }
  }

  const handleToggleRole = async (u: AdminUser) => {
    setActionLoading(u.id)
    try {
      const res = await apiFetch(`${API_BASE}/admin/users/${u.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role: u.role === 'admin' ? 'user' : 'admin' }),
      })
      if (res.ok) load()
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
                <th>ID</th>
                <th>用户名</th>
                <th>角色</th>
                <th>状态</th>
                <th>最近登录</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>{u.id}</td>
                  <td>{u.username}</td>
                  <td>
                    <span className={`ua-badge ${u.role === 'admin' ? 'ua-badge-admin' : 'ua-badge-user'}`}>
                      {u.role === 'admin' ? '管理员' : '普通用户'}
                    </span>
                  </td>
                  <td>
                    <span className={`ua-dot ${u.is_active ? 'ua-dot-on' : 'ua-dot-off'}`} />
                    {u.is_active ? '启用' : '禁用'}
                  </td>
                  <td>{u.last_login ? new Date(u.last_login).toLocaleString('zh-CN') : '—'}</td>
                  <td className="ua-actions">
                    <button
                      className="ua-btn-sm"
                      disabled={actionLoading === u.id}
                      onClick={() => handleToggleActive(u)}
                    >
                      {u.is_active ? '禁用' : '启用'}
                    </button>
                    <button
                      className="ua-btn-sm"
                      disabled={actionLoading === u.id}
                      onClick={() => handleToggleRole(u)}
                    >
                      {u.role === 'admin' ? '降为普通' : '设为管理员'}
                    </button>
                    <button
                      className="ua-btn-sm"
                      disabled={actionLoading === u.id}
                      onClick={() => { setResetTarget(u); setNewPwd('') }}
                    >
                      重置密码
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="ua-pager">
          <span>共 {total} 条，第 {page}/{totalPages} 页</span>
          <div>
            <button className="ua-btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>上一页</button>
            <button className="ua-btn-sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>下一页</button>
          </div>
        </div>

        {showCreate && (
          <div className="ua-modal-mask" onClick={() => setShowCreate(false)}>
            <div className="ua-modal" onClick={(e) => e.stopPropagation()}>
              <h3>新建用户</h3>
              <input
                className="ua-input"
                placeholder="用户名（3-32位字母数字下划线）"
                value={form.username}
                onChange={(e) => setForm({ ...form, username: e.target.value })}
              />
              <input
                className="ua-input"
                type="password"
                placeholder="密码（至少8位，含字母和数字）"
                value={form.password}
                onChange={(e) => setForm({ ...form, password: e.target.value })}
              />
              <select
                className="ua-input"
                value={form.role}
                onChange={(e) => setForm({ ...form, role: e.target.value })}
              >
                <option value="user">普通用户</option>
                <option value="admin">管理员</option>
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
              <input
                className="ua-input"
                type="password"
                placeholder="新密码（至少8位，含字母和数字）"
                value={newPwd}
                onChange={(e) => setNewPwd(e.target.value)}
              />
              <div className="ua-modal-actions">
                <button className="ua-btn-sm" onClick={() => setResetTarget(null)}>取消</button>
                <button
                  className="ua-btn-primary"
                  disabled={actionLoading === resetTarget.id || newPwd.length < 8}
                  onClick={handleResetPwd}
                >
                  确认重置
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
