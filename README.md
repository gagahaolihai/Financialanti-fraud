# 反诈卫士 v3.0 — 多模态智能反诈对话系统

> AI + 软件创新作品 · 面向电信网络诈骗的智能识别与劝阻系统
> 技术栈：Python 3.11 / Flask / sentence-transformers / FAISS / RAG(LLM) / EasyOCR

---

## 一、项目简介

反诈卫士是一套面向普通公众（尤其是老年人、学生等易受骗群体）的智能反诈对话系统。用户用自然语言描述遇到的情况，系统实时完成 **意图识别 → 风险研判 → 知识检索 → 劝阻干预**，并支持截图 / 语音多模态检测、情景模拟训练、举报分析与隐私保护。

核心能力：

- **智能识别**：语义向量 + 规则引擎双模，识别 16 类常见诈骗
- **风险研判**：多维度风险规则 + 时序累积，输出 5 级风险等级
- **RAG 增强**：知识库检索结果注入大模型，生成有依据、可解释的回复
- **多模态检测**：诈骗截图 OCR 特征检测、语音话术特征检测
- **人文关怀**：老年人模式、困惑简化、恐惧安抚
- **隐私优先**：PII 自动检测与 AES-256-GCM 加密脱敏，本地模型零联网

---

## 二、技术栈

| 层次 | 技术 |
|---|---|
| Web 框架 | Flask 3.0 + Gunicorn |
| 语义模型 | sentence-transformers（本地 `paraphrase-multilingual-MiniLM-L12-v2`，384 维） |
| 向量检索 | FAISS（IndexFlatIP，余弦相似度） |
| 大模型 | DeepSeek / OpenAI / Qwen（可选，兼容 OpenAI 接口） |
| 多模态 | EasyOCR（截图）/ Tesseract、pydub + whisper（语音） |
| 数据 | SQLAlchemy + SQLite |
| 安全 | cryptography（AES-256-GCM）、flask-limiter、flask-talisman |
| 部署 | Docker + Docker Compose + Nginx |

---

## 三、运行环境

- **操作系统**：Windows / Linux / macOS
- **Python**：3.11（推荐 3.11.x）
- **内存**：建议 ≥ 4 GB（加载语义模型约需 500 MB）
- **磁盘**：核心依赖约 1.5 GB（含 torch），仅核心功能约 500 MB

---

## 四、快速开始

### 1. 安装依赖

```bash
# 进入项目目录
cd 升级版反诈app

# 创建虚拟环境（推荐，避免污染系统环境）
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

# 安装核心依赖
pip install -r requirements.txt

# （可选）安装多模态与文档生成依赖
pip install -r requirements-extra.txt
```

> **重要**：若不安装 `sentence-transformers` 与 `faiss-cpu`，系统会自动降级为**纯规则引擎**模式——对话、风险研判、知识库仍可用，但语义检索与意图分类不可用。

### 2. 配置环境变量

```bash
# Windows
copy .env.example .env
# Linux / macOS
cp .env.example .env
```

关键配置（详见 `.env.example`）：

| 变量 | 说明 | 默认 |
|---|---|---|
| `PORT` | 服务端口 | 5000 |
| `LLM_ENABLED` | 是否启用大模型 | false |
| `LLM_API_KEY` | 大模型 API Key（不填则用规则引擎） | — |
| `NLP_OFFLINE_MODE` | 使用项目内本地模型，不联网下载 | true |
| `SAFE_MODE` | 纯规则引擎兜底模式 | false |

### 3. 启动服务

```bash
# 方式一：一键启动（自动打开浏览器）
python run.py

# 方式二：Windows 双击
run_local.bat
```

启动后访问：

- 对话主界面：http://localhost:5000
- 管理后台：http://localhost:5000/admin
- API 文档：http://localhost:5000/api/docs/ui
- 健康检查：http://localhost:5000/api/health

---

## 五、运行模式说明

系统支持三档运行模式，自动降级，保证任何环境下都能运行：

| 模式 | 触发条件 | 能力 |
|---|---|---|
| **完整模式** | 装齐依赖 + 配置 LLM Key | 语义 NLP + 向量检索 + RAG 大模型 + 多模态 |
| **本地智能模式** | 装齐依赖，无 LLM Key | 语义 NLP + 向量检索 + 规则引擎 |
| **规则兜底模式** | 依赖缺失 或 `SAFE_MODE=true` | 纯规则引擎，零网络依赖，100% 稳定 |

---

## 六、Docker 部署

```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

生产环境建议配合 `nginx.conf` 反向代理，并配置 HTTPS（`HTTPS_ONLY=true`）。

---

## 七、API 概览

| 分类 | 主要端点 |
|---|---|
| 对话 | `POST /api/chat` |
| 情景模拟 | `GET /api/scenario/list`、`POST /api/scenario/start`、`POST /api/scenario/step` |
| 举报 | `POST /api/report/url`、`POST /api/report/submit`、`GET /api/report/history` |
| 知识库 | `GET /api/knowledge/types`、`POST /api/knowledge/search`、`GET /api/knowledge/laws` |
| 多模态 | `POST /api/analyze/image`、`POST /api/analyze/audio`、`POST /api/analyze/text` |
| 隐私 | `GET /api/privacy/status`、`POST /api/privacy/clear-session` |
| 系统 | `GET /api/health` |

完整文档见 `/api/docs/ui`。

---

## 八、测试

```bash
# 运行全部测试
pytest tests/ -v

# 覆盖率
pytest tests/ --cov=. --cov-report=html
```

AI 效果评测（意图分类 / 诈骗类型匹配 / 向量检索 / 风险研判）：

```bash
python evaluation/run_evaluation.py
```

---

## 九、目录结构

```
升级版反诈app/
├── app.py                  # Flask 主应用与路由
├── run.py                  # 一键启动脚本
├── config.py               # 中央配置
├── engine/                 # 核心引擎
│   ├── nlp_encoder.py      # 语义向量编码器
│   ├── vector_search.py    # FAISS 向量检索
│   ├── intent_classifier.py# 语义意图分类
│   ├── rag_engine.py       # RAG 检索增强生成
│   ├── llm_client.py       # 大模型客户端
│   ├── risk_analyzer.py    # 风险研判引擎
│   ├── multimodal_detector.py # 多模态检测
│   ├── privacy_guard.py    # 隐私保护
│   └── security.py         # 加密与安全通道
├── knowledge_base/         # 知识库（诈骗类型/情景/法律/对话模板）
├── models/                 # 本地语义模型
├── templates/ static/      # 前端
├── tests/                  # 单元测试
├── evaluation/             # AI 效果评测
└── data/ logs/ voice/      # 数据 / 日志 / 演示配音
```

---

## 十、常见问题

**Q：启动后语义检索不生效？**
A：确认已安装 `sentence-transformers` 与 `faiss-cpu`，并保证 `models/paraphrase-multilingual-MiniLM-L12-v2/` 目录完整。可用 `/api/health` 查看 `nlp_semantic` 状态。

**Q：多模态上传提示"引擎未安装"？**
A：需安装 `requirements-extra.txt` 中的 `easyocr` / `pydub` 等；语音转写另需 `ffmpeg`。
   easyocr 首次运行会自动下载 OCR 模型（约 100 MB）。

**Q：安装 easyocr 时 shapely 编译报错？**
A：国内镜像可能缺少 shapely 预编译包。请先单独安装：
   `pip install shapely -i https://pypi.org/simple/`，再装 easyocr。

**Q：中文路径下 OCR 读取图片失败？**
A：已修复。`ImageFraudDetector` 改为通过 PIL 读图再传入 OCR，兼容中文路径。

**Q：没有大模型 Key 能用吗？**
A：可以。系统自动使用规则引擎 + 本地语义模型，功能完整可用。

---

*本项目仅供学习与竞赛使用，反诈数据以官方权威渠道为准。*
