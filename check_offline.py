#!/usr/bin/env python
"""
反诈卫士 v3.0 离线环境验证脚本
比赛现场运行此脚本，确认系统在零网络条件下正常工作

用法:
    python check_offline.py          # 全面检查
    python check_offline.py --safe   # 仅检查安全模式（纯规则引擎）
    python check_offline.py --full   # 检查包括NLP模型
"""
import os
import sys
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

PASS = "✅"
FAIL = "❌"
WARN = "⚠️"


def check(label: str, condition: bool, detail: str = "") -> bool:
    icon = PASS if condition else FAIL
    print(f"  {icon} {label}" + (f" — {detail}" if detail else ""))
    return condition


def main():
    import argparse
    parser = argparse.ArgumentParser(description="反诈卫士离线环境验证")
    parser.add_argument("--safe", action="store_true", help="仅检查安全模式")
    parser.add_argument("--full", action="store_true", help="全面检查")
    args = parser.parse_args()
    check_full = args.full or (not args.safe)

    print("=" * 55)
    print("  反诈卫士 v3.0 离线环境验证")
    print("=" * 55)
    print()

    all_ok = True

    # ===== 1. 基础环境 =====
    print("📦 [1/5] 基础环境检查")
    all_ok &= check("Python 3.11+", sys.version_info >= (3, 11),
                    f"Python {sys.version.split()[0]}")
    all_ok &= check("工作目录", os.path.exists("app.py"),
                    BASE_DIR)
    all_ok &= check("requirements", os.path.exists("requirements.txt"),
                    "依赖列表存在")
    print()

    # ===== 2. 离线 NLP 模型 =====
    if check_full:
        print("🧠 [2/5] NLP 语义模型 (离线)")
        model_dir = os.path.join(BASE_DIR, "models", "paraphrase-multilingual-MiniLM-L12-v2")
        has_model = os.path.isdir(model_dir)
        all_ok &= check("模型目录存在", has_model, model_dir if has_model else "缺失!")

        if has_model:
            has_config = os.path.exists(os.path.join(model_dir, "config.json"))
            has_weights = os.path.exists(os.path.join(model_dir, "model.safetensors"))
            has_tokenizer = os.path.exists(os.path.join(model_dir, "tokenizer.json"))
            all_ok &= check("config.json", has_config)
            all_ok &= check("model.safetensors", has_weights)
            all_ok &= check("tokenizer.json", has_tokenizer)

            # 尝试加载模型
            try:
                os.environ["NLP_OFFLINE_MODE"] = "1"
                os.environ["HF_HUB_OFFLINE"] = "1"
                from engine.nlp_encoder import SemanticEncoder
                encoder = SemanticEncoder()
                t0 = time.time()
                ok = encoder.load()
                elapsed = time.time() - t0
                all_ok &= check("模型加载测试", ok,
                                f"耗时 {elapsed:.1f}s, dim={encoder.vector_dim}")
            except Exception as e:
                all_ok &= check("模型加载测试", False, str(e)[:60])
        print()
    else:
        print("🧠 [2/5] NLP 语义模型 (跳过 — 安全模式)")
        print()

    # ===== 3. 规则引擎 =====
    print("⚙️  [3/5] 规则引擎 (无需网络)")
    try:
        from engine.response_generator import ResponseGenerator
        gen = ResponseGenerator()
        result = gen.generate_response("刷单兼职是真的吗")
        has_response = len(result.get("response", "")) > 20
        all_ok &= check("响应生成", has_response, "规则引擎正常")
    except Exception as e:
        all_ok &= check("响应生成", False, str(e)[:60])
    print()

    # ===== 4. 知识库 =====
    print("📚 [4/5] 知识库")
    try:
        from engine.knowledge_retriever import KnowledgeRetriever
        kr = KnowledgeRetriever()
        types = kr.get_fraud_list()
        all_ok &= check("诈骗类型数", len(types) >= 9,
                        f"{len(types)} 种")
        results = kr.search("刷单")
        all_ok &= check("TF-IDF 检索", len(results) > 0,
                        f"命中 {len(results)} 条")
    except Exception as e:
        all_ok &= check("知识库", False, str(e)[:60])
    print()

    # ===== 5. API 端点 =====
    print("🌐 [5/5] API 端点")
    try:
        from config import Config
        Config.DEBUG = True  # 避免 Talisman HTTPS 重定向
        from app import app
        with app.test_client() as client:
            resp = client.get('/api/health')
            all_ok &= check("健康检查 /api/health",
                            resp.status_code == 200,
                            f"status={resp.status_code}")

            resp2 = client.post('/api/chat', json={"message": "你好"})
            all_ok &= check("对话接口 /api/chat",
                            resp2.status_code == 200,
                            f"status={resp2.status_code}")

            resp3 = client.get('/api/knowledge/types')
            all_ok &= check("知识库接口 /api/knowledge/types",
                            resp3.status_code == 200,
                            f"status={resp3.status_code}")
    except Exception as e:
        all_ok &= check("API 端点", False, str(e)[:60])

    print()
    print("=" * 55)
    if all_ok:
        print("  ✅ 所有检查通过！系统可以离线运行。")
        print()
        print("  启动命令: python run.py")
        print("  安全模式: SAFE_MODE=true python run.py")
    else:
        print("  ❌ 部分检查未通过，请查看上方详情。")
        print()
        print("  兜底方案: SAFE_MODE=true python run.py")
        print("  (纯规则引擎，100% 稳定运行)")
    print("=" * 55)

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
