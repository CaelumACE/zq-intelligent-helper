import type { Conversation, QuickAction } from '../types';

export const mockConversations: Conversation[] = [
  {
    id: 'conv-1',
    title: '关于企业补贴政策咨询',
    messages: [],
    createdAt: Date.now() - 86400000,
    updatedAt: Date.now() - 86400000,
  },
  {
    id: 'conv-2',
    title: '公文写作 - 会议纪要',
    messages: [],
    createdAt: Date.now() - 172800000,
    updatedAt: Date.now() - 172800000,
  },
  {
    id: 'conv-3',
    title: '社保办理流程查询',
    messages: [],
    createdAt: Date.now() - 259200000,
    updatedAt: Date.now() - 259200000,
  },
];

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

export const mockResponses: Record<string, string> = {
  default: `您好！我是政企智能助手，可以为您提供以下服务：

**📋 政策咨询** — 查询最新政策法规、补贴政策
**✍️ 公文写作** — 智能生成通知、报告、纪要等
**📌 办事指引** — 了解办事流程和所需材料
**📊 数据分析** — 数据查询与统计分析

请问有什么可以帮您的？`,
};

export function getMockResponse(userMessage: string): { content: string; references?: { title: string; source: string; snippet: string }[] } {
  const lower = userMessage.toLowerCase();

  if (lower.includes('政策') || lower.includes('扶持') || lower.includes('补贴')) {
    return {
      content: `根据最新政策文件，以下是当前适用的主要扶持政策：

**一、税收优惠政策**
1. 小微企业年应纳税所得额不超过300万元的部分，实际税率降至5%
2. 增值税小规模纳税人月销售额15万元以下免征增值税

**二、财政补贴政策**
1. 科技创新型企业研发费用加计扣除比例提高至100%
2. 新引进高层次人才给予最高200万元安家补贴

**三、融资支持政策**
1. 政府性融资担保机构担保费率降至1%以下
2. 小微企业贷款贴息最高50万元

如需了解具体申报条件和流程，请继续提问。`,
      references: [
        { title: '关于进一步支持小微企业发展的若干意见', source: '国务院办公厅', snippet: '小微企业年应纳税所得额不超过300万元的部分...' },
        { title: '2024年科技创新扶持办法', source: '科技部', snippet: '科技创新型企业研发费用加计扣除比例提高至100%...' },
      ],
    };
  }

  if (lower.includes('公文') || lower.includes('通知') || lower.includes('写作') || lower.includes('撰写')) {
    return {
      content: `好的，我来帮您撰写一份公文。以下是一个通用通知模板：

---

**关于做好2024年度工作总结的通知**

各部门、各下属单位：

为全面总结2024年度工作成效，科学谋划2025年发展思路，现就做好年度工作总结有关事项通知如下：

**一、总结内容**
（一）年度主要目标完成情况
（二）重点工作推进成效与亮点
（三）存在问题及原因分析
（四）2025年工作计划

**二、工作要求**
1. 高度重视，专人负责
2. 数据准确，内容翔实
3. 于12月25日前报送办公室

特此通知。

---

如需调整内容或格式，请告诉我具体要求。`,
    };
  }

  if (lower.includes('流程') || lower.includes('办理') || lower.includes('怎么办') || lower.includes('材料')) {
    return {
      content: `为您查询到相关办事流程：

**企业注册变更办理流程**

**所需材料：**
1. 法定代表人签署的变更登记申请书
2. 营业执照正、副本原件
3. 股东会决议/董事会决议
4. 修改后的公司章程或章程修正案
5. 涉及股权转让的需提供股权转让协议

**办理步骤：**
1. **网上申请** → 登录政务服务网提交变更申请
2. **窗口递交** → 携带材料到市场监管窗口办理
3. **审核受理** → 3个工作日内完成审核
4. **领取新证** → 换发新营业执照

**办理时限：** 5个工作日
**收费标准：** 免费

如需了解其他事项办理流程，请继续提问。`,
      references: [
        { title: '企业登记管理办事指南', source: '市场监督管理局', snippet: '企业注册变更需提交法定代表人签署的变更登记申请书...' },
      ],
    };
  }

  return {
    content: `感谢您的提问！根据您的描述，我为您提供以下信息：

您提到的"${userMessage}"涉及多个方面，我已为您检索相关政策文件和办事指南。

建议您：
1. 明确具体的业务类型和办理事项
2. 我可以为您提供更精准的政策解读或办事指引
3. 如需公文写作帮助，请告诉我具体文体类型

请问您需要哪方面的详细帮助？`,
  };
}
