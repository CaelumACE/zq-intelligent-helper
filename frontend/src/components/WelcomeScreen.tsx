import { quickActions } from '../utils/mockData'

interface WelcomeScreenProps {
  onQuickAction: (prompt: string) => void
}

export default function WelcomeScreen({ onQuickAction }: WelcomeScreenProps) {
  return (
    <div className="max-w-3xl mx-auto px-6 pt-16 pb-10">
      <div className="text-center mb-10 animate-fade-in">
        <div className="w-16 h-16 bg-gradient-to-br from-[var(--primary)] to-[var(--primary-light)] rounded-2xl flex items-center justify-center mx-auto mb-5 shadow-lg">
          <span className="text-white text-2xl font-bold">政</span>
        </div>
        <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-3">
          政企智能助手
        </h1>
        <p className="text-sm text-[var(--text-secondary)] max-w-md mx-auto leading-relaxed">
          基于政策知识库的智能问答，支持政策咨询、公文写作、办事引导，回答可溯源、结果可查证。
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 animate-fade-in" style={{ animationDelay: '0.1s' }}>
        {quickActions.map((action) => (
          <button
            key={action.id}
            onClick={() => onQuickAction(action.prompt)}
            className="group bg-white border border-[var(--border)] rounded-xl p-4 text-left hover:border-[var(--primary-light)] hover:shadow-md transition-all"
          >
            <div className="text-2xl mb-2">{action.icon}</div>
            <div className="text-sm font-medium text-[var(--text-primary)] group-hover:text-[var(--primary)] transition-colors">
              {action.label}
            </div>
            <div className="text-xs text-[var(--text-muted)] mt-1">{action.description}</div>
          </button>
        ))}
      </div>

      <div className="mt-10 text-center text-xs text-[var(--text-muted)] animate-fade-in" style={{ animationDelay: '0.2s' }}>
        试试输入具体问题，例如「中小企业如何申请税收优惠？」
      </div>
    </div>
  )
}
