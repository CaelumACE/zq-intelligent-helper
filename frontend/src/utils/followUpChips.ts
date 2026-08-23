import type { Message } from '../types'

/**
 * 后续指令 chip 规则：只有“进入知识库检索并给出了实质回答”的 AI 回复
 * 才能在下方渲染快捷推荐问题。其它场景（开场白/拒答/感谢/告别/闲聊/公文写作）
 * 一律不渲染 chip，避免用户被引导到不相关流程（如被引入公文请示）。
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
 * 这些答复属于固定话术/拒答/未覆盖引导，本身不是具体知识回答，
 * 下面挂追问 chip 会让用户误以为可以继续追问具体事项，因此不显示 chip。
 */
const NO_CHIP_REPLIES = [
  /您好！我是政企智能助手/,
  /我是政企智能助手/,
  /我可以为您提供以下服务/,
  /抱歉，这个问题超出了/,
  /已识别为政务服务事项，但当前知识库暂未收录/,
  /不客气！/,
  /感谢使用政企智能助手/,
  /好的，还有其他需要帮助的吗？/,
  /很高兴能帮到您/,
]

/**
 * 这些 status 属于非实质问答状态，即使后端 status 没下发、旧消息没带 status，
 * 也必须强制不渲染 chip，作为前后端双重兜底。
 */
const NO_CHIP_STATUS = new Set([
  'greeting',
  'self_intro',
  'capability',
  'thanks',
  'acknowledge',
  'farewell',
  'chat',
  'refusal',
  'out_of_scope',
  'writing',
])

function isNoChipReply(content: string): boolean {
  return NO_CHIP_REPLIES.some((pattern) => pattern.test(content))
}

export function shouldShowChips(message: Message | undefined): boolean {
  if (!message || message.role !== 'assistant') return false
  // 全局规则：仅有参考资料（真正进入 RAG 检索）的实质回答才出 chip。
  if (!message.references || message.references.length === 0) return false
  if (message.status && NO_CHIP_STATUS.has(message.status)) return false
  return !isNoChipReply(message.content)
}

/**
 * 拒答/无结果判定：用于隐藏引用来源区等位置。
 * 只要回答属于“未收录 / 超出范围 / 暂无相关信息”，就不应再展示引用来源。
 */
export function isRefusalReply(content: string): boolean {
  if (isNoChipReply(content)) return true
  return /暂无相关信息|未提供具体|未收录|暂未查询到|暂未找到|知识库中暂无|超出.*服务范围/.test(content || '')
}

/**
 * 根据整条对话挑选 chip。
 * 先按最新 AI 回复做硬闸门：必须是进入 RAG 检索且有引用的实质回答；
 * 再取最近一条用户消息作为主题依据。
 */
export function pickFollowUpChips(messages: Message[]): string[] {
  const lastAssistant = [...messages].reverse().find((m) => m.role === 'assistant')
  if (!shouldShowChips(lastAssistant)) return []
  const lastUser = [...messages].reverse().find((m) => m.role === 'user')
  if (!lastUser) return []
  for (const group of CONTEXT_CHIPS_BY_TOPIC) {
    if (group.match.test(lastUser.content)) return group.chips
  }
  return DEFAULT_CHIPS
}
