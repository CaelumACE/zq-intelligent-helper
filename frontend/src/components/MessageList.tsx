import { useState } from 'react'
import type { Message } from '../types'
import { copyText } from '../utils/clipboard'

interface MessageListProps {
  messages: Message[]
  isLoading: boolean
  onStop?: () => void
}

function inlineRefs(content: string) {
  return content.replace(/\[(\d+)\]/g, (_, n) => `<sup class="cite">${n}</sup>`)
}

function MessageItem({ message }: { message: Message }) {
  const [showRefs, setShowRefs] = useState(false)
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'
  const html = inlineRefs(message.content)

  const handleCopy = async () => {
    await copyText(message.content)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className={`msg ${isUser ? 'user' : 'ai'}`}>
      <div className={isUser ? 'user-avatar' : 'ai-avatar'}>{isUser ? '我' : '政'}</div>
      <div className="msg-body">
        <div
          className={isUser ? 'bubble-user' : 'bubble-ai'}
          dangerouslySetInnerHTML={{ __html: html }}
        />
        <div className="msg-actions">
          <button className="mini-btn" onClick={handleCopy}>{copied ? '✓ 已复制' : '📋 复制'}</button>
          {!isUser && (
            <>
              <button className="mini-btn">👍</button>
              <button className="mini-btn">👎</button>
            </>
          )}
          {!isUser && message.model && <span className="stream-meta">由 {message.model === 'minimax' ? 'MiniMax' : 'DeepSeek'} 生成</span>}
        </div>
        {!isUser && message.references && message.references.length > 0 && (
          <div className="refs">
            <button
              onClick={() => setShowRefs(!showRefs)}
              className="ref-head"
            >
              {showRefs ? '▴ 收起引用来源' : '▾ 展开引用来源'}（{message.references.length}）
            </button>
            {showRefs && (
              <div className="ref-body">
                {message.references.map((ref, i) => (
                  <div key={i} className="ref-item">
                    <b>[{i + 1}] {ref.title}</b>
                    <div className="ref-meta">来源：{ref.source}</div>
                    <div className="ref-meta">{ref.snippet}</div>
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

export default function MessageList({ messages, isLoading, onStop }: MessageListProps) {
  return (
    <div className="chat-inner">
      {messages.map((msg) => (
        <MessageItem key={msg.id} message={msg} />
      ))}
      {isLoading && (
        <div className="msg ai">
          <div className="ai-avatar">政</div>
          <div className="msg-body">
            <div className="bubble-ai">
              <span className="loading-dots">
                <span className="loading-dot" />
                <span className="loading-dot" style={{ animationDelay: '0.2s' }} />
                <span className="loading-dot" style={{ animationDelay: '0.4s' }} />
              </span>
              <span className="typing-cursor" />
            </div>
            <div className="msg-actions">
              {onStop && <button className="mini-btn stop" onClick={onStop}>■ 停止生成</button>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
