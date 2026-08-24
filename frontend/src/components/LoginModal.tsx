import { useState } from 'react'
import { API_BASE } from '../utils/api'
import type { AuthUser } from '../types'

interface LoginModalProps {
  onLogin: (token: string, user: AuthUser) => void
  onClose: () => void
}

export default function LoginModal({ onLogin, onClose }: LoginModalProps) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const submit = async () => {
    setError('')
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/auth/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      })
      const data = await res.json()
      if (!res.ok) {
        setError(data.detail || '操作失败')
        return
      }
      onLogin(data.token, data.user)
    } catch {
      setError('网络异常，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-overlay" onClick={onClose}>
      <div className="login-card" onClick={(e) => e.stopPropagation()}>
        <div className="login-tabs">
          <button className={mode === 'login' ? 'active' : ''} onClick={() => setMode('login')}>登录</button>
          <button className={mode === 'register' ? 'active' : ''} onClick={() => setMode('register')}>注册</button>
        </div>
        <input
          className="login-input"
          placeholder="用户名"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />
        <input
          className="login-input"
          placeholder="密码"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <div className="login-error">{error}</div>}
        <button className="login-submit" disabled={loading} onClick={submit}>
          {loading ? '处理中…' : mode === 'login' ? '登录' : '注册'}
        </button>
        <div className="login-demo">测试账号 demo / demo123</div>
      </div>
    </div>
  )
}
