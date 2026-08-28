"""S06 图谱数据构建器：从 JSON 语料构建/更新 Phase1 政务知识图谱。

供两处共用：
- scripts/build_graph.py 手动重建
- main lifespan 启动时幂等填充（空图才构建，已存在则跳过）
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.core.logger import logger
from app.services.graph_store import graph_store


def clean_name(text) -> str:
    return re.sub(r"[\u3000\s]+", " ", (text or "").strip())


def extract_department(service: dict) -> Optional[str]:
    """从办事事项常见字段中提取部门名，无法可靠推导时返回 None。"""
    text = " ".join(str(service.get(k, "")) for k in ("location", "description", "consult_phone"))
    for kw, dept in [
        ("社保", "人力资源和社会保障局"),
        ("人社", "人力资源和社会保障局"),
        ("医保", "医疗保障局"),
        ("公安", "公安局"),
        ("税务", "税务局"),
        ("市场监督", "市场监督管理局"),
        ("市场监管", "市场监督管理局"),
        ("公积金", "住房公积金管理中心"),
        ("住房", "住房和城乡建设局"),
        ("不动产", "自然资源和规划局"),
        ("民政", "民政局"),
    ]:
        if kw in text:
            return dept
    return None


def _load_json(data_dir: Path, name: str):
    with open(data_dir / name, encoding="utf-8") as f:
        return json.load(f)


def build_graph(data_dir: Optional[Path] = None, reset: bool = False) -> Dict[str, int]:
    data_dir = Path(data_dir or settings.DATA_DIR)
    if reset:
        graph_store.clear_all()

    policies = _load_json(data_dir, "政策知识库.json")
    services = _load_json(data_dir, "办事事项.json")
    aliases_data = _load_json(data_dir, "aliases.json")

    policy_aliases = {}
    for entry in aliases_data.get("aliases", []):
        canonical = clean_name(entry.get("canonical"))
        for alias in entry.get("aliases", []):
            alias = clean_name(alias)
            if alias:
                policy_aliases[alias] = canonical
        policy_aliases[canonical] = canonical

    # policy 节点
    for item in policies:
        name = clean_name(item.get("title")) or clean_name(item.get("document_number"))
        if not name:
            continue
        graph_store.upsert_node(
            "policy", name,
            aliases=[alias for alias, canonical in policy_aliases.items() if canonical == name][:8],
            properties={
                "document_number": item.get("document_number", ""),
                "issuing_authority": item.get("issuing_authority", ""),
                "publish_date": item.get("publish_date", ""),
                "category": item.get("category", ""),
                "summary": item.get("summary", ""),
            },
            source_ref=item.get("id", ""),
        )

    # service + material + department + process 节点
    for item in services:
        service_name = clean_name(item.get("item_name"))
        if not service_name:
            continue
        aliases = [alias for alias, canonical in policy_aliases.items() if canonical == service_name]
        graph_store.upsert_node(
            "service", service_name, aliases=aliases,
            properties={
                "item_name": service_name,
                "category": item.get("category", ""),
                "description": item.get("description", ""),
                "location": item.get("location", ""),
                "time_limit": item.get("time_limit", ""),
                "fee": item.get("fee", ""),
                "consult_phone": item.get("consult_phone", ""),
            },
            source_ref=item.get("id", ""),
        )

        for mat in item.get("required_materials", []):
            mat = clean_name(mat)
            if not mat:
                continue
            graph_store.upsert_node("material", mat, source_ref=item.get("id", ""))
            graph_store.upsert_edge(service_name, mat, "requires", properties={"source": item.get("id", "")})

        dept = extract_department(item)
        if dept:
            graph_store.upsert_node("department", dept, source_ref=item.get("id", ""))
            graph_store.upsert_edge(service_name, dept, "belongs_to")

        prev_node = None
        for idx, step in enumerate(item.get("steps", [])):
            label = clean_name(step)[:40] or f"{service_name}步骤{idx + 1}"
            graph_store.upsert_node(
                "process_node", label,
                properties={"service": service_name, "step_order": idx + 1},
                source_ref=item.get("id", ""),
            )
            if prev_node:
                graph_store.upsert_edge(prev_node, label, "precedes")
            prev_node = label

    # policy -> service 关联：优先读取人工梳理的映射文件；缺失时不报错，只记录提示。
    policy_map_path = data_dir / "policy_service_map.json"
    if policy_map_path.exists():
        applied = 0
        mapping = _load_json(data_dir, "policy_service_map.json")
        for entry in mapping:
            policy_node = clean_name(entry.get("policy", ""))
            service_node = clean_name(entry.get("service", ""))
            relation = entry.get("relation", "") or "relates_to"
            if relation not in ("relates_to", "contains"):
                relation = "relates_to"
            if policy_node and service_node:
                graph_store.upsert_edge(policy_node, service_node, relation)
                applied += 1
        logger.info(f"已应用 {policy_map_path.name} 的政策→事项映射 {applied} 条")
    else:
        logger.warning("policy_service_map.json 不存在，跳过政策→事项关联")

    return graph_store.stats()


def ensure_populated(data_dir: Optional[Path] = None, reset: bool = False) -> Dict[str, int]:
    """启动时确保图谱非空；已有节点则跳过，避免覆盖运行中数据。"""
    data_dir = Path(data_dir or settings.DATA_DIR)
    if reset:
        return build_graph(data_dir, reset=True)
    stats = graph_store.stats()
    if stats.get("nodes"):
        logger.info(f"图谱已存在，跳过构建: nodes={stats['nodes']} edges={stats['edges']}")
        return stats
    logger.info("图谱为空，开始初始化构建…")
    stats = build_graph(data_dir, reset=False)
    logger.info(f"图谱初始化完成: nodes={stats['nodes']} edges={stats['edges']}")
    return stats
