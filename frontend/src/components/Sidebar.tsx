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
  onChangePassword?: () => void
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

function roleLabel(role?: string): string {
  if (role === 'super_admin') return '超管'
  if (role === 'admin') return '管理员'
  return '用户'
}

function userInitial(username?: string): string {
  if (!username) return '?'
  return username.charAt(0).toUpperCase()
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
  onChangePassword,
}: SidebarProps) {
  const groups = useMemo(() => groupByDate(conversations), [conversations])

  return (
    <aside className="sidebar">
      <div className="side-head">
        <div className="side-logo">
          <div className="logo-mark" aria-hidden="true">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 21h18" />
              <path d="M5 21V7l7-4 7 4v14" />
              <path d="M9 21v-6h6v6" />
            </svg>
          </div>
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
                  <div key={conv.id} className="conv-item-row">
                    <button
                      onClick={() => !isDeleting && onSelectConversation(conv.id)}
                      className={`conv-item ${active ? 'active' : ''}`}
                      disabled={isDeleting}
                      style={isDeleting ? { opacity: 0.5 } : undefined}
                      title={conv.title || '新对话'}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0, opacity: 0.65 }}>
                        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                      </svg>
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
                        {isDeleting ? '…' : <Icon name="x" size={13} />}
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
          <div className="side-foot-inner">
            <div className="side-foot-user">
              <span className="side-foot-avatar">{userInitial(user.username)}</span>
              <span className="side-foot-name" title={user.username}>{user.username}</span>
              <span className={`side-foot-badge ${user.role === 'super_admin' ? 'side-foot-badge-super' : 'side-foot-badge-admin'}`}>
                {roleLabel(user.role)}
              </span>
            </div>
            <div className="side-foot-actions">
              {(user.role === 'admin' || user.role === 'super_admin') && onOpenUserAdmin && (
                <button className="side-foot-btn" onClick={onOpenUserAdmin}>
                  用户管理
                </button>
              )}
              {onChangePassword && (
                <button className="side-foot-btn" onClick={onChangePassword}>
                  修改密码
                </button>
              )}
            </div>
          </div>
        ) : (
          <span style={{ color: 'rgba(255,255,255,0.5)', fontSize: 13 }}>未登录</span>
        )}
      </div>
    </aside>
  )
}
