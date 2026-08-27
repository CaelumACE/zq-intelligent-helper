"""知识库服务 - RAG 检索"""
import json
import re
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.logger import logger
from app.services.embedding_service import embedding_service
from app.services.vector_store import vector_store
from app.services.rerank_service import rerank_service
from app.services.pg_store import pg_store


# 领域同义词与扩展词表，用于在轻量关键词检索中提升语义召回
SYNONYMS = {
    "企": ["企业", "公司", "单位", "市场主体", "中小微企业"],
    "补贴": ["补助", "扶持", "奖补", "支持资金", "返还", "就业补贴", "社保补贴"],
    "小微": ["中小微企业", "小规模纳税人", "小型微利企业"],
    "社保": ["社会保险", "五险", "养老保险", "医疗保险", "失业保险", "工伤保险", "生育保险"],
    "医保": ["医疗保险", "基本医保", "大病保险", "医保报销"],
    "公积金": ["住房公积金", "住房公积金贷款", "缴存", "提取公积金", "公积金提取", "公积金贷款"],
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

# 纯寒暄/闲聊词：这类输入不应召回知识库，走统一拒答文案
GREETING_WORDS = {
    '你好', '您好', '你好呀', '嗨', '哈喽', '在吗', '在不在', '谢谢', '多谢',
    '早上好', '中午好', '晚上好', '早安', '午安', '晚安', '辛苦了', '再见', '拜拜',
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
    SEMANTIC_WEIGHT = 12.0

    def __init__(self):
        self.documents = []
        self.chunks = []
        self._corpus_embeddings = []
        self._corpus_ready = False
        self._pg_synced = False
        self.alias_entries = []
        self.alias_index = {}
        self.follow_up_patterns = []
        self._load_data()
        self._load_aliases()

    def _load_aliases(self):
        """加载外置别名映射表，供检索前扩展与定向加权使用。"""
        self.alias_entries = []
        self.alias_index = {}
        self.follow_up_patterns = []
        self.dialogue_scenarios = []
        self.refusal_template = {}
        self.response_style_rules = {}
        path = settings.DATA_DIR / 'aliases.json'
        if not path.exists():
            logger.warning("aliases.json 不存在，别名扩展未启用")
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw_all = json.load(f)
            from_pg = pg_store.load_aliases()
            if from_pg is None:
                pg_store.save_aliases(raw_all)
                data = raw_all
            else:
                data = from_pg
            for entry in data.get('aliases', []):
                self.alias_entries.append(entry)
                terms = list(entry.get('aliases', []) or [])
                canonical = entry.get('canonical') or ''
                if canonical and canonical not in terms:
                    terms.append(canonical)
                for term in terms:
                    if term:
                        self.alias_index[term] = entry
            for pattern in (data.get('follow_up_templates') or {}).get('patterns', []):
                if pattern.get('match') and pattern.get('rewrite'):
                    self.follow_up_patterns.append(pattern)
            # 对话场景固定话术：按配置顺序匹配，先 self_intro/capability 再 greeting
            for scenario in (data.get('dialogue_templates') or {}).get('scenarios', []):
                keywords = [str(k).strip().lower() for k in (scenario.get('keywords') or []) if str(k).strip()]
                if scenario.get('intent') and keywords:
                    self.dialogue_scenarios.append({
                        'intent': scenario['intent'],
                        'keywords': keywords,
                        'response': scenario.get('response', ''),
                        'show_chips': bool(scenario.get('show_chips', True)),
                    })
            self.refusal_template = data.get('dialogue_templates', {}).get('refusal_template') or {}
            self.response_style_rules = data.get('dialogue_templates', {}).get('response_style_rules') or {}
            logger.info(f"别名映射加载完成: {len(self.alias_entries)} 组 / {len(self.alias_index)} 条别名 / {len(self.follow_up_patterns)} 条追问模板 / {len(self.dialogue_scenarios)} 个对话场景")
        except Exception as e:
            logger.warning(f"别名映射加载失败: {e}")

    def match_dialogue(self, text: str):
        """匹配对话场景固定话术，返回 (intent, response)。未命中返回 (None, None)。

        优先级：self_intro → capability → farewell → thanks → acknowledge → greeting。
        - farewell/thanks/self_intro/capability 使用包含匹配，覆盖“我走了/拜拜了您”等口语变体
        - acknowledge/greeting 使用整句归一化等于匹配，避免“好的，公积金怎么办”被误判结束语
        """
        if not self.dialogue_scenarios:
            return None, None
        t = (text or '').strip().lower().rstrip("!！?？。.~～")
        if not t:
            return None, None
        t_norm = re.sub(r"[~～!！?？。.,，、\s]+$", "", t)
        t_bare = re.sub(r"^(哈|嘿|呵|嘻|呵|哦|噢|嗯)+$", "", t_norm) or t_norm

        scenarios = {sc['intent']: sc for sc in self.dialogue_scenarios if sc.get('intent')}
        # chat 与 acknowledge 一样，只接受整句归一化等于，避免“办理流程不错”被误判为闲聊
        priority = ('self_intro', 'capability', 'farewell', 'thanks', 'acknowledge', 'chat', 'greeting')
        exact_intents = {'acknowledge', 'chat'}
        for intent in priority:
            scenario = scenarios.get(intent)
            if not scenario:
                continue
            for kw in scenario.get('keywords', []):
                kw = str(kw).strip().lower()
                if not kw:
                    continue
                if intent in exact_intents:
                    if t_bare == kw:
                        return intent, scenario.get('response', '')
                elif intent == 'greeting':
                    # 纯英文词风险高（如 hi 会命中 this），仅整句匹配；
                    # 中文/拼音问候支持复合句包含匹配，覆盖“你好呀我是小弟”
                    if kw.isascii():
                        if t_bare == kw:
                            return intent, scenario.get('response', '')
                    elif kw in t_norm:
                        return intent, scenario.get('response', '')
                else:
                    if kw in t_norm:
                        return intent, scenario.get('response', '')
        return None, None

    def resolve_alias(self, query: str):
        """解析查询命中的别名，返回 (扩展词, 命中信息)。

        扩展词仅包含标准名称与补充同义口语，不含原查询；
        target_ids 为空数组的条目视为“已知但未覆盖”，不强行扩展，由上游引导 12333。
        """
        if not self.alias_index:
            return '', None
        # 精确/最长匹配优先：避免“高龄津贴”（优待证别名）抢先于更具体的“高龄津贴申领”标准名
        matched = sorted(
            ((term, entry) for term, entry in self.alias_index.items() if term in query),
            key=lambda pair: len(pair[0]),
            reverse=True,
        )
        if not matched:
            return '', None
        best_len = len(matched[0][0])
        matched = [(term, entry) for term, entry in matched if len(term) == best_len]

        seen = set()
        unique = []
        for alias, entry in matched:
            key = entry.get('canonical') or alias
            if key not in seen:
                seen.add(key)
                unique.append((alias, entry))

        aliases = list(dict.fromkeys(a for a, _ in matched))
        canonicals = []
        target_ids = []
        for _, entry in unique:
            canonical = entry.get('canonical', '')
            if canonical:
                canonicals.append(canonical)
            target_ids.extend(entry.get('target_ids', []) or [])
        target_ids = list(dict.fromkeys(target_ids))
        uncovered = all((entry.get('target_ids') or []) == [] for _, entry in unique)

        fallback_hints = []
        for _, entry in unique:
            hint = entry.get('fallback_hint') or ''
            if hint:
                fallback_hints.append(hint)

        extra = ''
        if not uncovered:
            extra_terms = list(dict.fromkeys(canonicals + [a for a in aliases if a not in canonicals]))
            extra = ' '.join(extra_terms)

        alias_hit = {
            'aliases': aliases,
            'canonical': canonicals,
            'target_ids': target_ids,
            'fallback_hints': fallback_hints,
            'uncovered': uncovered,
        }
        return extra, alias_hit

    def _load_data(self):
        """加载知识库数据：PG 优先，JSON 作为种子与兜底。"""
        try:
            from_pg = pg_store.load_documents()
            if from_pg:
                self.documents = {
                    'policies': from_pg.get('policies', []),
                    'services': from_pg.get('services', []),
                    'templates': from_pg.get('templates', []),
                    'knowledge': from_pg.get('knowledge', []),
                }
                self._build_chunks()
                logger.info(f"知识库从 PG 加载: {len(self.documents['policies'])} 政策 + {len(self.documents['services'])} 事项 + {len(self.documents['templates'])} 模板 + {len(self.documents['knowledge'])} 公文知识")
                return

            with open(settings.DATA_DIR / '政策知识库.json', 'r', encoding='utf-8') as f:
                policies = json.load(f)

            with open(settings.DATA_DIR / '办事事项.json', 'r', encoding='utf-8') as f:
                services = json.load(f)

            with open(settings.DATA_DIR / '公文模板.json', 'r', encoding='utf-8') as f:
                templates = json.load(f)

            knowledge = []
            knowledge_path = settings.DATA_DIR / '政务知识库.json'
            if knowledge_path.exists():
                with open(knowledge_path, 'r', encoding='utf-8') as f:
                    knowledge = json.load(f)

            self.documents = {
                'policies': policies,
                'services': services,
                'templates': templates,
                'knowledge': knowledge,
            }

            # 首次启动时把 JSON 种子写入 PG，后续读取走 PG
            pg_store.save_documents(self.documents)

            self._build_chunks()
            logger.info(f"知识库加载完成: {len(policies)} 政策 + {len(services)} 事项 + {len(templates)} 模板 + {len(knowledge)} 公文知识")

        except Exception as e:
            logger.error(f"知识库加载失败: {e}")
            self.documents = {'policies': [], 'services': [], 'templates': [], 'knowledge': []}
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
                'context_text': self._build_service_context(item),
                'raw_data': item,
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

        for item in self.documents.get('knowledge', []):
            chunk = {
                'id': item['id'],
                'type': 'knowledge',
                'title': item['title'],
                'category': item.get('category', '公文知识'),
                'summary': item.get('summary', ''),
                'source': item.get('source', '公文知识库'),
                'keywords': item.get('keywords', item.get('summary', '')),
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

    def _build_service_context(self, item: dict) -> str:
        """将办事事项的结构化字段拼成 LLM 可读的完整上下文。"""
        lines = [f"事项名称：{item.get('item_name', '')}"]
        if item.get('description'):
            lines.append(f"事项说明：{item['description']}")
        materials = item.get('required_materials') or []
        if materials:
            lines.append("所需材料：\n" + "\n".join(f"- {m}" for m in materials))
        steps = item.get('steps') or []
        if steps:
            lines.append("办理流程：\n" + "\n".join(steps))
        if item.get('location'):
            lines.append(f"办理地点：{item['location']}")
        if item.get('time_limit'):
            lines.append(f"办理时限：{item['time_limit']}")
        if item.get('fee'):
            lines.append(f"收费标准：{item['fee']}")
        if item.get('consult_phone'):
            lines.append(f"咨询电话：{item['consult_phone']}")
        return "\n".join(lines)

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
            tpl.get('doc_type', ''),
            tpl.get('type_name', ''),
            tpl.get('standard_structure', ''),
            ' '.join(tpl.get('writing_tips', [])),
            ' '.join(str(x.get('element', '')) for x in tpl.get('format_elements', [])),
        ]
        return ' '.join(str(p) for p in parts if p)

    def search(self, query: str, top_k: int = 5, apply_rerank: bool = True) -> List[Dict[str, Any]]:
        """检索知识库（当前为增强关键词检索，后续升级向量语义检索）。

        apply_rerank=False 时返回原始打分候选，供检索测试面板对比重排前后排名。
        """
        results = []
        query_lower = query.lower()
        if self._is_greeting(query_lower):
            return []
        alias_extra, alias_hit = self.resolve_alias(query_lower)
        # 已知但知识库未覆盖的事项：不生成候选，交由上游引导，避免用通用信息胡编
        if alias_hit and alias_hit.get('uncovered'):
            return []
        expanded_query = self._expand_query(query_lower)
        if alias_extra:
            expanded_query = (expanded_query + ' ' + alias_extra).strip()
        category = self._detect_category(query_lower)

        writing_intent = self.is_writing_intent(query_lower)
        query_vec = self._embed_query(query_lower)
        pg_scores = self._vector_scores(query_vec, top_k, query_lower) if query_vec is not None else {}

        for i, chunk in enumerate(self.chunks):
            text = f"{chunk['title']} {chunk['summary']} {chunk.get('keywords', '')} {chunk.get('category', '')}"
            score = self._keyword_score(expanded_query, text)
            score += self._semantic_score(query_vec, i, chunk, pg_scores)
            if category and category in chunk.get('category', ''):
                score += 2.0
            if writing_intent and chunk.get('type') == 'template':
                score += self._template_type_bonus(query_lower, chunk)
            # 非写作意图下，公文模板词频高容易抢占政策问答，予以降权
            if not writing_intent and chunk.get('type') == 'template':
                score -= 4.0
            if alias_hit and chunk['id'] in alias_hit.get('target_ids', []):
                score += 10.0
            score += self._title_bonus(query_lower, chunk['title'])
            if score > 0:
                result = {
                    'id': chunk['id'],
                    'type': chunk['type'],
                    'title': chunk['title'],
                    'category': chunk['category'],
                    'snippet': (chunk.get('context_text') or chunk.get('summary') or '')[:800],
                    'context_text': (chunk.get('context_text') or chunk.get('summary') or '')[:4000],
                    'source': chunk['source'],
                    'score': score,
                }
                if chunk.get('raw_data') is not None:
                    result['raw_data'] = chunk['raw_data']
                results.append(result)

        results.sort(key=lambda x: x['score'], reverse=True)
        if not results:
            return []
        top_score = max(r['score'] for r in results)
        absolute_threshold = self._absolute_threshold(query_lower, top_score)
        min_score = max(absolute_threshold, top_score * 0.35)
        # 先用原始分数过滤，再交给 rerank 排序。
        # 原来的顺序是把 rerank 后分数再拿去算门槛，rerank 会把所有分数抬到 ~100，
        # 导致大量正常简单问题（如“生育保险是什么”）被门槛误杀。
        results = [r for r in results if r['score'] >= min_score]
        if not results:
            return []
        if not apply_rerank:
            return results[:top_k]
        return rerank_service.rerank_sync(query, results)[:top_k]

    async def search_async(self, query: str, top_k: int = 5, apply_rerank: bool = True) -> List[Dict[str, Any]]:
        """search() 的异步版。检索阶段本身是轻型关键词匹配，不需要跑线程池；
        语义向量召回（pgvector）是同步 SQL 调用，放在线程池避免阻塞事件循环。"""
        import asyncio
        query_lower = query.lower()
        if self._is_greeting(query_lower):
            return []
        alias_extra, alias_hit = self.resolve_alias(query_lower)
        if alias_hit and alias_hit.get('uncovered'):
            return []
        expanded_query = self._expand_query(query_lower)
        if alias_extra:
            expanded_query = (expanded_query + ' ' + alias_extra).strip()
        category = self._detect_category(query_lower)
        writing_intent = self.is_writing_intent(query_lower)
        query_vec = await asyncio.to_thread(self._embed_query, query_lower)
        pg_scores = await asyncio.to_thread(self._vector_scores, query_vec, top_k, query_lower) if query_vec is not None else {}

        results = []
        for i, chunk in enumerate(self.chunks):
            text = f"{chunk['title']} {chunk['summary']} {chunk.get('keywords', '')} {chunk.get('category', '')}"
            score = self._keyword_score(expanded_query, text)
            score += self._semantic_score(query_vec, i, chunk, pg_scores)
            if category and category in chunk.get('category', ''):
                score += 2.0
            if writing_intent and chunk.get('type') == 'template':
                score += self._template_type_bonus(query_lower, chunk)
            if not writing_intent and chunk.get('type') == 'template':
                score -= 4.0
            if alias_hit and chunk['id'] in alias_hit.get('target_ids', []):
                score += 10.0
            score += self._title_bonus(query_lower, chunk['title'])
            if score > 0:
                result = {
                    'id': chunk['id'],
                    'type': chunk['type'],
                    'title': chunk['title'],
                    'category': chunk['category'],
                    'snippet': (chunk.get('context_text') or chunk.get('summary') or '')[:800],
                    'context_text': (chunk.get('context_text') or chunk.get('summary') or '')[:4000],
                    'source': chunk['source'],
                    'score': score,
                }
                if chunk.get('raw_data') is not None:
                    result['raw_data'] = chunk['raw_data']
                results.append(result)

        results.sort(key=lambda x: x['score'], reverse=True)
        if not results:
            return []
        top_score = max(r['score'] for r in results)
        absolute_threshold = self._absolute_threshold(query_lower, top_score)
        min_score = max(absolute_threshold, top_score * 0.35)
        results = [r for r in results if r['score'] >= min_score]
        if not results:
            return []
        if not apply_rerank:
            return results[:top_k]
        return (await rerank_service.rerank_async(query, results))[:top_k]

    def _is_greeting(self, query_lower: str) -> bool:
        # 仅保留中英文/数字，去除标点后做精确寒暄判断，避免“你好！”漏判
        clean = re.sub(r'[^0-9a-z\u4e00-\u9fff]+', '', query_lower.strip())
        return clean in GREETING_WORDS or clean.startswith(
            ('hello', 'hi', 'nihao', '早上好', '中午好', '晚上好')
        )

    def _absolute_threshold(self, query_lower: str, top_score: float) -> float:
        """绝对分数门槛，使用原始关键词/向量分数判断。

        语义分数非常低的输入（纯闲聊、无关问题）top_score 只有 0~3 分，
        会自然被这个最低门槛挡掉；启用去标点后的寒暄精确拦截后，
        这里不需要再按“top_score+1”误杀正常简单问题。
        """
        return 5.0

    def _embed_query(self, query: str) -> List[float] | None:
        """查询向量化；失败时返回 None 并按关键词检索降级"""
        try:
            self._ensure_corpus_embeddings()
            return embedding_service.sync_embed_batch([query], 'query')[0]
        except Exception as e:
            logger.warning(f"语义检索不可用，降级为关键词检索: {e}")
            return None

    def _ensure_corpus_embeddings(self):
        """惰性构建语料向量索引（结果缓存到本地）"""
        if self._corpus_ready:
            return
        if not self.chunks:
            self._corpus_ready = True
            return
        try:
            texts = [f"{c['title']} {c['summary']} {c.get('keywords', '')}" for c in self.chunks]
            vectors = embedding_service.sync_embed_batch(texts, 'db')
            if vectors and all(isinstance(v, list) and len(v) > 0 for v in vectors):
                self._corpus_embeddings = vectors
                self._corpus_ready = True
                logger.info(f"语义向量索引构建完成: {len(vectors)} 条")
                self._try_sync_pgvectors()
            else:
                logger.warning("语义向量索引为空，使用关键词检索")
        except Exception as e:
            logger.warning(f"语义向量索引构建失败，使用关键词检索: {e}")

    def _try_sync_pgvectors(self):
        """把内存向量索引同步到 PostgreSQL + pgvector（如启用）。"""
        if self._pg_synced:
            return
        if vector_store.mode != 'postgres' or not self._corpus_ready or not self._corpus_embeddings:
            return
        if vector_store.ensure_ready():
            if vector_store.rebuild_from_corpus(self.chunks, self._corpus_embeddings):
                self._pg_synced = True

    def _vector_scores(self, query_vec, top_k: int, query: str) -> dict:
        """获取 pgvector 的语义召回候选及分数映射。"""
        if vector_store.mode != 'postgres':
            return {}
        try:
            hits = vector_store.search_sync(query_vec, top_k=max(10, top_k * 4))
            return {h.get('id'): float(h.get('semantic_score') or 0.0) for h in (hits or []) if h.get('id')}
        except Exception as exc:
            logger.warning(f"pgvector 检索失败，使用内存向量: {exc}")
            return {}

    def _semantic_score(self, query_vec, index: int, chunk: dict, pg_scores: dict) -> float:
        """优先用 pgvector 分数，回退内存余弦。"""
        chunk_id = chunk.get('id')
        if chunk_id and chunk_id in pg_scores:
            return pg_scores[chunk_id] * self.SEMANTIC_WEIGHT
        if query_vec is not None and self._corpus_ready and index < len(self._corpus_embeddings):
            return embedding_service.cosine(query_vec, self._corpus_embeddings[index]) * self.SEMANTIC_WEIGHT
        return 0.0

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

    # 领域强指令词：命中的类别需要至少在下游分类感知加权，避免政务办事问被公文模板抢走
    _DOMAIN_GUARDS = {
        '社保医保': ['社保', '医保', '公积金', '养老', '医疗', '生育', '工伤', '失业'],
        '民生保障': ['公积金', '租房', '住房', '贷款', '补贴', '补助', '救助'],
    }

    def _detect_category(self, query: str) -> str:
        """粗粒度识别问题所属类别；强领域词可单命中生效。"""
        best = ''
        best_count = 0
        for category, words in CATEGORY_KEYWORDS.items():
            count = sum(1 for w in words if w in query)
            if count > best_count:
                best = category
                best_count = count
        if best:
            return best
        for category, words in self._DOMAIN_GUARDS.items():
            if any(w in query for w in words):
                return category
        return ''

    # 写作动词与常见写作句式
    WRITING_VERBS = {'写', '起草', '拟', '撰写', '生成', '写一份', '写一个', '帮我写', '起个稿'}
    # 知识问答标志词
    QUESTION_MARKERS = {'种类', '类型', '分类', '有几种', '有哪些', '什么叫', '是什么', '定义', '含义', '区别', '依据', '规定', '流程'}

    def is_writing_intent(self, query: str) -> bool:
        """判断是否公文写作意图"""
        return any(w in query for w in self.WRITING_VERBS)

    def is_question_intent(self, query: str) -> bool:
        """判断是否知识问答意图（避免误入写作模板）"""
        return any(w in query for w in self.QUESTION_MARKERS)

    # 明确的公文文种。只有写作动词 + 文种同时出现时，才认定为公文写作意图。
    DOC_TYPE_WORDS = {
        '通知', '报告', '请示', '函', '纪要', '通报', '公告', '决定', '意见',
    }
    # 政务办事/政策问答的强领域词。哪怕出现“写/申请”等词，只要命中这些词，也应优先当政务问题处理。
    DOMAIN_PRIORITY_WORDS = {
        '公积金', '住房公积金', '社保', '医保', '养老', '医疗', '生育', '工伤', '失业',
        '提取', '缴存', '贷款', '额度', '比例', '补缴', '材料', '流程', '办理', '咨询电话',
        '缴费', '补贴', '救助', '居住证', '落户',
    }
    # 后续指令词：这些输入依赖上轮结果，单独做 RAG 检索容易错配到公文知识。
    FOLLOW_UP_PATTERNS = (
        '换一种', '换个', '更正式', '更口语', '更简洁', '再写', '继续', '扩写', '展开',
        '补充', '润色', '改写', '总结一下', '概括', '归纳', '举例子', '举例', '示例',
        '重新写', '再来一版', '另一个版本', '换个说法', '换个方式', '调整', '分段',
        '加标题', '改成', '详细一点', '简单一点', '列出关键', '列出要点', '列要点',
        '要点是什么', '有哪些要点', '梳理',
        '咨询电话', '电话是多少', '热线是多少', '联系方式', '办理窗口', '去哪里办',
        '线上办理', '办理时限', '需要什么材料', '申请条件',
    )

    SMALLTALK_PATTERNS = (
        '咨询个问题', '请教个问题', '请教一下', '我想了解', '我想问',
        '问个事', '打听一下', '了解一下', '说说看',
        '你忙吗', '有人吗', '能问你吗', '可以问吗', '在不在',
    )

    def is_smalltalk_intent(self, query: str) -> bool:
        """判断是否为寒暄/元话语（无实质问题，不检索知识库，走LLM自然回复）。"""
        t = (query or '').strip()
        if not t:
            return True
        # 有明确领域词的不算smalltalk
        if any(w in t for w in self.DOMAIN_PRIORITY_WORDS):
            return False
        # 有办事/申请类动作词的不算
        if any(w in t for w in ('办理', '申领', '申请', '材料', '怎么办', '去哪里', '流程')):
            return False
        # 匹配元话语模式
        if any(p in t for p in self.SMALLTALK_PATTERNS):
            return True
        # 从配置读取额外的smalltalk patterns
        try:
            dt = self.aliases_data.get('dialogue_templates', {}) if hasattr(self, 'aliases_data') else {}
            extra = dt.get('smalltalk_patterns', [])
            if any(p in t for p in extra):
                return True
        except Exception:
            pass
        return False

    def classify_intent(self, query: str) -> str:
        """五分类：writing 写作 / service 办事 / qa 问答 / follow_up 后续指令 / smalltalk 寒暄。"""
        if self.is_follow_up_intent(query):
            return 'follow_up'
        if self.is_smalltalk_intent(query):
            return 'smalltalk'
        has_writing_verb = self.is_writing_intent(query)
        doc_type_count = sum(1 for w in self.DOC_TYPE_WORDS if w in query)
        domain_count = sum(1 for w in self.DOMAIN_PRIORITY_WORDS if w in query)
        # 领域词 > 文种词时，政务问题反向保护，优先走办事/问答。
        if has_writing_verb and doc_type_count >= domain_count and doc_type_count >= 1:
            return 'writing'
        if any(w in query for w in ('办理', '申领', '申请', '需要什么材料', '材料', '怎么办', '去哪里')):
            return 'service'
        if self.is_question_intent(query):
            return 'qa'
        if domain_count:
            return 'service'
        return 'qa'

    def is_follow_up_intent(self, query: str) -> bool:
        return any(p in query for p in self.FOLLOW_UP_PATTERNS)

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

    def rewrite_follow_up(self, follow_text: str, context_query: str):
        """按追问模板把“那医保呢/多久能办下来”等省略式追问改写为完整检索词。

        返回 rewrite（扩展 query）与 matched（命中的模板），未命中返回 (None, None)。
        """
        for pattern in self.follow_up_patterns:
            if any(w in follow_text for w in pattern.get('match', [])):
                rewrite = pattern.get('rewrite', '').replace('{topic}', context_query)
                return rewrite, pattern
        return None, None

    async def search_follow_up_async(self, follow_text: str, context_query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """后续指令检索的异步版：需要改写时并行双路召回，再按分数合并取 top_k。"""
        import asyncio
        rewrite, pattern = self.rewrite_follow_up(follow_text, context_query)
        if not rewrite:
            return await self.search_async(context_query, top_k=top_k)

        # 主问题召回与改写召回并行执行，避免追问题目出现“串行两跳”的额外延迟。
        preferred_task = asyncio.create_task(self.search_async(context_query, top_k=top_k))
        extra_task = asyncio.create_task(self.search_async(rewrite, top_k=max(3, top_k)))
        preferred = await preferred_task
        extra = await extra_task
        if not preferred:
            return extra or await self.search_async(follow_text, top_k=top_k)

        merged_seen = {r['id'] for r in preferred}
        for candidate in extra:
            if candidate['id'] not in merged_seen:
                preferred.append(candidate)
        preferred.sort(key=lambda x: x.get('score', 0.0), reverse=True)
        return preferred[:top_k]

    def search_follow_up(self, follow_text: str, context_query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """后续指令检索：优先复用上一轮主问题召回；模板命中时再补一路改写检索。

        双路召回取并集，这是多路召回/RRF 的轻量雏形，为 P2 铺路。
        """
        preferred = self.search(context_query, top_k=top_k)
        rewrite, pattern = self.rewrite_follow_up(follow_text, context_query)
        if not preferred:
            return self.search(rewrite, top_k=top_k) if rewrite else self.search(follow_text, top_k=top_k)

        merged_seen = {r['id'] for r in preferred}
        if not rewrite:
            return preferred
        # 仅当改写能带来新候选时才融合；改写检索失败则保持原召回，不回归
        extra = self.search(rewrite, top_k=max(3, top_k))
        if not extra:
            return preferred
        for candidate in extra:
            if candidate['id'] not in merged_seen:
                preferred.append(candidate)
        preferred.sort(key=lambda x: x.get('score', 0.0), reverse=True)
        return preferred[:top_k]

    def build_context(self, query: str, top_k: int = 5) -> str:
        results = self.search(query, top_k)
        return self.build_context_from_results(results)

    def build_context_from_results(self, results: List[Dict[str, Any]]) -> str:
        if not results:
            return ""
        context_parts = []
        for i, r in enumerate(results, 1):
            context_parts.append(f"[{i}] {r['title']}（{r['source']}）\n{r['snippet']}")
        return "\n\n".join(context_parts)

    def get_references(self, results: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        return [
            {
                'id': r.get('id'),
                'title': r['title'],
                'source': r['source'],
                'snippet': r['snippet'],
            }
            for r in results
        ]

    def get_service_answer(self, results: List[Dict[str, Any]], query: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """从 service 检索结果还原办事事项的结构化数据，供前端卡片直出。

        只在有足够信号时才返回卡片，避免政策问答（如“退休年龄最新规定”、“医保报销比例对比”）
        因检索结果中混入 service chunk 被误判成办事卡片。判定优先级：
        1. 别名词表命中的目标里，若有 service 候选，优先在其中选（PM 维护的映射可信度高）；
        2. 否则按“完整标题包含 + ngram 重叠 + 检索得分”综合打分选最优 service 候选；
        3. 命中不足以支撑“办事意图”时返回 None，由上游回退通用文本模式。
        """
        if not results:
            return None
        service_results = [r for r in results if r.get('type') == 'service']
        if not service_results:
            return None

        def _match_score(r: Dict[str, Any]) -> tuple:
            """(完整包含, ngram重叠字符数, 检索得分)，标题匹配优先于原始分数。"""
            title = str(r.get('title') or '')
            t = self._clean_query(title)
            contain = 2 if (q and t and (q in t or t in q)) else 0
            overlap = 0
            if q and t:
                for n in (2, 3, 4):
                    sq = {q[i:i + n] for i in range(len(q) - n + 1)} if len(q) >= n else set()
                    st = {t[i:i + n] for i in range(len(t) - n + 1)} if len(t) >= n else set()
                    overlap += len(sq & st)
            return (contain, overlap, float(r.get('score') or 0.0))

        q = self._clean_query(query) if query else ''
        chosen = service_results[0]
        target_ids: set = set()
        has_policy_target = False
        if q:
            alias_extra, alias_hit = self.resolve_alias(query)
            if alias_hit:
                target_ids = set(alias_hit.get('target_ids') or [])
                policy_ids = {d.get('id') for d in self.documents.get('policies', [])}
                has_policy_target = bool(target_ids & policy_ids)
                alias_candidates = [r for r in service_results if r.get('id') in target_ids]
                if alias_candidates:
                    service_results_for_pick = alias_candidates
                else:
                    service_results_for_pick = service_results
            else:
                service_results_for_pick = service_results
            service_results_for_pick = sorted(service_results_for_pick, key=_match_score, reverse=True)
            chosen = service_results_for_pick[0]

        contain, overlap, _ = _match_score(chosen)
        confident = bool(contain)
        if q:
            if not confident and target_ids and chosen.get('id') in target_ids and not has_policy_target:
                # 别名词表只指向办事事项（无政策目标），视为可靠的办事意图
                confident = True
            if not confident and overlap >= 8:
                confident = True
        if not q:
            # 无 query 时保守回退取第一条，理论上仅用于特殊调用；保留原行为
            confident = True
        if not chosen or not confident:
            return None

        item = chosen.get('raw_data')
        if not isinstance(item, dict):
            item_id = chosen.get('id')
            item = next((x for x in self.documents.get('services', []) if x.get('id') == item_id), None)
        if not isinstance(item, dict):
            return None
        materials = item.get('required_materials') or []
        steps = item.get('steps') or []
        return {
            'item_name': item.get('item_name') or None,
            'description': item.get('description') or None,
            'required_materials': [str(m) for m in materials if str(m).strip()],
            'steps': [str(x) for x in steps if str(x).strip()],
            'location': item.get('location') or None,
            'time_limit': item.get('time_limit') or None,
            'fee': item.get('fee') or None,
            'consult_phone': item.get('consult_phone') or None,
        }


knowledge_service = KnowledgeService()
