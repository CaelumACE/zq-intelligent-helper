import { useState, useEffect, useRef, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import ChatInput from './components/ChatInput'
import MessageList from './components/MessageList'
import WelcomeScreen from './components/WelcomeScreen'
import WritingPanel from './components/WritingPanel'
import GuidePanel from './components/GuidePanel'
import LoginModal from './components/LoginModal'
import UserAdmin from './components/UserAdmin'
import ChangePasswordModal from './components/ChangePasswordModal'
import ComparePanel from './components/ComparePanel'
import { apiFetch, setUnauthorizedHandler } from './utils/api'
import type { AuthUser, Message, Conversation, Reference, ModelProvider, WritingRequest, StructuredAnswer } from './types'
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
  const [changePwdOpen, setChangePwdOpen] = useState(false)
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

  // SSO check
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
      } catch { /* ignore */ }
    }
    const timer = setInterval(check, 60000)
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
    structuredAnswer?: StructuredAnswer,
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
                structuredAnswer: structuredAnswer !== undefined ? structuredAnswer : m.structuredAnswer,
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
          structuredAnswer,
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
    let structuredAnswer: StructuredAnswer | undefined
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

      const resetIdleTimer = () => {
        if (idleTimer) clearTimeout(idleTimer)
        idleTimer = setTimeout(() => {
          controller?.abort()
        }, 60000)
      }
      resetIdleTimer()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        resetIdleTimer()
        buffer += decoder.decode(value, { stream: true })

        let boundary: number
        while ((boundary = buffer.indexOf('\n\n')) >= 0) {
          const rawEvent = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)

          const lines = rawEvent.split('\n')
          let evt: { type?: string; content?: string; session_id?: string; references?: Reference[]; follow_up_chips?: string[]; status?: Message['status']; structured_answer?: StructuredAnswer; message?: string; message_id?: string }
          let payload = ''
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              payload += line.slice(6)
            }
          }
          if (!payload || payload === '[DONE]') {
            doneReceived = true
            break
          }
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
            if (evt.structured_answer) structuredAnswer = evt.structured_answer
          } else if (evt.type === 'structured_answer' && evt.structured_answer) {
            structuredAnswer = evt.structured_answer
          } else if (evt.type === 'done') {
            if (evt.status) statusRef.current = evt.status
            if (evt.follow_up_chips) followUpChips = evt.follow_up_chips
            if (evt.references) references = evt.references
            loadConversations()
          } else if (evt.type === 'delta' && evt.content) {
            if (!started) {
              started = true
              setIsLoading(false)
              appendAssistant(assistantId, evt.content, references, false, structuredAnswer)
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
      }

      if (idleTimer) clearTimeout(idleTimer)

      if (started) {
        setMessages(prev => prev.map(m => {
          if (m.id === assistantId) {
            return { ...m, references: references ?? m.references, followUpChips: followUpChips ?? m.followUpChips, structuredAnswer: structuredAnswer ?? m.structuredAnswer, model, status: statusRef.current }
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

  // 用ref持有最新的handleSendMessage，使回调引用稳定
  const sendMessageRef = useRef(handleSendMessage)
  sendMessageRef.current = handleSendMessage

  const handleRegenerate = useCallback((content: string) => {
    sendMessageRef.current(content, undefined, true)
  }, [])

  const handleFollowUp = useCallback((prompt: string) => {
    sendMessageRef.current(prompt, undefined, true)
  }, [])

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
    if (deletingId) return
    setDeletingId(id)
    sessionCacheRef.current.delete(id)

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
      setConversations(prevConversations)
    } finally {
      setDeletingId(null)
    }
  }

  // 登录守卫
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
      {/* PC sidebar */}
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
          onChangePassword={() => setChangePwdOpen(true)}
        />
      </div>

      {/* Mobile overlay */}
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
          onChangePassword={() => setChangePwdOpen(true)}
        />
      </div>

      <div className={`main-column ${writingOpen ? 'writing-open' : ''}`}>
        <Header
          activePanel={activePanel}
          onPanelChange={setActivePanel}
          onWriting={() => setWritingOpen(true)}
          onMenu={() => setSidebarOpen(true)}
          user={user}
          onLogout={handleLogout}
          model={model}
        />

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
                  currentSessionId={currentSessionId}
                  onStop={handleStop}
                  onRegenerate={handleRegenerate}
                  onFollowUp={handleFollowUp}
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
        {changePwdOpen && (
          <ChangePasswordModal
            onClose={() => setChangePwdOpen(false)}
            onSuccess={() => {
              sessionStorage.removeItem('token')
              sessionStorage.removeItem('user')
              setToken(null)
              setUser(null)
              setChangePwdOpen(false)
            }}
          />
        )}

        {userAdminOpen && user && user.role === 'user' && (
          <div className="ua-overlay" onClick={() => setUserAdminOpen(false)}>
            <div className="ua-panel" onClick={(e) => e.stopPropagation()} style={{maxWidth:380,textAlign:'center',padding:'32px 28px'}}>
              <div style={{fontSize:40,marginBottom:12}}>🔒</div>
              <h3 style={{margin:'0 0 8px',fontSize:16,color:'var(--text-primary)'}}>无访问权限</h3>
              <p style={{margin:'0 0 20px',fontSize:13,color:'var(--text-secondary)',lineHeight:1.6}}>当前账号无用户管理权限，<br/>请联系管理员。</p>
              <button className="ua-btn ua-btn-primary" onClick={() => setUserAdminOpen(false)} style={{width:'100%'}}>我知道了</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default App
