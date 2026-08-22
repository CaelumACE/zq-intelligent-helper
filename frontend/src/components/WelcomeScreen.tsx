import { quickActions } from '../utils/mockData'

interface WelcomeScreenProps {
  onQuickAction: (prompt: string) => void
}

export default function WelcomeScreen({ onQuickAction }: WelcomeScreenProps) {
  return (
    <div className="max-w-[820px] mx-auto px-6 pt-10 pb-6">
      <div className="text-center pt-10 pb-6">
        <div className="text-[20px] font-semibold text-[var(--navy)] mb-2" style={{ color: 'var(--navy)' }}>
          您好，我是政企智能助手 👋
        </div>
        <div className="text-sm text-[var(--text-3)] mb-9">
          政策问答 · 公文写作 · 办事流程导引，一个入口全搞定
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-[14px] max-w-[760px] mx-auto">
        {quickActions.map((action) => (
          <button key={action.id} onClick={() => onQuickAction(action.prompt)} className="suggest-card">
            <div className="text-2xl mb-1.5">{action.icon}</div>
            <div className="text-sm font-medium text-[var(--text-1)]">{action.label}</div>
            <div className="text-[11px] text-[var(--gold-strong)] mt-1.5">{action.description}</div>
          </button>
        ))}
      </div>

      <div className="mt-8 text-center text-xs text-[var(--text-muted)]">
        试试输入具体问题，例如「中小企业如何申请税收优惠？」
      </div>
    </div>
  )
}
