export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  references?: Reference[];
  model?: string;
}

export interface Reference {
  title: string;
  source: string;
  snippet: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

export interface QuickActionItem {
  id: string;
  icon: string;
  label: string;
  tag: string;
  prompt: string;
}

export type ModelProvider = 'minimax' | 'deepseek';
