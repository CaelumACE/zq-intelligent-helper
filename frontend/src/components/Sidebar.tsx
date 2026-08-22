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
    <div className="w-64 bg-[var(--bg-sidebar)] text-white flex flex-col h-screen">
      {/* Logo区域 */}
      <div className="p-4 border-b border-white/10">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-gradient-to-br from-blue-400 to-blue-600 rounded-lg flex items-center justify-center font-bold text-sm">
            政
          </div>
          <div>
            <h1 className="text-sm font-semibold">政企智能助手</h1>
            <p className="text-xs text-white/60">Government AI Assistant</p>
          </div>
        </div>
      </div>

      {/* 新建对话按钮 */}
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white rounded-lg py-2.5 px-4 text-sm font-medium transition-colors flex items-center justify-center gap-2"
        >
          <span className="text-lg">+</span>
          新建对话
        </button>
      </div>

      {/* 历史对话列表 */}
      <div className="flex-1 overflow-y-auto px-2">
        <div className="text-xs text-white/40 px-2 py-2 uppercase tracking-wide">
          历史对话
        </div>
        {conversations.length === 0 ? (
          <div className="text-xs text-white/30 text-center mt-6">暂无历史对话</div>
        ) : (
          conversations.map((conv) => {
            const active = conv.id === currentSessionId
            return (
              <div
                key={conv.id}
                onClick={() => onSelectConversation(conv.id)}
                className={`group w-full text-left px-3 py-2.5 rounded-lg mb-1 text-sm transition-colors cursor-pointer ${
                  active ? 'bg-white/15 text-white' : 'hover:bg-white/10 text-white/90'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="truncate flex-1">{conv.title}</div>
                  <button
                    onClick={(e) => onDeleteConversation(conv.id, e)}
                    className="opacity-0 group-hover:opacity-100 text-white/50 hover:text-white transition-opacity"
                    title="删除会话"
                  >
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
                <div className="text-xs text-white/40 mt-1">
                  {new Date(conv.updatedAt).toLocaleString('zh-CN', {
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </div>
              </div>
            )
          })
        )}
      </div>

      {/* 底部用户信息 */}
      <div className="p-3 border-t border-white/10">
        <div className="flex items-center gap-2 px-2 py-2 rounded-lg hover:bg-white/10 transition-colors cursor-pointer">
          <div className="w-8 h-8 bg-gradient-to-br from-purple-400 to-pink-400 rounded-full flex items-center justify-center text-sm font-medium">
            浩
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-sm font-medium truncate">浩哥</div>
            <div className="text-xs text-white/60">管理员</div>
          </div>
        </div>
      </div>
    </div>
  )
}
