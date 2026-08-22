import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import ChatInput from './components/ChatInput'
import MessageList from './components/MessageList'
import WelcomeScreen from './components/WelcomeScreen'
import type { Message, Conversation, Reference } from './types'
import './App.css'

const API_BASE = __API_BASE__

const WELCOME_GREETING = '你好，我是政企智能助手。您可以问我政策问题、让我帮您写公文，也可以了解办事流程。请问今天想了解什么？'

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [currentView, setCurrentView] = useState<'chat' | 'home'>('home')
  const [sidebarOpen, setSidebarOpen] = useState(false)

  useEffect(() => {
    loadConversations()
  }, [])

  const loadConversations = async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions`)
      const data = await res.json()
      setConversations(data.sessions || [])
    } catch (e) {
      console.error('加载会话失败', e)
    }
  }

  const appendAssistant = (
    id: string,
    chunk: string,
    refs?: Reference[],
    replace?: boolean,
  ) => {
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

  const handleSendMessage = async (content: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    const assistantId = (Date.now() + 1).toString()
    const nextMessages = [...messages, userMessage]
    setMessages(nextMessages)
    setCurrentView('chat')
    setIsLoading(true)
    setSidebarOpen(false)

    let sessionId = currentSessionId
    let references: Reference[] | undefined
    let started = false

    try {
      const history = nextMessages.filter(m => m.role !== 'system').map(m => ({
        role: m.role,
        content: m.content,
      }))

      const response = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content,
          session_id: sessionId || undefined,
          history,
        }),
      })

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`)
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })

        let boundary = buffer.indexOf('\n\n')
        while (boundary !== -1) {
          const block = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)

          for (const line of block.split('\n')) {
            if (!line.startsWith('data:')) continue
            const payload = line.slice(5).trim()
            if (!payload || payload === '[DONE]') continue

            let evt: { type?: string; content?: string; message?: string; references?: Reference[]; session_id?: string }
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

          boundary = buffer.indexOf('\n\n')
        }
      }

      if (started) {
        appendAssistant(assistantId, '', references)
      }
      loadConversations()
    } catch (error) {
      console.error('Chat error:', error)
      if (!started) {
        appendAssistant(assistantId, '抱歉，服务暂时不可用，请稍后重试。')
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleNewChat = () => {
    setMessages([
      {
        id: 'welcome',
        role: 'assistant',
        content: WELCOME_GREETING,
        timestamp: Date.now(),
      },
    ])
    setCurrentSessionId(null)
    setCurrentView('chat')
    setSidebarOpen(false)
  }

  const normalizeMessages = (raw: Message[], sessionId: string): Message[] => {
    return (raw || []).map((m, i) => ({
      ...m,
      id: m.id || `${sessionId}-${i}`,
      timestamp: m.timestamp || Date.now(),
      references: m.references && m.references.length > 0 ? m.references : undefined,
    }))
  }

  const handleSelectConversation = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions/${id}`)
      const data = await res.json()
      setCurrentSessionId(id)
      const normalized = normalizeMessages(data.messages || [], id)
      setMessages(normalized)
      setCurrentView(normalized.length ? 'chat' : 'home')
      setSidebarOpen(false)
    } catch (e) {
      console.error('加载会话详情失败', e)
    }
  }

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await fetch(`${API_BASE}/chat/sessions/${id}`, { method: 'DELETE' })
      if (id === currentSessionId) {
        handleNewChat()
      }
      loadConversations()
    } catch (err) {
      console.error('删除会话失败', err)
    }
  }

  const welcomeMessage: Message = {
    id: 'welcome',
    role: 'assistant',
    content: WELCOME_GREETING,
    timestamp: Date.now(),
  }

  return (
    <div className="app-shell">
      {/* PC 端固定侧边栏 */}
      <div className="hidden md:block">
        <Sidebar
          currentView={currentView}
          conversations={conversations}
          currentSessionId={currentSessionId}
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
        />
      </div>

      {/* 移动端抽屉侧边栏 */}
      {sidebarOpen && (
        <div className="mobile-overlay" onClick={() => setSidebarOpen(false)} />
      )}
      <div className={`mobile-drawer md:hidden ${sidebarOpen ? 'open' : ''}`}>
        <Sidebar
          currentView={currentView}
          conversations={conversations}
          currentSessionId={currentSessionId}
          onNewChat={handleNewChat}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
        />
      </div>

      <div className="main-column">
        <Header
          title={currentView === 'home' ? '政企智能助手' : '对话'}
          onMenu={() => setSidebarOpen(true)}
        />

        <main className="flex-1 overflow-y-auto">
          {currentView === 'home' && messages.length === 0 ? (
            <WelcomeScreen onQuickAction={handleSendMessage} />
          ) : (
            <MessageList
              messages={messages.length === 0 ? [welcomeMessage] : messages}
              isLoading={isLoading}
            />
          )}
        </main>

        <ChatInput onSend={handleSendMessage} disabled={isLoading} />
      </div>
    </div>
  )
}

export default App
