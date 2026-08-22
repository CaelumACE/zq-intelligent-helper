import type { Conversation } from '../types'

interface SidebarProps {
  currentView: 'chat' | 'home'
  conversations: Conversation[]
  currentSessionId: string | null
  onNewChat: () => void
  onSelectConversation: (id: string) => void
  onDeleteConversation: (id: string, e: React.MouseEvent) => void
}

export default function Sidebar({
  conversations,
  currentSessionId,
  onNewChat,
  onSelectConversation,
  onDeleteConversation,
}: SidebarProps) {
  return (
    <aside className="w-[260px] h-full flex-shrink-0 flex flex-col text-[#C7D2E0]" style={{ background: 'var(--navy)' }}>
      {/* Logo */}
      <div className="px-5 py-[18px] border-b border-white/[0.08]">
        <div className="flex items-center gap-2.5">
          <div className="logo-mark">政</div>
          <span className="text-white font-semibold text-[15px] tracking-[0.5px]">政企智能助手</span>
        </div>
      </div>

      {/* 新建对话 */}
      <button onClick={onNewChat} className="new-btn">
        ＋ 新建对话
      </button>

      {/* 历史对话 */}
      <div className="flex-1 overflow-y-auto sidebar-scroll px-[10px]">
        <div className="text-[11px] text-[#7E93AF] px-[10px] pb-1.5 pt-2 tracking-[0.06em]">历史对话</div>
        {conversations.length === 0 ? (
          <div className="text-xs text-[#7E93AF]/70 text-center mt-6">暂无历史对话</div>
        ) : (
          conversations.map((conv) => {
            const active = conv.id === currentSessionId
            return (
              <div key={conv.id} className="relative mb-0.5">
                <button
                  onClick={() => onSelectConversation(conv.id)}
                  className={`conv-item ${active ? 'active' : ''}`}
                >
                  {conv.title || '新对话'}
                </button>
                <button
                  onClick={(e) => onDeleteConversation(conv.id, e)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 w-[18px] h-[18px] rounded-full bg-white/[0.18] text-white/70 hover:text-white items-center justify-center text-[11px] hidden group-hover:flex"
                  title="删除会话"
                >
                  ✕
                </button>
              </div>
            )
          })
        )}
      </div>

      {/* 底部 */}
      <div className="px-5 py-[14px] text-xs text-[#7E93AF] border-t border-white/[0.08] flex items-center gap-2">
        <span>👤</span> 演示模式 · 无需登录
      </div>
    </aside>
  )
}
