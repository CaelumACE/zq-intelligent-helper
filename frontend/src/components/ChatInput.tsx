import { useEffect, useState, useRef, type KeyboardEvent } from 'react'
import type { ModelProvider } from '../types'

interface ChatInputProps {
  onSend: (content: string) => void
  onStop?: () => void
  disabled?: boolean
  model: ModelProvider
  onModelChange: (provider: ModelProvider) => void
}

const MODEL_LABEL: Record<ModelProvider, string> = {
  minimax: 'MiniMax',
  deepseek: 'DeepSeek',
}

export default function ChatInput({ onSend, onStop, disabled = false, model, onModelChange }: ChatInputProps) {
  const [value, setValue] = useState('')
  const [modelOpen, setModelOpen] = useState(false)
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
      <div className="input-card">
        <textarea
          ref={inputRef}
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入您的问题，Enter 发送，Shift+Enter 换行…"
          rows={4}
          className="chat-textarea"
          disabled={disabled}
        />
        <div className="input-toolbar">
          <button className="toolbar-plus" type="button" aria-label="添加" title="添加">＋</button>
          <div className="toolbar-right">
            <div className="model-dropdown">
              <button
                className="model-dropdown-trigger"
                type="button"
                disabled={disabled}
                onClick={() => setModelOpen(v => !v)}
                title="切换底层大模型"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <circle cx="12" cy="12" r="10" />
                  <path d="M2 12h20" />
                  <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                </svg>
                <span>{MODEL_LABEL[model]}</span>
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </button>
              {modelOpen && (
                <div className="dropdown-menu">
                  {Object.entries(MODEL_LABEL).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      className={model === key ? 'active' : ''}
                      onClick={() => {
                        onModelChange(key as ModelProvider)
                        setModelOpen(false)
                      }}
                    >
                      <span>{label}</span>
                      {model === key && <span aria-hidden="true">✓</span>}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <button
              onClick={handlePrimary}
              disabled={!disabled && !value.trim()}
              className={`send-icon-btn ${disabled ? 'streaming' : ''}`}
              aria-label={disabled ? '停止' : '发送'}
              title={disabled ? '停止' : '发送'}
            >
              {disabled ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <rect x="6" y="6" width="12" height="12" rx="2" />
                </svg>
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                  <path d="M22 2 11 13" />
                  <path d="M22 2 15 22 11 13 2 9 22 2z" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>
      <p className="input-hint">
        内容由 AI 生成，请以官方文件为准
      </p>
    </div>
  )
}
