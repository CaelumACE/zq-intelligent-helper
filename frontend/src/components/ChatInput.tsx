import { useState, type KeyboardEvent } from 'react'
import type { ModelProvider } from '../types'

interface ChatInputProps {
  onSend: (content: string) => void
  disabled?: boolean
  model: ModelProvider
}

const MODEL_LABEL: Record<ModelProvider, string> = {
  minimax: 'MiniMax',
  deepseek: 'DeepSeek',
}

export default function ChatInput({ onSend, disabled = false, model }: ChatInputProps) {
  const [value, setValue] = useState('')

  const handleSend = () => {
    const text = value.trim()
    if (!text || disabled) return
    onSend(text)
    setValue('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="chat-input">
      <div className="input-row">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入您的问题，Enter 发送，Shift+Enter 换行…"
          rows={1}
          className="chat-textarea"
        />
        <button onClick={handleSend} disabled={disabled || !value.trim()} className={`send-btn ${disabled ? 'streaming' : ''}`}>
          {disabled ? '停止' : '发送'}
        </button>
      </div>
      <p className="input-hint">
        当前模型：<span className="model-tag">{MODEL_LABEL[model]}</span> · 内容由 AI 生成，请以官方文件为准
      </p>
    </div>
  )
}
