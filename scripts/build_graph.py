"""S06-G3：从 JSON 语料构建 Phase1 政务知识图谱（幂等，可重复执行）。

图谱结构见 backend/app/services/graph_store.py：
- policy / service / material / department / process_node 五类实体
- contains / requires / belongs_to / precedes 四类关系
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.graph_builder import build_graph  # noqa: E402


def main():
    stats = build_graph(reset=True)
    print(f"构建完成: nodes={stats['nodes']} edges={stats['edges']}")
    return stats


if __name__ == "__main__":
    main()
