import { quickActions } from '../utils/mockData'
import Icon from './Icons'
import BotAvatar from './BotAvatar'

interface WelcomeScreenProps {
  onQuickAction: (prompt: string) => void
  disabled?: boolean
}

const CAPABILITIES = [
  { label: '政策问答', desc: '有出处可溯源' },
  { label: '公文写作', desc: '8类公文一键生成' },
  { label: '办事指引', desc: '材料清单一次说清' },
  { label: '政策比对', desc: '多版本差异定位' },
]

export default function WelcomeScreen({ onQuickAction, disabled = false }: WelcomeScreenProps) {
  return (
    <div className="chat-inner welcome-inner">
      <div className="chat-hero">
        <BotAvatar className="hero-avatar" size={68} state="idle" ink="#ffffff" paper="#0c4a6e" title="政企智能助手" />
        <h1 className="hero-title">您好，我是<span>政企智能助手</span></h1>
        <p className="hero-subtitle">把公文撰写、政策咨询与办事指引，交给政企一次完成。基于权威政策库，确保答案可溯源、可落地。</p>
      </div>

      <div className="capability-bar">
        {CAPABILITIES.map((cap) => (
          <span key={cap.label} className="capability-chip">
            <strong>{cap.label}</strong> · {cap.desc}
          </span>
        ))}
      </div>

      <div className="quick-cards">
        {quickActions.map((action) => (
          <button
            key={action.id}
            onClick={() => !disabled && onQuickAction(action.prompt)}
            disabled={disabled}
            className="quick-card"
          >
            <div className="quick-card-icon">
              <Icon name={action.icon} size={22} />
            </div>
            <h3 className="quick-card-title">{action.label}</h3>
            <p className="quick-card-desc">{action.description}</p>
            <span className="quick-card-tag">{action.tag}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

