import { useState } from 'react'
import { apiFetch, API_BASE } from '../utils/api'

interface ChangePasswordModalProps {
  onClose: () => void
  /** 修改成功后回调（父组件应清除token并跳回登录页） */
  onSuccess: () => void
}

export default function ChangePasswordModal({ onClose, onSuccess }: ChangePasswordModalProps) {
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [confirmPwd, setConfirmPwd] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    setError('')
    setMsg('')
    if (!oldPwd || !newPwd) { setError('请填写原密码和新密码'); return }
    if (newPwd.length < 8) { setError('新密码至少8位，需含字母和数字'); return }
    if (!/[a-zA-Z]/.test(newPwd) || !/\d/.test(newPwd)) { setError('新密码需同时包含字母和数字'); return }
    if (newPwd !== confirmPwd) { setError('两次输入的新密码不一致'); return }
    if (newPwd === oldPwd) { setError('新密码不能与原密码相同'); return }

    setLoading(true)
    try {
      const res = await apiFetch(`${API_BASE}/auth/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_password: oldPwd, new_password: newPwd }),
      })
      const data = await res.json()
      if (!res.ok) { setError(data.detail || '修改失败'); return }
      setMsg('密码修改成功，即将返回登录页…')
      setTimeout(() => onSuccess(), 1500)
    } catch {
      setError('网络异常，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="ua-overlay" onClick={onClose}>
      <div className="ua-panel" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 380, padding: '28px 24px' }}>
        <h3 style={{ margin: '0 0 20px', fontSize: 16, color: '#1A2433', textAlign: 'center' }}>修改密码</h3>

        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'block', fontSize: 13, color: '#4A5568', marginBottom: 4 }}>原密码</label>
          <input
            className="login-input"
            type="password"
            value={oldPwd}
            placeholder="请输入原密码"
            autoComplete="current-password"
            onChange={(e) => setOldPwd(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
          />
        </div>

        <div style={{ marginBottom: 12 }}>
          <label style={{ display: 'block', fontSize: 13, color: '#4A5568', marginBottom: 4 }}>新密码</label>
          <input
            className="login-input"
            type="password"
            value={newPwd}
            placeholder="至少8位，含字母和数字"
            autoComplete="new-password"
            onChange={(e) => setNewPwd(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
          />
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: 'block', fontSize: 13, color: '#4A5568', marginBottom: 4 }}>确认新密码</label>
          <input
            className="login-input"
            type="password"
            value={confirmPwd}
            placeholder="再次输入新密码"
            autoComplete="new-password"
            onChange={(e) => setConfirmPwd(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
          />
        </div>

        {error && <div className="login-error" style={{ marginBottom: 12 }}>{error}</div>}
        {msg && <div style={{ color: '#10b981', fontSize: 13, marginBottom: 12, textAlign: 'center' }}>{msg}</div>}

        <div style={{ display: 'flex', gap: 10 }}>
          <button
            className="ua-btn"
            onClick={onClose}
            disabled={loading}
            style={{ flex: 1 }}
          >
            取消
          </button>
          <button
            className="ua-btn ua-btn-primary"
            onClick={submit}
            disabled={loading}
            style={{ flex: 1 }}
          >
            {loading ? '处理中…' : '确认修改'}
          </button>
        </div>
      </div>
    </div>
  )
}
