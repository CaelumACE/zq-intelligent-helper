"""向量化服务 - MiniMax Embedding + 余弦相似度召回"""
import json
import time
import math
from pathlib import Path
from typing import List

import httpx

from app.core.config import settings
from app.core.logger import logger


class EmbeddingService:
    """MiniMax Embedding 服务（作为无 PG 环境下的语义召回实现）"""

    def __init__(self):
        self.base_url = settings.MINIMAX_BASE_URL
        self.api_key = settings.MINIMAX_API_KEY
        self.model = getattr(settings, 'EMBEDDING_MODEL', 'embo-01')
        self.cache_path = settings.DATA_DIR / 'embeddings_cache.json'
        self._cache = {}
        self._load_cache()

    def _load_cache(self):
        if self.cache_path.exists():
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
                logger.info(f"Embedding 缓存加载完成: {len(self._cache)} 条")
            except Exception as e:
                logger.warning(f"Embedding 缓存加载失败: {e}")
                self._cache = {}

    def _save_cache(self):
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Embedding 缓存保存失败: {e}")

    async def embed_batch(self, texts: List[str], purpose: str = 'db') -> List[List[float]]:
        """批量向量化，优先使用缓存（仅对 db 用途缓存）"""
        uncached_indexes = []
        uncached_texts = []
        results: List[List[float]] = []

        for i, text in enumerate(texts):
            key = self._cache_key(text)
            if purpose == 'db' and key in self._cache:
                results.append(self._cache[key])
            else:
                uncached_indexes.append(i)
                uncached_texts.append(text)
                results.append([])

        if uncached_texts:
            vectors = await self._call_api(uncached_texts, purpose)
            for idx, vec in zip(uncached_indexes, vectors):
                results[idx] = vec
                if purpose == 'db':
                    self._cache[self._cache_key(uncached_texts[uncached_indexes.index(idx)])] = vec
            self._save_cache()

        return results

    async def _call_api(self, texts: List[str], purpose: str) -> List[List[float]]:
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "texts": texts,
            "type": purpose,  # query / db，MiniMax 官方要求
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            if data.get('base_resp', {}).get('status_code') not in (0, None):
                raise ValueError(f"Embedding API 错误: {data.get('base_resp')}")
            return data.get('vectors') or []

    def sync_embed_batch(self, texts: List[str], purpose: str = 'db') -> List[List[float]]:
        """同步批量向量化（用于初始化构建索引）"""
        uncached_indexes = []
        uncached_texts = []
        results: List[List[float]] = []

        for i, text in enumerate(texts):
            key = self._cache_key(text)
            if purpose == 'db' and key in self._cache:
                results.append(self._cache[key])
            else:
                uncached_indexes.append(i)
                uncached_texts.append(text)
                results.append([])

        if uncached_texts:
            vectors = self._call_api_sync(uncached_texts, purpose)
            pos = 0
            for idx in uncached_indexes:
                results[idx] = vectors[pos]
                if purpose == 'db':
                    self._cache[self._cache_key(uncached_texts[pos])] = vectors[pos]
                pos += 1
            self._save_cache()

        return results

    def _call_api_sync(self, texts: List[str], purpose: str) -> List[List[float]]:
        import urllib.request
        url = f"{self.base_url}/embeddings"
        payload = json.dumps({"model": self.model, "texts": texts, "type": purpose}).encode('utf-8')
        req = urllib.request.Request(
            url, data=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        if data.get('base_resp', {}).get('status_code') not in (0, None):
            raise ValueError(f"Embedding API 错误: {data.get('base_resp')}")
        return data.get('vectors') or []

    @staticmethod
    def _cache_key(text: str) -> str:
        import hashlib
        return hashlib.md5(text.encode('utf-8')).hexdigest()

    @staticmethod
    def cosine(a: List[float], b: List[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        if na == 0 or nb == 0:
            return 0.0
        return dot / (na * nb)


embedding_service = EmbeddingService()
