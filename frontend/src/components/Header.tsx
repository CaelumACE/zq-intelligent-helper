import type { ModelProvider } from '../types'

interface HeaderProps {
  title: string;
  model: ModelProvider;
  onModelChange: (provider: ModelProvider) => void;
  streaming?: boolean;
  onMenu?: () => void;
  onWriting?: () => void;
}

const MODEL_OPTIONS: Array<{ value: ModelProvider; label: string }> = [
  { value: 'minimax', label: 'MiniMax' },
  { value: 'deepseek', label: 'DeepSeek' },
]

export default function Header({ title, model, onModelChange, streaming = false, onMenu, onWriting }: HeaderProps) {
  return (
    <header
      className="topbar"
    >
      {onMenu && (
        <button
          onClick={onMenu}
          className="md:hidden text-[var(--text-2)] hover:text-[var(--primary)] p-1.5 rounded-lg hover:bg-gray-100"
          aria-label="打开菜单"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      )}
      <h2 className="topbar-title">{title}</h2>
      <div className="topbar-actions">
        <div className="model-switch" title="切换底层大模型">
          <span className="ms-label">模型：</span>
          <div className="ms-options">
            {MODEL_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                className={`ms-opt ${model === opt.value ? 'active' : ''}`}
                disabled={streaming}
                onClick={() => onModelChange(opt.value)}
                title={streaming ? '生成中，请先停止后再切换' : undefined}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        {onWriting && (
          <button className="icon-btn" title="公文写作" onClick={onWriting}>✍️</button>
        )}
        <button className="icon-btn" title="帮助">❓</button>
      </div>
    </header>
  )
}
