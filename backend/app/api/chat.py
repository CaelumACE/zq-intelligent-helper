"""对话 API"""
import json
import re
import time
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models import ChatRequest, ChatResponse, Reference, ChatMessage
from app.services.knowledge_service import knowledge_service
from app.services.llm_service import LLMService
from app.services.session_store import session_store
from app.services.retrieval_log import log_retrieval
from app.core.config import settings
from app.core.logger import logger

router = APIRouter()

llm_service = LLMService()

SYSTEM_PROMPT = """你是政企智能助手，为政府机关和企事业单位提供专业、准确、合规的服务。

你的能力包括：
1. 政策咨询：基于知识库提供政策解读、补贴查询等服务
2. 公文写作：生成通知、报告、纪要等公文
3. 办事指引：提供办事流程、所需材料等信息

回答要求（必须严格遵守）：
1. 只基于给定的参考资料和对话历史回答，引用要准确、可溯源
2. 知识库中没有的内容一律回答「暂无相关信息」或明确说明未收录，严禁臆造、推测、补全或套用其他地区的政策
3. 涉及具体数据（金额/比例/时限/电话/地点）时，必须以参考资料原文为准并标注来源，资料未给出的数字不要自行给出
4. 不确定、不完整或来源缺失时，优先建议用户通过官方渠道（12333/12345或当地政府部门）核实
5. 保持中立客观，不发表未经验证的信息"""

WRITING_PROMPT_EXTRA = """
当前用户需要撰写公文。请严格依据参考资料中的公文格式与写作规范生成，结构完整、用语规范。
如参考资料不足以完成该文种，请说明需要用户补充的信息，不要臆造格式。"""
def _build_writing_message(request: ChatRequest) -> str:
    """把公文写作面板结构化参数还原为完整写作指令。"""
    doc_type = (request.doc_type or "").strip() or "通知"
    title = (request.title or "").strip()
    body = (request.body or "").strip()
    to = (request.to or "").strip()
    sign = (request.sign or "").strip()

    parts = [f"请帮我撰写一份{doc_type}。"]
    if title:
        parts.append(f"标题：{title}")
    if to:
        parts.append(f"主送单位：{to}")
    if body:
        parts.append(f"正文要点：{body}")
    if sign:
        parts.append(f"落款单位/日期：{sign}")
    parts.append("请严格按照公文格式生成，结构完整、用语规范。")
    return "；".join(parts)


QA_PROMPT_EXTRA = """
当前用户正在进行知识问答。请先准确理解问题，再仅依据参考资料作答。
如果是问"种类/类型/定义/区别"等概念性问题，请直接回答概念本身，不要擅自生成一篇公文模板。"""

SERVICE_PROMPT_EXTRA = """
当前用户需要办事指引。请严格依据参考资料逐项列出办理条件、所需材料、办理步骤、地点与时限。
资料中没有明确给出的字段或数字，必须说明「资料未提供」，不得凭常识补全、推测或套用其他地区标准；可引导用户通过 12345/12333 或当地办事窗口核实。"""

FOLLOW_UP_PROMPT_EXTRA = """
当前用户正在对上一轮回答做后续操作（如总结、列要点、改写、补充、咨询电话等）。
请严格基于对话历史中上一轮已回答的内容执行；如果历史中已包含所需信息，直接基于历史回答。
不要把它当作一个全新的无关问题进行检索或作答。"""


GREETING_PATTERNS = {
    "你好", "您好", "hi", "hello", "嗨", "哈喽", "早上好", "下午好", "晚上好", "中午好",
    "早安", "午安", "晚安", "在吗", "在不在", "谢谢", "多谢", "感谢", "辛苦了", "再见", "拜拜",
    "没事了", "没有了", "好的", "嗯", "嗯嗯", "哦", "ok", "okay", "早", "晚上好呀",
}

IDENTITY_PATTERNS = re.compile(
    r"你是谁(呀|啊|呢)?"
    r"|你叫(什么|啥)(名字|称呼)?"
    r"|介绍一下?你自己"
    r"|介绍一下?你"
    r"|你能做(什么|啥)"
    r"|你会(什么|什么功能|做什么|干(什么|啥))"
    r"|你有什么功能"
    r"|有什么功能"
    r"|你的功能(有)?哪些"
    r"|帮我介绍一下?你自己"
    r"|你在(吗|不在)"
    r"|你还在(吗|吧)"
)

def _normalize_input(text: str) -> str:
    t = text.strip().lower().rstrip("!！?？。.~～")
    return re.sub(r"[啊呀哦嘛呢吧哟诶唉啦]+$", "", t)


def _is_greeting(text: str) -> bool:
    t_norm = _normalize_input(text)
    if t_norm in GREETING_PATTERNS:
        return True
    # “你是谁 / 你叫什么名字 / 介绍一下自己 / 你能做什么 / 你会什么”属于打招呼范畴
    if IDENTITY_PATTERNS.fullmatch(t_norm):
        return True
    if len(t_norm) <= 6 and any(g in t_norm for g in ("你好", "您好", "hello", "hi ", "嗨", "你是谁")):
        return True
    return False


CLOSING_KEYWORDS = ("谢谢", "多谢", "感谢", "辛苦了", "麻烦你了", "再见", "拜拜", "没事了", "没有了", "好的", "嗯", "嗯嗯", "哦", "ok", "okay")


def _is_closing(text: str) -> bool:
    t_norm = _normalize_input(text)
    if t_norm in CLOSING_KEYWORDS:
        return True
    # “谢谢你的解答”“感谢提醒”这类口语收尾
    for kw in ("谢谢", "多谢", "感谢", "辛苦了", "麻烦你了", "再见", "拜拜"):
        if t_norm.startswith(kw) and len(t_norm) <= 12:
            return True
    return False


USER_INTRO_PATTERNS = re.compile(
    r"^(我叫|我姓|我的名字)|^(我是(?!说|问|想|要|来|去|查|办|申请|咨询))|^本人"
)


def _is_user_intro(text: str) -> bool:
    t_norm = _normalize_input(text)
    return bool(t_norm) and bool(USER_INTRO_PATTERNS.search(t_norm))


def _is_social(text: str) -> bool:
    return _is_greeting(text) or _is_user_intro(text) or _is_closing(text)


def _greeting_response(text: str) -> str:
    # 结束话术优先，其本质也是 greeting 态，但不渲染服务介绍
    if _is_closing(text):
        return CLOSING_RESPONSE
    if _is_user_intro(text):
        return USER_INTRO_RESPONSE
    return GREETING_RESPONSE


GREETING_RESPONSE = (
    "您好！我是政企智能助手，可以为您提供以下服务：\n\n"
    "📋 **政策咨询** — 社保、公积金、税收、外商投资、数字化转型等政策解读\n"
    "📝 **公文写作** — 通知、报告、纪要、请示、函等公文一键生成\n"
    "🏢 **办事指引** — 营业执照、社保登记、公积金贷款等办事流程\n\n"
    "请问您想了解什么？"
)


CLOSING_RESPONSE = (
    "不客气！很高兴能帮到您。\n\n"
    "如果后续还有政策咨询、公文写作或办事流程方面的问题，随时可以问我。"
)


USER_INTRO_RESPONSE = (
    "您好！很高兴认识你。\n\n"
    "我是政企智能助手，可以为您提供政策咨询、公文写作和办事指引等服务。\n\n"
    "请问有什么可以帮您？"
)


OUT_OF_SCOPE_RESPONSE = (
    "抱歉，这个问题超出了政企智能助手的服务范围。\n\n"
    "我可以为您提供以下服务：\n"
    "1. 政策咨询：政策解读、补贴查询等\n"
    "2. 公文写作：通知、报告、纪要、请示等\n"
    "3. 办事指引：营业执照、社保、税务等办事流程\n"
    "4. 公文知识：公文种类、文种定义与区别等\n\n"
    "请尝试提问与政企服务相关的问题。"
)


def _uncovered_response(topic: str, alias_hit=None) -> str:
    topic = (topic or "").strip() or "该事项"
    if alias_hit and alias_hit.get("fallback_hints"):
        hint = "\n".join(f"- {h}" for h in alias_hit.get("fallback_hints"))
        return (
            f"您咨询的「{topic}」已识别为政务服务事项，但当前知识库暂未收录详细办理信息。\n\n"
            f"{hint}\n\n"
            "如果您想了解其他具体政策或办事流程，也可以换一种问法告诉我。"
        )
    return (
        f"您咨询的「{topic}」已识别为政务服务事项，但当前知识库暂未收录详细办理信息。\n\n"
        "为避免给您错误信息，建议通过官方渠道确认：\n"
        "- 人社/社保业务：拨打 12333\n"
        "- 政府综合服务：拨打 12345\n\n"
        "如果您想了解其他具体政策或办事流程，也可以换一种问法告诉我。"
    )


def _resolve_session_id(request: ChatRequest) -> str:
    session_id = request.session_id
    if not session_id:
        return session_store.create()["id"]
    if session_store.get(session_id):
        return session_id
    # 客户端已提供 sid 但服务端还未建会话：以客户端 sid 落库，
    # 否则后续带同一 sid 的追问会查不到历史，导致追问被当成独立问题。
    try:
        return session_store.create(session_id=session_id)["id"]
    except ValueError:
        # 极小概率并发创建同 sid，直接复用既有会话即可
        return session_id


def _history_messages(request: ChatRequest, session_id: str) -> List[dict]:
    """优先取服务端会话历史，新会话则回退请求携带的 history。"""
    history = session_store.get_history(session_id)
    if history:
        return [m if isinstance(m, dict) else (m.to_dict() if hasattr(m, 'to_dict') else m) for m in history]
    return [m.to_dict() if isinstance(m, ChatMessage) else m for m in (request.history or [])]


def _previous_user_query(request: ChatRequest, session_id: str) -> str:
    """取上一轮真实用户问题，用于后续指令复用原始检索目标。"""
    for msg in reversed(_history_messages(request, session_id)):
        try:
            role = msg.get('role') if isinstance(msg, dict) else getattr(msg, 'role', None)
            content = msg.get('content') if isinstance(msg, dict) else getattr(msg, 'content', '')
        except Exception:
            continue
        if role == 'user' and content and content.strip() != request.message.strip():
            return content
    return request.message


def _build_jsonl_record(session_id: str, raw_query: str, expanded_query: str, intent: str, alias_hit, top_chunks: List[dict], latency_ms: float) -> dict:
    """构造结构化检索日志，仅含检索侧信息。"""
    alias = None
    if alias_hit:
        alias = {
            "aliases": alias_hit.get("aliases"),
            "canonical": alias_hit.get("canonical"),
            "fallback_hint": (alias_hit.get("fallback_hints") or [None])[0],
            "uncovered": bool(alias_hit.get("uncovered")),
        }
    return {
        "timestamp": datetime.now().isoformat(timespec="milliseconds"),
        "session_id": session_id,
        "raw_query": raw_query,
        "expanded_query": expanded_query,
        "intent": intent,
        "alias_hit": alias,
        "top_chunks": [
            {"id": c.get("id"), "score": round(float(c.get("score") or 0.0), 6)}
            for c in (top_chunks or [])
        ],
        "latency_ms": round(float(latency_ms), 2),
    }


def _build_messages(request: ChatRequest, session_id: str, intent: str, context: str):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    user_query = _build_writing_message(request) if intent == "writing" else request.message
    if intent == "writing":
        messages.append({"role": "system", "content": WRITING_PROMPT_EXTRA})
    elif intent == "service":
        messages.append({"role": "system", "content": SERVICE_PROMPT_EXTRA})
    elif intent == "follow_up":
        messages.append({"role": "system", "content": FOLLOW_UP_PROMPT_EXTRA})
    else:
        messages.append({"role": "system", "content": QA_PROMPT_EXTRA})

    if context:
        messages.append({"role": "system", "content": f"参考资料：\n{context}"})

    history = []
    if request.history:
        history = [m.to_dict() if isinstance(m, ChatMessage) else m for m in request.history]
    else:
        history = session_store.get_history(session_id)

    for msg in history[-6:]:
        if isinstance(msg, dict):
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    messages.append({"role": "user", "content": user_query})
    return messages


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """非流式对话接口（RAG 增强 + 会话持久化 + 双通道兜底）"""
    start_time = time.time()

    try:
        session_id = _resolve_session_id(request)

        # 0. 问候/身份询问/结束话术直接回复
        if _is_social(request.message):
            content = _greeting_response(request.message)
            retrieval_time = 0.0
            generation_time = 0.0
            references = []
            session_id = _resolve_session_id(request)
            user_msg = {"role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
            assistant_msg = {"role": "assistant", "content": content, "references": references, "timestamp": int(time.time() * 1000)}
            session_store.add_messages(session_id, [user_msg, assistant_msg])
            return ChatResponse(session_id=session_id, content=content, references=[], retrieval_time_ms=0, generation_time_ms=0)

        is_follow_up = bool(getattr(request, 'follow_up', False)) or knowledge_service.is_follow_up_intent(request.message)
        context_query = _previous_user_query(request, session_id) if is_follow_up else request.message

        # 1. 知识库检索 + 意图识别
        retrieval_start = time.time()
        alias_extra, alias_hit = knowledge_service.resolve_alias(context_query)
        intent = 'follow_up' if is_follow_up else knowledge_service.classify_intent(request.message)
        if is_follow_up:
            search_results = knowledge_service.search_follow_up(request.message, context_query, top_k=5)
            context = knowledge_service.build_context_from_results(search_results)
        else:
            search_results = knowledge_service.search(context_query, top_k=5)
            context = None
        retrieval_time = (time.time() - retrieval_start) * 1000
        log_retrieval(_build_jsonl_record(
            session_id, request.message, alias_extra, intent, alias_hit,
            search_results, retrieval_time,
        ))

        # 2. 无命中拒答
        if not search_results:
            if alias_hit and alias_hit.get('uncovered'):
                content = _uncovered_response(context_query or request.message, alias_hit)
            else:
                content = OUT_OF_SCOPE_RESPONSE
            generation_time = 0.0
            references = []
            logger.info(f"拒答（无知识库命中）: {request.message[:40]}")
        else:
            if context is None:
                context = knowledge_service.build_context(context_query, top_k=5)
            # 公文写作是生成类任务，引用来源不放大模型生成前的检索命中，避免“写作结果挂检索引用”
            references = [] if intent == 'writing' else knowledge_service.get_references(search_results)
            messages = _build_messages(request, session_id, intent, context)

            # 3. 主通道 + 失败时切 DeepSeek 兜底
            generation_start = time.time()
            try:
                llm_response = await llm_service.chat(messages, stream=False)
                content = _extract_content(llm_response)
            except Exception as primary_error:
                logger.warning(f"主通道 LLM 失败，尝试兜底通道: {primary_error}")
                try:
                    llm_response = await llm_service.chat(
                        messages, stream=False,
                        provider=settings.LLM_FALLBACK_PROVIDER,
                    )
                    content = _extract_content(llm_response)
                except Exception as fallback_error:
                    logger.warning(f"兜底通道 LLM 也失败，使用知识库兜底: {fallback_error}")
                    content = _fallback_response(request.message, search_results)
            generation_time = (time.time() - generation_start) * 1000

        # 4. 持久化会话
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


@router.post("/stream")
async def chat_stream(request: ChatRequest):
    """流式对话接口（SSE）：首 token 快速回显，降低体感等待"""
    session_id = _resolve_session_id(request)
    is_greeting = _is_social(request.message)
    is_follow_up = bool(getattr(request, 'follow_up', False)) or knowledge_service.is_follow_up_intent(request.message)
    intent = 'follow_up' if is_follow_up else knowledge_service.classify_intent(request.message)
    retrieval_start = time.time()
    alias_extra, alias_hit = '', None
    if is_follow_up:
        context_query = _previous_user_query(request, session_id)
        search_results = knowledge_service.search_follow_up(request.message, context_query, top_k=5)
    elif is_greeting:
        context_query = request.message
        search_results = []
    else:
        context_query = request.message
        alias_extra, alias_hit = knowledge_service.resolve_alias(request.message)
        search_results = knowledge_service.search(request.message, top_k=5)
    if not alias_extra:
        alias_extra, alias_hit = knowledge_service.resolve_alias(context_query)
    retrieval_time = (time.time() - retrieval_start) * 1000
    log_retrieval(_build_jsonl_record(
        session_id, request.message, alias_extra, intent, alias_hit,
        search_results, retrieval_time,
    ))
    # 公文写作是生成类任务，其检索仅用于取写作模板，不向用户展示引用来源
    references = [] if intent == 'writing' else knowledge_service.get_references(search_results)
    context = knowledge_service.build_context_from_results(search_results) if search_results else ""

    # 元信息一次性下发
    meta = {
        "session_id": session_id,
        "intent": "greeting" if is_greeting else ("follow_up" if is_follow_up else intent),
        "references": references,
        "hit_count": len(search_results),
        "status": "greeting" if is_greeting else ("refusal" if not search_results else "ok"),
    }

    async def event_stream():
        # 先发元信息和开始事件，前端可立即显示会话ID与引用数
        yield f"data: {json.dumps({'type': 'meta', **meta}, ensure_ascii=False)}\n\n"

        if is_greeting:
            greeting_text = _greeting_response(request.message)
            user_msg = {"role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
            assistant_msg = {"role": "assistant", "content": greeting_text, "references": [], "timestamp": int(time.time() * 1000)}
            session_store.add_messages(session_id, [user_msg, assistant_msg])
            yield f"data: {json.dumps({'type': 'delta', 'content': greeting_text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'references': [], 'status': 'greeting'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        if not search_results:
            refuse_text = _uncovered_response(context_query or request.message, alias_hit) if (alias_hit and alias_hit.get('uncovered')) else OUT_OF_SCOPE_RESPONSE
            yield f"data: {json.dumps({'type': 'error', 'message': refuse_text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'references': [], 'status': 'refusal'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            user_msg = {"role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
            assistant_msg = {"role": "assistant", "content": refuse_text, "references": [], "timestamp": int(time.time() * 1000)}
            session_store.add_messages(session_id, [user_msg, assistant_msg])
            return

        messages = _build_messages(request, session_id, intent, context)
        accumulated: List[str] = []
        primary_provider = request.provider or settings.LLM_PROVIDER

        async def stream_provider(provider: str, status: dict):
            """流式输出单个通道的文本增量，结果写入 status['ok']。"""
            try:
                async for delta in await llm_service.chat(messages, stream=True, provider=provider):
                    if delta:
                        accumulated.append(delta)
                        yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                status['ok'] = True
            except Exception as e:
                logger.warning(f"provider={provider} 流式失败: {e}")
                status['ok'] = False

        # 主通道生成；失败或无输出时切换兜底通道
        status = {'ok': False}
        async for event in stream_provider(primary_provider, status):
            yield event

        if primary_provider == settings.LLM_FALLBACK_PROVIDER:
            fallback_candidates = [settings.LLM_PROVIDER]
        else:
            fallback_candidates = [settings.LLM_FALLBACK_PROVIDER]

        for fallback_provider in fallback_candidates:
            if status['ok'] and accumulated:
                break
            accumulated.clear()
            status = {'ok': False}
            async for event in stream_provider(fallback_provider, status):
                yield event

        # 双通道都不可用时，仅罗列知识库原文，不编造
        if not accumulated:
            fallback_text = _fallback_response(request.message, search_results)
            accumulated.append(fallback_text)
            yield f"data: {json.dumps({'type': 'delta', 'content': fallback_text}, ensure_ascii=False)}\n\n"

        full_text = "".join(accumulated)
        user_msg = {"role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
        assistant_msg = {"role": "assistant", "content": full_text, "references": references, "timestamp": int(time.time() * 1000)}
        session_store.add_messages(session_id, [user_msg, assistant_msg])

        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'references': references, 'status': 'ok'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
