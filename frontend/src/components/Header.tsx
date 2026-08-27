import Icon from './Icons'
import type { AuthUser, ModelProvider } from '../types'

interface HeaderProps {
  activePanel: 'qa' | 'guide' | 'compare'
  onPanelChange: (panel: 'qa' | 'guide' | 'compare') => void
  onWriting: () => void
  onMenu?: () => void
  user: AuthUser | null
  onLogout: () => void
  model: ModelProvider
}

const TABS = [
  { key: 'qa' as const, label: '智能问答', icon: 'help-circle' as const },
  { key: 'guide' as const, label: '我要办事', icon: 'file-text' as const },
  { key: 'compare' as const, label: '政策比对', icon: 'git-compare' as const },
]

export default function Header({ activePanel, onPanelChange, onWriting, onMenu, user, onLogout, model }: HeaderProps) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        {onMenu && (
          <button onClick={onMenu} className="topbar-menu-btn md:hidden" aria-label="打开菜单">
            <Icon name="menu" size={20} />
          </button>
        )}
        <nav className="nav-tabs">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              className={`nav-tab ${activePanel === tab.key ? 'active' : ''}`}
              onClick={() => onPanelChange(tab.key)}
            >
              <Icon name={tab.icon} size={16} />
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      <div className="topbar-right">
        <span className="topbar-model">
          <span className="topbar-model-dot" />
          {model === 'minimax' ? 'MiniMax' : 'DeepSeek'}
        </span>
        <button className="write-btn" onClick={onWriting}>
          <Icon name="pen-line" size={16} />
          <span>写公文</span>
        </button>
        {user && (
          <div className="topbar-user">
            <div className="topbar-user-avatar">{user.username.charAt(0).toUpperCase()}</div>
            <div className="topbar-user-info">
              <span className="topbar-user-name">{user.username}</span>
            </div>
            <button className="topbar-logout" onClick={onLogout} title="退出登录">
              <Icon name="log-out" size={15} />
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
