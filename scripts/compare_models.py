"""双模型同题对比评测

对同一套 RAG 检索上下文，分别调用 MiniMax 与 DeepSeek 生成，
记录 TTFT、总耗时、引用标注数、回答长度，输出 JSON 台账。

用法:
  python scripts/compare_models.py
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))

from app.services.knowledge_service import knowledge_service
from app.services.llm_service import LLMService
from app.core.config import settings

CASES = [
    "中小企业有哪些扶持政策？",
    "办理营业执照需要什么材料？",
    "什么叫决议",
    "社保补贴和稳岗补贴有什么区别？",
    "帮我写一份关于年终总结的通知",
]

SYSTEM_PROMPT = """你是政企智能助手，为政府机关和企事业单位提供专业、准确、合规的服务。
请严格依据提供的参考资料回答，引用要准确、可溯源；资料中没有答案时明确说明，不要编造。"""


async def run_case(provider: str, query: str):
    """对单个 provider 跑一条用例。provider 为 minimax 或 deepseek。"""
    from app.services.llm_service import LLMService  # local import keeps provider config explicit
    svc = LLMService()
    svc.provider = provider
    svc.config = _config_for(provider)

    results = knowledge_service.search(query, top_k=5)
    context = knowledge_service.build_context(query, top_k=5)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if context:
        messages.append({"role": "system", "content": f"参考资料：\n{context}"})
    messages.append({"role": "user", "content": query})

    t0 = time.time()
    first_token_at = None
    content = ""
    try:
        stream_gen = await svc.chat(messages, stream=True)
        async for chunk in stream_gen:
            text = _extract_stream_delta(chunk)
            if not text:
                continue
            if first_token_at is None:
                first_token_at = time.time()
            content += text
    except Exception as e:
        return {
            "provider": provider,
            "query": query,
            "ok": False,
            "error": str(e),
            "ttft_ms": None,
            "total_ms": int((time.time() - t0) * 1000),
            "refs": len(results),
            "char_count": 0,
        }

    # 参考 [1] 标注数量（近似）
    ref_marks = content.count("[1]") + content.count("【1】")
    return {
        "provider": provider,
        "query": query,
        "ok": True,
        "ttft_ms": int((first_token_at - t0) * 1000) if first_token_at else None,
        "total_ms": int((time.time() - t0) * 1000),
        "refs": len(results),
        "ref_marks": ref_marks,
        "char_count": len(content),
        "head": content[:120],
    }


def _extract_stream_delta(chunk: str) -> str:
    """从 SSE 数据块中解析增量文本（MiniMax/DeepSeek 均为 delta.content）"""
    if not chunk:
        return ""
    try:
        data = json.loads(chunk)
    except Exception:
        return ""
    try:
        delta = data['choices'][0]['delta']
        return delta.get('content') or ""
    except (KeyError, IndexError, TypeError):
        return ""


def _config_for(provider: str):
    if provider == "minimax":
        return {
            "api_key": settings.MINIMAX_API_KEY,
            "model": settings.MINIMAX_MODEL,
            "base_url": settings.MINIMAX_BASE_URL,
        }
    return {
        "api_key": settings.DEEPSEEK_API_KEY,
        "model": settings.DEEPSEEK_MODEL,
        "base_url": settings.DEEPSEEK_BASE_URL,
    }


async def main():
    rows = []
    for provider in ("minimax", "deepseek"):
        for query in CASES:
            row = await run_case(provider, query)
            rows.append(row)
            print(f"[{provider}] {query[:24]}... ok={row['ok']} ttft={row['ttft_ms']}ms total={row['total_ms']}ms refs={row['refs']}", flush=True)

    out = Path(__file__).resolve().parent / "model_compare_result.json"
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n结果已写入:", out)


if __name__ == "__main__":
    asyncio.run(main())
