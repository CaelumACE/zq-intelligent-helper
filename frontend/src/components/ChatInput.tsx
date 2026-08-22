import { useState, type KeyboardEvent } from 'react'

interface ChatInputProps {
  onSend: (content: string) => void
  disabled?: boolean
}

export default function ChatInput({ onSend, disabled = false }: ChatInputProps) {
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
    <div className="bg-white border-t flex-shrink-0 px-4 md:px-6 pt-3.5 pb-2" style={{ borderColor: 'var(--border)' }}>
      <div className="max-w-[820px] mx-auto flex gap-3 items-end">
        <textarea
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入您的问题，Enter 发送，Shift+Enter 换行…"
          rows={1}
          className="ref-textarea flex-1 min-h-[50px] max-h-[140px]"
        />
        <button onClick={handleSend} disabled={disabled || !value.trim()} className="send-btn">
          {disabled ? '生成中…' : '发送'}
        </button>
      </div>
      <p className="max-w-[820px] mx-auto mt-2 text-center text-xs text-[var(--text-3)]">
        内容由 AI 生成，请以官方文件为准
      </p>
    </div>
  )
}
