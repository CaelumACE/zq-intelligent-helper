import type { QuickActionItem } from '../types';

export const quickActions: QuickActionItem[] = [
  {
    id: 'qa-1',
    icon: 'book',
    label: '最新社保缴费比例是多少？',
    tag: '政策问答',
    prompt: '最新社保缴费比例是多少？',
  },
  {
    id: 'qa-2',
    icon: 'pen',
    label: '帮我写一份会议通知',
    tag: '公文写作',
    prompt: '帮我写一份会议通知',
  },
  {
    id: 'qa-3',
    icon: 'compass',
    label: '营业执照怎么办理？',
    tag: '流程导引',
    prompt: '营业执照怎么办理？',
  },
  {
    id: 'qa-4',
    icon: 'home',
    label: '公积金贷款最高额度是多少？',
    tag: '政策问答',
    prompt: '公积金贷款最高额度是多少？',
  },
];
