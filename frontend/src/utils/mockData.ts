import type { QuickAction } from '../types';

export const quickActions: QuickAction[] = [
  {
    id: 'qa-1',
    icon: '📋',
    label: '政策咨询',
    description: '查询最新政策法规、补贴政策解读',
    prompt: '请帮我查询最新的中小企业扶持政策有哪些？',
  },
  {
    id: 'qa-2',
    icon: '✍️',
    label: '公文写作',
    description: '智能生成通知、报告、纪要等公文',
    prompt: '请帮我撰写一份关于年度工作总结的通知',
  },
  {
    id: 'qa-3',
    icon: '📌',
    label: '办事指引',
    description: '了解办事流程、所需材料和办理窗口',
    prompt: '企业注册变更需要哪些材料和流程？',
  },
  {
    id: 'qa-4',
    icon: '📊',
    label: '数据分析',
    description: '数据查询、统计分析与报表生成',
    prompt: '帮我统计本季度各部门的审批办理情况',
  },
];
