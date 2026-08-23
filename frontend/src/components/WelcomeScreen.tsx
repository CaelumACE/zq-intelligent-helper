import { quickActions } from '../utils/mockData'

interface WelcomeScreenProps {
  onQuickAction: (prompt: string) => void
  disabled?: boolean
}

const CAPABILITIES = [
  { dot: 'policy', text: '政策问答', suffix: ' · 有出处可溯源' },
  { dot: 'writing', text: '公文写作', suffix: ' · 4类公文一键生成' },
  { dot: 'guide', text: '流程导引', suffix: ' · 材料地点一次说清' },
]

export default function WelcomeScreen({ onQuickAction, disabled = false }: WelcomeScreenProps) {
  return (
    <div className="chat-inner">
      <div className="welcome-empty">
        <div className="greet-row">
          <div className="greet-avator">政</div>
          <div className="greet-text">
            <div className="greet-title">
              您好，我是政企智能助手 <span className="greet-hand">👋</span>
            </div>
            <div className="greet-sub">
              您可以问我<b>政策问题</b>、让我<b>帮您写公文</b>、或<b>了解办事流程</b>。请问今天想了解什么？
            </div>
          </div>
        </div>

        <div className="cap-row">
          {CAPABILITIES.map((cap) => (
            <span key={cap.text} className="cap-pill">
              <span className="cap-dot" />{cap.text}{cap.suffix}
            </span>
          ))}
        </div>

        <div className="suggest-grid">
          {quickActions.map((action) => (
            <button key={action.id} onClick={() => !disabled && onQuickAction(action.prompt)} disabled={disabled} className="suggest-card">
              <div className="suggest-ic">{action.icon}</div>
              <div className="suggest-q">{action.label}</div>
              <span className="suggest-tag">{action.tag}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
