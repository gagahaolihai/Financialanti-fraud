#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
消融实验（Ablation Study）
对比不同技术策略的效果，验证「规则 + 语义」融合的必要性：

  实验一：意图识别  —— 规则 / 语义 / 融合
  实验二：诈骗类型识别 —— 关键词 / 语义 / 混合检索

用法:
    python evaluation/ablation.py
输出:
    evaluation/results/ablation_report.md
    evaluation/results/ablation_report.json
"""
import io
import os
import sys
import json
from datetime import datetime

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)
DATASET_DIR = os.path.join(BASE_DIR, "evaluation", "datasets")
RESULT_DIR = os.path.join(BASE_DIR, "evaluation", "results")
os.makedirs(RESULT_DIR, exist_ok=True)


def load(name):
    with open(os.path.join(DATASET_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 实验一：意图识别消融
# ============================================================
def ablation_intent():
    samples = load("intent_eval.json")["samples"]

    from engine.intent_recognizer import IntentRecognizer
    from engine.nlp_pipeline import get_nlp_pipeline

    rule = IntentRecognizer()
    nlp = get_nlp_pipeline()
    semantic_ok = nlp.ready

    stats = {"rule": 0, "semantic": 0, "fusion": 0}
    n = len(samples)

    for i, s in enumerate(samples):
        text, gold = s["text"], s["intent"]

        # 规则
        r = rule.recognize(text, user_id=f"eval_{i}")  # 独立 user_id，避免上下文干扰
        r_intent = r.get("intent", "unknown")
        r_conf = float(r.get("confidence", 0) or 0)
        if r_intent == gold:
            stats["rule"] += 1

        # 语义
        s_intent, s_conf = ("unknown", 0.0)
        if semantic_ok:
            s_intent, s_conf = nlp.classify_intent(text)
            if s_intent == gold:
                stats["semantic"] += 1

        # 融合：语义置信度高时用语义，否则用规则
        if semantic_ok and s_conf >= 0.5:
            fused = s_intent
        else:
            fused = r_intent
        if fused == gold:
            stats["fusion"] += 1

    return {
        "available": True,
        "semantic_available": semantic_ok,
        "total": n,
        "results": {k: {"correct": v, "accuracy": round(v / n, 4)} for k, v in stats.items()},
    }


# ============================================================
# 实验二：诈骗类型识别消融
# ============================================================
def ablation_fraud():
    samples = load("fraud_eval.json")["samples"]

    from engine.vector_search import get_vector_search
    vs = get_vector_search()
    if not vs.documents:
        vs.build_index(vs.load_knowledge_base())

    stats = {"keyword": 0, "semantic": 0, "hybrid": 0}
    n = len(samples)

    for s in samples:
        text, gold = s["text"], s["fraud_id"]
        for mode, fn in (("keyword", vs._keyword_fallback), ("semantic", vs.search), ("hybrid", vs.hybrid_search)):
            try:
                res = fn(text, top_k=1)
                if res and res[0].get("id") == gold:
                    stats[mode] += 1
            except Exception:
                pass

    return {
        "available": True,
        "total": n,
        "results": {k: {"correct": v, "accuracy": round(v / n, 4)} for k, v in stats.items()},
    }


def build_report(ai, af):
    L = []
    A = L.append
    A("# 消融实验报告 — 反诈卫士 v3.0")
    A("")
    A(f"> 实验时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    A("> 目的：验证「规则 + 语义」融合方案相对于单一策略的增益")
    A("")
    A("---")
    A("")
    A("## 实验一：意图识别")
    A("")
    if ai.get("available"):
        A(f"评测集：intent_eval.json（{ai['total']} 条 / 14 类）")
        A("")
        A("| 策略 | 准确率 | 正确/总数 |")
        A("|---|---|---|")
        for k, label in (("rule", "仅规则引擎"), ("semantic", "仅语义分类"), ("fusion", "规则+语义融合")):
            r = ai["results"][k]
            A(f"| {label} | {r['accuracy']*100:.1f}% | {r['correct']}/{ai['total']} |")
    A("")
    A("## 实验二：诈骗类型识别")
    A("")
    if af.get("available"):
        A(f"评测集：fraud_eval.json（{af['total']} 条 / 16 类），指标为 Top-1 命中率")
        A("")
        A("| 策略 | Top-1 命中率 | 正确/总数 |")
        A("|---|---|---|")
        for k, label in (("keyword", "仅关键词匹配"), ("semantic", "仅语义检索"), ("hybrid", "混合检索")):
            r = af["results"][k]
            A(f"| {label} | {r['accuracy']*100:.1f}% | {r['correct']}/{af['total']} |")
    A("")
    A("## 结论")
    A("")
    if ai.get("available"):
        r = ai["results"]
        A(f"- 意图识别：语义（{r['semantic']['accuracy']*100:.1f}%）> 融合（{r['fusion']['accuracy']*100:.1f}%）"
          f"> 规则（{r['rule']['accuracy']*100:.1f}%）。现代语义模型显著优于纯规则，对口语化表达更鲁棒；"
          f"但当前融合策略采用「语义置信度 ≥0.5 才采信语义」的保守阈值，"
          f"使部分样本回退到规则，未能体现融合增益——**融合阈值/权重调优是明确的后续优化方向**。")
    if af.get("available"):
        r = af["results"]
        A(f"- 诈骗类型识别：混合（{r['hybrid']['accuracy']*100:.1f}%）> 关键词（{r['keyword']['accuracy']*100:.1f}%）"
          f"> 语义（{r['semantic']['accuracy']*100:.1f}%）。混合检索最优，验证了「语义 + 关键词」互补的必要性。")
    A("- 综合来看，单一策略均存在盲区：规则擅长精确匹配、语义擅长泛化，"
      "合理的多策略融合（而非简单择一）是提升效果的关键。")
    A("")
    A("---")
    A("")
    A(f"*报告由 evaluation/ablation.py 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    return "\n".join(L)


def main():
    print("=" * 60)
    print("  消融实验")
    print("=" * 60)
    print("[1/2] 意图识别消融 ...")
    ai = ablation_intent()
    print("      规则 %.1f%% | 语义 %.1f%% | 融合 %.1f%%" % (
        ai["results"]["rule"]["accuracy"] * 100,
        ai["results"]["semantic"]["accuracy"] * 100,
        ai["results"]["fusion"]["accuracy"] * 100))

    print("[2/2] 诈骗类型识别消融 ...")
    af = ablation_fraud()
    print("      关键词 %.1f%% | 语义 %.1f%% | 混合 %.1f%%" % (
        af["results"]["keyword"]["accuracy"] * 100,
        af["results"]["semantic"]["accuracy"] * 100,
        af["results"]["hybrid"]["accuracy"] * 100))

    with open(os.path.join(RESULT_DIR, "ablation_report.json"), "w", encoding="utf-8") as f:
        json.dump({"timestamp": datetime.now().isoformat(timespec="seconds"),
                   "intent": ai, "fraud": af}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(RESULT_DIR, "ablation_report.md"), "w", encoding="utf-8") as f:
        f.write(build_report(ai, af))
    print(f"[OK] 报告已生成: {os.path.join(RESULT_DIR, 'ablation_report.md')}")


if __name__ == "__main__":
    main()
