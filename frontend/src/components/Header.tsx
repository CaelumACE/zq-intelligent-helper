interface HeaderProps {
  title: string;
  onMenu?: () => void;
  onWriting?: () => void;
}

export default function Header({ title, onMenu, onWriting }: HeaderProps) {
  return (
    <header
      className="h-14 bg-white border-b border-[var(--border)] flex items-center px-4 md:px-[22px] gap-3.5 flex-shrink-0"
      style={{ borderColor: 'var(--border)' }}
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
      <h2 className="text-[15px] font-semibold text-[var(--text-1)] whitespace-nowrap overflow-hidden text-ellipsis">
        {title}
      </h2>
      <div className="ml-auto flex gap-2">
        {onWriting && (
          <button className="icon-btn" title="公文写作" onClick={onWriting}>✍️</button>
        )}
        <button className="icon-btn" title="帮助">❓</button>
      </div>
    </header>
  )
}
