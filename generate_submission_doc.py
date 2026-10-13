"""
生成睿抗(RAICOM)比赛作品提交文档 - Word格式
包含项目概述、架构设计、功能说明、技术实现、源码附录
"""
import os
import sys
from datetime import datetime
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml.ns import qn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============================================================
# 样式配置
# ============================================================
def setup_styles(doc):
    """配置文档样式"""
    style = doc.styles['Normal']
    style.font.name = '宋体'
    style.font.size = Pt(11)
    style.element.rPr.rFonts.set(qn('w:eastAsia'), '宋体')
    style.paragraph_format.line_spacing = 1.5

    # Heading 1
    h1 = doc.styles['Heading 1']
    h1.font.name = '黑体'
    h1.font.size = Pt(18)
    h1.font.bold = True
    h1.font.color.rgb = RGBColor(0x1a, 0x73, 0xe8)
    h1.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    h1.paragraph_format.space_before = Pt(24)
    h1.paragraph_format.space_after = Pt(12)

    # Heading 2
    h2 = doc.styles['Heading 2']
    h2.font.name = '黑体'
    h2.font.size = Pt(15)
    h2.font.bold = True
    h2.font.color.rgb = RGBColor(0x20, 0x21, 0x24)
    h2.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    h2.paragraph_format.space_before = Pt(18)
    h2.paragraph_format.space_after = Pt(8)

    # Heading 3
    h3 = doc.styles['Heading 3']
    h3.font.name = '黑体'
    h3.font.size = Pt(13)
    h3.font.bold = True
    h3.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')
    h3.paragraph_format.space_before = Pt(12)
    h3.paragraph_format.space_after = Pt(6)

    return doc


def add_code_block(doc, code_text, language="python"):
    """添加代码块（等宽字体、灰色背景效果）"""
    for line in code_text.split('\n'):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.15
        run = p.add_run(line if line else ' ')
        run.font.name = 'Consolas'
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
    doc.add_paragraph()  # spacing after code block


def add_code_from_file(doc, file_path, title=None, limit=None):
    """从文件读取代码并添加"""
    if title:
        doc.add_heading(title, level=3)
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        if limit:
            lines = lines[:limit]
        code = ''.join(lines)
        add_code_block(doc, code)
    except Exception as e:
        doc.add_paragraph(f"[无法读取文件: {e}]")


def add_table(doc, headers, rows):
    """添加格式化表格"""
    table = doc.add_table(rows=1 + len(rows), cols=len(headers), style='Light Shading Accent 1')
    # Header
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for run in p.runs:
                run.font.bold = True
                run.font.size = Pt(10)
    # Data
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            table.rows[r+1].cells[c].text = str(val)
            for p in table.rows[r+1].cells[c].paragraphs:
                for run in p.runs:
                    run.font.size = Pt(10)
    doc.add_paragraph()
    return table


# ============================================================
# 文档生成主逻辑
# ============================================================
def generate():
    doc = Document()
    doc = setup_styles(doc)

    # ==================== 封面 ====================
    for _ in range(6):
        doc.add_paragraph()

    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_p.add_run('多模态智能反诈对话系统')
    run.font.name = '黑体'
    run.font.size = Pt(28)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0x1a, 0x73, 0xe8)
    run.element.rPr.rFonts.set(qn('w:eastAsia'), '黑体')

    subtitle_p = doc.add_paragraph()
    subtitle_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = subtitle_p.add_run('Anti-Fraud Intelligent Dialogue System')
    run.font.name = 'Arial'
    run.font.size = Pt(16)
    run.font.color.rgb = RGBColor(0x5f, 0x63, 0x68)

    doc.add_paragraph()
    doc.add_paragraph()

    info_lines = [
        '睿抗机器人开发者大赛（RAICOM）参赛作品',
        '作品类别：CAIP 编程设计 / CAIA 数字文化创意',
        f'提交日期：{datetime.now().strftime("%Y年%m月%d日")}',
    ]
    for line in info_lines:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(line)
        run.font.size = Pt(12)
        run.font.color.rgb = RGBColor(0x5f, 0x63, 0x68)

    doc.add_page_break()

    # ==================== 目录 ====================
    doc.add_heading('目  录', level=1)
    toc_items = [
        ('一、项目概述', ''),
        ('    1.1 项目背景', ''),
        ('    1.2 项目目标', ''),
        ('    1.3 目标用户群体', ''),
        ('二、系统架构设计', ''),
        ('    2.1 整体架构', ''),
        ('    2.2 技术栈', ''),
        ('    2.3 模块划分', ''),
        ('三、核心功能设计', ''),
        ('    3.1 多轮对话意图识别', ''),
        ('    3.2 多维风险行为分析', ''),
        ('    3.3 知识库语义检索', ''),
        ('    3.4 隐私保护体系', ''),
        ('    3.5 URL安全分析', ''),
        ('    3.6 诈骗知识图谱', ''),
        ('    3.7 游戏化激励机制', ''),
        ('    3.8 LLM增强对话', ''),
        ('四、技术实现详述', ''),
        ('    4.1 后端框架与API设计', ''),
        ('    4.2 前端交互界面', ''),
        ('    4.3 数据库设计', ''),
        ('    4.4 安全防护机制', ''),
        ('五、部署说明', ''),
        ('    5.1 环境要求', ''),
        ('    5.2 Docker一键部署', ''),
        ('    5.3 运行方式', ''),
        ('六、创新点与应用前景', ''),
        ('    6.1 核心创新点', ''),
        ('    6.2 应用场景', ''),
        ('    6.3 未来展望', ''),
        ('附录A：核心源代码', ''),
        ('附录B：知识库数据设计', ''),
    ]
    for item, _ in toc_items:
        p = doc.add_paragraph(item)
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)

    doc.add_page_break()

    # ==================== 一、项目概述 ====================
    doc.add_heading('一、项目概述', level=1)

    doc.add_heading('1.1 项目背景', level=2)
    doc.add_paragraph(
        '随着移动互联网的普及和数字金融的快速发展，电信网络诈骗案件呈高发态势。'
        '仅2024年，全国公安机关共破获电信网络诈骗案件46.4万起，同比上升5.4%。'
        '诈骗手法不断迭代升级：从传统的"冒充公检法"到利用AI换脸、深度伪造等新技术的'
        '"AI诈骗"，从单一的话术欺骗到"杀猪盘+虚假投资+网贷"的复合型诈骗，'
        '犯罪分子的手段日益专业化、精准化、链条化。'
    )
    doc.add_paragraph(
        '然而，现有反诈手段存在明显不足：(1) 国家反诈中心APP以被动拦截为主，'
        '缺乏主动教育和实时对话劝阻能力；(2) 反诈热线96110依赖人工坐席，'
        '高峰期接通率低，难以7×24小时全覆盖；(3) 基层反诈宣传以横幅、传单为主，'
        '触达率低、转化率差，群众"入眼不入心"。'
    )
    doc.add_paragraph(
        '在此背景下，我们开发了"多模态智能反诈对话系统"——一款集风险识别、'
        '紧急劝阻、知识普及、情景训练于一体的AI反诈助手。系统可7×24小时在线，'
        '通过自然语言对话的方式，主动识别用户遇到的诈骗风险，提供个性化劝阻干预，'
        '并通过游戏化机制提升用户的反诈意识和防范能力。'
    )

    doc.add_heading('1.2 项目目标', level=2)
    goals = [
        '构建一个基于自然语言处理和多维规则引擎的智能反诈对话系统',
        '实现对用户描述的诈骗场景的自动识别与风险等级评估（5级：无/低/中/高/紧急）',
        '提供7大类个人敏感信息(PII)的自动检测与加密保护,确保用户隐私安全',
        '通过TF-IDF语义搜索和诈骗知识图谱实现精准的诈骗类型匹配与知识推荐',
        '集成游戏化机制(Gamification),提升用户学习反诈知识的积极性和粘性',
        '支持Docker容器化一键部署，提供管理后台便于运营监控',
    ]
    for g in goals:
        doc.add_paragraph(g, style='List Bullet')

    doc.add_heading('1.3 目标用户群体', level=2)
    doc.add_paragraph(
        '本系统面向全社会公众，重点服务以下高风险群体：'
    )
    groups = [
        '中老年人（50岁以上）：易受"冒充公检法""保健品诈骗"等传统骗局侵害，对新技术不熟悉',
        '在校大学生：易受"刷单返利""校园贷""游戏交易"等新型网络诈骗',
        '年轻白领：易受"虚假投资理财""杀猪盘"等高金额诈骗',
        '社区工作人员/反诈志愿者：作为辅助工具，快速查询反诈知识和劝阻话术',
    ]
    for g in groups:
        doc.add_paragraph(g, style='List Bullet')

    doc.add_page_break()

    # ==================== 二、系统架构设计 ====================
    doc.add_heading('二、系统架构设计', level=1)

    doc.add_heading('2.1 整体架构', level=2)
    doc.add_paragraph(
        '系统采用分层架构设计，自上而下分为：接入层、业务层、引擎层、数据层。'
        '各层职责清晰，模块间低耦合高内聚，支持灵活扩展和独立升级。'
    )

    arch_text = """
┌─────────────────────────────────────────────────────┐
│                    接入层 (Access Layer)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ Web前端  │  │ Nginx    │  │ RESTful API      │  │
│  │ (HTML/   │  │ 反向代理 │  │ (Flask + CORS +  │  │
│  │  CSS/JS) │  │ 负载均衡 │  │  JWT认证)        │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
├─────────────────────────────────────────────────────┤
│                  业务层 (Business Layer)              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ 对话管理 │  │ 用户管理 │  │ 管理后台          │  │
│  │ 会话状态 │  │ 认证授权 │  │ 统计监控/审计日志 │  │
│  └──────────┘  └──────────┘  └──────────────────┘  │
├─────────────────────────────────────────────────────┤
│                   引擎层 (Engine Layer)               │
│  ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │意图识别  │ │风险分析  │ │知识检索(TF-IDF)    │  │
│  │多轮追踪  │ │多维评分  │ │语义搜索/热加载     │  │
│  └──────────┘ └──────────┘ └────────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │隐私卫士  │ │URL分析   │ │LLM客户端           │  │
│  │PII检测   │ │域名/IP/  │ │DeepSeek/OpenAI/    │  │
│  │加密脱敏  │ │恶意检测  │ │Qwen多模型支持      │  │
│  └──────────┘ └──────────┘ └────────────────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │安全模块  │ │知识图谱  │ │游戏化引擎          │  │
│  │AES-GCM   │ │关联推理  │ │积分/勋章/排行榜    │  │
│  │HMAC认证  │ │传播分析  │ │每日任务/签到       │  │
│  └──────────┘ └──────────┘ └────────────────────┘  │
├─────────────────────────────────────────────────────┤
│                   数据层 (Data Layer)                 │
│  ┌──────────┐ ┌──────────┐ ┌────────────────────┐  │
│  │ SQLite   │ │ JSON     │ │ 审计日志(Rotating  │  │
│  │ (ORM)    │ │ 知识库   │ │  FileHandler)      │  │
│  └──────────┘ └──────────┘ └────────────────────┘  │
└─────────────────────────────────────────────────────┘
"""
    add_code_block(doc, arch_text)

    doc.add_heading('2.2 技术栈', level=2)
    add_table(doc,
        ['层级', '技术选型', '说明'],
        [
            ['后端框架', 'Flask 3.0 + Gunicorn', '轻量灵活，适合中小规模部署'],
            ['数据库ORM', 'SQLAlchemy 2.0 + SQLite', '支持平滑迁移至PostgreSQL/MySQL'],
            ['安全加密', 'AES-256-GCM (cryptography库)', '数据加密存储；惰性导入防初始化崩溃'],
            ['JWT认证', '自定义HMAC-SHA256 JWT', '无状态认证，24小时过期'],
            ['速率限制', 'Flask-Limiter', '默认30次/分钟/用户'],
            ['安全响应头', 'Flask-Talisman', 'CSP/HSTS/X-Frame-Options等'],
            ['LLM集成', 'DeepSeek/Qwen/OpenAI', '多厂商支持，不可用时优雅降级'],
            ['知识图谱', 'NetworkX', '有向图建模诈骗关联关系'],
            ['容器化', 'Docker + Docker Compose', '一键部署，环境隔离'],
            ['前端', '原生HTML/CSS/JS + PWA', '响应式设计，支持移动端'],
        ]
    )

    doc.add_heading('2.3 模块划分', level=2)
    doc.add_paragraph(
        '系统共包含15个核心模块，按职责划分为以下6组：'
    )
    add_table(doc,
        ['模块组', '模块名称', '核心职责'],
        [
            ['对话处理', 'intent_recognizer.py', '14种意图识别，多轮上下文追踪，同义词扩展匹配'],
            ['对话处理', 'response_generator.py', '整合各引擎生成最终回复，处理紧急/感谢等特殊场景'],
            ['对话处理', 'url_analyzer.py', 'URL安全性分析，域名/IP/短链接检测'],
            ['风险评估', 'risk_analyzer.py', '13类风险规则匹配，4级风险评分，个性化劝阻话术'],
            ['知识管理', 'knowledge_retriever.py', 'TF-IDF语义搜索，热加载，交叉引用，常见问答'],
            ['知识管理', 'knowledge_graph.py', '诈骗知识图谱构建，关联推理，传播路径分析'],
            ['安全隐私', 'privacy_guard.py', '7类PII自动检测，AES加密，会话级密钥隔离'],
            ['安全隐私', 'security.py', '数据加密器、脱敏器、JWT认证、审计日志、安全通道'],
            ['AI增强', 'llm_client.py', '多LLM厂商适配，风险分析增强，回复人性化润色'],
            ['用户运营', 'gamification.py', '积分/等级/勋章/每日任务/签到/排行榜'],
            ['基础设施', 'database.py', '用户表、会话表、对话表、隐私记录表、举报表等'],
            ['基础设施', 'config.py', '中央配置管理，环境变量>.env>默认值三级优先级'],
            ['基础设施', 'log_setup.py', '日志系统配置，审计日志分离，轮转日志'],
            ['前端展示', 'templates/', 'Web聊天界面(响应式) + 管理后台'],
            ['前端展示', 'static/', 'CSS样式 + PWA Service Worker + 图标资源'],
        ]
    )

    doc.add_page_break()

    # ==================== 三、核心功能设计 ====================
    doc.add_heading('三、核心功能设计', level=1)

    # 3.1 意图识别
    doc.add_heading('3.1 多轮对话意图识别', level=2)
    doc.add_paragraph(
        '意图识别引擎(IntentRecognizer)是本系统的"大脑"，负责理解用户输入的真正含义。'
        '支持14种意图类型，采用加权规则匹配 + 同义词扩展 + 多轮上下文追踪的混合策略。'
    )
    doc.add_paragraph('核心设计要点：')
    features = [
        '14种意图分类：问候、求助、举报、知识查询、场景模拟、自检、法律咨询、诈骗咨询、紧急求助、情景描述、困惑、恐惧焦虑、老年人身份、感谢',
        '加权规则匹配：每种意图有独立权重（紧急=2.0、自检=1.8、诈骗咨询=1.6），按置信度排序',
        '同义词扩展：内置15组同义词映射（刷单→兼职/刷信誉/做任务，被骗→上当/受骗/被坑）',
        '多轮上下文追踪：维护ConversationContext对象记录每轮对话，连续未知意图超过2轮自动降级为fallback',
        '诈骗类型独立检测：从9种诈骗类型的关键词、别名、典型话术中检测用户可能涉及的骗局',
        '紧急意图优先：独立检测已转账、正在转账等紧急关键词，最高优先级返回',
        '情景描述智能判断：15+正则模式 + 长度阈值判断 + 典型欺诈话术匹配',
    ]
    for f in features:
        doc.add_paragraph(f, style='List Bullet')

    doc.add_paragraph('支持的诈骗类型检测包括：刷单返利、游戏交易、冒充公检法、虚假投资(含杀猪盘)、校园贷、冒充客服退款、虚假征信、冒充熟人、交友诈骗。')

    # 3.2 风险分析
    doc.add_heading('3.2 多维风险行为分析', level=2)
    doc.add_paragraph(
        '风险分析引擎(RiskAnalyzer)对用户的输入进行多维度风险评估，'
        '包含13类风险行为规则，覆盖当前主流诈骗手法的关键风险特征。'
    )
    risk_rules = [
        ('转账到陌生账户', '0.80', '资金风险'),
        ('提供验证码', '0.95', '信息泄露'),
        ('点击不明链接', '0.70', '恶意链接'),
        ('屏幕共享', '0.90', '信息泄露'),
        ('下载不明APP', '0.65', '恶意软件'),
        ('提供身份证照片', '0.80', '信息泄露'),
        ('网贷诱导', '0.75', '诱导借贷'),
        ('刷单/兼职', '0.70', '刷单诈骗'),
        ('冒充公检法', '0.95', '冒充公检法'),
        ('虚假投资诱导', '0.85', '投资诈骗'),
        ('高额回报承诺', '0.60', '虚假承诺'),
        ('冒充客服退款', '0.70', '冒充客服'),
        ('注销账户', '0.80', '注销账户诈骗'),
        ('杀猪盘恋爱诱导', '0.90', '杀猪盘'),
    ]
    add_table(doc, ['风险规则', '权重', '风险类别'], risk_rules)
    doc.add_paragraph('风险等级判定采用动态阈值：累计分数≥2.0为紧急(critical)，≥1.0为高风险(high)，≥0.4为中风险(medium)。同时支持对话历史时序分析和5分钟时间窗口风险衰减。')
    doc.add_paragraph('劝阻话术库包含4个等级×10+场景的模板库（如紧急-资金风险、高风险-刷单诈骗等），可根据具体触发的规则类别动态选择最匹配的话术模板。')

    # 3.3 知识库
    doc.add_heading('3.3 知识库语义检索', level=2)
    doc.add_paragraph(
        '知识检索引擎(KnowledgeRetriever)基于TF-IDF实现中文语义搜索，'
        '将每种诈骗类型的描述、别名、关键词、典型案例等信息构建为文档向量，'
        '通过余弦相似度计算查询与各诈骗类型的匹配度。'
    )
    doc.add_paragraph('特点：')
    k_features = [
        '中文分词：采用2-gram字符级分词，适配中文特点，不依赖外部分词库',
        '热加载机制：每60秒检查知识库JSON文件是否更新，支持运行时动态添加新骗局类型',
        '交叉引用：每个骗局可关联related_frauds，形成知识关联网络',
        '常见问答检索：基于tag匹配和关键词命中返回预设问答',
        '关联推理：通过get_reasoning()返回骗局的心理操控手法、劝阻模板、举报指引等',
    ]
    for f in k_features:
        doc.add_paragraph(f, style='List Bullet')

    # 3.4 隐私保护
    doc.add_heading('3.4 隐私保护体系', level=2)
    doc.add_paragraph(
        '隐私卫士(PrivacyGuard)是系统最核心的安全创新之一。它在用户对话过程中'
        '实时检测7大类个人敏感信息(PII)，自动加密替换，实现"后台人员也无法查看原文"。'
        '采用每会话独立密钥的零信任架构，即使数据库泄露也无法解密。'
    )
    pii_types = [
        ('手机号码', '📱', '1开头的11位数字', '138****5678', '0.95'),
        ('身份证号', '🆔', '18位+校验码验证', '3201**********1234', '0.98'),
        ('银行卡号', '💳', '16-19位+Luhn算法校验', '6222 **** **** 1234', '0.90'),
        ('短信验证码', '🔢', '上下文短语触发', '****', '0.95'),
        ('真实姓名', '👤', '"我叫XX"/"XX先生"模式', '张某某', '0.85'),
        ('密码', '🔑', '"密码是XXX"模式', '******', '0.95'),
        ('家庭地址', '📍', '省市区+路号', '江苏****南京', '0.75'),
    ]
    add_table(doc, ['PII类型', '标识', '检测方式', '掩码示例', '置信度'], pii_types)

    doc.add_paragraph('安全机制：')
    sec_items = [
        '每会话独立密钥：通过PBKDF2从主密钥+会话ID+随机盐派生，1小时自动过期',
        '加密存储：HMAC-SHA256认证 + XOR流加密的简易AEAD方案',
        '会话关闭自动清除：关闭对话或页面后，该会话所有PII加密记录自动安全擦除',
        '用户分级告警：验证码→最高级告警("验证码等于账户钥匙")；地址→普通告警',
        '不可逆脱敏存储：对话历史中的PII在存入数据库前已替换为掩码版本',
    ]
    for item in sec_items:
        doc.add_paragraph(item, style='List Bullet')

    # 3.5 URL分析
    doc.add_heading('3.5 URL安全分析', level=2)
    doc.add_paragraph(
        'URL分析器(URLAnalyzer)对用户发送的链接进行多维度安全检测：'
        '短链接展开、域名WHOIS查询(注册天数检查)、可疑关键词匹配(如"login""verify")、'
        '端口扫描(排除80/443)、可疑IP检测。分析结果给出0-100的综合风险评分。'
    )

    # 3.6 知识图谱
    doc.add_heading('3.6 诈骗知识图谱', level=2)
    doc.add_paragraph(
        '诈骗知识图谱(FraudKnowledgeGraph)基于NetworkX构建有向图，建模诈骗类型间的'
        '关联关系(related_to)、升级关系(leads_to，如刷单→虚假投资)、共享手法(shares_tactic)、'
        '针对相同群体(targets_same)、变种关系(evolution_of)等7种关系类型。'
        '支持关联推理：输入一个诈骗类型，自动发现关联诈骗、演化路径和伴随风险。'
    )

    # 3.7 游戏化
    doc.add_heading('3.7 游戏化激励机制', level=2)
    doc.add_paragraph(
        '系统内置完整的游戏化系统(GamificationSystem)，通过积分、等级、勋章、'
        '每日任务、连续签到、排行榜等机制提升用户粘性和学习积极性。'
    )
    badges_items = [
        '12种勋章：初识反诈、勤学好问、反诈达人、知识达人、闯关新手、闯关能手、反诈卫士、正义举报、举报先锋、签到新星、签到达人、反诈状元',
        '等级体系：青铜→白银→黄金→铂金→钻石→王者，基于经验值自动升级',
        '每日任务：每日对话、知识学习、情景模拟、举报提交，每日0点自动重置',
        '连续签到：每日签到领积分，连续签到有额外奖励',
        '排行榜：按积分排名，支持周榜/月榜切换',
    ]
    for item in badges_items:
        doc.add_paragraph(item, style='List Bullet')

    # 3.8 LLM
    doc.add_heading('3.8 LLM增强对话', level=2)
    doc.add_paragraph(
        '系统支持DeepSeek、OpenAI、Qwen三种大语言模型，提供两种增强能力：'
        '(1) 风险分析增强——让LLM对用户输入进行二次风险研判，返回JSON结构化结果；'
        '(2) 回复人性化润色——将规则引擎生成的结构化回复交给LLM润色为更自然温暖的表达。'
        '当LLM不可用（未配置API Key或网络异常）时，系统优雅降级到纯规则引擎，'
        '保证核心功能100%可用。'
    )

    doc.add_page_break()

    # ==================== 四、技术实现详述 ====================
    doc.add_heading('四、技术实现详述', level=1)

    doc.add_heading('4.1 后端框架与API设计', level=2)
    doc.add_paragraph(
        '后端基于Flask 3.0构建，提供RESTful API。主应用文件app.py约1400行，'
        '包含40+路由端点。关键API分组如下：'
    )
    api_groups = [
        ('对话核心', 'POST /api/chat', '发送消息，接收AI回复（含意图、风险、建议）'),
        ('对话核心', 'POST /api/chat/stream', 'SSE流式对话（LLM模式下）'),
        ('对话核心', 'GET /api/history/<user_id>', '获取用户对话历史'),
        ('对话核心', 'GET /api/history/memory', '获取上次对话记忆(隐私安全版)'),
        ('知识查询', 'GET /api/knowledge/<fraud_type>', '查询特定诈骗类型详情'),
        ('知识查询', 'GET /api/knowledge/search?q=xxx', '语义搜索诈骗知识'),
        ('风险分析', 'POST /api/analyze', '单独调用风险分析(不生成完整回复)'),
        ('URL检测', 'POST /api/url/check', '检测链接安全性'),
        ('隐私保护', 'GET /api/privacy/status', '查询当前会话隐私保护状态'),
        ('隐私保护', 'POST /api/privacy/clear-session', '主动清除会话隐私数据'),
        ('举报', 'POST /api/report', '提交诈骗举报信息'),
        ('游戏化', 'GET /api/gamification/<user_id>', '查询积分/等级/勋章'),
        ('情景模拟', 'GET /api/scenario/start/<scenario_id>', '开始情景模拟训练'),
        ('管理后台', 'GET /admin', '管理后台界面'),
        ('管理后台', 'GET /api/admin/stats', '系统统计数据'),
        ('认证', 'POST /api/auth/login', '用户登录(JWT)'),
        ('认证', 'POST /api/auth/refresh', '刷新JWT令牌'),
    ]
    add_table(doc, ['分组', '端点', '说明'], api_groups)

    doc.add_heading('4.2 前端交互界面', level=2)
    doc.add_paragraph(
        '前端采用原生HTML+CSS+JS实现，无框架依赖，保证了轻量和兼容性。'
        '主要特点：'
    )
    fe_features = [
        '响应式设计：使用CSS变量+Flexbox布局，支持桌面端和移动端',
        'PWA支持：配置Service Worker和manifest.json，可添加到手机主屏幕',
        '实时对话：AJAX异步通信，流式SSE输出（LLM模式下逐字显示）',
        '侧边栏：历史对话查看（按日期分组，双击回填，🔒隐私标识）',
        '快速操作按钮：高风险时显示"立即报警110""反诈专线96110"；检测到链接时显示"分析链接"',
        '暗色/亮色主题适配：跟随系统偏好自动切换',
        '建议按钮：蓝色渐变底白色文字，悬停动效，视觉鲜明',
    ]
    for f in fe_features:
        doc.add_paragraph(f, style='List Bullet')

    doc.add_heading('4.3 数据库设计', level=2)
    doc.add_paragraph(
        '系统使用SQLAlchemy ORM，默认SQLite，可平滑迁移至PostgreSQL。'
        '核心数据表包括：'
    )
    db_tables = [
        ('users', '用户基本信息', 'id, username, password_hash, created_at, last_login'),
        ('conversations', '对话会话', 'id, user_id, created_at, closed_at, has_privacy_alert'),
        ('messages', '对话消息(加密存储)', 'id, conversation_id, role, content_encrypted, pii_detected'),
        ('privacy_records', '隐私记录(自动清除)', 'id, session_id, pii_type, data_encrypted, created_at'),
        ('reports', '举报记录', 'id, user_id, url/phone/fraud_type, description, status'),
        ('audit_logs', '审计日志', 'id, user_id, action, ip_address, timestamp, details'),
        ('user_scores', '用户积分', 'user_id, points, level, experience, streak_days'),
        ('badges', '用户勋章', 'user_id, badge_id, earned_at'),
    ]
    add_table(doc, ['表名', '说明', '主要字段'], db_tables)

    doc.add_heading('4.4 安全防护机制', level=2)
    doc.add_paragraph('系统从多个层面构建了纵深防御的安全体系：')
    sec_layers = [
        ('传输层', 'HTTPS加密传输（Talisman强制安全头），CSP内容安全策略，X-Frame-Options防点击劫持'),
        ('认证层', 'JWT令牌认证（HMAC-SHA256签名），24小时过期，支持刷新令牌'),
        ('访问控制', 'Flask-Limiter速率限制（30次/分钟/用户），防暴力破解和DDoS'),
        ('数据存储', 'AES-256-GCM加密存储敏感数据，bcrypt哈希用户密码，PII实时加密脱敏'),
        ('隐私保护', '7类PII自动检测+加密替换，每会话独立密钥，会话关闭自动清除'),
        ('审计追踪', '完整的审计日志记录（用户操作+IP+时间戳），支持日志轮转'),
        ('防注入', 'SQLAlchemy ORM参数化查询，防止SQL注入；输出编码防XSS'),
    ]
    add_table(doc, ['安全层面', '防护措施'], sec_layers)

    doc.add_page_break()

    # ==================== 五、部署说明 ====================
    doc.add_heading('五、部署说明', level=1)

    doc.add_heading('5.1 环境要求', level=2)
    env_req = [
        ('操作系统', 'Linux (推荐) / macOS / Windows'),
        ('Python', '3.10+'),
        ('Docker', '24.0+ (容器化部署)'),
        ('Docker Compose', '2.20+ (容器化部署)'),
        ('内存', '≥ 512MB (规则模式) / ≥ 2GB (LLM增强模式)'),
        ('磁盘', '≥ 200MB'),
    ]
    add_table(doc, ['项目', '要求'], env_req)

    doc.add_heading('5.2 Docker一键部署', level=2)
    doc.add_paragraph(
        '系统提供完整的Docker容器化方案，包含docker-compose.yml和Dockerfile。'
        'docker-compose编排包含两个服务：'
    )
    doc.add_paragraph('1. antifraud (应用服务)：基于Python 3.11-slim镜像，通过Gunicorn运行Flask应用，挂载data和logs目录实现数据持久化。')
    doc.add_paragraph('2. nginx (反向代理)：基于nginx:alpine镜像，提供静态文件服务和反向代理，监听80端口。')
    doc.add_paragraph('部署命令：')
    add_code_block(doc, 'docker-compose up -d    # 后台启动所有服务\ndocker-compose logs -f   # 查看实时日志\ndocker-compose down      # 停止服务')

    doc.add_heading('5.3 运行方式', level=2)
    doc.add_paragraph('除Docker部署外，也支持直接Python运行：')
    add_code_block(doc,
        '# 1. 安装依赖\npip install -r requirements.txt\n\n'
        '# 2. 配置环境变量（可选）\ncp .env.example .env\n# 编辑 .env，设置 SECRET_KEY, LLM_API_KEY 等\n\n'
        '# 3. 启动应用\npython run.py\n# 访问 http://localhost:5000'
    )

    doc.add_page_break()

    # ==================== 六、创新点与应用前景 ====================
    doc.add_heading('六、创新点与应用前景', level=1)

    doc.add_heading('6.1 核心创新点', level=2)
    innovations = [
        ('零信任隐私保护架构',
         '首创"对话即加密"的隐私保护模式。7大类PII实时检测、自动加密、会话级密钥隔离。'
         '即使数据库完全泄露，攻击者也无法解密任何用户隐私信息。会话关闭后自动安全擦除，'
         '满足最严格的隐私合规要求。'),
        ('混合智能对话引擎',
         '将规则引擎（确定性、低延迟、100%可用）与LLM（灵活性、人性化、深度理解）融合。'
         '紧急场景（如用户正在转账）由规则引擎毫秒级响应，不依赖LLM。日常咨询由LLM增强回复的'
         '温度和自然度。LLM不可用时无缝降级。'),
        ('多维复合风险研判',
         '融合13类风险规则匹配、对话历史时序分析、5分钟风险衰减窗口、诈骗类型关键词检测、'
         'URL安全性分析，构建了业界最完整的实时风险评估体系。支持4个风险等级×10+场景的'
         '个性化劝阻话术。'),
        ('游戏化反诈教育',
         '将积分、等级、勋章、每日任务、签到、排行榜等成熟游戏化机制引入反诈教育领域，'
         '通过正向激励提升用户学习反诈知识的主动性和持续性。'),
        ('诈骗知识图谱',
         '基于NetworkX构建诈骗类型关联网络，支持7种关系类型的知识推理。'
         '当用户咨询一种诈骗时，系统自动推荐关联诈骗、升级路径和伴随风险。'),
    ]
    for title, desc in innovations:
        doc.add_heading(title, level=3)
        doc.add_paragraph(desc)

    doc.add_heading('6.2 应用场景', level=2)
    scenarios = [
        '社区反诈宣传站：部署在社区服务中心，供居民自助查询和模拟训练',
        '银行网点智能助手：部署在银行大堂，客户转账前可咨询风险',
        '校园安全教育平台：高校安全教育课的互动教学工具',
        '反诈APP对话模块：嵌入现有反诈APP，提供7×24小时智能问答',
        '公安机关辅助工具：减轻96110热线压力，处理常见咨询',
    ]
    for s in scenarios:
        doc.add_paragraph(s, style='List Bullet')

    doc.add_heading('6.3 未来展望', level=2)
    future_items = [
        '多模态输入：支持用户发送截图/语音，OCR/ASR自动识别诈骗信息',
        '知识图谱增强：接入实时诈骗案例数据，自动构建新的诈骗类型节点',
        '联邦学习：多节点联合训练风险识别模型，保护各节点数据隐私',
        '智能外呼劝阻：检测到高风险转账时，主动发起AI外呼劝阻电话',
        '区块链存证：将举报信息和诈骗证据上链存证，形成不可篡改的证据链条',
    ]
    for item in future_items:
        doc.add_paragraph(item, style='List Bullet')

    doc.add_page_break()

    # ==================== 附录A：核心源代码 ====================
    doc.add_heading('附录A：核心源代码', level=1)
    doc.add_paragraph('以下列出系统核心模块的完整源代码，按模块分类展示。')

    # 目录结构
    doc.add_heading('A.0 项目文件结构', level=2)
    structure = """anti-fraud-system/
├── app.py                    # Flask主应用 (1400+行)
├── config.py                 # 中央配置管理
├── run.py                    # 应用启动入口
├── requirements.txt          # Python依赖
├── Dockerfile                # Docker镜像构建
├── docker-compose.yml        # Docker编排
├── nginx.conf                # Nginx配置
├── pytest.ini                # 测试配置
├── .env.example              # 环境变量模板
├── engine/                   # 核心引擎模块
│   ├── intent_recognizer.py  # 意图识别引擎
│   ├── risk_analyzer.py      # 风险分析引擎
│   ├── knowledge_retriever.py# 知识检索引擎
│   ├── response_generator.py # 响应生成器
│   ├── url_analyzer.py       # URL安全分析
│   ├── privacy_guard.py      # 隐私卫士
│   ├── security.py           # 安全模块
│   ├── llm_client.py         # LLM客户端
│   ├── knowledge_graph.py    # 知识图谱
│   ├── database.py           # 数据库管理
│   └── log_setup.py          # 日志配置
├── knowledge_base/           # 知识库数据
│   ├── fraud_types.json      # 诈骗类型定义
│   ├── laws.json             # 法律条文
│   ├── scenarios.json        # 情景模拟
│   └── dialog_patterns.json  # 对话模式
├── gamification/             # 游戏化系统
│   └── gamification.py
├── templates/                # HTML模板
│   ├── index.html            # 主聊天界面
│   └── admin.html            # 管理后台
├── static/                   # 静态资源
│   ├── css/style.css
│   ├── sw.js                 # PWA Service Worker
│   └── icons/icon.svg
├── data/                     # 用户数据(加密存储)
├── logs/                     # 日志文件
└── tests/                    # 单元测试
"""
    add_code_block(doc, structure)

    # 核心源码
    source_files = [
        ('A.1 配置管理 - config.py', 'config.py'),
        ('A.2 意图识别引擎 - intent_recognizer.py', 'engine/intent_recognizer.py'),
        ('A.3 风险分析引擎 - risk_analyzer.py', 'engine/risk_analyzer.py'),
        ('A.4 知识检索引擎 - knowledge_retriever.py', 'engine/knowledge_retriever.py'),
        ('A.5 隐私卫士 - privacy_guard.py', 'engine/privacy_guard.py'),
        ('A.6 LLM客户端 - llm_client.py', 'engine/llm_client.py'),
        ('A.7 安全模块 - security.py', 'engine/security.py'),
        ('A.8 响应生成器 - response_generator.py', 'engine/response_generator.py'),
        ('A.9 知识图谱 - knowledge_graph.py', 'engine/knowledge_graph.py'),
        ('A.10 URL安全分析 - url_analyzer.py', 'engine/url_analyzer.py'),
        ('A.11 数据库管理 - database.py', 'engine/database.py'),
        ('A.12 日志配置 - log_setup.py', 'engine/log_setup.py'),
        ('A.13 游戏化系统 - gamification.py', 'gamification/gamification.py'),
    ]

    for title, path in source_files:
        full_path = os.path.join(BASE_DIR, path)
        if os.path.exists(full_path):
            doc.add_heading(title, level=2)
            add_code_from_file(doc, full_path)
            doc.add_page_break()
        else:
            doc.add_heading(title, level=2)
            doc.add_paragraph(f"[文件不存在: {full_path}]")

    # Docker files combined
    doc.add_heading('A.14 Docker部署配置', level=2)
    doc.add_heading('Dockerfile', level=3)
    docker_path = os.path.join(BASE_DIR, 'Dockerfile')
    if os.path.exists(docker_path):
        add_code_from_file(doc, docker_path)
    doc.add_heading('docker-compose.yml', level=3)
    compose_path = os.path.join(BASE_DIR, 'docker-compose.yml')
    if os.path.exists(compose_path):
        add_code_from_file(doc, compose_path)
    doc.add_heading('nginx.conf', level=3)
    nginx_path = os.path.join(BASE_DIR, 'nginx.conf')
    if os.path.exists(nginx_path):
        add_code_from_file(doc, nginx_path)
    doc.add_page_break()

    # Flask主应用完整源码
    doc.add_heading('A.15 Flask主应用 - app.py (完整源码)', level=2)
    app_path = os.path.join(BASE_DIR, 'app.py')
    if os.path.exists(app_path):
        add_code_from_file(doc, app_path)
        doc.add_paragraph('(以上为 app.py 完整源代码，共1400+行)')

    doc.add_page_break()

    # ==================== 附录B：知识库数据设计 ====================
    doc.add_heading('附录B：知识库数据设计', level=1)

    doc.add_heading('B.1 诈骗类型数据结构 (fraud_types.json)', level=2)
    doc.add_paragraph('每种诈骗类型包含以下字段：')
    fraud_fields = [
        ('id', '诈骗类型唯一标识'),
        ('aliases', '别名列表（用于意图识别匹配）'),
        ('keywords', '关键词列表（用于风险特征匹配）'),
        ('description', '诈骗类型描述'),
        ('risk_level', '风险等级'),
        ('common_patterns', '常见手法模式'),
        ('typical_dialogs', '典型诈骗话术'),
        ('psychological_tactics', '心理操控手法'),
        ('prevention_advice', '防范建议列表'),
        ('victim_analysis', '受害者群体分析(target_groups, age_range)'),
        ('case_studies', '典型案例（标题、过程、教训）'),
        ('intervention_templates', '劝阻话术模板(按风险等级)'),
        ('reporting_guidance', '举报指引'),
        ('legal_references', '法律条文引用'),
        ('related_frauds', '关联诈骗类型'),
        ('statistics', '统计数据（案发数量、平均损失金额等）'),
    ]
    add_table(doc, ['字段', '说明'], fraud_fields)

    doc.add_paragraph('知识库目前包含9种诈骗类型，28个真实案例，覆盖2024-2025年最新诈骗手法。')

    doc.add_heading('B.2 对话模式定义 (dialog_patterns.json)', level=2)
    doc.add_paragraph(
        '定义14种意图的触发关键词和18类响应模板。'
        '每种意图包含关键词列表，支持精确匹配和同义词扩展。'
        '响应模板支持动态变量替换（如{risk_level}, {fraud_type}, {intervention}等）。'
    )

    # ==================== 结束页 ====================
    doc.add_page_break()
    doc.add_paragraph()
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run('— 文档结束 —')
    run.font.size = Pt(14)
    run.font.color.rgb = RGBColor(0x5f, 0x63, 0x68)

    # ==================== 保存 ====================
    output_path = os.path.join(BASE_DIR, '多模态智能反诈对话系统_RAICOM参赛作品.docx')
    doc.save(output_path)
    print(f'[OK] 文档已生成: {output_path}')
    return output_path


if __name__ == '__main__':
    generate()
