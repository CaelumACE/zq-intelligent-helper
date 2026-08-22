"""对话 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from app.services.llm_service import LLMService
from app.services.knowledge_service import KnowledgeService
from app.core.logger import logger

router = APIRouter()

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []

class Reference(BaseModel):
    title: str
    source: str
    snippet: str

class ChatResponse(BaseModel):
    content: str
    references: Optional[List[Reference]] = []

# Mock 数据（演示用）
MOCK_RESPONSES = {
    "政策": {
        "content": """根据最新政策文件，以下是当前适用的主要扶持政策：

**一、税收优惠政策**
1. 小微企业年应纳税所得额不超过300万元的部分，实际税率降至5%
2. 增值税小规模纳税人月销售额15万元以下免征增值税

**二、财政补贴政策**
1. 科技创新型企业研发费用加计扣除比例提高至100%
2. 新引进高层次人才给予最高200万元安家补贴

如需了解具体申报条件和流程，请继续提问。""",
        "references": [
            {"title": "关于进一步支持小微企业发展的若干意见", "source": "国务院办公厅", "snippet": "小微企业年应纳税所得额不超过300万元的部分..."},
            {"title": "2024年科技创新扶持办法", "source": "科技部", "snippet": "科技创新型企业研发费用加计扣除比例提高至100%..."},
        ]
    },
    "公文": {
        "content": """好的，我来帮您撰写一份公文。以下是一个通用通知模板：

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

如需调整内容或格式，请告诉我具体要求。""",
        "references": []
    },
    "流程": {
        "content": """为您查询到相关办事流程：

**企业注册变更办理流程**

**所需材料：**
1. 法定代表人签署的变更登记申请书
2. 营业执照正、副本原件
3. 股东会决议/董事会决议
4. 修改后的公司章程或章程修正案

**办理步骤：**
1. **网上申请** → 登录政务服务网提交变更申请
2. **窗口递交** → 携带材料到市场监管窗口办理
3. **审核受理** → 3个工作日内完成审核
4. **领取新证** → 换发新营业执照

**办理时限：** 5个工作日
**收费标准：** 免费""",
        "references": [
            {"title": "企业登记管理办事指南", "source": "市场监督管理局", "snippet": "企业注册变更需提交法定代表人签署的变更登记申请书..."},
        ]
    }
}

def get_mock_response(message: str) -> dict:
    """根据关键词返回 mock 响应"""
    for key, value in MOCK_RESPONSES.items():
        if key in message:
            return value
    return {
        "content": "您好！我是政企智能助手，可以为您提供政策咨询、公文写作、办事指引等服务。请问有什么可以帮您的？",
        "references": []
    }

@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """对话接口"""
    try:
        logger.info(f"Received chat request: {request.message[:50]}...")
        
        # TODO: 接入真实 RAG 流程
        # 1. 知识库检索
        # 2. 构建 prompt
        # 3. 调用 LLM
        # 4. 返回结果
        
        # 临时使用 mock 数据
        response = get_mock_response(request.message)
        return ChatResponse(**response)
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/mock")
async def mock_chat(request: ChatRequest):
    """Mock 对话接口（降级用）"""
    response = get_mock_response(request.message)
    return response
