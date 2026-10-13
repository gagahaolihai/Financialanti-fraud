#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
反诈卫士 v3.0 — 真实使用数据评测脚本
============================================
用 data/antifraud.db 中提取的真实用户输入（人工标注）评测三类 AI 能力：
  1. 意图分类        —— 准确率
  2. 诈骗类型匹配    —— Top-1 / Top-3 命中率
  3. 风险研判        —— Precision / Recall / F1 / Accuracy

同时：
  - 统计真实输入的分布（意图 / 风险等级 / 诈骗类型），与自建评测集的"均匀分布"对比
  - 对比"历史存储结果"与"当前代码重跑结果"，观察系统行为是否一致

用法:
    python evaluation/evaluate_real_data.py
结果:
    控制台摘要 + evaluation/results/real_data_report.json + 真实数据评测报告.md
"""
import io
import os
import sys
import json
import sqlite3
import time
from datetime import datetime
from collections import defaultdict, Counter

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

DATASET = os.path.join(BASE_DIR, "evaluation", "datasets", "real_eval.json")
RESULT_DIR = os.path.join(BASE_DIR, "evaluation", "results")
DB_PATH = os.path.join(BASE_DIR, "data", "antifraud.db")
os.makedirs(RESULT_DIR, exist_ok=True)


def load_dataset():
    with open(DATASET, "r", encoding="utf-8") as f:
        return json.load(f)


def load_stored_risk():
    """从数据库读取真实消息的历史存储风险等级（用于对比）"""
    stored = {}
    if not os.path.exists(DB_PATH):
        return stored
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute(
            "SELECT content, risk_level, COUNT(*) n FROM conversations "
            "WHERE role='user' GROUP BY content ORDER BY n DESC"
        ).fetchall()
        for content, risk_level, _n in rows:
            stored.setdefault(content, risk_level)
    finally:
        conn.close()
    return stored


# ============================================================
# 1. 意图分类
# ============================================================
def eval_intent(samples, nlp):
    """意图分类评测。

    输出两个口径：
      - semantic  ：纯语义分类器 `nlp.classify_intent`（单组件视角）
      - production：规则 + 语义融合 `IntentRecognizer.recognize_enhanced`
                    （**与线上 generate_response 的实际路径一致**）
    两者差异说明"语义组件准确率"≠"系统准确率"。
    """
    correct = 0
    prod_correct = 0
    details = []

    # 生产路径识别器（逐样本独立 user_id，隔离对话上下文）
    recognizer = None
    try:
        from engine.intent_recognizer import IntentRecognizer
        recognizer = IntentRecognizer()
    except Exception:
        recognizer = None

    for i, s in enumerate(samples):
        pred, score = nlp.classify_intent(s["text"])
        ok = pred in s["intents"]
        correct += ok

        prod_pred, prod_conf = None, None
        if recognizer is not None:
            try:
                r = recognizer.recognize_enhanced(s["text"], user_id=f"intent_eval_{i}")
                prod_pred = r.get("intent")
                prod_conf = r.get("confidence")
            except Exception:
                prod_pred = None
            if prod_pred in s["intents"]:
                prod_correct += 1

        details.append({
            "text": s["text"], "gold": s["intents"], "pred": pred,
            "confidence": round(float(score), 3), "correct": bool(ok),
            "prod_pred": prod_pred,
            "prod_confidence": round(float(prod_conf), 3) if prod_conf is not None else None,
            "prod_correct": (prod_pred in s["intents"]) if prod_pred is not None else None,
        })

    n = len(samples)
    return {"total": n, "correct": correct,
            "accuracy": round(correct / n, 4) if n else 0,
            "prod_correct": prod_correct,
            "prod_accuracy": round(prod_correct / n, 4) if n else 0,
            "details": details}


# ============================================================
# 2. 诈骗类型匹配
# ============================================================
def eval_fraud_type(samples, nlp):
    """诈骗类型匹配评测。

    输出两个口径：
      - semantic  ：纯语义匹配 `nlp.match_fraud_type`
      - production：融合匹配 `IntentRecognizer.detect_fraud_type_hybrid`
                    （关键词/别名优先 + 语义兜底，**与线上 recognize() 一致**）
    """
    sub = [s for s in samples if s.get("fraud_types")]

    recognizer = None
    try:
        from engine.intent_recognizer import IntentRecognizer
        recognizer = IntentRecognizer()
    except Exception:
        recognizer = None

    top1 = top3 = 0
    hy1 = hy3 = 0
    details = []
    for s in sub:
        gold = set(s["fraud_types"])
        matches = nlp.match_fraud_type(s["text"]) or []
        ranked = [m[0] for m in matches]
        hit1 = bool(ranked[:1] and ranked[0] in gold)
        hit3 = bool(set(ranked[:3]) & gold)
        top1 += hit1
        top3 += hit3

        hyb = []
        if recognizer is not None:
            try:
                hyb = [t[0] for t in recognizer.detect_fraud_type_hybrid(s["text"], top_k=3)]
            except Exception:
                hyb = []
        h1 = bool(hyb[:1] and hyb[0] in gold)
        h3 = bool(set(hyb[:3]) & gold)
        hy1 += h1
        hy3 += h3

        details.append({"text": s["text"], "gold": sorted(gold),
                        "pred_top3": ranked[:3], "hit_top1": hit1, "hit_top3": hit3,
                        "prod_top3": hyb, "prod_hit_top1": h1, "prod_hit_top3": h3})
    n = len(sub)
    return {"total": n, "top1_hits": top1, "top3_hits": top3,
            "top1_accuracy": round(top1 / n, 4) if n else 0,
            "top3_accuracy": round(top3 / n, 4) if n else 0,
            "prod_top1_hits": hy1, "prod_top3_hits": hy3,
            "prod_top1_accuracy": round(hy1 / n, 4) if n else 0,
            "prod_top3_accuracy": round(hy3 / n, 4) if n else 0,
            "details": details}


# ============================================================
# 3. 风险研判
# ============================================================
def _prf(tp, fp, tn, fn, n):
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    acc = (tp + tn) / n if n else 0
    return (round(precision, 4), round(recall, 4), round(f1, 4), round(acc, 4))


def eval_risk(samples, ra, stored, nlp=None):
    """风险研判评测。

    关键修正：**逐样本隔离**。每条样本使用独立 user_id，避免 risk_history
    跨样本累积把后续无风险样本"顶"成高危（历史衰减分污染）。
    同时传入系统预测意图，与线上 generate_response 的单轮路径一致
    （知识咨询意图会触发规则门控）。

    另设 risk_raw 对照：隔离历史但不传意图，用于观察意图门控的净贡献。
    """
    tp = fp = tn = fn = 0
    tp2 = fp2 = tn2 = fn2 = 0
    details = []
    stored_hit = 0
    stored_total = 0
    for i, s in enumerate(samples):
        gold = bool(s["has_risk"])
        uid = f"eval_iso_{i}"

        intent = None
        if nlp is not None:
            try:
                intent, _ = nlp.classify_intent(s["text"])
            except Exception:
                intent = None

        # 主口径：隔离历史 + 传意图（生产等价）
        res = ra.analyze_risk(s["text"], user_id=uid, intent=intent) or {}
        pred = bool(res.get("has_risk"))
        level = res.get("risk_level", "none")

        # 对照口径：隔离历史 + 不传意图（纯规则）
        res2 = ra.analyze_risk(s["text"], user_id=uid + "_raw") or {}
        pred2 = bool(res2.get("has_risk"))

        if gold and pred:
            tp += 1
        elif gold and not pred:
            fn += 1
        elif (not gold) and pred:
            fp += 1
        else:
            tn += 1

        if gold and pred2:
            tp2 += 1
        elif gold and not pred2:
            fn2 += 1
        elif (not gold) and pred2:
            fp2 += 1
        else:
            tn2 += 1

        # 历史存储结果对比（仅对有存储记录的样本）
        s_risk = stored.get(s["text"])
        if s_risk is not None:
            stored_total += 1
            s_pred = s_risk in ("high", "critical")
            stored_hit += (s_pred == gold)

        details.append({"text": s["text"], "gold": gold, "pred": pred,
                        "level": level, "intent": intent, "stored": s_risk})

    n = len(samples)
    precision, recall, f1, acc = _prf(tp, fp, tn, fn, n)
    p2, r2, f2, a2 = _prf(tp2, fp2, tn2, fn2, n)
    return {
        "total": n, "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1, "accuracy": acc,
        "stored_accuracy": round(stored_hit / stored_total, 4) if stored_total else None,
        "stored_total": stored_total,
        "details": details,
        "risk_raw": {
            "tp": tp2, "fp": fp2, "tn": tn2, "fn": fn2,
            "precision": p2, "recall": r2, "f1": f2, "accuracy": a2,
        },
    }


# ============================================================
# 4. 真实分布统计
# ============================================================
def distribution(samples, ra, nlp=None):
    risk_dist = Counter()
    type_dist = Counter()
    for i, s in enumerate(samples):
        intent = None
        if nlp is not None:
            try:
                intent, _ = nlp.classify_intent(s["text"])
            except Exception:
                intent = None
        # 逐样本隔离，避免历史累积污染分布统计
        res = ra.analyze_risk(s["text"], user_id=f"eval_dist_{i}", intent=intent) or {}
        risk_dist[res.get("risk_level", "none")] += 1
    return {"risk_level": dict(risk_dist), "type_dist": dict(type_dist)}


def load_selfbuilt():
    p = os.path.join(RESULT_DIR, "evaluation_report.json")
    if os.path.exists(p):
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 64)
    print("  反诈卫士 v3.0 — 真实使用数据评测")
    print("=" * 64)

    ds = load_dataset()
    samples = ds["samples"]
    print(f"\n评测集：{ds['metadata']['name']}  共 {len(samples)} 条（人工标注）")

    from engine.nlp_pipeline import get_nlp_pipeline
    from engine.risk_analyzer import RiskAnalyzer
    nlp = get_nlp_pipeline()
    ra = RiskAnalyzer()
    print(f"语义模型就绪：{nlp.ready}")

    stored = load_stored_risk()
    report = {"timestamp": datetime.now().isoformat(timespec="seconds"),
              "dataset": ds["metadata"], "total": len(samples)}

    print("\n[1/3] 意图分类 ...")
    report["intent"] = eval_intent(samples, nlp)
    _i = report["intent"]
    print(f"      [纯语义]   {_i['accuracy']*100:.1f}% ({_i['correct']}/{_i['total']})")
    print(f"      [生产路径] {_i['prod_accuracy']*100:.1f}% ({_i['prod_correct']}/{_i['total']})")

    print("[2/3] 诈骗类型匹配 ...")
    report["fraud_type"] = eval_fraud_type(samples, nlp)
    _f = report["fraud_type"]
    print(f"      [纯语义]   Top-1 {_f['top1_accuracy']*100:.1f}%  Top-3 {_f['top3_accuracy']*100:.1f}%")
    print(f"      [生产路径] Top-1 {_f['prod_top1_accuracy']*100:.1f}%  Top-3 {_f['prod_top3_accuracy']*100:.1f}%"
          f"  (n={_f['total']})")

    print("[3/3] 风险研判 ...")
    report["risk"] = eval_risk(samples, ra, stored, nlp)
    r = report["risk"]
    print(f"      [生产等价·隔离+意图] P {r['precision']*100:.1f}%  R {r['recall']*100:.1f}%  "
          f"F1 {r['f1']*100:.1f}%  Acc {r['accuracy']*100:.1f}%")
    print(f"      TP={r['tp']} FP={r['fp']} TN={r['tn']} FN={r['fn']}")
    rw = r["risk_raw"]
    print(f"      [纯规则·隔离无意图] P {rw['precision']*100:.1f}%  R {rw['recall']*100:.1f}%  "
          f"F1 {rw['f1']*100:.1f}%  Acc {rw['accuracy']*100:.1f}%")
    print(f"      TP={rw['tp']} FP={rw['fp']} TN={rw['tn']} FN={rw['fn']}")
    if r["stored_accuracy"] is not None:
        print(f"      历史存储结果准确率 {r['stored_accuracy']*100:.1f}% (n={r['stored_total']})")

    report["distribution"] = distribution(samples, ra, nlp)

    out_json = os.path.join(RESULT_DIR, "real_data_report.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存：{out_json}")

    # 与自建评测集对比
    sb = load_selfbuilt()
    if sb:
        print("\n" + "=" * 64)
        print("  与自建评测集对比")
        print("=" * 64)
        try:
            print(f"  意图：自建 {sb['intent_classification']['accuracy']*100:.1f}% "
                  f"vs 真实 {report['intent']['accuracy']*100:.1f}%")
        except Exception:
            pass
        try:
            print(f"  类型：自建 Top-1 {sb['fraud_type_matching'].get('prod_top1_accuracy', sb['fraud_type_matching']['top1_accuracy'])*100:.1f}% "
                  f"vs 真实 {report['fraud_type']['prod_top1_accuracy']*100:.1f}%")
        except Exception:
            pass
        try:
            print(f"  风险：自建 P {sb['risk_analysis']['precision']*100:.1f}%/"
                  f"R {sb['risk_analysis']['recall']*100:.1f}%  vs 真实 "
                  f"P {r['precision']*100:.1f}%/R {r['recall']*100:.1f}%")
        except Exception:
            pass


if __name__ == "__main__":
    main()
