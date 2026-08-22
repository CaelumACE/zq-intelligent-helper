"""大模型服务 - 支持 MiniMax 和 DeepSeek"""
import httpx
from typing import AsyncGenerator
from app.core.config import settings
from app.core.logger import logger


class LLMService:
    """大模型服务抽象层"""
    
    def __init__(self):
        self.provider = settings.LLM_PROVIDER
        self.config = settings.get_llm_config()
        logger.info(f"LLM Service initialized with provider: {self.provider}")
    
    async def chat(self, messages: list, stream: bool = False) -> dict | AsyncGenerator:
        """
        调用大模型对话接口
        
        Args:
            messages: OpenAI 格式的消息列表
            stream: 是否流式返回
            
        Returns:
            非流式：返回完整响应字典
            流式：返回异步生成器
        """
        if self.provider == 'minimax':
            return await self._call_minimax(messages, stream)
        elif self.provider == 'deepseek':
            return await self._call_deepseek(messages, stream)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")
    
    async def _call_minimax(self, messages: list, stream: bool) -> dict | AsyncGenerator:
        """调用 MiniMax API"""
        url = f"{self.config['base_url']}/text/chatcompletion_v2"
        headers = {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.config['model'],
            "messages": messages,
            "stream": stream,
            "temperature": 0.7,
            "max_tokens": 2048
        }
        
        if stream:
            return self._stream_response(url, headers, payload)
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
    
    async def _call_deepseek(self, messages: list, stream: bool) -> dict | AsyncGenerator:
        """调用 DeepSeek API（OpenAI 兼容格式）"""
        url = f"{self.config['base_url']}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.config['model'],
            "messages": messages,
            "stream": stream,
            "temperature": 0.7,
            "max_tokens": 2048
        }
        
        if stream:
            return self._stream_response(url, headers, payload)
        else:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
    
    async def _stream_response(self, url: str, headers: dict, payload: dict) -> AsyncGenerator:
        """流式响应处理"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data == "[DONE]":
                            break
                        yield data
