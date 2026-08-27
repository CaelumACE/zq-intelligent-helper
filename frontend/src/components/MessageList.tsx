import { memo, useState, useMemo } from 'react'
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

const EMPTY_ARRAY: Message[] = []

const MessageItem = memo(function MessageItem({
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
    <div className={`msg-item ${isUser ? 'user' : 'assistant'}`}>
      <div className="msg-avatar">{isUser ? '我' : '政'}</div>
      <div className="msg-body">
        <div className={`msg-bubble${isWriting ? ' writing-doc' : ''}`}>
          <MarkdownContent content={shownContent} streaming={streaming} />
          {isLong && !expanded && (
            <button className="collapse-toggle" onClick={() => setExpanded(true)}>展开全文</button>
          )}
          {isLong && expanded && (
            <button className="collapse-toggle" onClick={() => setExpanded(false)}>收起</button>
          )}
        </div>

        {message.structuredAnswer && (
          <ServiceCard data={message.structuredAnswer} />
        )}

        {!streaming && !refusal && (
          <div className="msg-actions">
            <button className="msg-action-btn" onClick={handleCopy}>
              {copied ? <><Icon name="check" size={13} /> 已复制</> : <><Icon name="copy" size={13} /> 复制</>}
            </button>
            {isWriting && (
              <button className="msg-action-btn" onClick={handleExportDocx} disabled={exporting}>
                <Icon name="download" size={13} /> {exporting ? '导出中…' : '导出Word'}
              </button>
            )}
            {!isUser && (
              <>
                <button
                  className={`msg-action-btn ${feedback === 'up' ? 'active' : ''}`}
                  onClick={() => handleFeedback('up')}
                  disabled={feedbackSent}
                  title="满意"
                >
                  <Icon name="thumbs-up" size={13} />
                </button>
                <button
                  className={`msg-action-btn ${feedback === 'down' ? 'active' : ''}`}
                  onClick={() => handleFeedback('down')}
                  disabled={feedbackSent}
                  title="不满意"
                >
                  <Icon name="thumbs-down" size={13} />
                </button>
                {onRegenerate && (
                  <button className="msg-action-btn" onClick={() => onRegenerate(message.content)}>
                    <Icon name="refresh" size={13} /> 重新生成
                  </button>
                )}
              </>
            )}
            {!isUser && message.model && (
              <span className="stream-meta">已完成 · {message.model === 'minimax' ? 'MiniMax' : 'DeepSeek'}</span>
            )}
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
              <button className="msg-action-btn" onClick={() => { setShowDownComment(false); setFeedback(null) }}>取消</button>
              <button className="msg-action-btn active" onClick={submitDownFeedback}>提交</button>
            </div>
          </div>
        )}
        {!isUser && feedbackSent && (
          <span className="feedback-thanks">感谢反馈</span>
        )}

        {!isUser && chips.length > 0 && (
          <div className="follow-up-row">
            {chips.map((chip) => (
              <button key={chip} className="follow-up-chip" onClick={() => onFollowUp?.(chip)}>
                {chip}
              </button>
            ))}
          </div>
        )}

        {!isUser && !refusal && message.references && message.references.length > 0 && (
          <div className="ref-section">
            <button onClick={() => setShowRefs(!showRefs)} className="ref-toggle">
              {showRefs ? '▴ 收起引用来源' : '▾ 展开引用来源'}（{message.references.length}）
            </button>
            {showRefs && (
              <div className="ref-list">
                {message.references.map((ref, i) => (
                  <div key={i} className="ref-item">
                    <div className="ref-num">{i + 1}</div>
                    <div>
                      <div className="ref-title">{ref.title}</div>
                      <div className="ref-source">来源：{ref.source}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
})

export default function MessageList({ messages, isLoading, isStreaming = false, currentSessionId, onStop, onRegenerate, onFollowUp }: MessageListProps) {
  const active = isLoading || isStreaming

  const latestAiId = (() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') return messages[i].id
    }
    return null
  })()

  const streamingLatestId = isStreaming && !isLoading && latestAiId != null ? latestAiId : null

  const stableMessages = useMemo(() => messages, [messages])

  return (
    <div className="msg-list">
      {messages.map((msg) => (
        <MessageItem
          key={msg.id}
          message={msg}
          isLatest={!active && msg.id === latestAiId}
          streaming={msg.id === streamingLatestId}
          sessionId={currentSessionId}
          onRegenerate={onRegenerate}
          onFollowUp={onFollowUp}
          allMessages={msg.id === latestAiId ? stableMessages : EMPTY_ARRAY}
        />
      ))}
      {isLoading && (
        <div className="msg-item assistant">
          <div className="msg-avatar">政</div>
          <div className="msg-body">
            <div className="msg-bubble">
              <span className="typing-indicator">
                <span />
                <span />
                <span />
              </span>
            </div>
            <div className="msg-actions">
              {onStop && <button className="msg-action-btn" onClick={onStop}><Icon name="square" size={12} /> 停止生成</button>}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
