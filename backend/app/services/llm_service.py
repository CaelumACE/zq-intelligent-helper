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

    async def chat(self, messages: list, stream: bool = False, provider: str | None = None) -> dict | AsyncGenerator:
        """调用大模型对话接口。provider 可临时覆盖当前实例的 provider。"""
        current = provider or self.provider
        config = self._config_for(current)
        if current == 'minimax':
            return await self._call_minimax(messages, stream, config)
        if current == 'deepseek':
            return await self._call_deepseek(messages, stream, config)
        raise ValueError(f"Unknown provider: {current}")

    async def _call_minimax(self, messages: list, stream: bool, config: dict) -> dict | AsyncGenerator:
        url = f"{config['base_url']}/text/chatcompletion_v2"
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config['model'],
            "messages": messages,
            "stream": stream,
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        if stream:
            return self._stream_response(url, headers, payload)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def _call_deepseek(self, messages: list, stream: bool, config: dict) -> dict | AsyncGenerator:
        url = f"{config['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {config['api_key']}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": config['model'],
            "messages": messages,
            "stream": stream,
            "temperature": 0.7,
            "max_tokens": 2048,
        }
        if stream:
            return self._stream_response(url, headers, payload)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    async def _stream_response(self, url: str, headers: dict, payload: dict) -> AsyncGenerator:
        """流式响应：仅产出增量文本片段。"""
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    delta = self._parse_stream_delta(data)
                    if delta:
                        yield delta

    @staticmethod
    def _parse_stream_delta(data: str) -> str:
        """解析 SSE 增量文本，兼容 MiniMax 与 DeepSeek（delta.content）"""
        try:
            obj = json.loads(data)
        except Exception:
            return ""
        try:
            delta = obj.get("choices", [{}])[0].get("delta") or {}
        except Exception:
            return ""
        return delta.get("content") or ""

    async def stream_text(self, messages: list, provider: str | None = None) -> AsyncGenerator:
        """便捷流式接口：直接产出文本片段"""
        async for delta in await self.chat(messages, stream=True, provider=provider):
            yield delta
