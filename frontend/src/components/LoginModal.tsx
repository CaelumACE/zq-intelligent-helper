import { useState } from 'react'
import { API_BASE } from '../utils/api'
import type { AuthUser } from '../types'
import BotAvatar from './BotAvatar'

interface LoginModalProps {
  onLogin: (token: string, user: AuthUser) => void
  onClose?: () => void
  /** 全屏模式：未登录时只显示登录页，不渲染主界面 */
  fullscreen?: boolean
}

export default function LoginModal({ onLogin, onClose, fullscreen }: LoginModalProps) {
  const [username, setUsername] = useState(() => localStorage.getItem('zq_remember_user') || '')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(() => !!localStorage.getItem('zq_remember_user'))
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    if (!username.trim() || !password) {
      setError('请输入用户名和密码')
      return
    }
    setError('')
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username.trim(), password }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || '登录失败')
        return
      }
      if (remember) {
        localStorage.setItem('zq_remember_user', username.trim())
      } else {
        localStorage.removeItem('zq_remember_user')
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
    <div className={fullscreen ? 'login-card' : 'login-card login-card-modal'} onClick={(e) => e.stopPropagation()}>
      <div className="login-logo">
        <BotAvatar size={52} state={loading ? 'thinking' : 'idle'} ink="#ffffff" paper="#0c4a6e" attract={!loading} title="政企智能助手" />
      </div>
      <div className="login-title">政企智能助手</div>
      <div className="login-subtitle">安全登录 · 智启政务</div>

      <div className="login-form">
        <div className="login-field">
          <label htmlFor="login-user">用户名</label>
          <input
            id="login-user"
            type="text"
            placeholder="请输入用户名"
            value={username}
            autoComplete="username"
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
            autoFocus
          />
        </div>
        <div className="login-field">
          <label htmlFor="login-pass">密码</label>
          <input
            id="login-pass"
            type="password"
            placeholder="请输入密码"
            value={password}
            autoComplete="current-password"
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && submit()}
          />
        </div>

        <div className="login-options">
          <label className="login-remember">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            <span>记住我</span>
          </label>
          <span className="login-forgot" title="暂未开放">忘记密码？</span>
        </div>

        {error && <div className="login-error">{error}</div>}

        <button className="login-btn" disabled={loading} onClick={submit}>
          {loading ? '登录中…' : '登 录'}
        </button>
      </div>

      <div className="login-footer">© 2026 政企智能助手 · 私有化部署</div>

      {!fullscreen && onClose && (
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: 14,
            right: 14,
            width: 30,
            height: 30,
            borderRadius: '50%',
            border: '1px solid var(--border)',
            background: '#fff',
            cursor: 'pointer',
            color: 'var(--text-tertiary)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          aria-label="关闭"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <path d="M18 6 6 18M6 6l12 12" />
          </svg>
        </button>
      )}
    </div>
  )

  if (fullscreen) {
    return <div className="login-page">{card}</div>
  }

  return (
    <div className="modal-overlay" onClick={onClose} style={{ zIndex: 300 }}>
      {card}
    </div>
  )
}

