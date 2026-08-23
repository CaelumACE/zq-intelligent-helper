export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  references?: Reference[];
  followUpChips?: string[];
  model?: string;
  status?: 'ok' | 'greeting' | 'self_intro' | 'capability' | 'thanks' | 'acknowledge' | 'farewell' | 'chat' | 'refusal' | 'out_of_scope' | 'writing';
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

export interface WritingRequest {
  docType: string;
  title: string;
  to: string;
  body: string;
  sign: string;
}

export interface QuickActionItem {
  id: string;
  icon: string;
  label: string;
  tag: string;
  prompt: string;
}

export type ModelProvider = 'minimax' | 'deepseek';
