#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
反诈卫士 v3.0 — 真实使用数据统计（应用价值量化）
读取 data/user_*.json，统计用户规模、使用量、活跃度与转化率。

用法:
    python analytics/usage_stats.py
输出:
    analytics/usage_report.md   —— 可读报告（可并入软件说明文档"应用价值"章节）
    analytics/usage_stats.json  —— 结构化数据
"""
import io
import os
import sys
import json
import glob
from datetime import datetime
from collections import Counter

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


def ts(v):
    try:
        return datetime.fromtimestamp(int(v))
    except Exception:
        return None


def load_users():
    users = []
    for f in glob.glob(os.path.join(DATA_DIR, "user_*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                users.append(json.load(fp))
        except Exception:
            continue
    return users


def analyze(users):
    n = len(users)
    if n == 0:
        return None

    def s(key):
        return sum(int(u.get(key, 0) or 0) for u in users)

    conv = s("total_conversations")
    risk = s("risk_identifications")
    report = s("reports_submitted")
    selfchk = s("self_checks_done")
    scenario_done = sum(len(u.get("completed_scenarios", []) or []) for u in users)
    knowledge = sum(len(u.get("knowledge_learned", []) or []) for u in users)
    points = s("points")
    days = s("total_days_active")

    active = [u for u in users if int(u.get("total_days_active", 0) or 0) > 0]
    talked = [u for u in users if int(u.get("total_conversations", 0) or 0) > 0]
    risk_users = [u for u in users if int(u.get("risk_identifications", 0) or 0) > 0]

    created = [ts(u.get("created_at")) for u in users if u.get("created_at")]
    last = [ts(u.get("last_active")) for u in users if u.get("last_active")]
    created = [c for c in created if c]
    last = [l for l in last if l]

    badges = Counter()
    for u in users:
        for b in (u.get("badges", []) or []):
            badges[b] += 1

    top = sorted(users, key=lambda u: int(u.get("points", 0) or 0), reverse=True)[:10]

    def ratio(x):
        return round(x / n * 100, 1) if n else 0

    return {
        "total_users": n,
        "active_users": len(active),
        "active_rate": ratio(len(active)),
        "total_conversations": conv,
        "avg_conversations": round(conv / n, 2),
        "total_risk_identifications": risk,
        "risk_user_count": len(risk_users),
        "risk_user_rate": ratio(len(risk_users)),
        "total_reports": report,
        "total_self_checks": selfchk,
        "total_scenarios_completed": scenario_done,
        "total_knowledge_learned": knowledge,
        "total_points": points,
        "total_active_days": days,
        "avg_active_days": round(days / n, 2),
        "first_active": min(created).strftime("%Y-%m-%d") if created else "",
        "last_active": max(last).strftime("%Y-%m-%d") if last else "",
        "badges_distribution": dict(badges.most_common(10)),
        "top_users": [{"user_id": u.get("user_id"), "points": u.get("points"),
                       "conversations": u.get("total_conversations")} for u in top],
    }


def build_report(a):
    L = []
    A = L.append
    A("# 反诈卫士 v3.0 — 真实使用数据统计报告")
    A("")
    A(f"> 统计时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    A(f"> 数据来源：data/user_*.json（真实运行产生的用户数据）")
    A("")
    A("---")
    A("")
    A("## 一、用户规模与活跃度")
    A("")
    A("| 指标 | 数值 |")
    A("|---|---|")
    A(f"| 累计用户数 | {a['total_users']} |")
    A(f"| 有效活跃用户 | {a['active_users']}（{a['active_rate']}%） |")
    A(f"| 人均活跃天数 | {a['avg_active_days']} 天 |")
    A(f"| 数据时间跨度 | {a['first_active']} ~ {a['last_active']} |")
    A("")
    A("## 二、使用量统计")
    A("")
    A("| 功能 | 累计次数 |")
    A("|---|---|")
    A(f"| 对话总数 | {a['total_conversations']} |")
    A(f"| 风险识别次数 | {a['total_risk_identifications']} |")
    A(f"| 用户自查次数 | {a['total_self_checks']} |")
    A(f"| 举报提交数 | {a['total_reports']} |")
    A(f"| 情景训练完成数 | {a['total_scenarios_completed']} |")
    A(f"| 知识学习条目数 | {a['total_knowledge_learned']} |")
    A("")
    A("## 三、转化与粘性")
    A("")
    A("| 指标 | 数值 |")
    A("|---|---|")
    A(f"| 人均对话数 | {a['avg_conversations']} |")
    A(f"| 触发过风险识别的用户占比 | {a['risk_user_rate']}% |")
    A(f"| 累计积分 | {a['total_points']} |")
    A("")
    A("## 四、勋章分布（Top 10）")
    A("")
    A("| 勋章 | 获得人数 |")
    A("|---|---|")
    for k, v in a["badges_distribution"].items():
        A(f"| {k} | {v} |")
    A("")
    A("## 五、活跃用户积分榜（Top 10）")
    A("")
    A("| 排名 | 用户 | 积分 | 对话数 |")
    A("|---|---|---|---|")
    for i, u in enumerate(a["top_users"], 1):
        A(f"| {i} | {u['user_id']} | {u['points']} | {u['conversations']} |")
    A("")
    A("---")
    A("")
    A(f"*报告由 analytics/usage_stats.py 自动生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    return "\n".join(L)


def main():
    users = load_users()
    a = analyze(users)
    if not a:
        print("[警告] 未找到用户数据 data/user_*.json")
        return
    md = build_report(a)
    with open(os.path.join(OUT_DIR, "usage_report.md"), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(OUT_DIR, "usage_stats.json"), "w", encoding="utf-8") as f:
        json.dump(a, f, ensure_ascii=False, indent=2)
    print(f"[OK] 用户数: {a['total_users']}  对话: {a['total_conversations']}  "
          f"风险识别: {a['total_risk_identifications']}  举报: {a['total_reports']}")
    print(f"[OK] 报告已生成: {os.path.join(OUT_DIR, 'usage_report.md')}")


if __name__ == "__main__":
    main()
