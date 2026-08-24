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
        {onWriting && (
          <button className="icon-btn" title="公文写作" onClick={onWriting}>✍️</button>
        )}
        <button className="icon-btn" title="帮助">❓</button>
      </div>
    </header>
  )
}
