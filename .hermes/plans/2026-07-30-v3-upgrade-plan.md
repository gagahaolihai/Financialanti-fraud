# 反诈卫士 v3.0 — 国赛深度优化实施计划

> **Goal:** 从规则引擎升级为「规则+AI混合引擎」，新增多模态检测和现代NLP，打造国赛级智能反诈系统

**Architecture:** 保留现有 Flask 架构，增量升级三大核心模块：LLM+RAG混合引擎、多模态检测（截图/语音）、现代NLP语义理解

**Tech Stack:** Python 3.11, Flask, sentence-transformers, DeepSeek API, EasyOCR, pydub, ChromaDB/FAISS

---

## Phase 1: 现代 NLP 引擎升级（替换 TF-IDF）

### Task 1.1: 安装依赖 & 创建新引擎骨架
### Task 1.2: 实现 sentence-transformers 语义向量编码器
### Task 1.3: 实现 FAISS 向量检索（替代 TF-IDF 搜索）
### Task 1.4: 实现 BERT 级意图分类器（替代纯规则匹配）
### Task 1.5: 集成到现有引擎管道

## Phase 2: LLM + RAG 混合引擎

### Task 2.1: 升级 LLM Client 支持流式输出
### Task 2.2: 实现 RAG 检索增强生成管道
### Task 2.3: 实现「规则+LLM」双模切换策略
### Task 2.4: 实现多轮对话记忆管理
### Task 2.5: 集成到 /api/chat 主流程

## Phase 3: 多模态诈骗检测

### Task 3.1: 诈骗截图分析模块（OCR + 关键词检测）
### Task 3.2: 语音/音频诈骗检测模块
### Task 3.3: 多模态 API 端点和前端上传

---

**Verification:** 每个 Phase 完成后跑 `pytest tests/ -v` 确保不破坏现有功能
