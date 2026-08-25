import { useMemo } from 'react'
import Icon from './Icons'
import type { Conversation, AuthUser } from '../types'

interface SidebarProps {
  conversations: Conversation[]
  currentSessionId: string | null
  onNewChat: () => void
  onSelectConversation: (id: string) => void
  onDeleteConversation: (id: string, e: React.MouseEvent) => void
  deletingId?: string | null
  user?: AuthUser | null
  onOpenUserAdmin?: () => void
}

interface Group {
  title: string
  items: Conversation[]
}

const DAY_MS = 24 * 60 * 60 * 1000

function groupByDate(items: Conversation[]): Group[] {
  const now = new Date()
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const yesterdayStart = todayStart - DAY_MS

  const groups: Group[] = [
    { title: '今天', items: [] },
    { title: '昨天', items: [] },
    { title: '更早', items: [] },
  ]

  for (const item of items) {
    const t = item.updatedAt || item.createdAt || 0
    if (t >= todayStart) groups[0].items.push(item)
    else if (t >= yesterdayStart) groups[1].items.push(item)
    else groups[2].items.push(item)
  }

  return groups.filter((g) => g.items.length > 0)
}

export default function Sidebar({
  conversations,
  currentSessionId,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
  deletingId,
  user,
  onOpenUserAdmin,
}: SidebarProps) {
  const groups = useMemo(() => groupByDate(conversations), [conversations])

  return (
    <aside className="sidebar">
      <div className="side-head">
        <div className="side-logo">
          <div className="logo-mark">政</div>
          <span>政企智能助手</span>
        </div>
      </div>

      <button onClick={onNewChat} className="new-btn">
        <Icon name="plus" size={15} /> 新建对话
      </button>

      <div className="conv-wrap">
        {groups.length === 0 ? (
          <div className="conv-empty">暂无历史对话</div>
        ) : (
          groups.map((group) => (
            <div key={group.title} className="conv-group">
              <div className="g-title">{group.title}</div>
              {group.items.map((conv) => {
                const active = conv.id === currentSessionId
                const isDeleting = deletingId === conv.id
                return (
                  <div key={conv.id} className="conv-item-row group">
                    <button
                      onClick={() => !isDeleting && onSelectConversation(conv.id)}
                      className={`conv-item ${active ? 'active' : ''}`}
                      disabled={isDeleting}
                      style={isDeleting ? { opacity: 0.5 } : undefined}
                    >
                      <span className="conv-item-text">{conv.title || '新对话'}</span>
                      <span
                        className="conv-del"
                        role="button"
                        tabIndex={0}
                        title={isDeleting ? '删除中…' : '删除会话'}
                        onClick={(e) => { if (!isDeleting) onDeleteConversation(conv.id, e) }}
                        onKeyDown={(e) => {
                          if (!isDeleting && e.key === 'Enter') onDeleteConversation(conv.id, e as unknown as React.MouseEvent)
                        }}
                        style={isDeleting ? { pointerEvents: 'none', opacity: 0.4 } : undefined}
                      >
                        {isDeleting ? '…' : <Icon name="x" size={14} />}
                      </span>
                    </button>
                  </div>
                )
              })}
            </div>
          ))
        )}
      </div>

      <div className="side-foot">
        {user ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
            <span>👤 {user.username}{user.role === 'admin' ? '（管理员）' : ''}</span>
            {user.role === 'admin' && onOpenUserAdmin && (
              <button
                onClick={onOpenUserAdmin}
                style={{ background: 'none', border: '1px solid rgba(255,255,255,0.3)', color: 'inherit', fontSize: 11, padding: '2px 8px', borderRadius: 4, cursor: pointer }}
              >
                用户管理
              </button>
            )}
          </div>
        ) : (
          <span>未登录</span>
        )}
      </div>
    </aside>
  )
}
