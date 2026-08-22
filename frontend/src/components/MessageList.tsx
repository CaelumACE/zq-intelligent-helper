import { useState } from 'react'
import type { Message } from '../types'

interface MessageListProps {
  messages: Message[]
  isLoading: boolean
}

function MessageItem({ message }: { message: Message }) {
  const [showRefs, setShowRefs] = useState(false)
  const isUser = message.role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} animate-fade-in`}>
      <div className={`max-w-[75%] ${isUser ? 'order-1' : ''}`}>
        {!isUser && (
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 bg-[var(--primary)] rounded-lg flex items-center justify-center text-white text-xs">
              政
            </div>
            <span className="text-xs text-[var(--text-secondary)]">政企智能助手</span>
          </div>
        )}
        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed whitespace-pre-wrap ${
            isUser
              ? 'bg-[var(--primary)] text-white rounded-br-sm'
              : 'bg-white border border-[var(--border)] text-[var(--text-primary)] rounded-bl-sm'
          }`}
        >
          {message.content}
        </div>

        {!isUser && message.references && message.references.length > 0 && (
          <div className="mt-2">
            <button
              onClick={() => setShowRefs(!showRefs)}
              className="text-xs text-[var(--primary-light)] hover:underline flex items-center gap-1"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
              引用来源（{message.references.length}）
            </button>
            {showRefs && (
              <div className="mt-2 space-y-2">
                {message.references.map((ref, i) => (
                  <div key={i} className="bg-[var(--bg-main)] border border-[var(--border)] rounded-lg p-3">
                    <div className="text-xs font-medium text-[var(--primary)]">{ref.title}</div>
                    <div className="text-xs text-[var(--text-muted)] mt-1">来源：{ref.source}</div>
                    <p className="text-xs text-[var(--text-secondary)] mt-1.5 leading-relaxed">{ref.snippet}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function MessageList({ messages, isLoading }: MessageListProps) {
  return (
    <div className="max-w-3xl mx-auto px-6 py-6 space-y-6">
      {messages.map((msg) => (
        <MessageItem key={msg.id} message={msg} />
      ))}
      {isLoading && (
        <div className="flex justify-start animate-fade-in">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-[var(--primary)] rounded-lg flex items-center justify-center text-white text-xs">
              政
            </div>
            <div className="bg-white border border-[var(--border)] rounded-2xl rounded-bl-sm px-4 py-3">
              <div className="flex gap-1.5">
                <span className="w-2 h-2 bg-[var(--primary-light)] rounded-full animate-pulse"></span>
                <span className="w-2 h-2 bg-[var(--primary-light)] rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></span>
                <span className="w-2 h-2 bg-[var(--primary-light)] rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
