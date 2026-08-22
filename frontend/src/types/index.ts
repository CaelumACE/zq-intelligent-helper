export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  references?: Reference[];
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

export interface QuickAction {
  id: string;
  icon: string;
  label: string;
  description: string;
  prompt: string;
}
