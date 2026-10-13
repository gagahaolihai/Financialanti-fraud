#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
反诈卫士 v3.0 — AI 效果评测脚本
============================================
评测四类 AI 能力：
  1. 意图分类        —— 准确率 / 每类准确率
  2. 诈骗类型匹配    —— Top-1 / Top-3 命中率
  3. 向量检索        —— 语义 / 关键词 / 混合 三种模式的 Top-1 命中率
  4. 风险研判        —— Precision / Recall / F1 / Accuracy

用法:
    python evaluation/run_evaluation.py
结果:
    控制台打印摘要 + 保存到 evaluation/results/evaluation_report.json
"""
import io
import os
import sys
import json
import time
from datetime import datetime
from collections import defaultdict

# 控制台 UTF-8（Windows 兼容）
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
except Exception:
    pass

# 将项目根目录加入 import 路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

DATASET_DIR = os.path.join(BASE_DIR, "evaluation", "datasets")
RESULT_DIR = os.path.join(BASE_DIR, "evaluation", "results")
os.makedirs(RESULT_DIR, exist_ok=True)


def load_json(name):
    with open(os.path.join(DATASET_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 1. 意图分类评测
# ============================================================
def eval_intent():
    data = load_json("intent_eval.json")["samples"]
    try:
        from engine.nlp_pipeline import get_nlp_pipeline
        nlp = get_nlp_pipeline()
    except Exception as e:
        return {"available": False, "reason": f"无法加载 NLP 管道: {e}"}

    if not nlp.ready:
        return {"available": False, "reason": "语义模型未就绪（请安装 sentence-transformers 并确认本地模型存在）"}

    # 生产路径识别器（规则 + 语义融合，与线上 generate_response 一致）
    recognizer = None
    try:
        from engine.intent_recognizer import IntentRecognizer
        recognizer = IntentRecognizer()
    except Exception:
        recognizer = None

    correct = 0
    prod_correct = 0
    per_class = defaultdict(lambda: {"total": 0, "correct": 0})
    confusion = defaultdict(lambda: defaultdict(int))
    details = []

    for i, s in enumerate(data):
        text, gold = s["text"], s["intent"]
        pred, score = nlp.classify_intent(text)
        per_class[gold]["total"] += 1
        confusion[gold][pred] += 1
        ok = (pred == gold)
        if ok:
            correct += 1
            per_class[gold]["correct"] += 1

        prod_pred = None
        if recognizer is not None:
            try:
                r = recognizer.recognize_enhanced(text, user_id=f"self_intent_{i}")
                prod_pred = r.get("intent")
            except Exception:
                prod_pred = None
            if prod_pred == gold:
                prod_correct += 1

        details.append({"text": text, "gold": gold, "pred": pred,
                        "confidence": round(float(score), 3), "correct": ok,
                        "prod_pred": prod_pred,
                        "prod_correct": (prod_pred == gold) if prod_pred is not None else None})

    n = len(data)
    return {
        "available": True,
        "total": n,
        "correct": correct,
        "accuracy": round(correct / n, 4) if n else 0,
        "prod_correct": prod_correct,
        "prod_accuracy": round(prod_correct / n, 4) if n else 0,
        "per_class": {
            k: {"accuracy": round(v["correct"] / v["total"], 4) if v["total"] else 0,
                "total": v["total"], "correct": v["correct"]}
            for k, v in per_class.items()
        },
        "details": details,
    }


# ============================================================
# 2. 诈骗类型匹配评测
# ============================================================
def eval_fraud_type():
    data = load_json("fraud_eval.json")["samples"]
    try:
        from engine.nlp_pipeline import get_nlp_pipeline
        nlp = get_nlp_pipeline()
    except Exception as e:
        return {"available": False, "reason": f"无法加载 NLP 管道: {e}"}

    if not nlp.ready:
        return {"available": False, "reason": "语义模型未就绪"}

    # 生产路径：关键词/别名优先 + 语义兜底（与线上 recognize 一致）
    recognizer = None
    try:
        from engine.intent_recognizer import IntentRecognizer
        recognizer = IntentRecognizer()
    except Exception:
        recognizer = None

    top1 = top3 = 0
    hy1 = hy3 = 0
    details = []
    for s in data:
        text, gold = s["text"], s["fraud_id"]
        matches = nlp.match_fraud_type(text) or []
        ranked = [m[0] for m in matches]
        hit1 = ranked[:1] == [gold]
        hit3 = gold in ranked[:3]
        top1 += hit1
        top3 += hit3

        hyb = []
        if recognizer is not None:
            try:
                hyb = [t[0] for t in recognizer.detect_fraud_type_hybrid(text, top_k=3)]
            except Exception:
                hyb = []
        h1 = hyb[:1] == [gold]
        h3 = gold in hyb[:3]
        hy1 += h1
        hy3 += h3

        details.append({"text": text, "gold": gold,
                        "pred_top3": ranked[:3], "hit_top1": hit1, "hit_top3": hit3,
                        "prod_top3": hyb, "prod_hit_top1": h1, "prod_hit_top3": h3})

    n = len(data)
    return {
        "available": True,
        "total": n,
        "top1_hits": top1,
        "top3_hits": top3,
        "top1_accuracy": round(top1 / n, 4) if n else 0,
        "top3_accuracy": round(top3 / n, 4) if n else 0,
        "prod_top1_hits": hy1,
        "prod_top3_hits": hy3,
        "prod_top1_accuracy": round(hy1 / n, 4) if n else 0,
        "prod_top3_accuracy": round(hy3 / n, 4) if n else 0,
        "details": details,
    }


# ============================================================
# 3. 向量检索评测
# ============================================================
def eval_retrieval():
    data = load_json("fraud_eval.json")["samples"]
    try:
        from engine.vector_search import get_vector_search
        vs = get_vector_search()
        if not vs.documents:
            docs = vs.load_knowledge_base()
            vs.build_index(docs)
    except Exception as e:
        return {"available": False, "reason": f"无法加载向量检索: {e}"}

    if not vs.is_ready and vs.doc_vectors is None:
        return {"available": False, "reason": "向量索引未就绪（需 sentence-transformers）"}

    modes = {"semantic": vs.search, "keyword": vs._keyword_fallback, "hybrid": vs.hybrid_search}
    results = {}
    for mode_name, fn in modes.items():
        hit = 0
        for s in data:
            try:
                res = fn(s["text"], top_k=1)
                if res and res[0].get("id") == s["fraud_id"]:
                    hit += 1
            except Exception:
                pass
        results[mode_name] = {
            "top1_hits": hit,
            "total": len(data),
            "top1_accuracy": round(hit / len(data), 4) if data else 0,
        }
    results["available"] = True
    return results


# ============================================================
# 4. 风险研判评测
# ============================================================
def eval_risk():
    data = load_json("risk_eval.json")["samples"]
    try:
        from engine.risk_analyzer import RiskAnalyzer
        ra = RiskAnalyzer()
    except Exception as e:
        return {"available": False, "reason": f"无法加载风险引擎: {e}"}

    # 意图分类器（用于知识咨询意图门控，与线上 generate_response 一致）
    nlp = None
    try:
        from engine.nlp_pipeline import get_nlp_pipeline
        _nlp = get_nlp_pipeline()
        nlp = _nlp if _nlp.ready else None
    except Exception:
        nlp = None

    tp = fp = tn = fn = 0
    details = []
    for i, s in enumerate(data):
        text, gold = s["text"], s["has_risk"]
        intent = None
        if nlp is not None:
            try:
                intent, _ = nlp.classify_intent(text)
            except Exception:
                intent = None
        # 逐样本隔离 user_id：避免 risk_history 跨样本累积造成历史衰减分污染
        # 传入预测意图：知识咨询类意图会触发规则门控
        pred = bool(ra.analyze_risk(text, user_id=f"self_eval_{i}", intent=intent).get("has_risk"))
        if gold and pred:
            tp += 1
        elif gold and not pred:
            fn += 1
        elif (not gold) and pred:
            fp += 1
        else:
            tn += 1
        details.append({"text": text, "gold": gold, "pred": pred})

    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    acc = (tp + tn) / len(data) if data else 0

    return {
        "available": True,
        "total": len(data),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(acc, 4),
        "details": details,
    }


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 64)
    print("  反诈卫士 v3.0 — AI 效果评测")
    print("=" * 64)

    t0 = time.time()
    report = {"timestamp": datetime.now().isoformat(timespec="seconds"), "version": "3.0"}

    print("\n[1/4] 意图分类评测 ...")
    report["intent_classification"] = eval_intent()
    _print_intent(report["intent_classification"])

    print("\n[2/4] 诈骗类型匹配评测 ...")
    report["fraud_type_matching"] = eval_fraud_type()
    _print_fraud(report["fraud_type_matching"])

    print("\n[3/4] 向量检索评测 ...")
    report["retrieval"] = eval_retrieval()
    _print_retrieval(report["retrieval"])

    print("\n[4/4] 风险研判评测 ...")
    report["risk_analysis"] = eval_risk()
    _print_risk(report["risk_analysis"])

    report["elapsed_seconds"] = round(time.time() - t0, 2)

    out = os.path.join(RESULT_DIR, "evaluation_report.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 64)
    print(f"  评测完成，耗时 {report['elapsed_seconds']}s")
    print(f"  报告已保存: {out}")
    print("=" * 64)
    return report


def _print_intent(r):
    if not r.get("available"):
        print(f"  [跳过] {r.get('reason')}")
        return
    print(f"  样本数: {r['total']}  正确: {r['correct']}  准确率: {r['accuracy']:.2%}")
    if r.get("prod_accuracy") is not None:
        print(f"  [生产路径·规则+语义] 正确: {r['prod_correct']}  准确率: {r['prod_accuracy']:.2%}")
    for k, v in sorted(r["per_class"].items(), key=lambda x: x[1]["accuracy"]):
        print(f"    {k:<20} {v['accuracy']:.0%}  ({v['correct']}/{v['total']})")


def _print_fraud(r):
    if not r.get("available"):
        print(f"  [跳过] {r.get('reason')}")
        return
    print(f"  样本数: {r['total']}")
    print(f"  [纯语义]   Top-1 {r['top1_accuracy']:.2%}  ({r['top1_hits']}/{r['total']})"
          f"  Top-3 {r['top3_accuracy']:.2%}  ({r['top3_hits']}/{r['total']})")
    if r.get("prod_top1_accuracy") is not None:
        print(f"  [生产路径] Top-1 {r['prod_top1_accuracy']:.2%}  ({r['prod_top1_hits']}/{r['total']})"
              f"  Top-3 {r['prod_top3_accuracy']:.2%}  ({r['prod_top3_hits']}/{r['total']})")


def _print_retrieval(r):
    if not r.get("available"):
        print(f"  [跳过] {r.get('reason')}")
        return
    for mode in ("semantic", "keyword", "hybrid"):
        m = r[mode]
        print(f"  {mode:<10} Top-1 命中率: {m['top1_accuracy']:.2%}  ({m['top1_hits']}/{m['total']})")


def _print_risk(r):
    if not r.get("available"):
        print(f"  [跳过] {r.get('reason')}")
        return
    print(f"  样本数: {r['total']}  (TP={r['tp']} FP={r['fp']} TN={r['tn']} FN={r['fn']})")
    print(f"  Precision: {r['precision']:.2%}   Recall: {r['recall']:.2%}   "
          f"F1: {r['f1']:.2%}   Accuracy: {r['accuracy']:.2%}")


if __name__ == "__main__":
    main()
