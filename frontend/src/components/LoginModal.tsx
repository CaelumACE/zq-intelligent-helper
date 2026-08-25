import { useState } from 'react'
import { API_BASE } from '../utils/api'
import type { AuthUser } from '../types'

interface LoginModalProps {
  onLogin: (token: string, user: AuthUser) => void
  onClose: () => void
}

export default function LoginModal({ onLogin, onClose }: LoginModalProps) {
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

  return (
    <div className="login-overlay" onClick={onClose}>
      <div className="login-card" onClick={(e) => e.stopPropagation()}>
        <h2 className="login-title">登录</h2>
        <input
          className="login-input"
          placeholder="用户名"
          value={username}
          autoComplete="username"
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          className="login-input"
          placeholder="密码"
          type="password"
          value={password}
          autoComplete="current-password"
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <div className="login-error">{error}</div>}
        <button className="login-submit" disabled={loading} onClick={submit}>
          {loading ? '处理中…' : '登录'}
        </button>
      </div>
    </div>
  )
}
