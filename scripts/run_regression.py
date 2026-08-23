#!/usr/bin/env python3
"""RAG 回归跑批脚本：基于 data/regression_tests.json 校验检索侧行为。

只校验检索侧（意图、别名、召回 chunk、未覆盖/问候拒答），不调用 LLM，
适合每次代码变更后快速跑，防止修复引入新问题。

用法：
    python3 scripts/run_regression.py          # 全部用例
    python3 scripts/run_regression.py --id 3   # 单条用例
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.services.knowledge_service import knowledge_service  # noqa: E402

TOP_K = 5


def run_case(case: dict) -> tuple[bool, str, list, str, list]:
    qid = case.get("id")
    query = case.get("query", "")
    expected = case.get("expected_chunks") or []
    exp_intent = case.get("intent", "")
    follow_up = bool(case.get("follow_up"))
    context_query = case.get("context_query") or ""

    results: list = []
    got_intent = exp_intent
    note = ""

    if follow_up:
        got_intent = "follow_up"
        results = knowledge_service.search_follow_up(query, context_query, top_k=TOP_K)
    else:
        got_intent = knowledge_service.classify_intent(query)
        if knowledge_service._is_greeting(query.lower()):
            note = "greeting"
            results = []
        else:
            _, alias_hit = knowledge_service.resolve_alias(query.lower())
            if alias_hit and alias_hit.get("uncovered"):
                note = "known-uncovered"
                results = []
            else:
                results = knowledge_service.search(query, top_k=TOP_K)

    hit_ids = [r["id"] for r in results]
    ok = False

    if follow_up:
        # 追问：需命中期望 chunk（复用上轮上下文），特殊：那医保呢会额外召回医保条目
        ok = any(eid in hit_ids for eid in expected) if expected else bool(results)
    elif note == "known-uncovered":
        ok = not expected and not results
    elif note == "greeting":
        ok = not expected and not results
    elif exp_intent == "writing":
        # 公文写作：期望空 chunk，但检索应命中公文模板
        ok = any(r["type"] == "template" for r in results)
    elif expected:
        ok = any(eid in hit_ids for eid in expected)
    else:
        ok = bool(results)

    summary = f"命中 {len(results)} 条：{hit_ids[:TOP_K]}"
    return ok, note, hit_ids, got_intent, summary


def main() -> int:
    parser = argparse.ArgumentParser(description="RAG 回归跑批")
    parser.add_argument("--id", type=int, help="只跑指定用例 id")
    parser.add_argument("--top-k", type=int, default=TOP_K)
    args = parser.parse_args()

    tests = json.loads((ROOT / "data" / "regression_tests.json").read_text(encoding="utf-8"))
    cases = tests.get("test_cases", [])
    if args.id is not None:
        cases = [c for c in cases if c.get("id") == args.id]

    passed = 0
    failed = 0
    intent_mismatch = 0
    print(f"共 {len(cases)} 条用例\n")
    print(f"{'#':>2}  {'结果':<4} {'期望意图':<10} {'实际意图':<10} {'备注':<16} 摘要")
    for case in cases:
        ok, note, hit_ids, got_intent, summary = run_case(case)
        exp_intent = case.get("intent", "")
        if ok:
            passed += 1
        else:
            failed += 1
        intent_flag = ""
        if got_intent != exp_intent:
            intent_mismatch += 1
            intent_flag = " ⚠意图"
        note = note or ("+" if case.get("follow_up") else "")
        print(
            f"{case.get('id'):>2}  {'PASS' if ok else 'FAIL':<4} "
            f"{exp_intent:<10} {got_intent:<10} {note:<16} {summary}{intent_flag}"
        )

    print(f"\n结果：{passed} PASS / {failed} FAIL / {intent_mismatch} 意图标注偏差")
    if failed:
        print("存在 FAIL，请先修复再提交。")
        return 1
    print("全部检索侧用例通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
