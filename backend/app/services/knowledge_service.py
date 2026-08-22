"""知识库服务 - RAG 检索"""
import json
import re
from typing import List, Dict, Any
from app.core.config import settings
from app.core.logger import logger


# 领域同义词与扩展词表，用于在轻量关键词检索中提升语义召回
SYNONYMS = {
    "企": ["企业", "公司", "单位", "市场主体", "中小微企业"],
    "补贴": ["补助", "扶持", "奖补", "支持资金", "返还", "就业补贴", "社保补贴"],
    "小微": ["中小微企业", "小规模纳税人", "小型微利企业"],
    "社保": ["社会保险", "养老保险", "医疗保险", "失业保险", "工伤保险", "生育保险"],
    "医保": ["医疗保险", "基本医保", "大病保险", "医保报销"],
    "公积金": ["住房公积金", "缴存", "提取公积金"],
    "执照": ["营业执照", "工商注册", "企业登记", "市场主体登记"],
    "办证": ["办理", "申领", "申请", "登记", "注册"],
    "落户": ["户口", "户口迁移", "迁户"],
    "居住证": ["居住登记", "居住证办理"],
    "报税": ["税务登记", "纳税申报", "缴税"],
    "办税": ["税务", "电子税务局", "纳税"],
    "开店": ["个体工商户", "注册登记", "市场准入"],
    "公文": ["通知", "报告", "纪要", "函", "请示"],
    "通知": ["公文", "红头文件"],
    "总结": ["年终总结", "工作总结", "述职报告", "工作报告"],
    "报告": ["工作报告", "汇报材料", "情况报告"],
    "纪要": ["会议纪要", "会议记录"],
    "请示": ["请示/函", "汇报请示"],
    "函": ["商洽函", "询问函", "答复函"],
    "会议": ["会议纪要", "纪要"],
}

STOPWORDS = {
    '哪些', '什么', '怎么', '如何', '请问', '帮我', '一下', '有没有', '是不是', '为什么',
    '可以', '吗', '呢', '啊', '哦', '请', '能', '要', '想', '需要', '了解', '查询', '知道',
    '的', '了', '我', '你', '它', '与', '和', '或', '及', '对', '在', '为', '关于', '有关',
}

CATEGORY_KEYWORDS = {
    '社保医保': ['社保', '医保', '养老', '医疗', '生育', '工伤', '失业', '保险', '参保', '医保报销'],
    '减税降费': ['税', '减税', '降费', '退税', '税收优惠', '增值税', '所得税', '免税'],
    '就业创业': ['就业', '创业', '招聘', '稳岗', '失业保险', '见习', '岗位'],
    '市场准入': ['市场准入', '登记', '注册', '执照', '个体工商户', '开办', '准入门槛'],
    '营商环境': ['营商环境', '审批', '服务', '便利化', '证照'],
    '民生保障': ['民生', '保障', '救助', '补贴', '补助', '养老', '残疾人'],
    '数字政府': ['数字', '政务', '一网通办', '数据', '电子证照'],
}


class KnowledgeService:
    """知识库检索服务"""

    def __init__(self):
        self.documents = []
        self.chunks = []
        self._load_data()

    def _load_data(self):
        """加载知识库数据"""
        try:
            with open(settings.DATA_DIR / '政策知识库.json', 'r', encoding='utf-8') as f:
                policies = json.load(f)

            with open(settings.DATA_DIR / '办事事项.json', 'r', encoding='utf-8') as f:
                services = json.load(f)

            with open(settings.DATA_DIR / '公文模板.json', 'r', encoding='utf-8') as f:
                templates = json.load(f)

            self.documents = {
                'policies': policies,
                'services': services,
                'templates': templates,
            }

            self._build_chunks()
            logger.info(f"知识库加载完成: {len(policies)} 政策 + {len(services)} 事项 + {len(templates)} 模板")

        except Exception as e:
            logger.error(f"知识库加载失败: {e}")
            self.documents = {'policies': [], 'services': [], 'templates': []}
            self.chunks = []

    def _build_chunks(self):
        """构建文档分块索引"""
        self.chunks = []

        for doc in self.documents['policies']:
            chunk = {
                'id': doc['id'],
                'type': 'policy',
                'title': doc['title'],
                'category': doc.get('category', ''),
                'summary': doc.get('summary', ''),
                'source': doc.get('issuing_authority', ''),
                'keywords': self._extract_policy_keywords(doc),
            }
            self.chunks.append(chunk)

        for item in self.documents['services']:
            chunk = {
                'id': item['id'],
                'type': 'service',
                'title': item['item_name'],
                'category': item.get('category', ''),
                'summary': item.get('description', ''),
                'source': '政务服务',
                'keywords': self._extract_service_keywords(item),
            }
            self.chunks.append(chunk)

        for tpl in self.documents['templates']:
            tips = tpl.get('writing_tips', [])
            if isinstance(tips, list):
                tips = ' '.join(tips)
            chunk = {
                'id': tpl['id'],
                'type': 'template',
                'title': tpl['type_name'],
                'doc_type': tpl.get('doc_type', ''),
                'category': '公文模板',
                'summary': tips,
                'source': '公文规范',
                'keywords': self._extract_template_keywords(tpl),
            }
            self.chunks.append(chunk)

    def _extract_policy_keywords(self, doc: dict) -> str:
        parts = [
            doc.get('title', ''),
            doc.get('category', ''),
            doc.get('issuing_authority', ''),
            doc.get('document_number', ''),
            doc.get('summary', ''),
        ]
        return ' '.join(str(p) for p in parts if p)

    def _extract_service_keywords(self, item: dict) -> str:
        parts = [
            item.get('item_name', ''),
            item.get('category', ''),
            item.get('description', ''),
            ' '.join(item.get('required_materials', [])),
            ' '.join(item.get('steps', [])),
            str(item.get('location', '')),
            str(item.get('time_limit', '')),
        ]
        return ' '.join(str(p) for p in parts if p)

    def _extract_template_keywords(self, tpl: dict) -> str:
        parts = [
            tpl.get('type_name', ''),
            tpl.get('doc_type', ''),
            tpl.get('standard_structure', ''),
            ' '.join(tpl.get('writing_tips', [])),
            ' '.join(str(x.get('element', '')) for x in tpl.get('format_elements', [])),
        ]
        return ' '.join(str(p) for p in parts if p)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """检索知识库（当前为增强关键词检索，后续升级向量语义检索）"""
        results = []
        query_lower = query.lower()
        expanded_query = self._expand_query(query_lower)
        category = self._detect_category(query_lower)

        writing_intent = any(w in query_lower for w in ('写', '起草', '拟', '撰写', '生成', '帮我写'))

        for chunk in self.chunks:
            text = f"{chunk['title']} {chunk['summary']} {chunk.get('keywords', '')}"
            score = self._keyword_score(expanded_query, text.lower())
            if category and category in chunk.get('category', ''):
                score += 2.0
            if writing_intent and chunk.get('type') == 'template':
                score += self._template_type_bonus(query_lower, chunk)
            score += self._title_bonus(query_lower, chunk['title'])
            if score > 0:
                results.append({
                    'id': chunk['id'],
                    'type': chunk['type'],
                    'title': chunk['title'],
                    'category': chunk['category'],
                    'snippet': (chunk['summary'] or '')[:200],
                    'source': chunk['source'],
                    'score': score,
                })

        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    def _expand_query(self, query: str) -> str:
        """基于同义词扩展查询词，提升召回"""
        terms = []
        for key, expansions in SYNONYMS.items():
            if key in query:
                terms.extend(expansions)
        if not terms:
            return query
        terms = list(dict.fromkeys(terms))
        return query + ' ' + ' '.join(terms)

    def _detect_category(self, query: str) -> str:
        """粗粒度识别问题所属类别"""
        best = ''
        best_count = 0
        for category, words in CATEGORY_KEYWORDS.items():
            count = sum(1 for w in words if w in query)
            if count > best_count:
                best = category
                best_count = count
        return best if best_count >= 2 else ''

    def _title_bonus(self, query: str, title: str) -> float:
        clean = self._clean_query(query)
        if not clean:
            return 0.0
        bonus = 0.0
        for n in (4, 3, 2):
            for i in range(len(clean) - n + 1):
                if clean[i:i + n] in title.lower():
                    bonus += 0.8 if n == 2 else (1.2 if n == 3 else 1.6)
        return bonus

    def _template_type_bonus(self, query: str, chunk: dict) -> float:
        """写作意图下按公文文种强加权"""
        doc_type = chunk.get('doc_type', '')
        type_name = chunk.get('title', '')
        bonus = 0.0
        if doc_type and doc_type in query:
            bonus += 8.0
        if type_name and type_name in query:
            bonus += 8.0
        # 同义文种映射
        if '总结' in query and ('报告' in doc_type or '报告' in type_name):
            bonus += 6.0
        if ('纪要' in query or '会议记录' in query) and ('纪要' in doc_type or '纪要' in type_name):
            bonus += 6.0
        if ('函' in query or '商洽' in query) and '函' in doc_type:
            bonus += 6.0
        if '请示' in query and '请示' in doc_type:
            bonus += 6.0
        return bonus

    def _clean_query(self, query: str) -> str:
        clean = re.sub(r'[？?，。！!、：:；;"\'（）()\[\]【】《》\s]', '', query.lower())
        for word in sorted(STOPWORDS, key=len, reverse=True):
            clean = clean.replace(word, '')
        return clean

    def _keyword_score(self, query: str, text: str) -> float:
        """轻量中文关键词匹配打分（字符 n-gram + 关键词命中）"""
        score = 0.0
        clean = self._clean_query(query)

        # 完整命中
        if clean and clean in text:
            score += 5.0

        # 关键词级命中（同义词扩展词）
        for term in self._iter_terms(query):
            if len(term) >= 2 and term in text:
                score += 1.2 if len(term) >= 4 else 0.8

        # 连续 2-4 字 n-gram 匹配
        matched = set()
        for n in range(2, 5):
            for i in range(len(clean) - n + 1):
                gram = clean[i:i + n]
                if gram in matched:
                    continue
                if gram in text:
                    matched.add(gram)
                    weight = 1.0 if n == 2 else (1.5 if n == 3 else 2.0)
                    score += weight

        return score

    def _iter_terms(self, query: str):
        """迭代查询中的关键词片段"""
        parts = re.split(r'\s+', query)
        seen = set()
        for part in parts:
            part = self._clean_query(part)
            if len(part) >= 2 and part not in seen:
                seen.add(part)
                yield part

    def get_all_documents(self) -> Dict[str, List]:
        return self.documents

    def build_context(self, query: str, top_k: int = 5) -> str:
        results = self.search(query, top_k)
        if not results:
            return ""
        context_parts = []
        for i, r in enumerate(results, 1):
            context_parts.append(f"[{i}] {r['title']}（{r['source']}）\n{r['snippet']}")
        return "\n\n".join(context_parts)

    def get_references(self, results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        return [
            {
                'title': r['title'],
                'source': r['source'],
                'snippet': r['snippet'],
            }
            for r in results
        ]


knowledge_service = KnowledgeService()
