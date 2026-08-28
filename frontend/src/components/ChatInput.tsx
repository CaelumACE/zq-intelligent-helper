import { useEffect, useState, useRef, type KeyboardEvent } from 'react'
import Icon from './Icons'
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

/** 仅桌面端（有精确指针/鼠标）返回 true，手机/平板等触摸设备返回 false */
function isDesktop(): boolean {
  if (typeof window === 'undefined') return false
  // 双重判断：有鼠标指针 + 可hover，比单 pointer:fine 更可靠
  const finePointer = window.matchMedia('(pointer: fine)').matches
  const canHover = window.matchMedia('(hover: hover)').matches
  return finePointer && canHover
}

export default function ChatInput({ onSend, onStop, disabled = false, model, onModelChange }: ChatInputProps) {
  const [value, setValue] = useState('')
  const [modelOpen, setModelOpen] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const prevDisabledRef = useRef(disabled)
  const modelSelectRef = useRef<HTMLDivElement>(null)

  // 自适应高度
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = 'auto'
    ta.style.height = Math.min(ta.scrollHeight, 140) + 'px'
  }, [value])

  useEffect(() => {
    if (!disabled && prevDisabledRef.current && isDesktop()) {
      textareaRef.current?.focus()
    }
    prevDisabledRef.current = disabled
  }, [disabled])

  // 点击外部关闭模型下拉
  useEffect(() => {
    if (!modelOpen) return
    const handler = (e: MouseEvent) => {
      if (modelSelectRef.current && !modelSelectRef.current.contains(e.target as Node)) {
        setModelOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [modelOpen])

  const handleSend = () => {
    const content = value.trim()
    if (!content || disabled) return
    onSend(content)
    setValue('')
    window.setTimeout(() => { if (isDesktop()) textareaRef.current?.focus() }, 0)
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
    <div className="chat-input-wrap">
      <div className="chat-input-inner">
        {disabled && (
          <div className="stream-banner show">
            <span className="stream-dot" />
            AI 正在回复中，请等待完成后再发送
          </div>
        )}
        <div className="input-wrapper">
          <textarea
            ref={(el) => {
              textareaRef.current = el
              if (el && isDesktop()) el.focus()
            }}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入您的问题，Enter 发送，Shift+Enter 换行…"
            rows={1}
            className="input-field"
            disabled={disabled}
          />
          <div className="input-toolbar">
            <div className="toolbar-left">
              <div
                className="model-select-wrap"
                ref={modelSelectRef}
              >
                <button
                  type="button"
                  className="model-select"
                  onClick={(e) => { e.stopPropagation(); setModelOpen(v => !v) }}
                >
                  <Icon name="zap" size={13} />
                  <span>{MODEL_LABEL[model]}</span>
                  <Icon name="chevron-down" size={11} />
                </button>
                {modelOpen && (
                  <div className="model-select-menu">
                    {Object.entries(MODEL_LABEL).map(([key, label]) => (
                      <button
                        key={key}
                        type="button"
                        className={`model-select-item ${model === key ? 'active' : ''}`}
                        onClick={() => {
                          onModelChange(key as ModelProvider)
                          setModelOpen(false)
                        }}
                      >
                        <span>{label}</span>
                        {model === key && <Icon name="check" size={13} />}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
            <button
              onClick={handlePrimary}
              disabled={!disabled && !value.trim()}
              className={`send-btn ${disabled ? 'stop' : ''}`}
              aria-label={disabled ? '停止' : '发送'}
              title={disabled ? '停止' : '发送'}
            >
              {disabled ? <Icon name="square" size={14} /> : <Icon name="send" size={16} />}
            </button>
          </div>
        </div>
        <p className="input-hint">内容由 AI 生成，请以官方文件为准</p>
      </div>
    </div>
  )
}
