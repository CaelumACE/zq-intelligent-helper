import { useState, useEffect } from 'react'
import Sidebar from './components/Sidebar'
import Header from './components/Header'
import ChatInput from './components/ChatInput'
import MessageList from './components/MessageList'
import WelcomeScreen from './components/WelcomeScreen'
import type { Message, Conversation } from './types'
import './App.css'

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [currentView, setCurrentView] = useState<'chat' | 'home'>('home')

  // 加载历史会话
  useEffect(() => {
    loadConversations()
  }, [])

  const loadConversations = async () => {
    try {
      const res = await fetch('/api/chat/sessions')
      const data = await res.json()
      setConversations(data.sessions || [])
    } catch (e) {
      console.error('加载会话失败', e)
    }
  }

  const handleSendMessage = async (content: string) => {
    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: Date.now(),
    }
    const nextMessages = [...messages, userMessage]
    setMessages(nextMessages)
    setCurrentView('chat')
    setIsLoading(true)

    try {
      // 若已有会话历史，传完整历史给后端；否则传当前 session_id
      const history = nextMessages.filter(m => m.role !== 'system').map(m => ({
        role: m.role,
        content: m.content,
      }))

      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content,
          session_id: currentSessionId || undefined,
          history,
        }),
      })

      const data = await response.json()

      if (data.session_id) {
        setCurrentSessionId(data.session_id)
      }

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: data.content,
        timestamp: Date.now(),
        references: data.references,
      }
      setMessages(prev => [...prev, assistantMessage])
      loadConversations()
    } catch (error) {
      console.error('Chat error:', error)
      try {
        const mockResponse = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: content, history: [userMessage] }),
        })
        const data = await mockResponse.json()
        const assistantMessage: Message = {
          id: (Date.now() + 1).toString(),
          role: 'assistant',
          content: data.content,
          timestamp: Date.now(),
          references: data.references,
        }
        setMessages(prev => [...prev, assistantMessage])
      } catch (e2) {
        console.error('fallback error', e2)
      }
    } finally {
      setIsLoading(false)
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setCurrentSessionId(null)
    setCurrentView('home')
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
      const res = await fetch(`/api/chat/sessions/${id}`)
      const data = await res.json()
      setCurrentSessionId(id)
      const normalized = normalizeMessages(data.messages || [], id)
      setMessages(normalized)
      setCurrentView(normalized.length ? 'chat' : 'home')
    } catch (e) {
      console.error('加载会话详情失败', e)
    }
  }

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await fetch(`/api/chat/sessions/${id}`, { method: 'DELETE' })
      if (id === currentSessionId) {
        handleNewChat()
      }
      loadConversations()
    } catch (err) {
      console.error('删除会话失败', err)
    }
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        currentView={currentView}
        conversations={conversations}
        currentSessionId={currentSessionId}
        onNewChat={handleNewChat}
        onSelectConversation={handleSelectConversation}
        onDeleteConversation={handleDeleteConversation}
      />

      <div className="flex-1 flex flex-col overflow-hidden">
        <Header
          title={currentView === 'home' ? '政企智能助手' : '对话'}
          subtitle="为您提供政策咨询、公文写作、办事指引等服务"
        />

        <main className="flex-1 overflow-y-auto">
          {currentView === 'home' && messages.length === 0 ? (
            <WelcomeScreen onQuickAction={handleSendMessage} />
          ) : (
            <MessageList messages={messages} isLoading={isLoading} />
          )}
        </main>

        <ChatInput onSend={handleSendMessage} disabled={isLoading} />
      </div>
    </div>
  )
}

export default App
