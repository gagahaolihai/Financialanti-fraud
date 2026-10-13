# AI 效果评测

本目录用于**量化评测反诈卫士的 AI 能力**，作为赛题提交材料之「测试报告」的数据来源。

## 目录结构

```
evaluation/
├── datasets/
│   ├── intent_eval.json    # 意图分类评测集（14 类 × 5 条）
│   ├── fraud_eval.json     # 诈骗类型匹配评测集（16 类 × 4 条）
│   └── risk_eval.json      # 风险研判评测集（正负各 20 条）
├── results/                # 评测结果（自动生成）
├── run_evaluation.py       # 效果评测主脚本
├── generate_report.py      # 测试报告生成脚本
├── ablation.py             # 消融实验（规则 / 语义 / 融合 对比）
└── benchmark.py            # 性能基准测试
```

## 评测内容

| 评测项 | 指标 | 说明 |
|---|---|---|
| 意图分类 | 准确率、每类准确率 | 语义意图分类器对 14 类意图的判定能力 |
| 诈骗类型匹配 | Top-1 / Top-3 命中率 | 文本与 16 类诈骗的匹配准确度 |
| 向量检索 | 语义 / 关键词 / 混合 三模式 Top-1 命中率 | 知识检索召回能力对比 |
| 风险研判 | Precision / Recall / F1 / Accuracy | 风险引擎的判别能力 |

## 使用方法

```bash
# 1. 运行效果评测（需已安装 sentence-transformers、faiss-cpu）
python evaluation/run_evaluation.py

# 2. 生成 Markdown 报告
python evaluation/generate_report.py

# 3. 消融实验（规则 / 语义 / 融合 对比）
python evaluation/ablation.py

# 4. 性能基准测试
python evaluation/benchmark.py
```

结果输出：

- `evaluation/results/evaluation_report.json` — 结构化指标数据
- `evaluation/results/AI效果测试报告.md` — 可读报告
- `evaluation/results/ablation_report.md` — 消融实验报告
- `evaluation/results/benchmark_report.md` — 性能基准报告

## 说明

- 评测样本贴近真实口语表达，与训练锚点/关键词**不重复**，保证评测公平。
- 若语义模型未安装，脚本会跳过语义相关评测并给出提示，风险研判评测仍可运行。
- 评测集可随时扩充，建议每次模型或知识库更新后回归测试。
