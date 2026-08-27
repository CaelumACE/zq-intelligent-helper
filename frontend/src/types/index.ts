export interface StructuredAnswer {
  item_name: string;
  description?: string;
  required_materials?: string[];
  steps?: string[];
  location?: string;
  time_limit?: string;
  fee?: string;
  consult_phone?: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  sessionId?: string;
  references?: Reference[];
  followUpChips?: string[];
  model?: string;
  structuredAnswer?: StructuredAnswer;
  status?: 'ok' | 'greeting' | 'self_intro' | 'capability' | 'thanks' | 'acknowledge' | 'farewell' | 'chat' | 'refusal' | 'out_of_scope' | 'writing' | 'service_card';
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
  icon: IconName;
  label: string;
  tag: string;
  prompt: string;
}

export type ModelProvider = 'minimax' | 'deepseek';

export type IconName =
  | 'book'
  | 'pen'
  | 'compass'
  | 'home'
  | 'bell'
  | 'star'
  | 'search'
  | 'user'
  | 'menu'
  | 'chevron-down'
  | 'copy'
  | 'refresh'
  | 'thumbs-up'
  | 'thumbs-down'
  | 'square'
  | 'send'
  | 'plus'
  | 'download'
  | 'x';

export interface GuideMaterial {
  name: string;
  copies?: number;
  required?: boolean;
  notes?: string;
}

export interface GuideStep {
  id: string;
  step_order: number;
  name: string;
  department?: string;
  duration_days: number;
  channel: 'online' | 'offline' | 'both';
  channel_detail?: string;
  materials: GuideMaterial[];
  prerequisites: string[];
  fee: string;
  notes?: string;
}

export interface GuideTheme {
  id: string;
  name: string;
  icon?: string;
  description?: string;
  category?: string;
  keywords?: string[];
  estimated_days: number;
}

export interface GuideRoadmap {
  matched?: boolean;
  candidates?: { id: string; name: string; score: number }[];
  message?: string;
  theme: GuideTheme;
  steps: GuideStep[];
  total_days: number;
}

export interface AuthUser {
  id: number;
  username: string;
  role: string;
}

export interface CompareDoc {
  title: string;
  content: string;
}

export interface DiffItem {
  type: 'added' | 'removed' | 'modified';
  clause: string;
  old_text: string;
  new_text: string;
  change_note: string;
}

export interface CompareResult {
  task_id: string;
  summary: {
    added: number;
    removed: number;
    modified: number;
    total_changes: number;
    brief: string;
  };
  total_changes: number;
  diffs: DiffItem[];
}

export interface KnowledgeItem {
  id: number;
  title: string;
  category: string;
  source: string;
  status: string;
  metadata: Record<string, unknown>;
  content: string;
}
