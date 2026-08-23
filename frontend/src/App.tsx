import { useState, useEffect, useRef } from 'react'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import ChatInput from './components/ChatInput'
import MessageList from './components/MessageList'
import WelcomeScreen from './components/WelcomeScreen'
import WritingPanel from './components/WritingPanel'
import type { Message, Conversation, Reference, ModelProvider, WritingRequest } from './types'
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
  const [model, setModel] = useState<ModelProvider>('deepseek')
  const [writingOpen, setWritingOpen] = useState(false)

  const activeRequestRef = useRef<AbortController | null>(null)
  const activeAssistantIdRef = useRef<string | null>(null)

  useEffect(() => {
    loadConversations()
  }, [])

  useEffect(() => {
    if (!isLoading && messages.length === 0) {
      setCurrentView('home')
    }
  }, [isLoading, messages.length])

  const loadConversations = async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/sessions`)
      const data = await res.json()
      setConversations(data.sessions || [])
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
    if (isLoading || isStreaming) return
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
    let started = false
    let controller: AbortController | null = null

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

      const response = await fetch(`${API_BASE}/chat/stream`, {
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
            } else if (evt.type === 'done') {
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

          boundary = buffer.indexOf('\n\n')
        }
      }

      if (started) {
        setMessages(prev => prev.map(m => {
          if (m.id === assistantId) {
            return { ...m, references: references ?? m.references, model }
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
    setCurrentSessionId(null)
    setCurrentView('home')
    setSidebarOpen(false)
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

  const handleSelectConversation = async (id: string) => {
    abortActiveRequest()
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
    e.preventDefault()
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
        />
      </div>

      <div className="main-column">
        <Header
          title={currentView === 'home' ? '政企智能助手' : '对话'}
          model={model}
          streaming={isStreaming || isLoading}
          onModelChange={setModel}
          onMenu={() => setSidebarOpen(true)}
          onWriting={() => setWritingOpen(true)}
        />

        <div className={`chat-stream ${currentView === 'home' && messages.length === 0 ? 'home' : ''}`}>
          {currentView === 'home' && messages.length === 0 ? (
            <WelcomeScreen onQuickAction={handleSendMessage} disabled={isStreaming || isLoading} />
          ) : (
            <MessageList
              messages={messages}
              isLoading={isLoading || isStreaming}
              onStop={handleStop}
              onFollowUp={(prompt) => handleSendMessage(prompt, undefined, true)}
            />
          )}
        </div>

        <ChatInput onSend={handleSendMessage} onStop={handleStop} disabled={isStreaming || isLoading} model={model} />

        <WritingPanel
          open={writingOpen}
          model={model}
          onClose={() => setWritingOpen(false)}
          onGenerate={(prompt, _model, writing) => {
            setWritingOpen(false)
            handleSendMessage(prompt, writing)
          }}
        />
      </div>
    </div>
  )
}

export default App
