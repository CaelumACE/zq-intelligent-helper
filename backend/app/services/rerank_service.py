"""RAG Rerank 服务

目标：降低关键词/向量召回后的模板抢占与标题噪声，提高 top_k 精度。

内置两种后端：
1. offline：不依赖外部 API，用标题 n-gram + RRF 思想对已有候选重排。
2. api：RERANK_PROVIDER=xxx 时调用兼容 OpenAI 风格的 /rerank 接口；
   未配置 API Key 或服务不可用时自动回退 offline，保证请求不阻塞。

说明：正式 Rerank 模型通常需要 GPU/大量内存，沙盒环境不安装 sentence-transformers，
     正式 VPS 部署时通过环境变量切换 API 地址即可平滑启用。
"""
import re
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.core.logger import logger
import httpx

OFFLINE_STOPWORDS = {
    "哪些", "什么", "怎么", "如何", "请问", "帮我", "一下", "有没有", "是不是", "为什么",
    "可以", "吗", "呢", "啊", "哦", "请", "能", "要", "想", "需要", "办理", "申请",
}


class RerankService:
    """检索后重排；每条候选需要包含 id/title/snippet/score。"""

    def __init__(self):
        self.provider = (settings.RERANK_PROVIDER or "offline").strip().lower()

    @property
    def configured_api(self) -> bool:
        if self.provider in ("", "offline", "none"):
            return False
        return bool(settings.RERANK_BASE_URL and settings.RERANK_API_KEY)

    def rerank_sync(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not candidates:
            return []
        if self.configured_api:
            try:
                return self._rerank_api(query, candidates)
            except Exception as exc:
                logger.warning(f"Rerank API 调用失败，切换离线重排: {exc}")
        return self._rerank_offline(query, candidates)

    async def rerank_async(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not candidates:
            return []
        if not self.configured_api:
            return self._rerank_offline(query, candidates)
        try:
            return await self._rerank_api_async(query, candidates)
        except Exception as exc:
            logger.warning(f"Rerank API 调用失败，切换离线重排: {exc}")
            return self._rerank_offline(query, candidates)

    def _rerank_api(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        url = settings.RERANK_BASE_URL.rstrip("/") + "/rerank"
        payload = {
            "model": settings.RERANK_MODEL,
            "query": query,
            "documents": [self._candidate_text(c) for c in candidates],
            "top_n": len(candidates),
        }
        headers = {
            "Authorization": f"Bearer {settings.RERANK_API_KEY}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=20.0) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return self._apply_api_order(candidates, data)

    async def _rerank_api_async(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        url = settings.RERANK_BASE_URL.rstrip("/") + "/rerank"
        payload = {
            "model": settings.RERANK_MODEL,
            "query": query,
            "documents": [self._candidate_text(c) for c in candidates],
            "top_n": len(candidates),
        }
        headers = {
            "Authorization": f"Bearer {settings.RERANK_API_KEY}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
        return self._apply_api_order(candidates, data)

    def _rerank_offline(self, query: str, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """离线重排：语义特征 + 原始模型分数归一化。"""
        clean = self._clean(query)

        def final_score(item: Dict[str, Any], index: int) -> float:
            text = self._candidate_text(item)
            feature = 0.0
            if clean and clean in text:
                feature += 5.0
            for gram in self._grams(clean, n=3):
                if gram in text:
                    feature += 1.4
            if clean and clean[: min(12, len(clean))] in item.get("title", ""):
                feature += 3.0
            original = float(item.get("score") or 0.0)
            # 排序位置作为微弱先验，避免模型分数相近时不稳定。
            original_norm = 100.0 * (1.0 / (1.0 + index * 0.06))
            return original + feature + original_norm

        scored = []
        for index, item in enumerate(candidates):
            value = final_score(item, index)
            scored.append((value, index, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        ordered = []
        for rank, (value, index, item) in enumerate(scored, 1):
            reranked = item.copy()
            reranked["rerank_score"] = round(value, 6)
            reranked["rerank_rank"] = rank
            reranked["score"] = value
            ordered.append(reranked)
        return ordered

    def _apply_api_order(self, candidates: List[Dict[str, Any]], data: dict) -> List[Dict[str, Any]]:
        results = data.get("results") or data.get("data") or []
        order_map: Dict[int, float] = {}
        for item in results:
            idx = item.get("index")
            if idx is None and isinstance(item.get("document"), dict):
                index = item["document"].get("index")
                if index is not None:
                    idx = index
            if idx is None:
                continue
            if "relevance_score" in item:
                score = item["relevance_score"]
            elif "score" in item:
                score = item["score"]
            else:
                score = 1.0
            order_map[int(idx)] = float(score)
        if not order_map:
            return candidates
        ordered = sorted(range(len(candidates)), key=lambda i: order_map.get(i, -1.0), reverse=True)
        return [candidates[i] for i in ordered]

    @staticmethod
    def _candidate_text(item: Dict[str, Any]) -> str:
        return f"{item.get('title', '')} {item.get('snippet', '')} {item.get('source', '')}".lower()

    @staticmethod
    def _clean(query: str) -> str:
        clean = re.sub(r"[？?，。！!、：:；;\"'（）()\[\]【】《》\s]", "", query.lower())
        for word in sorted(OFFLINE_STOPWORDS, key=len, reverse=True):
            clean = clean.replace(word, "")
        return clean

    @staticmethod
    def _grams(clean: str, n: int):
        if len(clean) < n:
            return []
        return {clean[i : i + n] for i in range(len(clean) - n + 1)}


rerank_service = RerankService()
