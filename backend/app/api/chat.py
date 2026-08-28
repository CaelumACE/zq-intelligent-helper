"""对话 API"""
import json
import re
import time
import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from app.models import ChatRequest, ChatResponse, Reference, ChatMessage, StructuredAnswer
from app.routers.auth import UserOut, current_user
from app.services.knowledge_service import knowledge_service
from app.services.llm_service import LLMService
from app.services.session_store import session_store
from app.services.pg_store import pg_store
from app.services.docx_writer import build_writing_docx
from app.services.graph_store import graph_store
from app.services.retrieval_log import log_retrieval
from app.core.config import settings
from app.core.logger import logger
from urllib.parse import quote

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

def _llm_params_for_intent(intent: str | None) -> dict:
    """按意图分档 LLM 采样参数：政务 QA/办事求低幻觉，公文写作/闲聊允许更自然。"""
    writing_like = intent in ("writing", "writing_revise")
    smalltalk = intent in ("smalltalk", "greeting")
    if smalltalk:
        return {"temperature": 0.7, "max_tokens": 1024}
    if writing_like:
        return {"temperature": 0.5, "max_tokens": 4096}
    return {"temperature": 0.1, "max_tokens": 4096}


WRITING_PROMPT_EXTRA = """
当前用户需要撰写公文。请严格依据参考资料中的公文格式与写作规范生成，结构完整、用语规范。
如参考资料不足以完成该文种，请说明需要用户补充的信息，不要臆造格式。

回复风格与格式要求（来自产品规范）：
{style}

要求：先输出一句“以下为参考草稿，请根据实际情况审核修改后下发。”再按国标公文格式排版（标题居中、主送机关顶格、正文分段、落款和日期右对齐）。"""

WRITING_REVISE_PROMPT_EXTRA = (
    "用户正在对已生成的公文进行修改。请基于以下公文原文，只修改用户要求的部分，"
    "其他内容保持不变。输出完整的修改后公文（按国标公文格式排版：标题居中、"
    "主送机关顶格、正文分段、落款和日期右对齐）。"
)

# 公文修改意图关键词：上一轮为公文写作时，命中即进入 writing_revise 模式
WRITING_REVISE_KEYWORDS = (
    "改", "修改", "加", "补充", "增", "删除", "去掉", "删去", "移除",
    "调整", "语气", "格式", "标题", "正文", "落款", "日期", "主送",
    "加一段", "改成", "换", "缩写", "扩写", "润色", "精简", "完善",
    "加上", "删掉", "改一下", "重新写", "重写",
)

# 明显是全新写作请求的触发词（即使上一轮是公文，也优先当作新写作）
NEW_WRITING_TRIGGERS = ("帮我写", "请写", "撰写一", "生成一", "起草一", "写一份", "写一篇")


def _msg_get(msg, key, default=None):
    if isinstance(msg, dict):
        return msg.get(key, default)
    return getattr(msg, key, default)


def _latest_writing_assistant(session_id: str, user_id=None) -> Optional[dict]:
    """从持久化会话历史中读取最近一条 status=writing 的 assistant 消息。"""
    history = session_store.get_history(session_id, limit=50, user_id=user_id)
    for msg in reversed(history):
        if _msg_get(msg, "role") == "assistant" and _msg_get(msg, "status") == "writing":
            content = _msg_get(msg, "content", "") or ""
            if content.strip():
                mid = _msg_get(msg, "id")
                return {"content": content, "id": mid}
    return None


def _detect_writing_revise(message: str, session_id: str, user_id=None) -> Optional[dict]:
    """判断是否进入公文修改模式。

    条件：会话中最近一条 assistant 消息 status 为 writing，且用户消息不是全新
    写作请求，并包含修改类关键词。命中返回公文原文 dict，否则 None。
    所有上下文均从数据库 session_store 读取，多 worker / 重启安全。
    """
    if not message or not session_id:
        return None
    text = message.strip()
    # 全新写作请求不走修改模式
    if any(t in text for t in NEW_WRITING_TRIGGERS):
        return None
    last_writing = _latest_writing_assistant(session_id, user_id=user_id)
    if not last_writing:
        return None
    if not any(kw in text for kw in WRITING_REVISE_KEYWORDS):
        return None
    return last_writing


def _new_message_id() -> str:
    return uuid.uuid4().hex


def _related_chips(search_results) -> list:
    """从 aliases.json 的 related_chips 配置读取关联推荐问题。

    按检索命中条目的 id/title/canonical 三路兜底匹配，取前 3 条；
    配置缺失时返回空列表（前端回退到基于知识库标题的匹配）。
    """
    matched = []
    alias_entries = knowledge_service.alias_entries or []
    for result in (search_results or [])[:5]:
        result_id = result.get('id')
        result_title = result.get('title')
        for entry in alias_entries:
            target_ids = entry.get('target_ids') or []
            related = entry.get('related_chips') or []
            if not related:
                continue
            canonical = entry.get('canonical') or ''
            aliases = entry.get('aliases') or []
            hits = result_id in target_ids or result_title in (canonical, *aliases) or canonical == result_title
            if hits:
                for chip in related:
                    if chip and chip not in matched:
                        matched.append(chip)
                    if len(matched) >= 3:
                        return matched
    return matched

def _style_section(key: str) -> str:
    """读取 aliases.json response_style_rules 的提示词补充，空配置安全降级。"""
    rules = knowledge_service.response_style_rules or {}
    item = (rules.get(key) or {}).copy()
    lines = []
    # 既支持英文字段名，也兼容纯中文配置键
    for label in ("style", "格式要求", "format", "结构化格式", "multi_turn_prefix",
                  "追问衔接", "reference_display", "引用说明", "disclaimer", "免责声明"):
        value = item.get(label)
        if isinstance(value, str) and value.strip():
            lines.append(value.strip())
    return "\n".join(lines)


_GRAPH_RELEVANT_TYPES = ("service", "department", "process_node", "policy")


def _graph_context_for(query: str, intent: str) -> str:
    """图谱实体关联召回：命中实体后取一层子图作为上下文补充，失败时静默降级为空。

    仅做“补充关系上下文”，不替代检索结果；图谱为空或未命中时返回空串。
    """
    try:
        if not graph_store.stats().get("nodes"):
            return ""
    except Exception:
        return ""
    entity_types = ["service", "department", "process_node"] if intent == "service" else list(_GRAPH_RELEVANT_TYPES)
    candidates = [query]
    try:
        _, alias_hit = knowledge_service.resolve_alias(query)
        if alias_hit and alias_hit.get("canonical"):
            candidates = list(alias_hit["canonical"]) + candidates
    except Exception:
        pass
    roots = []
    for candidate in candidates:
        roots = graph_store.find_node(candidate, entity_types=entity_types)
        if roots:
            break
    subgraph = graph_store.get_subgraph([n["name"] for n in roots[:3]], depth=1)
    if not subgraph.get("nodes"):
        return ""
    lines = []
    seen = set()
    for n in subgraph["nodes"][:12]:
        label = f"[{n['entity_type']}] {n['name']}"
        if label in seen:
            continue
        seen.add(label)
        props = n.get("properties") or {}
        extra = ""
        if n["entity_type"] == "service":
            extra = "；".join(
                f"{k}:{props[k]}"
                for k in ("category", "location", "time_limit", "consult_phone")
                if props.get(k)
            )
        elif n["entity_type"] == "policy":
            doc_no = props.get("document_number") or ""
            summary = props.get("summary") or ""
            extra = f"{doc_no}。{summary}" if doc_no or summary else ""
        if extra:
            lines.append(f"{label}：{extra}")
        else:
            lines.append(label)
    if not lines:
        return ""
    return "【政务知识图谱关联实体】\n" + "\n".join(lines)


def _service_context_text(results) -> str:
    """办事事项类回答附加上下文：优先用结构化 context_text，缺失时回退 snippet。
    用于在 prompt 中明确告诉 LLM「结构化字段是权威来源，逐字段精确作答」。"""
    parts = []
    for r in (results or [])[:5]:
        text = (r.get('context_text') or r.get('snippet') or '')
        if text:
            parts.append(f"[{r.get('title')}]\n{text}")
    return "\n\n".join(parts)

def _build_service_answer(search_results, message: str = "") -> Optional[StructuredAnswer]:
    """构建办事指南卡片结构化数据；非 service 结果或无原始事项时返回 None。"""
    try:
        data = knowledge_service.get_service_answer(search_results, query=message)
        if not data:
            return None
        return StructuredAnswer(**data)
    except Exception as exc:
        logger.warning(f"构建办事结构化答案失败: {exc}")
        return None


def _build_service_llm_messages(request: ChatRequest, session_id: str, structured_answer: Optional[StructuredAnswer], user_id=None):
    """service 意图的短引导语生成：字段全部由卡片直出，LLM 只允许说一句开场白。"""
    from app.models import ChatMessage
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    item_name = (structured_answer.item_name or "").strip() if structured_answer else ""
    if item_name:
        guide_prompt = (
            f"用户正在咨询办事事项「{item_name}」。该事项的材料、流程、地点、时限、费用、电话等字段"
            "已经由系统在前端以办理指南卡片直接展示，用户能看到。"
            "你现在只允许输出一句不超过50字的开场引导语，例如“以下是「" + item_name + "」的办理指南：”。"
            "严禁罗列材料清单、严禁复述办理流程步骤、严禁重新输出任何卡片字段。"
        )
    else:
        guide_prompt = (
            "用户正在咨询一项办事事项。该事项的字段已经由系统在前端卡片直接展示。"
            "你只允许输出一句不超过50字的开场引导语，严禁罗列材料、复述流程或输出卡片字段。"
        )
    messages.append({"role": "system", "content": guide_prompt})
    history = []
    if request.history:
        history = [m.to_dict() if isinstance(m, ChatMessage) else m for m in request.history]
    else:
        history = session_store.get_history(session_id, user_id=user_id)
    for msg in history[-6:]:
        if isinstance(msg, dict):
            messages.append({"role": msg["role"], "content": msg.get("content", "")})
    messages.append({"role": "user", "content": request.message})
    return messages


def _build_writing_message(request: ChatRequest) -> str:
    """把公文写作面板结构化参数还原为完整写作指令。

    两种入口：
    1. 对话栏自然语言（如"帮我写一份国庆放假通知"）：结构化字段为空，
       直接透传用户原始 message，不得丢弃。
    2. 公文写作抽屉面板：doc_type/title/body 等字段有值，按面板参数拼装。
    """
    doc_type = (request.doc_type or "").strip()
    title = (request.title or "").strip()
    body = (request.body or "").strip()
    to = (request.to or "").strip()
    sign = (request.sign or "").strip()

    # 面板字段全部为空 → 对话栏入口，透传用户原始消息
    if not any([doc_type, title, body, to, sign]):
        return request.message

    # 面板入口：按结构化参数拼装
    doc_type = doc_type or "通知"
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
资料中没有明确给出的字段或数字，必须说明「资料未提供」，不得凭常识补全、推测或套用其他地区标准；可引导用户通过 12345/12333 或当地办事窗口核实。

回复风格与结构要求（来自产品规范）：
{style}

请优先采用以下结构化字段顺序呈现（资料未给出的字段直接省略，不得编造）：
📋 办理材料 / 📍 办理地点 / ⏰ 办理时限 / 💰 费用 / 📞 咨询电话 / 📝 办理流程"""

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


USER_INTRO_PATTERNS = re.compile(
    r"^(我叫|我姓|我的名字)|^(我是(?!说|问|想|要|来|去|查|办|申请|咨询))|^本人"
)


def _is_user_intro(text: str) -> bool:
    t_norm = _normalize_input(text)
    return bool(t_norm) and bool(USER_INTRO_PATTERNS.search(t_norm))


def _dialogue_reply(text: str):
    """对话场景固定话术：优先读取产品配置，未配置再使用轻量兜底。

    返回 (intent, response)。命中即短路，不检索、不调LLM、不出chips/引用。
    """
    intent, response = knowledge_service.match_dialogue(text)
    if response:
        return intent, response

    t_norm = _normalize_input(text)
    if _is_user_intro(t_norm):
        return 'self_intro', USER_INTRO_RESPONSE
    if t_norm in GREETING_PATTERNS or _is_greeting(t_norm):
        return 'greeting', GREETING_RESPONSE
    return None, None


GREETING_RESPONSE = (
    "您好！我是政企智能助手，可以为您提供以下服务：\n\n"
    "📋 **政策咨询** — 社保、公积金、税收、外商投资、数字化转型等政策解读\n"
    "📝 **公文写作** — 通知、报告、纪要、请示、函等公文一键生成\n"
    "🏢 **办事指引** — 营业执照、社保登记、公积金贷款等办事流程\n\n"
    "请问您想了解什么？"
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


def _out_of_scope_response() -> str:
    """超范围固定话术：优先读取产品配置 v1.6，缺失时使用内置兜底。"""
    template = (knowledge_service.refusal_template or {}).get('out_of_scope')
    return template or OUT_OF_SCOPE_RESPONSE


def _no_knowledge_response(topic: str, alias_hit=None) -> str:
    """知识库未收录固定话术：优先别名兜底引导，其次读取产品配置 v1.6。"""
    if alias_hit and alias_hit.get('fallback_hints'):
        return _uncovered_response(topic, alias_hit)
    template = (knowledge_service.refusal_template or {}).get('no_knowledge')
    if template:
        return template
    return _uncovered_response(topic, None)


def _resolve_session_id(request: ChatRequest, user_id=None) -> str:
    session_id = request.session_id
    if not session_id:
        return session_store.create(user_id=user_id)["id"]
    existing = session_store.get(session_id)
    if existing and existing.get("user_id") == user_id:
        return session_id
    # 客户端 sid 不存在时才复用客户端 sid 落库；若该 sid 属于其他账号，
    # 不能以原 sid 覆盖写入，否则会造成跨账号会话接管，改为新建会话。
    try:
        return session_store.create(
            session_id=None if existing else session_id,
            user_id=user_id,
        )["id"]
    except ValueError:
        # 极小概率并发创建同 sid，直接复用既有会话即可
        return session_id


def _history_messages(request: ChatRequest, session_id: str, user_id=None) -> List[dict]:
    """优先取服务端会话历史，新会话则回退请求携带的 history。

    安全：服务端只信任 user/assistant 角色，客户端提交的 system 一律丢弃，
    防止注入 system prompt 绕过“严禁臆造”护栏。
    """
    history = session_store.get_history(session_id, user_id=user_id)

    def _to_dict(m):
        d = m if isinstance(m, dict) else (m.to_dict() if hasattr(m, 'to_dict') else m)
        return d if isinstance(d, dict) else {}

    messages = [_to_dict(m) for m in history] if history else [_to_dict(m) for m in (request.history or [])]
    return [m for m in messages if m.get('role') in ('user', 'assistant')]


def _previous_user_query(request: ChatRequest, session_id: str, user_id=None) -> str:
    """取上一轮真实用户问题，用于后续指令复用原始检索目标。"""
    for msg in reversed(_history_messages(request, session_id, user_id=user_id)):
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



SMALLTALK_SYSTEM_PROMPT = (
    "你是政企智能助手。用户当前没有提出具体的政务问题，只是在表达提问意向或进行简短交流。\n"
    "请用简洁、友好、专业的语气回复，自然地引导用户说出具体需求。\n"
    "可以简要提及你能提供的服务范围（政策咨询、公文写作、办事指引）。\n"
    "不要编造具体政策信息，不要回答寒暄和引导之外的内容。\n"
    "回复控制在2句话以内，不要使用emoji，不要分条列举。"
)


def _build_smalltalk_messages(user_message: str, session_history: list = None) -> list:
    """构建smalltalk意图的LLM消息，不检索知识库，纯大模型自然回复。"""
    messages = [{"role": "system", "content": SMALLTALK_SYSTEM_PROMPT}]
    # 带上最近几轮历史让LLM理解上下文
    if session_history:
        for msg in session_history[-4:]:
            if isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
                messages.append({"role": msg["role"], "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_message})
    return messages


def _build_messages(request: ChatRequest, session_id: str, intent: str, context: str, user_id=None, writing_revise_content: str = ""):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    user_query = request.message
    if intent == "writing_revise":
        # 对话式公文修改：把已生成的公文全文作为上下文，要求只改用户要求的部分
        user_query = request.message
        original = (writing_revise_content or "").strip()
        revise_prompt = WRITING_REVISE_PROMPT_EXTRA
        if original:
            revise_prompt += "\n\n【公文原文】\n" + original
        messages.append({"role": "system", "content": revise_prompt})
        style = _style_section("writing_reply")
        if style:
            messages.append({"role": "system", "content": "回复风格与格式要求：\n" + style})
    elif intent == "writing":
        user_query = _build_writing_message(request)
        style = _style_section("writing_reply")
        messages.append({"role": "system", "content": WRITING_PROMPT_EXTRA.format(style=style) if style else WRITING_PROMPT_EXTRA.replace("{style}", "")})
    elif intent == "service":
        style = _style_section("rag_service_reply")
        messages.append({"role": "system", "content": SERVICE_PROMPT_EXTRA.format(style=style) if style else SERVICE_PROMPT_EXTRA.replace("{style}", "")})
    elif intent == "follow_up":
        style = _style_section("rag_service_reply")
        follow_prompt = FOLLOW_UP_PROMPT_EXTRA
        if style:
            follow_prompt += "\n\n回复风格与结构要求：\n" + style
        topic = _previous_user_query(request, session_id, user_id=user_id)
        follow_prompt += "\n\n追问衔接要求：回答开头先确认话题，例如「关于您刚才问的{话题}：」。".format(
            话题=("「%s」" % topic.strip()[:20]) if topic else "上一轮问题")
        messages.append({"role": "system", "content": follow_prompt})
    else:
        messages.append({"role": "system", "content": QA_PROMPT_EXTRA})

    if context:
        messages.append({"role": "system", "content": f"参考资料：\n{context}"})

    history = []
    if request.history:
        history = [m.to_dict() if isinstance(m, ChatMessage) else m for m in request.history]
    else:
        history = session_store.get_history(session_id, user_id=user_id)

    for msg in history[-6:]:
        if isinstance(msg, dict):
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    messages.append({"role": "user", "content": user_query})
    return messages


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest, user: UserOut = Depends(current_user)):
    """非流式对话接口（RAG 增强 + 会话持久化 + 双通道兜底）"""
    start_time = time.time()
    user_id = user.id

    try:
        session_id = _resolve_session_id(request, user_id=user_id)

        # 0. 问候/身份询问/感谢/告别等对话场景直接短路回复
        dialogue_intent, dialogue_reply = _dialogue_reply(request.message)
        if dialogue_reply:
            content = dialogue_reply
            retrieval_time = 0.0
            generation_time = 0.0
            references = []
            user_msg = {"role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
            assistant_msg = {"role": "assistant", "content": content, "references": references, "timestamp": int(time.time() * 1000)}
            session_store.add_messages(session_id, [user_msg, assistant_msg], user_id=user_id)
            return ChatResponse(session_id=session_id, content=content, references=[], retrieval_time_ms=0, generation_time_ms=0)

        # 对话式公文修改：上一轮为公文生成且本轮包含修改指令时，直接进入修改模式
        writing_revise = _detect_writing_revise(request.message, session_id, user_id=user_id)

        is_follow_up = bool(getattr(request, 'follow_up', False)) or knowledge_service.is_follow_up_intent(request.message)
        context_query = _previous_user_query(request, session_id, user_id=user_id) if is_follow_up else request.message

        # 1. 意图识别（smalltalk不检索知识库，直接走LLM）
        intent = 'writing_revise' if writing_revise else ('follow_up' if is_follow_up else knowledge_service.classify_intent(request.message))

        if intent == 'smalltalk':
            history = _history_messages(request, session_id, user_id=user_id)
            smalltalk_msgs = _build_smalltalk_messages(request.message, history)
            generation_start = time.time()
            try:
                llm_response = await llm_service.chat(smalltalk_msgs, stream=False, **_llm_params_for_intent('smalltalk'))
                content = _extract_content(llm_response)
            except Exception as e:
                logger.warning(f"smalltalk LLM失败: {e}")
                content = "您好，请问您想咨询什么问题？我可以为您提供政策咨询、公文写作和办事指引服务。"
            generation_time = (time.time() - generation_start) * 1000
            references = []
            user_msg = {"role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
            assistant_msg = {"role": "assistant", "content": content, "references": [], "timestamp": int(time.time() * 1000)}
            session_store.add_messages(session_id, [user_msg, assistant_msg], user_id=user_id)
            return ChatResponse(
                session_id=session_id, content=content, references=[],
                retrieval_time_ms=0, generation_time_ms=generation_time,
            )

        # 1.5 公文修改：基于已生成公文原文调用 LLM，不做知识库检索
        if writing_revise:
            references = []
            retrieval_time = 0.0
            messages = _build_messages(
                request, session_id, "writing_revise", context="",
                user_id=user_id, writing_revise_content=writing_revise["content"],
            )
            generation_start = time.time()
            try:
                llm_response = await llm_service.chat(messages, stream=False, **_llm_params_for_intent(intent))
                content = _extract_content(llm_response)
            except Exception as primary_error:
                logger.warning(f"公文修改主通道失败，尝试兜底: {primary_error}")
                try:
                    llm_response = await llm_service.chat(
                        messages, stream=False, provider=settings.LLM_FALLBACK_PROVIDER,
                        **_llm_params_for_intent('writing_revise'),
                    )
                    content = _extract_content(llm_response)
                except Exception as fallback_error:
                    logger.warning(f"公文修改兜底也失败: {fallback_error}")
                    content = "抱歉，公文修改失败，请稍后重试。"
            generation_time = (time.time() - generation_start) * 1000
            search_results = []
            user_msg = {"id": _new_message_id(), "role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
            assistant_msg = {"id": _new_message_id(), "role": "assistant", "content": content, "references": [], "timestamp": int(time.time() * 1000), "status": "writing"}
            session_store.add_messages(session_id, [user_msg, assistant_msg], user_id=user_id)
            return ChatResponse(
                session_id=session_id, content=content, references=[],
                retrieval_time_ms=0, generation_time_ms=generation_time,
            )

        # 2. 知识库检索
        retrieval_start = time.time()
        alias_extra, alias_hit = knowledge_service.resolve_alias(context_query)
        if is_follow_up:
            search_results = await knowledge_service.search_follow_up_async(request.message, context_query, top_k=5)
            context = knowledge_service.build_context_from_results(search_results)
        else:
            search_results = await knowledge_service.search_async(context_query, top_k=5)
            context = None
        retrieval_time = (time.time() - retrieval_start) * 1000
        log_retrieval(_build_jsonl_record(
            session_id, request.message, alias_extra, intent, alias_hit,
            search_results, retrieval_time,
        ))

        structured_answer = None

        # 2. 无命中拒答
        if not search_results:
            if alias_hit and alias_hit.get('uncovered'):
                content = _no_knowledge_response(context_query or request.message, alias_hit)
            else:
                content = _out_of_scope_response()
            generation_time = 0.0
            references = []
            logger.info(f"拒答（无知识库命中）: {request.message[:40]}")
        else:
            if context is None:
                if intent == 'service':
                    context = _service_context_text(search_results)
                else:
                    context = knowledge_service.build_context(context_query, top_k=5)
                graph_extra = _graph_context_for(context_query, intent)
                if graph_extra:
                    context = (context + "\n\n" + graph_extra).strip()
            # 公文写作是生成类任务，引用来源不放大模型生成前的检索命中，避免“写作结果挂检索引用”
            references = [] if intent == 'writing' else knowledge_service.get_references(search_results)
            structured_answer = _build_service_answer(search_results, request.message)
            if structured_answer is not None:
                messages = _build_service_llm_messages(request, session_id, structured_answer, user_id=user_id)
            else:
                messages = _build_messages(request, session_id, intent, context, user_id=user_id)

            # 3. 主通道 + 失败时切 DeepSeek 兜底
            generation_start = time.time()
            try:
                llm_response = await llm_service.chat(messages, stream=False, **_llm_params_for_intent(intent))
                content = _extract_content(llm_response)
            except Exception as primary_error:
                logger.warning(f"主通道 LLM 失败，尝试兜底通道: {primary_error}")
                try:
                    llm_response = await llm_service.chat(
                        messages, stream=False,
                        provider=settings.LLM_FALLBACK_PROVIDER,
                        **_llm_params_for_intent(intent),
                    )
                    content = _extract_content(llm_response)
                except Exception as fallback_error:
                    logger.warning(f"兜底通道 LLM 也失败，使用知识库兜底: {fallback_error}")
                    content = _fallback_response(request.message, search_results)
            generation_time = (time.time() - generation_start) * 1000

        # 4. 持久化会话
        user_msg = {"id": _new_message_id(), "role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
        assistant_msg = {"id": _new_message_id(), "role": "assistant", "content": content, "references": references, "timestamp": int(time.time() * 1000)}
        if intent == "writing":
            assistant_msg["status"] = "writing"
        if structured_answer is not None:
            assistant_msg["structured_answer"] = structured_answer.model_dump()
        session_store.add_messages(session_id, [user_msg, assistant_msg], user_id=user_id)

        logger.info(
            f"对话完成: session={session_id[:8]} intent={intent} 检索 {retrieval_time:.0f}ms, "
            f"生成 {generation_time:.0f}ms, 命中 {len(search_results)} 条"
        )

        return ChatResponse(
            session_id=session_id,
            content=content,
            references=[Reference(**ref) for ref in references],
            structured_answer=structured_answer,
            retrieval_time_ms=retrieval_time,
            generation_time_ms=generation_time,
        )

    except Exception as e:
        logger.error(f"对话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(request: ChatRequest, user: UserOut = Depends(current_user)):
    """流式对话接口（SSE）：首 token 快速回显，降低体感等待"""
    user_id = user.id
    session_id = _resolve_session_id(request, user_id=user_id)
    dialogue_intent, dialogue_reply = _dialogue_reply(request.message)
    is_greeting = bool(dialogue_reply)
    # 对话式公文修改：上一轮为公文生成且本轮含修改指令，直接进入修改模式（不检索）
    writing_revise = _detect_writing_revise(request.message, session_id, user_id=user_id)
    is_follow_up = bool(getattr(request, 'follow_up', False)) or knowledge_service.is_follow_up_intent(request.message)
    intent = 'writing_revise' if writing_revise else ('follow_up' if is_follow_up else knowledge_service.classify_intent(request.message))
    is_smalltalk = (intent == 'smalltalk')
    retrieval_start = time.time()
    alias_extra, alias_hit = '', None
    if writing_revise:
        # 公文修改不做知识库检索，直接基于已生成公文原文交给 LLM
        context_query = request.message
        search_results = []
    elif is_smalltalk:
        context_query = request.message
        search_results = []
    elif is_follow_up:
        context_query = _previous_user_query(request, session_id, user_id=user_id)
        search_results = await knowledge_service.search_follow_up_async(request.message, context_query, top_k=5)
    elif is_greeting:
        context_query = request.message
        search_results = []
    else:
        context_query = request.message
        alias_extra, alias_hit = knowledge_service.resolve_alias(request.message)
        search_results = await knowledge_service.search_async(request.message, top_k=5)
    if not alias_extra:
        alias_extra, alias_hit = knowledge_service.resolve_alias(context_query)
    retrieval_time = (time.time() - retrieval_start) * 1000
    log_retrieval(_build_jsonl_record(
        session_id, request.message, alias_extra, intent, alias_hit,
        search_results, retrieval_time,
    ))
    # 公文写作/修改是生成类任务，其检索仅用于取写作模板，不向用户展示引用来源
    references = [] if intent in ('writing', 'writing_revise') else knowledge_service.get_references(search_results)
    if search_results and intent == 'service':
        context = _service_context_text(search_results)
    else:
        context = knowledge_service.build_context_from_results(search_results) if search_results else ""
    graph_extra = _graph_context_for(context_query, intent)
    if graph_extra:
        context = (context + "\n\n" + graph_extra).strip()
    structured_answer = _build_service_answer(search_results, request.message) if search_results else None

    # 元信息一次性下发
    meta = {
        "session_id": session_id,
        "intent": "greeting" if is_greeting else ("follow_up" if is_follow_up else intent),
        "references": references,
        "hit_count": len(search_results),
        "status": "smalltalk" if is_smalltalk else ("greeting" if is_greeting else ("writing" if writing_revise else ("refusal" if not search_results else ("writing" if intent == "writing" else "ok")))),
        "structured_answer": structured_answer.model_dump() if structured_answer else None,
    }
    follow_up_chips = _related_chips(search_results) if (search_results and references) else []

    async def event_stream():
        # 先发元信息和开始事件，前端可立即显示会话ID与引用数
        yield f"data: {json.dumps({'type': 'meta', **meta}, ensure_ascii=False)}\n\n"

        if is_greeting:
            user_msg = {"id": _new_message_id(), "role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
            assistant_msg = {"id": _new_message_id(), "role": "assistant", "content": dialogue_reply, "references": [], "timestamp": int(time.time() * 1000)}
            session_store.add_messages(session_id, [user_msg, assistant_msg], user_id=user_id)
            yield f"data: {json.dumps({'type': 'delta', 'content': dialogue_reply}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'message_id': assistant_msg['id'], 'references': [], 'status': 'greeting'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        if is_smalltalk:
            history = _history_messages(request, session_id, user_id=user_id)
            smalltalk_msgs = _build_smalltalk_messages(request.message, history)
            accumulated_st: List[str] = []
            st_primary = request.provider or settings.LLM_PROVIDER
            st_status = {'ok': False}
            try:
                async for chunk in await llm_service.chat(smalltalk_msgs, stream=True, provider=st_primary, **_llm_params_for_intent('smalltalk')):
                    delta = chunk.get("content") if isinstance(chunk, dict) else chunk
                    if delta:
                        accumulated_st.append(delta)
                        yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                st_status['ok'] = True
            except Exception as e:
                logger.warning(f"smalltalk流式失败({st_primary}): {e}")
            if not st_status['ok'] or not accumulated_st:
                try:
                    fb = settings.LLM_FALLBACK_PROVIDER
                    async for chunk in await llm_service.chat(smalltalk_msgs, stream=True, provider=fb, **_llm_params_for_intent('smalltalk')):
                        delta = chunk.get("content") if isinstance(chunk, dict) else chunk
                        if delta:
                            accumulated_st.append(delta)
                            yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                except Exception as e2:
                    logger.warning(f"smalltalk兜底也失败: {e2}")
            if not accumulated_st:
                fallback_st = "您好，请问您想咨询什么问题？我可以为您提供政策咨询、公文写作和办事指引服务。"
                accumulated_st.append(fallback_st)
                yield f"data: {json.dumps({'type': 'delta', 'content': fallback_st}, ensure_ascii=False)}\n\n"
            full_st = "".join(accumulated_st)
            user_msg = {"id": _new_message_id(), "role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
            assistant_msg = {"id": _new_message_id(), "role": "assistant", "content": full_st, "references": [], "timestamp": int(time.time() * 1000)}
            session_store.add_messages(session_id, [user_msg, assistant_msg], user_id=user_id)
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'message_id': assistant_msg['id'], 'references': [], 'follow_up_chips': [], 'status': 'smalltalk'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 公文修改模式：不依赖检索结果，直接基于已生成公文原文流式生成
        if writing_revise:
            messages = _build_messages(
                request, session_id, "writing_revise", context="",
                user_id=user_id, writing_revise_content=writing_revise["content"],
            )
            accumulated_rev: List[str] = []
            rev_status = {"ok": False}
            rev_truncated = False
            try:
                async for chunk in await llm_service.chat(messages, stream=True, provider=(request.provider or settings.LLM_PROVIDER), **_llm_params_for_intent('writing_revise')):
                    delta = chunk.get("content") if isinstance(chunk, dict) else chunk
                    if delta:
                        accumulated_rev.append(delta)
                        yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                    if isinstance(chunk, dict) and chunk.get("finish_reason") == "length":
                        rev_truncated = True
                rev_status["ok"] = True
            except Exception as e:
                logger.warning(f"公文修改流式失败: {e}")
            if not rev_status["ok"] or not accumulated_rev:
                rev_truncated = False
                try:
                    async for chunk in await llm_service.chat(messages, stream=True, provider=settings.LLM_FALLBACK_PROVIDER, **_llm_params_for_intent('writing_revise')):
                        delta = chunk.get("content") if isinstance(chunk, dict) else chunk
                        if delta:
                            accumulated_rev.append(delta)
                            yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                        if isinstance(chunk, dict) and chunk.get("finish_reason") == "length":
                            rev_truncated = True
                except Exception as e2:
                    logger.warning(f"公文修改兜底流式也失败: {e2}")
            if rev_truncated and accumulated_rev:
                yield f"data: {json.dumps({'type': 'warning', 'code': 'truncated', 'message': '公文内容较长，已被截断。可点击「继续生成」或补充追问获取完整内容。'}, ensure_ascii=False)}\n\n"
            if not accumulated_rev:
                fallback_rev = "抱歉，公文修改失败，请稍后重试。"
                accumulated_rev.append(fallback_rev)
                yield f"data: {json.dumps({'type': 'delta', 'content': fallback_rev}, ensure_ascii=False)}\n\n"
            full_rev = "".join(accumulated_rev)
            user_msg = {"id": _new_message_id(), "role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
            assistant_msg = {"id": _new_message_id(), "role": "assistant", "content": full_rev, "references": [], "timestamp": int(time.time() * 1000), "status": "writing"}
            assistant_message_id = assistant_msg["id"]
            session_store.add_messages(session_id, [user_msg, assistant_msg], user_id=user_id)
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'message_id': assistant_message_id, 'references': [], 'follow_up_chips': [], 'status': 'writing'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        if structured_answer is not None:
            yield f"data: {json.dumps({'type': 'structured_answer', 'data': structured_answer.model_dump()}, ensure_ascii=False)}\n\n"

        if not search_results:
            refuse_text = _no_knowledge_response(context_query or request.message, alias_hit) if (alias_hit and alias_hit.get('uncovered')) else _out_of_scope_response()
            yield f"data: {json.dumps({'type': 'error', 'message': refuse_text}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'references': [], 'status': 'refusal'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            user_msg = {"id": _new_message_id(), "role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
            assistant_msg = {"id": _new_message_id(), "role": "assistant", "content": refuse_text, "references": [], "timestamp": int(time.time() * 1000)}
            session_store.add_messages(session_id, [user_msg, assistant_msg], user_id=user_id)
            return

        if structured_answer is not None:
            messages = _build_service_llm_messages(request, session_id, structured_answer, user_id=user_id)
        else:
            messages = _build_messages(request, session_id, intent, context, user_id=user_id)
        accumulated: List[str] = []
        primary_provider = request.provider or settings.LLM_PROVIDER

        # 主通道流式生成
        stream_ok = False
        truncated = False
        try:
            async for chunk in await llm_service.chat(messages, stream=True, provider=primary_provider, **_llm_params_for_intent(intent)):
                delta = chunk.get("content") if isinstance(chunk, dict) else chunk
                if delta:
                    accumulated.append(delta)
                    yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                if isinstance(chunk, dict) and chunk.get("finish_reason") == "length":
                    truncated = True
            if accumulated:
                stream_ok = True
        except Exception as e:
            logger.warning(f"provider={primary_provider} 流式失败: {e}")

        # 主通道失败或无输出时切换兜底通道
        if not stream_ok:
            truncated = False
            if primary_provider == settings.LLM_FALLBACK_PROVIDER:
                fallback_provider = settings.LLM_PROVIDER
            else:
                fallback_provider = settings.LLM_FALLBACK_PROVIDER
            accumulated.clear()
            try:
                async for chunk in await llm_service.chat(messages, stream=True, provider=fallback_provider, **_llm_params_for_intent(intent)):
                    delta = chunk.get("content") if isinstance(chunk, dict) else chunk
                    if delta:
                        accumulated.append(delta)
                        yield f"data: {json.dumps({'type': 'delta', 'content': delta}, ensure_ascii=False)}\n\n"
                    if isinstance(chunk, dict) and chunk.get("finish_reason") == "length":
                        truncated = True
            except Exception as e2:
                logger.warning(f"fallback provider={fallback_provider} 流式也失败: {e2}")

        # 输出被 max_tokens 截断时，向前端发 warning 事件
        if truncated and accumulated:
            yield f"data: {json.dumps({'type': 'warning', 'code': 'truncated', 'message': '回复内容较长，已被截断。可点击「继续生成」或补充追问获取完整内容。'}, ensure_ascii=False)}\n\n"

        # 双通道都不可用时，仅罗列知识库原文，不编造
        if not accumulated:
            fallback_text = _fallback_response(request.message, search_results)
            accumulated.append(fallback_text)
            yield f"data: {json.dumps({'type': 'delta', 'content': fallback_text}, ensure_ascii=False)}\n\n"

        full_text = "".join(accumulated)
        user_msg = {"id": _new_message_id(), "role": "user", "content": request.message, "timestamp": int(time.time() * 1000)}
        assistant_msg = {"id": _new_message_id(), "role": "assistant", "content": full_text, "references": references, "timestamp": int(time.time() * 1000)}
        if intent == "writing":
            assistant_msg["status"] = "writing"
        if structured_answer is not None:
            assistant_msg["structured_answer"] = structured_answer.model_dump()
        assistant_message_id = assistant_msg["id"]
        session_store.add_messages(session_id, [user_msg, assistant_msg], user_id=user_id)

        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'message_id': assistant_message_id, 'references': references, 'follow_up_chips': follow_up_chips, 'structured_answer': structured_answer.model_dump() if structured_answer else None, 'status': 'writing' if intent == 'writing' else 'ok'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/sessions")
async def list_sessions(user: UserOut = Depends(current_user)):
    """获取当前用户的会话"""
    return {"sessions": session_store.list(user_id=user.id)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: UserOut = Depends(current_user)):
    """获取当前用户指定会话"""
    session = session_store.get(session_id, user_id=user.id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, user: UserOut = Depends(current_user)):
    """删除当前用户指定会话"""
    if not session_store.delete(session_id, user_id=user.id):
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


# ----------------------------------------------------------------------
# T02: 公文 docx 导出 / T04: 满意度反馈
# ----------------------------------------------------------------------

class ExportDocxRequest(BaseModel):
    session_id: Optional[str] = None
    message_id: Optional[str] = None
    content: Optional[str] = None
    title: Optional[str] = None


class FeedbackRequest(BaseModel):
    session_id: str
    message_id: Optional[str] = ""
    rating: str
    comment: Optional[str] = ""


def _safe_docx_filename(title: str) -> str:
    """从公文标题生成安全的下载文件名（去后缀、限长、URL 编码兼容中文）。"""
    name = (title or "公文").strip()
    # 去掉 Markdown 标记与首尾空白/符号
    name = re.sub(r"[#*`>\-]", "", name).strip()
    name = re.sub(r"\s+", "", name)
    if not name:
        name = "公文"
    if len(name) > 60:
        name = name[:60]
    return name


@router.post("/export-docx")
async def export_docx(body: ExportDocxRequest, user: UserOut = Depends(current_user)):
    """将公文内容导出为国标格式 docx。

    支持两种取数方式：
    1. 传 session_id + message_id：从会话存储读取对应 assistant 消息 content
    2. 直接传 content（可选 title）：直接导出传入内容
    """
    content = ""
    title_hint = (body.title or "").strip()

    if body.content and body.content.strip():
        content = body.content
    elif body.session_id and body.message_id:
        # 校验会话归属权
        session = session_store.get(body.session_id, user_id=user.id)
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在或无权访问")
        msg = session_store.get_message(body.session_id, body.message_id, user_id=user.id)
        if not msg:
            raise HTTPException(status_code=404, detail="消息不存在")
        content = msg.get("content", "") or ""
        if not title_hint:
            title_hint = (session.get("title") or "").strip()
    else:
        raise HTTPException(status_code=400, detail="参数错误：需提供 content 或 session_id+message_id")

    if not content.strip():
        raise HTTPException(status_code=400, detail="公文内容为空，无法导出")

    try:
        docx_bytes = build_writing_docx(content, title_hint=title_hint)
    except Exception as e:
        logger.error(f"公文 docx 导出失败: {e}")
        raise HTTPException(status_code=500, detail="导出失败")

    # 文件名：从正文首个 # 标题推断，回退 title_hint，再回退“公文”
    filename_title = title_hint or "公文"
    for line in content.splitlines():
        s = line.strip()
        if s.startswith("#"):
            t = s.lstrip("#").strip()
            if t:
                filename_title = t
                break
    safe_name = _safe_docx_filename(filename_title)
    # RFC 5987 编码：filename 用 ASCII 回退，filename* 承载 UTF-8 中文文件名
    encoded = quote(safe_name)
    ascii_fallback = "document"
    headers = {
        "Content-Disposition": f"attachment; filename=\"{ascii_fallback}.docx\"; filename*=UTF-8''{encoded}.docx"
    }
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


# 满意度反馈挂在 /api 前缀下，对外路径为 /api/feedback
feedback_router = APIRouter()


@feedback_router.post("/feedback")
async def submit_feedback(body: FeedbackRequest, user: UserOut = Depends(current_user)):
    """满意度反馈：点赞/点踩，落库 feedback_logs。"""
    rating = (body.rating or "").strip().lower()
    if rating not in ("up", "down"):
        raise HTTPException(status_code=400, detail="rating 必须为 up 或 down")
    if not body.session_id:
        raise HTTPException(status_code=400, detail="session_id 不能为空")

    # 校验会话归属权：A 用户不能给 B 用户的会话写反馈
    session = session_store.get(body.session_id, user_id=user.id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")

    # 幂等：同一 session_id + message_id + user_id 已有反馈则拒绝重复提交
    if pg_store.has_feedback(
        session_id=body.session_id,
        message_id=body.message_id or "",
        user_id=user.id,
    ):
        raise HTTPException(status_code=409, detail="该内容已提交过反馈，请勿重复提交")

    ok = pg_store.insert_feedback(
        session_id=body.session_id,
        message_id=body.message_id or "",
        rating=rating,
        payload={"comment": (body.comment or ""), "user_id": user.id},
    )
    if not ok:
        # PG 未就绪或写入失败：记录日志但仍返回成功，避免阻断前端交互
        logger.warning("反馈写入 PG 失败（可能 PG 未就绪，已降级）")
    return {"ok": True}
