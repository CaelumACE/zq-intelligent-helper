"""对话 API"""
import time
from fastapi import APIRouter, HTTPException
from app.models import ChatRequest, ChatResponse, Reference, ChatMessage
from app.services.knowledge_service import knowledge_service
from app.services.llm_service import LLMService
from app.services.session_store import session_store
from app.core.logger import logger

router = APIRouter()

llm_service = LLMService()

SYSTEM_PROMPT = """你是政企智能助手，为政府机关和企事业单位提供专业、准确、合规的服务。

你的能力包括：
1. 政策咨询：基于知识库提供政策解读、补贴查询等服务
2. 公文写作：生成通知、报告、纪要等公文
3. 办事指引：提供办事流程、所需材料等信息

回答要求：
1. 基于给定的参考资料回答，引用要准确、可溯源
2. 如果资料中没有答案，明确说"暂无相关信息"，不要编造
3. 涉及具体数据时标注来源
4. 保持中立客观，不发表未经验证的信息"""

WRITING_PROMPT_EXTRA = """
当前用户需要撰写公文。请严格依据参考资料中的公文格式与写作规范生成，结构完整、用语规范。
如参考资料不足以完成该文种，请说明需要用户补充的信息，不要臆造格式。"""

QA_PROMPT_EXTRA = """
当前用户正在进行知识问答。请先准确理解问题，再仅依据参考资料作答。
如果是问"种类/类型/定义/区别"等概念性问题，请直接回答概念本身，不要擅自生成一篇公文模板。"""

SERVICE_PROMPT_EXTRA = """
当前用户需要办事指引。请依据参考资料，清晰列出办理条件、所需材料、办理步骤、地点与时限。
如资料未覆盖某项，请明确说明，不要臆造。"""

OUT_OF_SCOPE_RESPONSE = (
    "抱歉，这个问题超出了政企智能助手的服务范围。\n\n"
    "我可以为您提供以下服务：\n"
    "1. 政策咨询：政策解读、补贴查询等\n"
    "2. 公文写作：通知、报告、纪要、请示等\n"
    "3. 办事指引：营业执照、社保、税务等办事流程\n"
    "4. 公文知识：公文种类、文种定义与区别等\n\n"
    "请尝试提问与政企服务相关的问题。"
)


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """对话接口（RAG 增强 + 会话持久化 + 意图路由）"""
    start_time = time.time()

    try:
        # 会话管理
        session_id = request.session_id
        if not session_id:
            session_id = session_store.create()["id"]
        elif not session_store.get(session_id):
            session_id = session_store.create()["id"]

        # 1. 知识库检索 + 意图识别
        retrieval_start = time.time()
        intent = knowledge_service.classify_intent(request.message)
        search_results = knowledge_service.search(request.message, top_k=5)
        retrieval_time = (time.time() - retrieval_start) * 1000

        # 2. 无检索命中的拒答保护：不调用 LLM，直接返回，避免编造
        if not search_results:
            content = OUT_OF_SCOPE_RESPONSE
            generation_time = 0.0
            references = []
            logger.info(f"拒答（无知识库命中）: {request.message[:40]}")
        else:
            context = knowledge_service.build_context(request.message, top_k=5)
            references = knowledge_service.get_references(search_results)

            # 3. 按意图构建 prompt
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            if intent == "writing":
                messages.append({"role": "system", "content": WRITING_PROMPT_EXTRA})
            elif intent == "service":
                messages.append({"role": "system", "content": SERVICE_PROMPT_EXTRA})
            else:
                messages.append({"role": "system", "content": QA_PROMPT_EXTRA})

            if context:
                messages.append({
                    "role": "system",
                    "content": f"参考资料：\n{context}"
                })

            # 优先使用已持久化的会话历史，其次使用请求中的临时历史
            history = []
            if request.history:
                history = [m.to_dict() if isinstance(m, ChatMessage) else m for m in request.history]
            else:
                history = session_store.get_history(session_id)

            for msg in history[-6:]:
                if isinstance(msg, dict):
                    messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

            messages.append({"role": "user", "content": request.message})

            # 4. 调用 LLM
            generation_start = time.time()
            try:
                llm_response = await llm_service.chat(messages, stream=False)
                content = _extract_content(llm_response)
                generation_time = (time.time() - generation_start) * 1000
            except Exception as llm_error:
                logger.warning(f"LLM 调用失败，使用知识库兜底: {llm_error}")
                content = _fallback_response(request.message, search_results)
                generation_time = (time.time() - generation_start) * 1000

        # 5. 持久化本轮对话（引用来源随历史保存）
        user_msg = {"role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
        assistant_msg = {"role": "assistant", "content": content, "references": references, "timestamp": int(time.time() * 1000)}
        session_store.add_messages(session_id, [user_msg, assistant_msg])

        logger.info(
            f"对话完成: session={session_id[:8]} intent={intent} 检索 {retrieval_time:.0f}ms, "
            f"生成 {generation_time:.0f}ms, 命中 {len(search_results)} 条"
        )

        return ChatResponse(
            session_id=session_id,
            content=content,
            references=[Reference(**ref) for ref in references],
            retrieval_time_ms=retrieval_time,
            generation_time_ms=generation_time,
        )

    except Exception as e:
        logger.error(f"对话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def list_sessions():
    """获取所有会话"""
    return {"sessions": session_store.list()}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """获取指定会话"""
    session = session_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """删除指定会话"""
    if not session_store.delete(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True}


def _extract_content(llm_response: dict) -> str:
    """从 LLM 响应中提取内容"""
    try:
        return llm_response['choices'][0]['message']['content']
    except (KeyError, IndexError, TypeError):
        try:
            return llm_response['choices'][0]['text']
        except (KeyError, IndexError, TypeError):
            return str(llm_response)


def _fallback_response(query: str, results: list) -> str:
    """LLM 失败时的兜底响应（仅罗列知识库原文，不编造）"""
    if not results:
        return "抱歉，暂时无法回答该问题。请尝试更具体地描述，或咨询其他问题。"

    parts = ["根据知识库检索结果，为您提供以下相关信息：\n"]
    for i, r in enumerate(results[:3], 1):
        parts.append(f"\n【{i}】{r['title']}\n{r['snippet']}")

    parts.append("\n\n如需更详细的解答，请继续提问。")
    return "".join(parts)
