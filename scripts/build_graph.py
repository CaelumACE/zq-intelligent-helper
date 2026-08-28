"""S06-G3：从 JSON 语料构建 Phase1 政务知识图谱（幂等，可重复执行）。

图谱结构见 backend/app/services/graph_store.py：
- policy / service / material / department / process_node 五类实体
- contains / requires / belongs_to / precedes 四类关系
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.graph_store import graph_store  # noqa: E402

DATA = ROOT / "data"


def load_json(name):
    with open(DATA / name, encoding="utf-8") as f:
        return json.load(f)


def clean_name(text):
    return re.sub(r"[\u3000\\s]+", " ", (text or "").strip())


def extract_department(service):
    """从办事事项常见字段中提取部门名，无法可靠时推导为经办部门泛化节点。"""
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


def main():
    policies = load_json("政策知识库.json")
    services = load_json("办事事项.json")
    aliases_data = load_json("aliases.json")

    print("清空旧图谱…", end=" ")
    graph_store.clear_all()
    print("done")

    policy_aliases = {}
    for entry in aliases_data.get("aliases", []):
        canonical = clean_name(entry.get("canonical"))
        for alias in entry.get("aliases", []):
            alias = clean_name(alias)
            if alias:
                policy_aliases[alias] = canonical
        # 单条目别名单
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
        service_props = {
            "item_name": service_name,
            "category": item.get("category", ""),
            "description": item.get("description", ""),
            "location": item.get("location", ""),
            "time_limit": item.get("time_limit", ""),
            "fee": item.get("fee", ""),
            "consult_phone": item.get("consult_phone", ""),
        }
        graph_store.upsert_node(
            "service", service_name, aliases=aliases,
            properties=service_props, source_ref=item.get("id", ""),
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

    # policy -> service contains：数据源没有显式关联时，由小钱人工梳理后维护 mapping 文件。
    # 文件格式：[{"policy": "政策节点名", "service": "事项节点名"}]
    policy_map_path = DATA / "policy_service_map.json"
    if policy_map_path.exists():
        for entry in load_json("policy_service_map.json"):
            policy_node = clean_name(entry.get("policy", ""))
            service_node = clean_name(entry.get("service", ""))
            if policy_node and service_node:
                graph_store.upsert_edge(policy_node, service_node, "contains")
        print(f"  已应用 {policy_map_path.name} 的政策→事项 contains 映射")

    stats = graph_store.stats()
    print(f"构建完成: nodes={stats['nodes']} edges={stats['edges']}")
    return stats


if __name__ == "__main__":
    main()
