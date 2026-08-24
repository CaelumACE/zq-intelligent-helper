import Icon from './Icons'

interface HeaderProps {
  title: string;
  onMenu?: () => void;
  onWriting?: () => void;
}

export default function Header({ title, onMenu, onWriting }: HeaderProps) {
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
        <button className="icon-btn" title="搜索" aria-label="搜索"><Icon name="search" size={18} /></button>
        <button className="icon-btn icon-btn-badge" title="通知" aria-label="通知">
          <Icon name="bell" size={18} />
          <span className="icon-badge">3</span>
        </button>
        <button className="icon-btn" title="收藏夹" aria-label="收藏夹"><Icon name="star" size={18} /></button>
        <button className="avatar-btn" title="个人中心" aria-label="个人中心"><Icon name="user" size={18} /></button>
        {onWriting && (
          <button className="icon-btn" title="公文写作" aria-label="公文写作" onClick={onWriting}><Icon name="pen" size={18} /></button>
        )}
      </div>
    </header>
  )
}
