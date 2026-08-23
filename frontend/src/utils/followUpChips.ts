import type { Message } from '../types'

/**
 * 后续指令 chip 规则：根据上一轮用户问题的主题，
 * 给出 3 个最相关的追问/改写建议。
 * 这些 chip 会渲染在 AI 回复气泡下方，点击后作为下一条消息发送。
 */
const CONTEXT_CHIPS_BY_TOPIC: Array<{ match: RegExp; chips: string[] }> = [
  { match: /年终|报告|总结/, chips: ['继续写完整报告', '调整语气更正式', '补充数据说明'] },
  { match: /通知/, chips: ['补充参会人员', '调整语气更正式', '写明时间地点'] },
  { match: /政策|补贴|扶持/, chips: ['申请条件是什么', '需要准备哪些材料', '找办理窗口'] },
  { match: /办理|流程|材料/, chips: ['办理时限多久', '可以线上办理吗', '需要哪些材料'] },
  { match: /社保|公积金|养老|医疗|失业|工伤|生育/, chips: ['缴费比例是多少', '如何办理补缴', '咨询电话是多少'] },
  { match: /公文|文种|种类|类型/, chips: ['介绍下请示和报告的区别', '函的适用场景', '举个通知的例子'] },
]

const DEFAULT_CHIPS = ['换一种更正式的说法', '列出关键要点', '补充具体示例']

/**
 * 根据整条对话挑选 chip。取最近一条用户消息作为主题依据。
 */
export function pickFollowUpChips(messages: Message[]): string[] {
  const lastUser = [...messages].reverse().find((m) => m.role === 'user')
  if (!lastUser) return []
  for (const group of CONTEXT_CHIPS_BY_TOPIC) {
    if (group.match.test(lastUser.content)) return group.chips
  }
  return DEFAULT_CHIPS
}
