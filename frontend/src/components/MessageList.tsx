import { useState } from 'react'
import type { Message } from '../types'
import { copyText } from '../utils/clipboard'
import MarkdownContent from './MarkdownContent'

const COLLAPSE_THRESHOLD = 300
const COLLAPSE_PREVIEW = 200

interface MessageListProps {
  messages: Message[]
  isLoading: boolean
  onStop?: () => void
  onRegenerate?: (content: string) => void
}

function MessageItem({ message, onRegenerate }: { message: Message; onRegenerate?: (content: string) => void }) {
  const [showRefs, setShowRefs] = useState(false)
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null)
  const [expanded, setExpanded] = useState(false)
  const isUser = message.role === 'user'
  const isLong = !isUser && message.content.length > COLLAPSE_THRESHOLD
  const shownContent = isLong && !expanded
    ? message.content.slice(0, COLLAPSE_PREVIEW)
    : message.content

  const handleCopy = async () => {
    await copyText(message.content)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  return (
    <div className={`msg ${isUser ? 'user' : 'ai'}`}>
      <div className={isUser ? 'user-avatar' : 'ai-avatar'}>{isUser ? '我' : '政'}</div>
      <div className="msg-body">
        <div className={isUser ? 'bubble-user' : 'bubble-ai'}>
          <MarkdownContent content={shownContent} />
          {isLong && !expanded && (
            <button className="collapse-toggle" onClick={() => setExpanded(true)}>展开全文 ▼</button>
          )}
          {isLong && expanded && (
            <button className="collapse-toggle" onClick={() => setExpanded(false)}>收起 ▲</button>
          )}
        </div>
        <div className="msg-actions">
          <button className="mini-btn" onClick={handleCopy}>{copied ? '✓ 已复制' : '📋 复制'}</button>
          {!isUser && (
            <>
              <button className={`mini-btn ${feedback === 'up' ? 'active' : ''}`} onClick={() => setFeedback(feedback === 'up' ? null : 'up')}>👍</button>
              <button className={`mini-btn ${feedback === 'down' ? 'active' : ''}`} onClick={() => setFeedback(feedback === 'down' ? null : 'down')}>👎</button>
              {onRegenerate && <button className="mini-btn" onClick={() => onRegenerate(message.content)}>🔄 重新生成</button>}
            </>
          )}
          {!isUser && message.model && <span className="stream-meta">已完成 · {message.model === 'minimax' ? 'MiniMax' : 'DeepSeek'}</span>}
        </div>
        {!isUser && message.references && message.references.length > 0 && (
          <div className="refs">
            <button onClick={() => setShowRefs(!showRefs)} className="ref-head">
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

export default function MessageList({ messages, isLoading, onStop, onRegenerate }: MessageListProps) {
  return (
    <div className="chat-inner">
      {messages.map((msg) => (
        <MessageItem key={msg.id} message={msg} onRegenerate={onRegenerate} />
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
