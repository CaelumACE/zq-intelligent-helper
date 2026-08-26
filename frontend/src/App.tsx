import { useState, useEffect, useRef } from 'react'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import ChatInput from './components/ChatInput'
import MessageList from './components/MessageList'
import WelcomeScreen from './components/WelcomeScreen'
import WritingPanel from './components/WritingPanel'
import GuidePanel from './components/GuidePanel'
import LoginModal from './components/LoginModal'
import UserAdmin from './components/UserAdmin'
import ComparePanel from './components/ComparePanel'
import { apiFetch, setUnauthorizedHandler } from './utils/api'
import type { AuthUser, Message, Conversation, Reference, ModelProvider, WritingRequest } from './types'
import './App.css'

const API_BASE = __API_BASE__

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentView, setCurrentView] = useState<'chat' | 'home'>('home')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [model, setModel] = useState<ModelProvider>('minimax')

  // 方案A：启动时从后端/health读取实际LLM provider，动态设置默认模型
  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.llm_provider === 'deepseek' || data?.llm_provider === 'minimax') {
          setModel(data.llm_provider)
        }
      })
      .catch(() => {})
  }, [])
  const [writingOpen, setWritingOpen] = useState(false)
  const [activePanel, setActivePanel] = useState<'qa' | 'guide' | 'compare'>('qa')
  const [loginOpen, setLoginOpen] = useState(false)
  const [deletingId, setDeletingId] = useState<string | null>(null)
  const [userAdminOpen, setUserAdminOpen] = useState(false)
  const [token, setToken] = useState<string | null>(() => sessionStorage.getItem('token'))
  const [user, setUser] = useState<AuthUser | null>(() => {
    const raw = sessionStorage.getItem('user')
    return raw ? JSON.parse(raw) : null
  })
  const sessionCacheRef = useRef<Map<string, Message[]>>(new Map())

  const activeRequestRef = useRef<AbortController | null>(null)
  const activeAssistantIdRef = useRef<string | null>(null)
  const statusRef = useRef<Message['status'] | undefined>(undefined)
  const sendingRef = useRef(false)
  const sessionSelectRef = useRef<string | null>(null)

  // 单点登录检测：每60秒检查当前token是否仍有效，被其他端踢线则自动登出
  useEffect(() => {
    if (!token) return
    const check = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/auth/me`, {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.status === 401) {
          sessionStorage.removeItem('token')
          sessionStorage.removeItem('user')
          setToken(null)
          setUser(null)
        }
      } catch { /* network error, ignore */ }
    }
    const timer = setInterval(check, 60000)
    // 页面可见时也检查一次（从其他标签切回来时）
    const onVisible = () => { if (document.visibilityState === 'visible') check() }
    document.addEventListener('visibilitychange', onVisible)
    return () => { clearInterval(timer); document.removeEventListener('visibilitychange', onVisible) }
  }, [token])

  useEffect(() => {
    loadConversations()
  }, [token])

  useEffect(() => {
    if (token) {
      setUnauthorizedHandler(() => {
        sessionStorage.removeItem('token')
        sessionStorage.removeItem('user')
        setToken(null)
        setUser(null)
        setLoginOpen(true)
      })
    } else {
      setUnauthorizedHandler(null)
      setLoginOpen(false)
    }
  }, [token])

  useEffect(() => {
    if (!isLoading && messages.length === 0) {
      setCurrentView('home')
    }
  }, [isLoading, messages.length])

  const loadConversations = async () => {
    if (!token) {
      setConversations([])
      return
    }
    try {
      const res = await apiFetch(`${API_BASE}/chat/sessions`)
      const data = await res.json()
      const sessions: Conversation[] = data.sessions || []
      setConversations(sessions)
    } catch (e) {
      console.error('加载会话失败', e)
    }
  }

  const abortActiveRequest = () => {
    if (activeRequestRef.current) {
      activeRequestRef.current.abort()
      activeRequestRef.current = null
    }
    activeAssistantIdRef.current = null
  }

  const appendAssistant = (
    id: string,
    chunk: string,
    refs?: Reference[],
    replace?: boolean,
  ) => {
    if (activeAssistantIdRef.current !== id) return
    setMessages(prev => {
      const existing = prev.find(m => m.id === id)
      if (existing) {
        return prev.map(m =>
          m.id === id
            ? {
                ...m,
                content: replace ? chunk : m.content + chunk,
                references: refs !== undefined ? refs : m.references,
              }
            : m,
        )
      }
      return [
        ...prev,
        {
          id,
          role: 'assistant' as const,
          content: chunk,
          timestamp: Date.now(),
          references: refs,
        },
      ]
    })
  }

  const handleSendMessage = async (content: string, writing?: WritingRequest, followUp = false) => {
    if (!token) {
      setLoginOpen(true)
      return
    }
    if (isLoading || isStreaming) return
    if (sendingRef.current) return
    sendingRef.current = true
    statusRef.current = undefined
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    const assistantId = (Date.now() + 1).toString()
    activeAssistantIdRef.current = assistantId
    const nextMessages = [...messages, userMessage]
    setMessages(nextMessages)
    setCurrentView('chat')
    setIsLoading(true)
    setIsStreaming(true)
    setSidebarOpen(false)

    let sessionId = currentSessionId
    let references: Reference[] | undefined
    let followUpChips: string[] | undefined
    let started = false
    let controller: AbortController | null = null
    let idleTimer: ReturnType<typeof setTimeout> | null = null

    try {
      const history = nextMessages.filter(m => m.role !== 'system').map(m => ({
        role: m.role,
        content: m.content,
      }))

      controller = new AbortController()
      const previousController = activeRequestRef.current
      if (previousController) {
        previousController.abort()
      }
      activeRequestRef.current = controller

      const response = await apiFetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          message: content,
          session_id: sessionId || undefined,
          history,
          provider: model,
          follow_up: followUp || undefined,
          doc_type: writing?.docType,
          title: writing?.title,
          to: writing?.to,
          body: writing?.body,
          sign: writing?.sign,
        }),
      })

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let doneReceived = false

      // 60 秒无数据超时保护：代理层/连接挂起时主动 abort，
      // 避免 reader.read() 一直等待导致 isLoading/isStreaming 无法复位。
      const resetIdleTimer = () => {
        if (idleTimer) clearTimeout(idleTimer)
        idleTimer = setTimeout(() => {
          controller?.abort()
        }, 60000)
      }
      resetIdleTimer()

      while (!doneReceived) {
        const { done, value } = await reader.read()
        resetIdleTimer()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        let boundary = buffer.indexOf('\n\n')
        while (boundary !== -1) {
          const block = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)

          for (const line of block.split('\n')) {
            if (!line.startsWith('data:')) continue
            const payload = line.slice(5).trim()
            if (!payload) continue
            // 收到 [DONE] 立即退出，不依赖 TCP 连接正常关闭，避免流挂起
            if (payload === '[DONE]') {
              doneReceived = true
              break
            }

            let evt: { type?: string; content?: string; message?: string; references?: Reference[]; follow_up_chips?: string[]; session_id?: string; status?: Message['status'] }
            try {
              evt = JSON.parse(payload)
            } catch {
              continue
            }

            if (evt.type === 'meta') {
              if (evt.session_id) {
                sessionId = evt.session_id
                setCurrentSessionId(evt.session_id)
              }
              if (evt.references) references = evt.references
              if (evt.follow_up_chips) followUpChips = evt.follow_up_chips
              if (evt.status) statusRef.current = evt.status
            } else if (evt.type === 'done') {
              if (evt.status) statusRef.current = evt.status
              if (evt.follow_up_chips) followUpChips = evt.follow_up_chips
              // Reload conversation list to show the new session in sidebar
              loadConversations()
            } else if (evt.type === 'delta' && evt.content) {
              if (!started) {
                started = true
                setIsLoading(false)
                appendAssistant(assistantId, evt.content, references)
              } else {
                appendAssistant(assistantId, evt.content)
              }
            } else if (evt.type === 'error' && evt.message) {
              if (!started) {
                started = true
                setIsLoading(false)
              }
              appendAssistant(assistantId, evt.message, undefined, true)
            }
          }

          if (doneReceived) break
          boundary = buffer.indexOf('\n\n')
        }
      }

      if (idleTimer) clearTimeout(idleTimer)

      if (started) {
        setMessages(prev => prev.map(m => {
          if (m.id === assistantId) {
            return { ...m, references: references ?? m.references, followUpChips: followUpChips ?? m.followUpChips, model, status: statusRef.current }
          }
          return m
        }))
      }
      loadConversations()
    } catch (error) {
      if ((error as Error)?.name === 'AbortError') {
        console.log('Chat stream aborted', assistantId)
      } else {
        console.error('Chat error:', error)
        if (!started) {
          appendAssistant(assistantId, '抱歉，服务暂时不可用，请稍后重试。')
        }
      }
    } finally {
      if (idleTimer) clearTimeout(idleTimer)
      sendingRef.current = false
      const isCurrentRequest = activeRequestRef.current === controller
      if (isCurrentRequest) {
        activeRequestRef.current = null
      }
      if (activeAssistantIdRef.current === assistantId) {
        activeAssistantIdRef.current = null
      }
      setIsLoading(false)
      if (isCurrentRequest) {
        setIsStreaming(false)
      }
    }
  }

  const handleNewChat = () => {
    abortActiveRequest()
    setIsLoading(false)
    setIsStreaming(false)
    setMessages([])
    sessionCacheRef.current.clear()
    setCurrentSessionId(null)
    setCurrentView('home')
    setActivePanel('qa')
    setSidebarOpen(false)
  }

  const handleLogout = async () => {
    abortActiveRequest()
    setIsLoading(false)
    setIsStreaming(false)
    // 通知后端使当前 token 失效
    try {
      await apiFetch(`${API_BASE}/auth/logout`, { method: 'POST' })
    } catch { /* ignore */ }
    sessionStorage.removeItem('token')
    sessionStorage.removeItem('user')
    setToken(null)
    setUser(null)
    setMessages([])
    setConversations([])
    setCurrentSessionId(null)
    setCurrentView('home')
    sessionCacheRef.current.clear()
  }

  const handleStop = () => {
    abortActiveRequest()
    setIsLoading(false)
    setIsStreaming(false)
  }

  const normalizeMessages = (raw: Message[], sessionId: string): Message[] => {
    return (raw || []).map((m, i) => ({
      ...m,
      id: m.id || `${sessionId}-${i}`,
      timestamp: m.timestamp || Date.now(),
      references: m.references && m.references.length > 0 ? m.references : undefined,
    }))
  }

  const handleSelectConversation = (id: string) => {
    sessionSelectRef.current = id
    abortActiveRequest()
    setIsLoading(false)
    setIsStreaming(false)
    setCurrentSessionId(id)
    const cached = sessionCacheRef.current.get(id)
    if (cached) {
      setMessages(cached)
      setCurrentView(cached.length ? 'chat' : 'home')
      setSidebarOpen(false)
      return
    }
    setSidebarOpen(false)
    apiFetch(`${API_BASE}/chat/sessions/${id}`)
      .then((res) => (res.ok ? res.json() : Promise.reject(new Error(`HTTP ${res.status}`))))
      .then((data) => {
        if (sessionSelectRef.current !== id) return
        const normalized = normalizeMessages(data.messages || [], id)
        sessionCacheRef.current.set(id, normalized)
        setMessages(normalized)
        setCurrentView(normalized.length ? 'chat' : 'home')
        setSidebarOpen(false)
      })
      .catch((e) => console.error('加载会话详情失败', e))
  }

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    e.preventDefault()
    if (deletingId) return // 防竞态：有删除进行中时拒绝新请求
    setDeletingId(id)
    sessionCacheRef.current.delete(id)

    // 先在本地点掉侧栏条目，再发请求，避免等 DELETE 响应 + 列表重载造成的延迟
    const prevConversations = conversations
    setConversations(prev => prev.filter(c => c.id !== id))
    if (id === currentSessionId) {
      handleNewChat()
    }

    try {
      const res = await apiFetch(`${API_BASE}/chat/sessions/${id}`, { method: 'DELETE' })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
    } catch (err) {
      console.error('删除会话失败', err)
      // 失败回滚 UI
      setConversations(prevConversations)
    } finally {
      setDeletingId(null)
    }
  }

  // S03-8: 全局登录守卫——未登录只渲染全屏登录页
  if (!token) {
    return (
      <LoginModal
        fullscreen
        onLogin={(newToken, newUser) => {
          sessionStorage.setItem('token', newToken)
          sessionStorage.setItem('user', JSON.stringify(newUser))
          setLoginOpen(false)
          setToken(newToken)
          setUser(newUser)
        }}
      />
    )
  }

  return (
    <div className="app-shell">
      {/* PC 端固定侧边栏 */}
      <div className="hidden md:block h-full">
        <Sidebar
          conversations={conversations}
          currentSessionId={currentSessionId}
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
          deletingId={deletingId}
          user={user}
          onOpenUserAdmin={() => setUserAdminOpen(true)}
        />
      </div>

      {/* 移动端抽屉侧边栏 */}
      {sidebarOpen && (
        <div className="mobile-overlay" onClick={() => setSidebarOpen(false)} />
      )}
      <div className={`mobile-drawer md:hidden ${sidebarOpen ? 'open' : ''}`}>
        <Sidebar
          conversations={conversations}
          currentSessionId={currentSessionId}
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
          deletingId={deletingId}
          user={user}
          onOpenUserAdmin={() => setUserAdminOpen(true)}
        />
      </div>

      <div className="main-column">
        <Header
          title={currentView === 'home' ? '政企智能助手' : (conversations.find(c => c.id === currentSessionId)?.title || '新对话')}
          onMenu={() => setSidebarOpen(true)}
          onWriting={() => setWritingOpen(true)}
        />

        <div className="app-tabs">
          <button className={activePanel === 'qa' ? 'app-tab active' : 'app-tab'} onClick={() => setActivePanel('qa')}>智能问答</button>
          <button className={activePanel === 'guide' ? 'app-tab active' : 'app-tab'} onClick={() => setActivePanel('guide')}>我要办事</button>
          <button className={activePanel === 'compare' ? 'app-tab active' : 'app-tab'} onClick={() => setActivePanel('compare')}>政策比对</button>
          <div className="app-tabs-right">
            {user ? (
              <>
                <span className="app-user">{user.username}</span>
                <button className="app-user-btn" onClick={handleLogout}>退出</button>
              </>
            ) : (
              <button className="app-user-btn" onClick={() => setLoginOpen(true)}>登录</button>
            )}
          </div>
        </div>

        {activePanel === 'guide' ? (
          <div className="guide-panel">
            <GuidePanel token={token} onRequireLogin={() => setLoginOpen(true)} />
          </div>
        ) : activePanel === 'compare' ? (
          <div className="guide-panel">
            <ComparePanel token={token} userRole={user?.role} onRequireLogin={() => setLoginOpen(true)} />
          </div>
        ) : (
          <>
        <div className={`chat-stream ${currentView === 'home' && messages.length === 0 ? 'home' : ''}`}>
          {currentView === 'home' && messages.length === 0 ? (
            <WelcomeScreen onQuickAction={handleSendMessage} disabled={isStreaming || isLoading} />
          ) : (
            <MessageList
              messages={messages}
              isLoading={isLoading}
              isStreaming={isStreaming}
              onStop={handleStop}
              onFollowUp={(prompt) => handleSendMessage(prompt, undefined, true)}
            />
          )}
        </div>

        <ChatInput onSend={handleSendMessage} onStop={handleStop} disabled={isStreaming || isLoading} model={model} onModelChange={setModel} />
          </>
        )}

        {loginOpen && (
          <LoginModal
            onClose={() => setLoginOpen(false)}
            onLogin={(newToken, newUser) => {
              sessionStorage.setItem('token', newToken)
              sessionStorage.setItem('user', JSON.stringify(newUser))
              setToken(newToken)
              setUser(newUser)
              setLoginOpen(false)
            }}
          />
        )}

        <WritingPanel
          open={writingOpen}
          model={model}
          onClose={() => setWritingOpen(false)}
          onGenerate={(prompt, _model, writing) => {
            setWritingOpen(false)
            handleSendMessage(prompt, writing)
          }}
        />

        {userAdminOpen && user && (user.role === 'admin' || user.role === 'super_admin') && (
          <UserAdmin onClose={() => setUserAdminOpen(false)} currentUserId={user.id} currentUserRole={user.role} />
        )}
        {userAdminOpen && user && user.role === 'user' && (
          <div className="ua-overlay" onClick={() => setUserAdminOpen(false)}>
            <div className="ua-panel" onClick={(e) => e.stopPropagation()} style={{maxWidth:380,textAlign:'center',padding:'32px 28px'}}>
              <div style={{fontSize:40,marginBottom:12}}>🔒</div>
              <h3 style={{margin:'0 0 8px',fontSize:16,color:'#1A2433'}}>无访问权限</h3>
              <p style={{margin:'0 0 20px',fontSize:13,color:'#8A94A6',lineHeight:1.6}}>当前账号无用户管理权限，<br/>请联系管理员。</p>
              <button className="ua-btn ua-btn-primary" onClick={() => setUserAdminOpen(false)} style={{width:'100%'}}>我知道了</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
