"""知识库服务 - RAG 检索"""
import json
import hashlib
from typing import List, Dict, Any
from app.core.config import settings
from app.core.logger import logger


class KnowledgeService:
    """知识库检索服务"""
    
    def __init__(self):
        self.documents = []
        self.chunks = []
        self._load_data()
    
    def _load_data(self):
        """加载知识库数据"""
        try:
            # 加载政策文档
            with open(settings.DATA_DIR / '政策知识库.json', 'r', encoding='utf-8') as f:
                policies = json.load(f)
            
            # 加载办事事项
            with open(settings.DATA_DIR / '办事事项.json', 'r', encoding='utf-8') as f:
                services = json.load(f)
            
            # 加载公文模板
            with open(settings.DATA_DIR / '公文模板.json', 'r', encoding='utf-8') as f:
                templates = json.load(f)
            
            self.documents = {
                'policies': policies,
                'services': services,
                'templates': templates,
            }
            
            # 构建 chunk 索引（简单字符串匹配，后续升级为向量检索）
            self._build_chunks()
            logger.info(f"知识库加载完成: {len(policies)} 政策 + {len(services)} 事项 + {len(templates)} 模板")
            
        except Exception as e:
            logger.error(f"知识库加载失败: {e}")
            self.documents = {'policies': [], 'services': [], 'templates': []}
            self.chunks = []
    
    def _build_chunks(self):
        """构建文档分块索引"""
        self.chunks = []
        
        # 政策文档 - 按摘要分块
        for doc in self.documents['policies']:
            chunk = {
                'id': doc['id'],
                'type': 'policy',
                'title': doc['title'],
                'category': doc.get('category', ''),
                'summary': doc.get('summary', ''),
                'source': doc.get('issuing_authority', ''),
            }
            self.chunks.append(chunk)
        
        # 办事事项 - 按描述分块
        for item in self.documents['services']:
            chunk = {
                'id': item['id'],
                'type': 'service',
                'title': item['item_name'],
                'category': item.get('category', ''),
                'summary': item.get('description', ''),
                'source': '政务服务',
            }
            self.chunks.append(chunk)
        
        # 公文模板
        for tpl in self.documents['templates']:
            chunk = {
                'id': tpl['id'],
                'type': 'template',
                'title': tpl['type_name'],
                'category': '公文模板',
                'summary': tpl.get('writing_tips', ''),
                'source': '公文规范',
            }
            self.chunks.append(chunk)
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        检索知识库
        
        当前为简单关键词匹配，后续升级：
        1. Embedding 向量化
        2. 向量相似度检索
        3. Rerank 重排
        """
        results = []
        query_lower = query.lower()
        
        for chunk in self.chunks:
            text = f"{chunk['title']} {chunk['summary']}"
            score = self._keyword_score(query_lower, text.lower())
            if score > 0:
                results.append({
                    'id': chunk['id'],
                    'type': chunk['type'],
                    'title': chunk['title'],
                    'category': chunk['category'],
                    'snippet': chunk['summary'][:200],
                    'source': chunk['source'],
                    'score': score,
                })
        
        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]
    
    def _keyword_score(self, query: str, text: str) -> float:
        """简单关键词匹配打分"""
        score = 0.0
        
        # 完整匹配
        if query in text:
            score += 3.0
        
        # 分词匹配（简单处理）
        keywords = [k for k in query.replace('，', ' ').replace('、', ' ').split() if len(k) >= 2]
        for kw in keywords:
            if kw in text:
                score += 1.0
        
        return score
    
    def get_all_documents(self) -> Dict[str, List]:
        """获取所有文档"""
        return self.documents
    
    def build_context(self, query: str, top_k: int = 5) -> str:
        """构建 RAG 上下文"""
        results = self.search(query, top_k)
        
        if not results:
            return ""
        
        context_parts = []
        for i, r in enumerate(results, 1):
            context_parts.append(f"[{i}] {r['title']}（{r['source']}）\n{r['snippet']}")
        
        return "\n\n".join(context_parts)
    
    def get_references(self, results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """转换为引用格式"""
        return [
            {
                'title': r['title'],
                'source': r['source'],
                'snippet': r['snippet'],
            }
            for r in results
        ]


knowledge_service = KnowledgeService()
