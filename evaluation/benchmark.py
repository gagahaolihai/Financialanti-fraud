#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
性能基准测试（Performance Benchmark）
测量核心 AI 链路的耗时，评估系统运行效率：

  1. 语义模型加载时间
  2. 单条文本编码延迟
  3. 批量编码吞吐
  4. FAISS 向量检索延迟
  5. 端到端响应延迟（意图识别 + 风险研判 + 知识检索 + 生成）

用法:
    python evaluation/benchmark.py
输出:
    evaluation/results/benchmark_report.md
    evaluation/results/benchmark_report.json
"""
import io
import os
import sys
import json
import time
import statistics
from datetime import datetime

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)
RESULT_DIR = os.path.join(BASE_DIR, "evaluation", "results")
os.makedirs(RESULT_DIR, exist_ok=True)

QUERIES = [
    "接到电话说我涉嫌洗钱，让我把钱转到安全账户",
    "网上兼职说动动手指日赚三百",
    "客服打电话说我的快递丢了要理赔",
    "有人推荐我买USDT挖矿",
    "什么是刷单诈骗",
    "我今年七十了，有人让我转账",
    "我要举报一个可疑链接",
    "有人用AI换脸冒充我亲戚视频借钱",
]


def timed(fn, repeat=1):
    t0 = time.perf_counter()
    for _ in range(repeat):
        fn()
    return (time.perf_counter() - t0) / repeat


def main():
    print("=" * 60)
    print("  性能基准测试")
    print("=" * 60)
    R = {"timestamp": datetime.now().isoformat(timespec="seconds")}

    # 1. 模型加载
    print("[1/5] 语义模型加载 ...")
    from engine.nlp_encoder import get_semantic_encoder
    enc = get_semantic_encoder()
    t0 = time.perf_counter()
    ok = enc.load()
    R["model_load_seconds"] = round(time.perf_counter() - t0, 3)
    R["model_available"] = bool(ok)
    print(f"      加载耗时: {R['model_load_seconds']}s  可用: {ok}")

    # 2. 单条编码
    if ok:
        print("[2/5] 单条编码延迟 ...")
        times = []
        for q in QUERIES:
            t0 = time.perf_counter()
            enc.encode(q)
            times.append(time.perf_counter() - t0)
        R["encode_single_ms"] = round(statistics.mean(times) * 1000, 2)
        R["encode_single_p95_ms"] = round(sorted(times)[int(len(times) * 0.95) - 1] * 1000, 2)
        print(f"      平均 {R['encode_single_ms']}ms  P95 {R['encode_single_p95_ms']}ms")

        # 3. 批量编码
        print("[3/5] 批量编码吞吐 ...")
        batch = QUERIES * 8  # 64 条
        t0 = time.perf_counter()
        enc.encode_batch(batch)
        dur = time.perf_counter() - t0
        R["batch_size"] = len(batch)
        R["batch_total_ms"] = round(dur * 1000, 2)
        R["throughput_per_sec"] = round(len(batch) / dur, 1)
        print(f"      {len(batch)} 条耗时 {R['batch_total_ms']}ms，吞吐 {R['throughput_per_sec']} 条/秒")

        # 4. FAISS 检索
        print("[4/5] 向量检索延迟 ...")
        from engine.vector_search import get_vector_search
        vs = get_vector_search()
        if not vs.documents:
            vs.build_index(vs.load_knowledge_base())
        rt = []
        for q in QUERIES:
            t0 = time.perf_counter()
            vs.search(q, top_k=3)
            rt.append(time.perf_counter() - t0)
        R["retrieval_ms"] = round(statistics.mean(rt) * 1000, 2)
        print(f"      平均 {R['retrieval_ms']}ms")
    else:
        print("[2-4/5] 跳过（语义模型不可用）")

    # 5. 端到端
    print("[5/5] 端到端响应延迟 ...")
    from engine.response_generator import ResponseGenerator
    rg = ResponseGenerator()
    e2e = []
    for q in QUERIES:
        t0 = time.perf_counter()
        rg.generate_response(q, user_id="bench")
        e2e.append(time.perf_counter() - t0)
    R["e2e_ms"] = round(statistics.mean(e2e) * 1000, 2)
    R["e2e_p95_ms"] = round(sorted(e2e)[int(len(e2e) * 0.95) - 1] * 1000, 2)
    R["e2e_qps"] = round(1000 / R["e2e_ms"], 1) if R["e2e_ms"] else 0
    print(f"      平均 {R['e2e_ms']}ms  P95 {R['e2e_p95_ms']}ms  约 {R['e2e_qps']} QPS(单线程)")

    with open(os.path.join(RESULT_DIR, "benchmark_report.json"), "w", encoding="utf-8") as f:
        json.dump(R, f, ensure_ascii=False, indent=2)
    with open(os.path.join(RESULT_DIR, "benchmark_report.md"), "w", encoding="utf-8") as f:
        f.write(build_report(R))
    print(f"[OK] 报告已生成: {os.path.join(RESULT_DIR, 'benchmark_report.md')}")


def build_report(R):
    L = []
    A = L.append
    A("# 性能基准测试报告 — 反诈卫士 v3.0")
    A("")
    A(f"> 测试时间：{R.get('timestamp')}")
    A("> 测试环境：Windows / Python 3.11 / CPU 推理")
    A("")
    A("---")
    A("")
    A("## 一、测试结果")
    A("")
    A("| 指标 | 数值 | 说明 |")
    A("|---|---|---|")
    A(f"| 语义模型加载 | {R.get('model_load_seconds', 'N/A')} s | 首次加载，之后常驻内存 |")
    if "encode_single_ms" in R:
        A(f"| 单条编码延迟 | {R['encode_single_ms']} ms | P95 {R.get('encode_single_p95_ms')} ms |")
        A(f"| 批量编码吞吐 | {R.get('throughput_per_sec')} 条/秒 | {R.get('batch_size')} 条耗时 {R.get('batch_total_ms')} ms |")
        A(f"| 向量检索延迟 | {R.get('retrieval_ms')} ms | FAISS Top-3 |")
    A(f"| 端到端响应延迟 | {R.get('e2e_ms')} ms | P95 {R.get('e2e_p95_ms')} ms |")
    A(f"| 单线程吞吐 | {R.get('e2e_qps')} QPS | 意图+风险+检索+生成全链路 |")
    A("")
    A("## 二、分析")
    A("")
    A("- 语义模型首次加载耗时较长，建议服务启动时预热，避免首个请求超时。")
    A("- 单条编码与向量检索均在毫秒级，满足实时对话需求。")
    A("- 端到端延迟主要来自知识检索与文本生成，可通过缓存与并发优化。")
    A("")
    A("---")
    A("")
    A(f"*报告由 evaluation/benchmark.py 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    return "\n".join(L)


if __name__ == "__main__":
    main()
