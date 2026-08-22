import { useState, useMemo, type KeyboardEvent } from 'react'
import type { ModelProvider, Message } from '../types'

interface ChatInputProps {
  onSend: (content: string) => void
  onStop?: () => void
  disabled?: boolean
  model: ModelProvider
  messages: Message[]
}

const MODEL_LABEL: Record<ModelProvider, string> = {
  minimax: 'MiniMax',
  deepseek: 'DeepSeek',
}

const CONTEXT_CHIPS_BY_TOPIC: Array<{ match: RegExp; chips: string[] }> = [
  { match: /年终|报告|总结/, chips: ['继续写完整报告', '调整语气更正式', '补充数据说明'] },
  { match: /通知/, chips: ['补充参会人员', '调整语气更正式', '写明时间地点'] },
  { match: /政策|补贴|扶持/, chips: ['申请条件是什么', '需要准备哪些材料', '找办理窗口'] },
  { match: /办理|流程|材料/, chips: ['办理时限多久', '可以线上办理吗', '需要哪些材料'] },
]

const DEFAULT_CHIPS = ['换一种更正式的说法', '列出关键要点', '补充具体示例']

function pickChips(messages: Message[]): string[] {
  const lastUser = [...messages].reverse().find((m) => m.role === 'user')
  if (!lastUser) return []
  for (const group of CONTEXT_CHIPS_BY_TOPIC) {
    if (group.match.test(lastUser.content)) return group.chips
  }
  return DEFAULT_CHIPS
}

export default function ChatInput({ onSend, onStop, disabled = false, model, messages }: ChatInputProps) {
  const [value, setValue] = useState('')
  const chips = useMemo(() => pickChips(messages), [messages])

  const handleSend = (text?: string) => {
    const content = (text ?? value).trim()
    if (!content || disabled) return
    onSend(content)
    setValue('')
  }

  const handlePrimary = () => {
    if (disabled) {
      onStop?.()
      return
    }
    handleSend()
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  // 空状态时隐藏推荐 chips，避免与欢迎页卡片重复；仅在一轮对话后显示
  if (messages.length === 0) {
    return (
      <div className="chat-input">
        <div className={`stream-banner ${disabled ? 'show' : ''}`}>
          <span className="dot" />
          AI 正在回复中，请等待完成后再发送
        </div>
        <div className="input-row">
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入您的问题，Enter 发送，Shift+Enter 换行…"
            rows={1}
            className="chat-textarea"
            disabled={disabled}
          />
          <button
            onClick={handlePrimary}
            disabled={!disabled && !value.trim()}
            className={`send-btn ${disabled ? 'streaming' : ''}`}
          >
            {disabled ? '停止' : '发送'}
          </button>
        </div>
        <p className="input-hint">
          当前模型：<span className="model-tag">{MODEL_LABEL[model]}</span> · 内容由 AI 生成，请以官方文件为准
        </p>
      </div>
    )
  }

  return (
    <div className="chat-input">
      <div className={`stream-banner ${disabled ? 'show' : ''}`}>
        <span className="dot" />
        AI 正在回复中，请等待完成后再发送
      </div>
      {chips.length > 0 && (
        <div className="chip-row">
          {chips.map((chip) => (
            <button key={chip} className="chip" disabled={disabled} onClick={() => handleSend(chip)}>
              {chip}
            </button>
          ))}
        </div>
      )}
      <div className="input-row">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入您的问题，Enter 发送，Shift+Enter 换行…"
          rows={1}
          className="chat-textarea"
          disabled={disabled}
        />
        <button
          onClick={handlePrimary}
          disabled={!disabled && !value.trim()}
          className={`send-btn ${disabled ? 'streaming' : ''}`}
        >
          {disabled ? '停止' : '发送'}
        </button>
      </div>
      <p className="input-hint">
        当前模型：<span className="model-tag">{MODEL_LABEL[model]}</span> · 内容由 AI 生成，请以官方文件为准
      </p>
    </div>
  )
}
