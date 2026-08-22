import { useState } from 'react';
import type { Conversation } from '../types';
import { mockConversations } from '../utils/mockData';

interface SidebarProps {
  currentView: 'chat' | 'home';
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
}

export default function Sidebar({ currentView, onNewChat, onSelectConversation }: SidebarProps) {
  const [conversations] = useState<Conversation[]>(mockConversations);

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
        <div className="text-xs text-white/40 px-2 py-2 uppercase tracking-wide">历史对话</div>
        {conversations.map((conv) => (
          <button
            key={conv.id}
            onClick={() => onSelectConversation(conv.id)}
            className={`w-full text-left px-3 py-2.5 rounded-lg mb-1 text-sm transition-colors ${
              currentView === 'chat'
                ? 'hover:bg-white/10 text-white/90'
                : 'hover:bg-white/10 text-white/90'
            }`}
          >
            <div className="truncate">{conv.title}</div>
            <div className="text-xs text-white/40 mt-1">
              {new Date(conv.updatedAt).toLocaleDateString('zh-CN')}
            </div>
          </button>
        ))}
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
  );
}
