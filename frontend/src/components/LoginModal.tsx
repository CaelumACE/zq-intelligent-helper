import { useState } from 'react'
import { API_BASE } from '../utils/api'
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

  const card = (
    <div className={fullscreen ? 'login-fs-card' : 'login-card'} onClick={(e) => e.stopPropagation()}>
      {fullscreen ? (
        <div className="login-fs-logo">
          <div className="login-fs-mark">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 21h18"/>
              <path d="M5 21V7l7-4 7 4v14"/>
              <path d="M9 21v-6h6v6"/>
            </svg>
          </div>
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
