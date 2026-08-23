import { useEffect, useState, useRef, type KeyboardEvent } from 'react'
import type { ModelProvider } from '../types'

interface ChatInputProps {
  onSend: (content: string) => void
  onStop?: () => void
  disabled?: boolean
  model: ModelProvider
}

const MODEL_LABEL: Record<ModelProvider, string> = {
  minimax: 'MiniMax',
  deepseek: 'DeepSeek',
}

export default function ChatInput({ onSend, onStop, disabled = false, model }: ChatInputProps) {
  const [value, setValue] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const prevDisabledRef = useRef(disabled)

  useEffect(() => {
    // 流式/加载结束后（disabled 从 true 变回 false）自动把光标送回输入框
    if (!disabled && prevDisabledRef.current) {
      inputRef.current?.focus()
    }
    prevDisabledRef.current = disabled
  }, [disabled])

  const handleSend = () => {
    const content = value.trim()
    if (!content || disabled) return
    onSend(content)
    setValue('')
    // 发送后立即把光标放回输入框；若流式期间被 disabled，待完成后再恢复
    window.setTimeout(() => inputRef.current?.focus(), 0)
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

  return (
    <div className="chat-input">
      <div className={`stream-banner ${disabled ? 'show' : ''}`}>
        <span className="dot" />
        AI 正在回复中，请等待完成后再发送
      </div>
      <div className="input-row">
        <textarea
          ref={inputRef}
          autoFocus
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
