import { useState } from 'react'
import type { Message } from '../types'

interface MessageListProps {
  messages: Message[]
  isLoading: boolean
}

function inlineRefs(content: string) {
  return content.replace(/\[(\d+)\]/g, (_, n) => `<sup class="cite">${n}</sup>`)
}

function MessageItem({ message }: { message: Message }) {
  const [showRefs, setShowRefs] = useState(false)
  const isUser = message.role === 'user'
  const html = inlineRefs(message.content)

  return (
    <div className={`flex gap-3 mb-[22px] ${isUser ? 'flex-row-reverse' : ''}`}>
      {isUser ? (
        <div className="user-avatar">我</div>
      ) : (
        <div className="ai-avatar">政</div>
      )}
      <div className={`flex-1 min-w-0 ${isUser ? 'flex justify-end' : ''}`}>
        <div
          className={isUser ? 'bubble-user' : 'bubble-ai'}
          dangerouslySetInnerHTML={{ __html: html }}
        />
        {!isUser && message.references && message.references.length > 0 && (
          <div className="mt-3 border-t border-dashed pt-2.5" style={{ borderColor: 'var(--border)' }}>
            <button
              onClick={() => setShowRefs(!showRefs)}
              className="text-xs text-[var(--text-3)] hover:text-[var(--gold-strong)] flex items-center gap-1.5"
            >
              {showRefs ? '▴ 收起引用来源' : '▾ 展开引用来源'}（{message.references.length}）
            </button>
            {showRefs && (
              <div className="mt-2 space-y-2">
                {message.references.map((ref, i) => (
                  <div
                    key={i}
                    className="border border-[var(--border)] border-l-4 border-l-[var(--gold)] rounded-md p-2.5"
                    style={{ background: '#FBF9F4' }}
                  >
                    <div className="text-xs font-semibold text-[var(--primary)]">{ref.title}</div>
                    <div className="text-[11px] text-[var(--text-3)] mt-0.5">来源：{ref.source}</div>
                    <p className="text-xs text-[var(--text-2)] mt-1 leading-relaxed">{ref.snippet}</p>
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
    <div className="max-w-[820px] mx-auto px-4 md:px-6 py-6">
      {messages.map((msg) => (
        <MessageItem key={msg.id} message={msg} />
      ))}
      {isLoading && (
        <div className="flex gap-3 mb-[22px]">
          <div className="ai-avatar">政</div>
          <div className="bubble-ai">
            <div className="flex gap-1.5">
              <span className="w-2 h-2 bg-[var(--gold)] rounded-full animate-pulse"></span>
              <span className="w-2 h-2 bg-[var(--gold)] rounded-full animate-pulse" style={{ animationDelay: '0.2s' }}></span>
              <span className="w-2 h-2 bg-[var(--gold)] rounded-full animate-pulse" style={{ animationDelay: '0.4s' }}></span>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
