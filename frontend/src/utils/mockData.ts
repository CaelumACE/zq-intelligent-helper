import type { QuickActionItem } from '../types';

export const quickActions: QuickActionItem[] = [
  {
    id: 'qa-1',
    icon: 'help-circle',
    label: '最新社保缴费比例是多少？',
    description: '查询养老、医疗、失业、工伤、生育保险最新缴费基数与比例。',
    tag: '政策问答',
    prompt: '最新社保缴费比例是多少？',
  },
  {
    id: 'qa-2',
    icon: 'file-text',
    label: '帮我写一份会议通知',
    description: '自动生成符合党政机关公文格式的会议通知模板。',
    tag: '公文写作',
    prompt: '帮我写一份会议通知',
  },
  {
    id: 'qa-3',
    icon: 'git-compare',
    label: '营业执照怎么办理？',
    description: '梳理开办企业全流程、所需材料、办理时限与窗口信息。',
    tag: '办事指引',
    prompt: '营业执照怎么办理？',
  },
  {
    id: 'qa-4',
    icon: 'building',
    label: '公积金贷款最高额度是多少？',
    description: '按缴存地、首套房/二套房、贷款年限给出额度测算。',
    tag: '政策问答',
    prompt: '公积金贷款最高额度是多少？',
  },
];
