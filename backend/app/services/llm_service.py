"""大模型服务 - 支持 MiniMax 和 DeepSeek，双通道 + 流式"""
import json
from typing import AsyncGenerator, List

import httpx

from app.core.config import settings
from app.core.logger import logger


class LLMService:
    """大模型服务抽象层"""

    def __init__(self, provider: str | None = None):
        self.provider = provider or settings.LLM_PROVIDER
        self.config = self._config_for(self.provider)

    @staticmethod
    def _config_for(provider: str) -> dict:
        if provider == 'minimax':
            return {
                'api_key': settings.MINIMAX_API_KEY,
                'model': settings.MINIMAX_MODEL,
                'base_url': settings.MINIMAX_BASE_URL,
            }
        if provider == 'deepseek':
            return {
                'api_key': settings.DEEPSEEK_API_KEY,
                'model': settings.DEEPSEEK_MODEL,
                'base_url': settings.DEEPSEEK_BASE_URL,
            }
        raise ValueError(f"Unknown provider: {provider}")

    @staticmethod
    def _limits():
        """多 worker 下为每个 AsyncClient 设置保守连接池上限，避免连接数爆炸。"""
        return httpx.Limits(max_connections=20, max_keepalive_connections=10)

    async def chat(self, messages: list, stream: bool = False, provider: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> dict | AsyncGenerator:
        """调用大模型对话接口。provider 可临时覆盖当前实例的 provider。

        temperature / max_tokens 可选项：QA / 办事等低幻觉场景应传低温度，
        公文写作与闲聊可传稍高温度，按意图分档。
        """
        current = provider or self.provider
        config = self._config_for(current)
        if current == 'minimax':
            return await self._call_minimax(messages, stream, config, temperature, max_tokens)
        if current == 'deepseek':
            return await self._call_deepseek(messages, stream, config, temperature, max_tokens)
        raise ValueError(f"Unknown provider: {current}")

    async def _call_minimax(self, messages: list, stream: bool, config: dict, temperature: float | None = None, max_tokens: int | None = None) -> dict | AsyncGenerator:
        url = f"{config['base_url']}/text/chatcompletion_v2"
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config['model'],
            "messages": messages,
            "stream": stream,
            "temperature": 0.7 if temperature is None else max(0.0, min(float(temperature), 2.0)),
            "max_tokens": 2048 if max_tokens is None else int(max_tokens),
        }
        if stream:
            return self._stream_response(url, headers, payload)
        async with httpx.AsyncClient(timeout=120.0, limits=LLMService._limits()) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def _call_deepseek(self, messages: list, stream: bool, config: dict, temperature: float | None = None, max_tokens: int | None = None) -> dict | AsyncGenerator:
        url = f"{config['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config['model'],
            "messages": messages,
            "stream": stream,
            "temperature": 0.7 if temperature is None else max(0.0, min(float(temperature), 2.0)),
            "max_tokens": 2048 if max_tokens is None else int(max_tokens),
        }
        if stream:
            return self._stream_response(url, headers, payload)
        async with httpx.AsyncClient(timeout=120.0, limits=LLMService._limits()) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def _stream_response(self, url: str, headers: dict, payload: dict) -> AsyncGenerator[dict, None]:
        """流式响应：产出 chunk dict {content, finish_reason}。"""
        async with httpx.AsyncClient(timeout=120.0, limits=LLMService._limits()) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    chunk = self._parse_stream_chunk(data)
                    if chunk.get("content") or chunk.get("finish_reason"):
                        yield chunk

    @staticmethod
    def _parse_stream_chunk(data: str) -> dict:
        """解析 SSE 增量，返回 {content, finish_reason}，兼容 MiniMax 与 DeepSeek。"""
        try:
            obj = json.loads(data)
        except Exception:
            return {"content": "", "finish_reason": None}
        try:
            choice = (obj.get("choices") or [{}])[0] or {}
        except Exception:
            return {"content": "", "finish_reason": None}
        delta = choice.get("delta") or {}
        content = delta.get("content") or ""
        finish_reason = choice.get("finish_reason")
        return {"content": content, "finish_reason": finish_reason}

    async def stream_chunks(self, messages: list, provider: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> AsyncGenerator[dict, None]:
        """流式接口：产出 chunk dict {content, finish_reason}，用于需要感知截断等状态的场景。"""
        async for chunk in await self.chat(messages, stream=True, provider=provider, temperature=temperature, max_tokens=max_tokens):
            yield chunk

    async def stream_text(self, messages: list, provider: str | None = None, temperature: float | None = None, max_tokens: int | None = None) -> AsyncGenerator:
        """便捷流式接口：直接产出文本片段（向后兼容）。"""
        async for chunk in await self.chat(messages, stream=True, provider=provider, temperature=temperature, max_tokens=max_tokens):
            content = chunk.get("content") if isinstance(chunk, dict) else chunk
            if content:
                yield content
