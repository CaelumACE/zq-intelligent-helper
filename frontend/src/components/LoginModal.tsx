import { useState } from 'react'
import { apiFetch, API_BASE } from '../utils/api'
import type { AuthUser } from '../types'

interface LoginModalProps {
  onLogin: (token: string, user: AuthUser) => void
  onClose?: () => void
  /** 全屏模式：未登录时只显示登录页，不渲染主界面 */
  fullscreen?: boolean
}

export default function LoginModal({ onLogin, onClose, fullscreen }: LoginModalProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showChangePwd, setShowChangePwd] = useState(false)
  const [oldPwd, setOldPwd] = useState('')
  const [newPwd, setNewPwd] = useState('')
  const [pwdMsg, setPwdMsg] = useState('')
  const [pwdError, setPwdError] = useState('')
  const [pwdLoading, setPwdLoading] = useState(false)

  const submit = async () => {
    setError('')
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || '登录失败')
        return
      }
      onLogin(data.token, data.user)
      setUsername('')
      setPassword('')
    } catch {
      setError('网络异常，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  const handleChangePwd = async () => {
    setPwdError('')
    setPwdMsg('')
    if (newPwd.length < 8) { setPwdError('新密码至少8位，含字母和数字'); return }
    setPwdLoading(true)
    try {
      const res = await apiFetch(`${API_BASE}/auth/change-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ old_password: oldPwd, new_password: newPwd }),
      })
      const data = await res.json()
      if (!res.ok) { setPwdError(data.detail || '修改失败'); return }
      setPwdMsg('密码已修改，请用新密码重新登录')
      setOldPwd('')
      setNewPwd('')
    } catch {
      setPwdError('网络异常')
    } finally {
      setPwdLoading(false)
    }
  }

  const card = (
    <div className={fullscreen ? 'login-fs-card' : 'login-card'} onClick={(e) => e.stopPropagation()}>
      {fullscreen ? (
        <div className="login-fs-logo">
          <div className="login-fs-mark">政</div>
          <div className="login-fs-title">政企智能助手</div>
          <div className="login-fs-sub">安全登录</div>
        </div>
      ) : (
        <h2 className="login-title">登录</h2>
      )}
      <input
        className="login-input"
        placeholder="用户名"
        value={username}
        autoComplete="username"
        onChange={(e) => setUsername(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
      />
      <input
        className="login-input"
        placeholder="密码"
        type="password"
        value={password}
        autoComplete="current-password"
        onChange={(e) => setPassword(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
      />
      {error && <div className="login-error">{error}</div>}
      <button className="login-submit" disabled={loading} onClick={submit}>
        {loading ? '处理中…' : '登录'}
      </button>
      {!fullscreen && onClose && (
        <button className="login-cancel" onClick={onClose} style={{ marginTop: 8, background: 'none', border: 'none', color: '#6b7280', cursor: 'pointer', fontSize: 13, width: '100%' }}>
          取消
        </button>
      )}

      <div style={{ marginTop: 16, textAlign: 'center' }}>
        <button
          onClick={() => { setShowChangePwd(!showChangePwd); setPwdMsg(''); setPwdError('') }}
          style={{ background: 'none', border: 'none', color: '#2563eb', cursor: 'pointer', fontSize: 12 }}
        >
          {showChangePwd ? '返回登录' : '修改密码'}
        </button>
      </div>

      {showChangePwd && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid #e5e7eb' }}>
          <input className="login-input" type="password" placeholder="原密码" value={oldPwd} onChange={(e) => setOldPwd(e.target.value)} />
          <input className="login-input" type="password" placeholder="新密码（至少8位，含字母数字）" value={newPwd} onChange={(e) => setNewPwd(e.target.value)} />
          {pwdError && <div className="login-error">{pwdError}</div>}
          {pwdMsg && <div style={{ color: '#10b981', fontSize: 12, marginBottom: 8 }}>{pwdMsg}</div>}
          <button className="login-submit" disabled={pwdLoading} onClick={handleChangePwd} style={{ background: '#059669' }}>
            {pwdLoading ? '处理中…' : '确认修改'}
          </button>
        </div>
      )}
    </div>
  )

  if (fullscreen) {
    return <div className="login-fullscreen">{card}</div>
  }

  return (
    <div className="login-overlay" onClick={onClose}>
      {card}
    </div>
  )
}
