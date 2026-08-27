import { useState } from 'react'
import type { Message } from '../types'
import { copyText } from '../utils/clipboard'
import { pickFollowUpChips, isRefusalReply } from '../utils/followUpChips'
import { apiFetch, API_BASE } from '../utils/api'
import MarkdownContent from './MarkdownContent'
import ServiceCard from './ServiceCard'
import Icon from './Icons'

const COLLAPSE_THRESHOLD = 300
const COLLAPSE_PREVIEW = 200

interface MessageListProps {
  messages: Message[]
  isLoading: boolean
  isStreaming?: boolean
  currentSessionId?: string | null
  onStop?: () => void
  onRegenerate?: (content: string) => void
  onFollowUp?: (prompt: string) => void
}

function MessageItem({
  message,
  isLatest,
  streaming = false,
  sessionId,
  onRegenerate,
  onFollowUp,
  allMessages,
}: {
  message: Message
  isLatest: boolean
  streaming?: boolean
  sessionId?: string | null
  onRegenerate?: (content: string) => void
  onFollowUp?: (prompt: string) => void
  allMessages: Message[]
}) {
  const [showRefs, setShowRefs] = useState(false)
  const [copied, setCopied] = useState(false)
  const [feedback, setFeedback] = useState<'up' | 'down' | null>(null)
  const [feedbackSent, setFeedbackSent] = useState(false)
  const [showDownComment, setShowDownComment] = useState(false)
  const [downComment, setDownComment] = useState('')
  const [expanded, setExpanded] = useState(false)
  const [exporting, setExporting] = useState(false)
  const isUser = message.role === 'user'
  const refusal = !isUser && isRefusalReply(message.content)
  const isWriting = !isUser && message.status === 'writing'
  const isLong = !isUser && message.content.length > COLLAPSE_THRESHOLD
  const shownContent = isLong && !expanded
    ? message.content.slice(0, COLLAPSE_PREVIEW)
    : message.content

  const chips = !isUser && isLatest ? pickFollowUpChips(allMessages, message.followUpChips) : []

  const handleCopy = async () => {
    await copyText(message.content)
    setCopied(true)
    window.setTimeout(() => setCopied(false), 1600)
  }

  const handleFeedback = async (rating: 'up' | 'down') => {
    if (feedbackSent) return
    if (rating === 'down') {
      setShowDownComment(true)
      setFeedback('down')
      return
    }
    setFeedback('up')
    try {
      await apiFetch(`${API_BASE}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId || message.sessionId || '',
          message_id: message.id,
          rating: 'up',
        }),
      })
      setFeedbackSent(true)
    } catch {
      // silent
    }
  }

  const submitDownFeedback = async () => {
    try {
      await apiFetch(`${API_BASE}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId || message.sessionId || '',
          message_id: message.id,
          rating: 'down',
          comment: downComment,
        }),
      })
      setFeedbackSent(true)
      setShowDownComment(false)
    } catch {
      // silent
    }
  }

  const handleExportDocx = async () => {
    if (exporting) return
    setExporting(true)
    try {
      const res = await apiFetch(`${API_BASE}/chat/export-docx`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: message.content, title: '' }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const firstLine = message.content.split('\n').find(l => l.trim().startsWith('#'))?.replace(/^#+\s*/, '').trim() || '公文'
      a.download = `${firstLine}.docx`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      console.error('导出失败:', e)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className={`msg ${isUser ? 'user' : 'ai'}`}>
      <div className={isUser ? 'user-avatar' : `ai-avatar${streaming && !isUser ? ' streaming' : ''}`}>{isUser ? '我' : '政'}</div>
      <div className="msg-body">
        <div className={`bubble-ai${isWriting ? ' writing-doc' : ''}${message.structuredAnswer ? ' has-svc-card' : ''}`}>
          <MarkdownContent content={shownContent} />
          {isLong && !expanded && (
            <button className="collapse-toggle" onClick={() => setExpanded(true)}>展开全文</button>
          )}
          {isLong && expanded && (
            <button className="collapse-toggle" onClick={() => setExpanded(false)}>收起</button>
          )}
          {message.structuredAnswer && (
            <ServiceCard data={message.structuredAnswer} />
          )}
        </div>
        {!streaming && !refusal && (
          <div className="msg-actions">
            <button className="mini-btn" onClick={handleCopy}>{copied ? '✓ 已复制' : <><Icon name="copy" size={13} /> 复制</>}</button>
            {isWriting && (
              <button className="mini-btn export-btn" onClick={handleExportDocx} disabled={exporting}>
                <Icon name="download" size={13} /> {exporting ? '导出中…' : '导出Word'}
              </button>
            )}
            {!isUser && (
              <>
                <button
                  className={`mini-btn ${feedback === 'up' ? 'active' : ''}`}
                  onClick={() => handleFeedback('up')}
                  disabled={feedbackSent}
                  title="满意"
                >
                  <Icon name="thumbs-up" size={13} />
                </button>
                <button
                  className={`mini-btn ${feedback === 'down' ? 'active' : ''}`}
                  onClick={() => handleFeedback('down')}
                  disabled={feedbackSent}
                  title="不满意"
                >
                  <Icon name="thumbs-down" size={13} />
                </button>
                {onRegenerate && <button className="mini-btn" onClick={() => onRegenerate(message.content)}><Icon name="refresh" size={13} /> 重新生成</button>}
              </>
            )}
            {!isUser && message.model && <span className="stream-meta">已完成 · {message.model === 'minimax' ? 'MiniMax' : 'DeepSeek'}</span>}
          </div>
        )}
        {!isUser && showDownComment && !feedbackSent && (
          <div className="feedback-comment">
            <textarea
              value={downComment}
              onChange={e => setDownComment(e.target.value)}
              placeholder="请描述问题或改进建议…"
              rows={2}
            />
            <div className="feedback-comment-actions">
              <button className="mini-btn" onClick={() => { setShowDownComment(false); setFeedback(null) }}>取消</button>
              <button className="mini-btn primary" onClick={submitDownFeedback}>提交</button>
            </div>
          </div>
        )}
        {!isUser && feedbackSent && (
          <span className="feedback-thanks">感谢反馈</span>
        )}
        {!isUser && chips.length > 0 && (
          <div className="followup-row">
            {chips.map((chip) => (
              <button key={chip} className="followup-chip" onClick={() => onFollowUp?.(chip)}>
                {chip}
              </button>
            ))}
          </div>
        )}
        {!isUser && !refusal && message.references && message.references.length > 0 && (
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

export default function MessageList({ messages, isLoading, isStreaming = false, currentSessionId, onStop, onRegenerate, onFollowUp }: MessageListProps) {
  const active = isLoading || isStreaming

  const latestAiId = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') return messages[i].id
    }
    return null
  })()

  const streamingLatestId = isStreaming && !isLoading && latestAiId != null ? latestAiId : null

  return (
    <div className="chat-inner">
      {messages.map((msg) => (
        <MessageItem
          key={msg.id}
          message={msg}
          isLatest={!active && msg.id === latestAiId}
          streaming={msg.id === streamingLatestId}
          sessionId={currentSessionId}
          onRegenerate={onRegenerate}
          onFollowUp={onFollowUp}
          allMessages={messages}
        />
      ))}
      {isLoading && (
        <div className="msg ai">
          <div className="ai-avatar streaming">政</div>
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
              {onStop && <button className="mini-btn stop" onClick={onStop}><Icon name="square" size={12} /> 停止生成</button>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
