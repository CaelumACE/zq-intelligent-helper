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
    <div className="border-t border-[var(--border)] bg-white p-4">
      <div className="max-w-3xl mx-auto flex items-end gap-3">
        <div className="flex-1 relative">
          <textarea
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="请输入您的问题，例如：查询最新的中小企业扶持政策…"
            rows={1}
            className="w-full resize-none rounded-lg border border-[var(--border)] px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-light)] focus:border-transparent min-h-[46px] max-h-[140px]"
          />
          <div className="absolute bottom-2 right-3 text-xs text-[var(--text-muted)]">
            Enter 发送 / Shift+Enter 换行
          </div>
        </div>
        <button
          onClick={handleSend}
          disabled={disabled || !value.trim()}
          className="shrink-0 bg-[var(--primary)] hover:bg-[var(--primary-light)] disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg px-5 py-3 text-sm font-medium transition-colors flex items-center gap-2"
        >
          {disabled ? (
            <span className="animate-pulse">思考中…</span>
          ) : (
            <>
              <span>发送</span>
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7l5 5m0 0l-5 5m5-5H6" />
              </svg>
            </>
          )}
        </button>
      </div>
      <p className="text-center text-xs text-[var(--text-muted)] mt-2">
        内容由 AI 生成，请结合实际情况审慎判断
      </p>
    </div>
  )
}
