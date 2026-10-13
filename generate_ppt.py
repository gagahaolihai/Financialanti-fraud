"""生成项目介绍PPT - 针对RAICOM方向三评分细则优化"""
from pptx import Presentation
from pptx.util import Inches, Pt, Cm, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# === 颜色方案 ===
PRIMARY = RGBColor(0xC6, 0x28, 0x28)
PRIMARY_DARK = RGBColor(0x8B, 0x00, 0x00)
ACCENT_BLUE = RGBColor(0x15, 0x65, 0xC0)
ACCENT_GOLD = RGBColor(0xF5, 0x7C, 0x00)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLACK = RGBColor(0x33, 0x33, 0x33)
GRAY = RGBColor(0x66, 0x66, 0x66)
LIGHT_GRAY = RGBColor(0xF0, 0xF0, 0xF0)
LIGHT_RED = RGBColor(0xFF, 0xEB, 0xEE)
LIGHT_BLUE = RGBColor(0xE3, 0xF2, 0xFD)
LIGHT_GREEN = RGBColor(0xE8, 0xF5, 0xE9)
DARK_BG = RGBColor(0x1A, 0x1A, 0x2E)
GREEN = RGBColor(0x2E, 0x7D, 0x32)
PURPLE = RGBColor(0x7B, 0x1F, 0xA2)

FONT_TITLE = '微软雅黑'
FONT_BODY = '微软雅黑'

SCORE_COLORS = {
    '完成度': PRIMARY,
    '创新性': ACCENT_GOLD,
    '实用性': ACCENT_BLUE,
    '成熟度': GREEN,
    '安全性': PURPLE,
}


def add_bg(slide, color):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = color


def add_textbox(slide, left, top, width, height, text, font_size=14, bold=False,
                color=BLACK, align=PP_ALIGN.LEFT, font_name=FONT_BODY):
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.bold = bold
    p.font.color.rgb = color
    p.font.name = font_name
    p.alignment = align
    return tf


def add_multiline(slide, left, top, width, height, lines, font_size=13, color=BLACK):
    txBox = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, item in enumerate(lines):
        if isinstance(item, str):
            text, bold, c = item, False, color
        else:
            text = item[0]
            bold = item[1] if len(item) > 1 else False
            c = item[2] if len(item) > 2 else color
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = text
        p.font.size = Pt(font_size)
        p.font.bold = bold
        p.font.color.rgb = c
        p.font.name = FONT_BODY
        p.space_after = Pt(3)
    return tf


def add_rect(slide, left, top, width, height, color, border=None):
    shape = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    if border:
        shape.line.color.rgb = border
        shape.line.width = Pt(1)
    else:
        shape.line.fill.background()
    return shape


def add_circle(slide, left, top, size, color):
    shape = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(left), Inches(top), Inches(size), Inches(size))
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    return shape


def add_top_bar(slide, title_text, subtitle_text=None, score_tag=None):
    add_rect(slide, 0, 0, 13.333, 1.3, PRIMARY)
    add_rect(slide, 0, 1.3, 13.333, 0.05, ACCENT_GOLD)
    add_textbox(slide, 0.8, 0.12, 10.5, 0.65, title_text, font_size=28, bold=True, color=WHITE, font_name=FONT_TITLE)
    if subtitle_text:
        add_textbox(slide, 0.8, 0.72, 10.5, 0.4, subtitle_text, font_size=13, color=RGBColor(0xFF, 0xCD, 0xD2))
    if score_tag:
        tag_w = 2.0
        tag = add_rect(slide, 10.8, 0.25, 2.0, 0.55, ACCENT_GOLD)
        tf = tag.text_frame
        p = tf.paragraphs[0]
        p.text = score_tag
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = WHITE
        p.font.name = FONT_BODY
        p.alignment = PP_ALIGN.CENTER


def add_footer(slide, page_num):
    add_textbox(slide, 11.5, 7.1, 1.5, 0.3, str(page_num), font_size=9, color=GRAY, align=PP_ALIGN.RIGHT)
    add_textbox(slide, 0.5, 7.1, 4, 0.3, 'RAICOM CAIP 智能算法及应用赛项 — 金融反诈智能守护', font_size=8, color=GRAY)


def add_card(slide, left, top, width, height, title, desc, icon_color=None, tag=None):
    if icon_color is None:
        icon_color = PRIMARY
    add_rect(slide, left, top, width, height, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
    add_rect(slide, left, top, width, 0.06, icon_color)
    add_textbox(slide, left + 0.25, top + 0.15, width - 0.5, 0.3, title, font_size=14, bold=True, color=BLACK)
    add_textbox(slide, left + 0.25, top + 0.5, width - 0.5, height - 0.65, desc, font_size=11, color=GRAY)
    if tag:
        tag_shape = add_rect(slide, left + width - 1.05, top + 0.12, 0.8, 0.25, icon_color)
        tf = tag_shape.text_frame
        p = tf.paragraphs[0]
        p.text = tag
        p.font.size = Pt(8)
        p.font.color.rgb = WHITE
        p.font.name = FONT_BODY
        p.alignment = PP_ALIGN.CENTER


def add_score_badge(slide, left, top, label, score):
    """添加评分维度标签"""
    color = SCORE_COLORS.get(label, PRIMARY)
    badge = add_rect(slide, left, top, 1.3, 0.4, color)
    tf = badge.text_frame
    p = tf.paragraphs[0]
    p.text = f'{label} {score}分'
    p.font.size = Pt(9)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.font.name = FONT_BODY
    p.alignment = PP_ALIGN.CENTER


# ============================================================
# Slide 1: 封面
# ============================================================
slide1 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide1, DARK_BG)
add_rect(slide1, 0, 0, 13.333, 0.12, PRIMARY)
add_rect(slide1, 0, 7.38, 13.333, 0.12, PRIMARY)
add_rect(slide1, 0, 4.5, 13.333, 3.0, RGBColor(0x22, 0x22, 0x3E))
add_rect(slide1, 1.5, 1.5, 0.07, 2.5, ACCENT_GOLD)

add_textbox(slide1, 2.0, 1.55, 10, 1.0, '多模态智能反诈对话系统', font_size=44, bold=True, color=WHITE, font_name=FONT_TITLE)
add_textbox(slide1, 2.0, 2.5, 10, 0.55, 'Multi-modal Intelligent Anti-Fraud Dialogue System', font_size=17, color=RGBColor(0xAA, 0xAA, 0xAA))
add_textbox(slide1, 2.0, 3.35, 10, 0.45, '面向反诈教育的智能客服 — 方向三', font_size=20, color=ACCENT_GOLD, bold=True)
add_textbox(slide1, 2.0, 3.85, 10, 0.35, 'RAICOM 睿抗机器人开发者大赛 · CAIP强脑赛道 · 智能算法及应用赛项', font_size=14, color=RGBColor(0xCC, 0xCC, 0xCC))
add_textbox(slide1, 2.0, 5.2, 10, 0.4, '以游戏化交互+智能研判，构建多模态反诈教育对话系统', font_size=14, color=RGBColor(0x99, 0x99, 0x99))
add_textbox(slide1, 2.0, 5.8, 10, 0.35, '2026年6月', font_size=12, color=GRAY)

# ============================================================
# Slide 2: 评分维度总览
# ============================================================
slide2 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide2, WHITE)
add_top_bar(slide2, '评分维度总览 — 我们的应答策略', 'SCORING ALIGNMENT MAP')

dims = [
    ('完成度', '20分', '知识库 · 意图识别 · 风险劝阻\n举报功能 · 游戏化 · 泛终端适配', PRIMARY,
     ['结构化反诈知识库，5类骗局+详细知识', '规则引擎+上下文意图识别', '风险劝阻+一键举报+URL研判', '积分/勋章/闯关+情景模拟', '响应式网页+移动端适配']),
    ('创新性', '20分', '算法 · 架构 · 交互方式的\n独创性与创新性', ACCENT_GOLD,
     ['8引擎模块化协同架构', '多模态融合(文本+URL+知识图谱)', '游戏化反诈教育闭环', '知识图谱驱动的诈骗关联推理']),
    ('实用性', '20分', '落地可行性 · 工程化实现\n业务适配度', ACCENT_BLUE,
     ['真实可运行的Flask Web应用', '完整的API体系与前端交互', '覆盖10+常见诈骗类型', '对话+知识库+情景三位一体']),
    ('成熟度', '20分', '系统稳定性 · 可扩展性\n代码与文档规范性', GREEN,
     ['模块化8引擎架构，松耦合可插拔', 'python-docx自动生成参赛文档', '审计日志+结构化数据管理', '演示视频+配音讲解稿完整配套']),
    ('安全性', '20分', '全生命周期数据加密\n隐私保护 + 传输安全', PURPLE,
     ['AES-256-GCM端到端加密', 'PII实时检测与自动脱敏', 'JWT Token身份认证', '审计日志+隐私状态面板']),
]

for i, (title, score, desc, color, points) in enumerate(dims):
    y = 1.7 + i * 1.08
    # 左侧标签
    add_rect(slide2, 0.3, y, 2.0, 0.9, color)
    add_textbox(slide2, 0.3, y + 0.08, 2.0, 0.4, title, font_size=18, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_textbox(slide2, 0.3, y + 0.48, 2.0, 0.35, f'占 {score}', font_size=12, color=RGBColor(0xFF, 0xFF, 0xFF), align=PP_ALIGN.CENTER)
    # 描述
    add_textbox(slide2, 2.5, y + 0.05, 3.0, 0.8, desc, font_size=11, color=GRAY)
    # 我们的实现
    for j, pt in enumerate(points):
        x = 6.0 + j * 1.85
        add_rect(slide2, x, y + 0.1, 1.7, 0.7, LIGHT_GRAY if j % 2 == 0 else WHITE, border=RGBColor(0xE8, 0xE8, 0xE8))
        add_textbox(slide2, x + 0.1, y + 0.15, 1.5, 0.6, f'✓ {pt}', font_size=9, color=BLACK)

add_footer(slide2, 2)

# ============================================================
# Slide 3: 项目背景
# ============================================================
slide3 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide3, WHITE)
add_top_bar(slide3, '项目背景 — 金融反诈刻不容缓', 'PROJECT BACKGROUND')

cards = [
    ('电信诈骗年案额', '超千亿元', '公安部统计数据', '电信网络诈骗已成为\n第一大刑事犯罪类型'),
    ('受害群体特征', '老年+学生\n为高危人群', '70岁以上、在校大学生\n为诈骗重灾区', '老年人易信权威、学生\n缺乏社会经验'),
    ('诈骗手段演进', '每月新增\n数百种变种', '骗术迭代周期＜30天\n对抗手法持续升级', '传统宣传教育方式\n覆盖面有限、效果滞后'),
    ('政策导向', '国家反诈中心\n全面推进', '《反电信网络诈骗法》\n2022年正式施行', 'AI反诈技术被列为\n重点发展方向'),
]
for i, (title, value, src, detail) in enumerate(cards):
    x = 0.4 + i * 3.2
    add_rect(slide3, x, 1.7, 3.0, 3.2, WHITE, border=RGBColor(0xE8, 0xE8, 0xE8))
    add_rect(slide3, x, 1.7, 3.0, 0.06, PRIMARY)
    add_textbox(slide3, x + 0.2, 1.9, 2.6, 0.35, title, font_size=13, color=GRAY)
    add_textbox(slide3, x + 0.2, 2.3, 2.6, 0.8, value, font_size=20, bold=True, color=PRIMARY)
    add_textbox(slide3, x + 0.2, 3.5, 2.6, 0.4, src, font_size=9, color=GRAY)
    add_rect(slide3, x + 0.2, 4.05, 2.6, 0.01, RGBColor(0xE0, 0xE0, 0xE0))
    add_textbox(slide3, x + 0.2, 4.2, 2.6, 0.6, detail, font_size=10, color=GRAY)

add_multiline(slide3, 0.6, 5.2, 12, 1.5, [
    ('赛题要求（方向三）：面向学生群体及泛个人用户的反诈科普与实时风险劝阻场景，开发具备游戏化交互+智能研判功能的多模态智能反诈对话系统', True, PRIMARY),
    ('以多轮智能对话形式普及刷单返利、游戏交易、冒充公检法、虚假投资、校园贷等常见骗局的防范知识', False, BLACK),
    ('提供反诈知识普及、风险行为实时劝阻、可疑链接/内容一键举报、风险场景智能研判等全流程交互服务', False, BLACK),
], font_size=13)

add_footer(slide3, 3)

# ============================================================
# Slide 4: 系统架构总览
# ============================================================
slide4 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide4, WHITE)
add_top_bar(slide4, '系统架构总览 — 8引擎协同驱动', 'SYSTEM ARCHITECTURE', score_tag='创新性 20分')

# 三层架构
# 用户交互层
add_rect(slide4, 0.5, 1.7, 12.3, 0.65, LIGHT_RED)
add_textbox(slide4, 0.5, 1.8, 12.3, 0.35, '用户交互层 — Web对话界面 · 多模态输入(文本+URL) · 响应式适配网页/移动端', font_size=13, bold=True, color=PRIMARY, align=PP_ALIGN.CENTER)

# 8引擎核心层
add_textbox(slide4, 0.5, 2.6, 12, 0.3, '核心引擎层（8大模块协同）', font_size=13, bold=True, color=BLACK)
engines = [
    ('意图识别引擎', '关键词+句式\n+上下文NLU', LIGHT_RED),
    ('风险分析引擎', '多维度\n风险评估', RGBColor(0xFF, 0xCD, 0xD2)),
    ('知识检索引擎', '结构化知识库\n匹配与推理', LIGHT_BLUE),
    ('隐私守护引擎', 'PII检测\nAES加密', RGBColor(0xE3, 0xF2, 0xFD)),
    ('URL分析引擎', '钓鱼链接\n特征检测', LIGHT_GREEN),
    ('LLM客户端', '大语言模型\n对话接入', RGBColor(0xE8, 0xF5, 0xE9)),
    ('响应生成引擎', '多模态输出\n整合与优化', RGBColor(0xFF, 0xF3, 0xE0)),
    ('知识图谱引擎', '诈骗关联\n溯源推理', RGBColor(0xF3, 0xE5, 0xF5)),
]
for i, (name, desc, bg) in enumerate(engines):
    x = 0.3 + i * 1.6
    add_rect(slide4, x, 3.0, 1.45, 0.82, bg, border=RGBColor(0xDD, 0xDD, 0xDD))
    add_textbox(slide4, x + 0.05, 3.05, 1.35, 0.3, name, font_size=10, bold=True, color=BLACK, align=PP_ALIGN.CENTER)
    add_textbox(slide4, x + 0.05, 3.38, 1.35, 0.4, desc, font_size=9, color=GRAY, align=PP_ALIGN.CENTER)

# 数据层
add_rect(slide4, 0.5, 4.1, 12.3, 0.65, LIGHT_BLUE)
add_textbox(slide4, 0.5, 4.2, 12.3, 0.35, '数据与存储层 — SQLAlchemy ORM · SQLite数据库 · 结构化知识库 · 情景库 · 举报记录 · 用户数据', font_size=13, bold=True, color=ACCENT_BLUE, align=PP_ALIGN.CENTER)

# 安全层
add_rect(slide4, 0.5, 5.0, 12.3, 0.65, RGBColor(0xF3, 0xE5, 0xF5))
add_textbox(slide4, 0.5, 5.1, 12.3, 0.35, '安全与合规层 — AES-256-GCM加密 · JWT认证 · PII脱敏 · 审计日志 · HTTPS传输', font_size=13, bold=True, color=PURPLE, align=PP_ALIGN.CENTER)

# 底部三大特色
features = [
    ('多模态融合', '文本对话 → URL分析 →\n知识图谱推理 → 情景模拟\n四维一体，覆盖反诈全场景'),
    ('游戏化驱动', '积分·等级·勋章·闯关\n情景模拟沉浸式训练\n从"被动学"到"主动练"'),
    ('隐私优先', 'AES-256-GCM加密存储\nPII实时检测脱敏\n全生命周期数据保护'),
]
for i, (title, desc) in enumerate(features):
    x = 0.5 + i * 4.2
    add_rect(slide4, x, 6.0, 3.9, 1.2, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
    add_textbox(slide4, x + 0.2, 6.08, 3.5, 0.3, title, font_size=14, bold=True, color=PRIMARY if i == 0 else (ACCENT_GOLD if i == 1 else PURPLE))
    add_textbox(slide4, x + 0.2, 6.4, 3.5, 0.7, desc, font_size=10, color=GRAY)

add_footer(slide4, 4)

# ============================================================
# Slide 5: 完成度(一) — 知识库 + 意图识别 (10分)
# ============================================================
slide5 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide5, WHITE)
add_top_bar(slide5, '完成度(一)：反诈知识库构建 + 意图识别与规则引擎', 'KNOWLEDGE BASE & INTENT RECOGNITION', score_tag='完成度 10/20分')

# 左：知识库
add_rect(slide5, 0.5, 1.7, 6.0, 5.3, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
add_rect(slide5, 0.5, 1.7, 6.0, 0.06, PRIMARY)
add_textbox(slide5, 0.8, 1.85, 5.5, 0.3, '结构化反诈知识库（完成度 5分）', font_size=16, bold=True, color=PRIMARY)
add_multiline(slide5, 0.8, 2.3, 5.4, 4.5, [
    ('评分要求：', True, PRIMARY),
    ('以结构化、半结构化或规则化形式组织骗局特征、', False, GRAY),
    ('手法、典型案例、防范建议及法律法规等内容', False, GRAY),
    ('', False, BLACK),
    ('我们的实现：', True, GREEN),
    ('', False, BLACK),
    ('1. 结构化知识组织', True, BLACK),
    ('  ├ 5大骗局类型：刷单返利 · 游戏交易 · 冒充公检法 · 虚假投资 · 校园贷', False, GRAY),
    ('  ├ 每类包含：诈骗手法拆解 · 常见话术 · 典型案例 · 识别要点 · 防范建议 · 法律法规', False, GRAY),
    ('  └ 知识存储：JSON结构化文件 + SQLite数据库双模式', False, GRAY),
    ('', False, BLACK),
    ('2. 知识检索机制', True, BLACK),
    ('  ├ 关键词匹配 + 语义相似度计算', False, GRAY),
    ('  ├ LLM增强的知识生成与推理', False, GRAY),
    ('  └ 支持新增骗局快速接入（扩展JSON即可）', False, GRAY),
    ('', False, BLACK),
    ('3. 知识库与对话联动', True, BLACK),
    ('  └ 用户在知识库点击任意类型 → 系统自动在聊天区呈现详细知识点', False, GRAY),
], font_size=11)

# 右：意图识别
add_rect(slide5, 6.8, 1.7, 6.0, 5.3, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
add_rect(slide5, 6.8, 1.7, 6.0, 0.06, ACCENT_BLUE)
add_textbox(slide5, 7.1, 1.85, 5.5, 0.3, '意图识别与规则引擎（完成度 5分）', font_size=16, bold=True, color=ACCENT_BLUE)
add_multiline(slide5, 7.1, 2.3, 5.4, 4.5, [
    ('评分要求：', True, PRIMARY),
    ('设计规则引擎或轻量级意图识别模块，依据关键词、', False, GRAY),
    ('句式、上下文识别用户意图并匹配知识内容', False, GRAY),
    ('', False, BLACK),
    ('我们的实现：', True, GREEN),
    ('', False, BLACK),
    ('1. 意图识别引擎', True, BLACK),
    ('  ├ 关键词匹配：提取刷单/返利/投资/警察等核心词', False, GRAY),
    ('  ├ 句式分析：识别疑问句/陈述句/紧急求助句式', False, GRAY),
    ('  ├ 上下文建模：多轮对话状态追踪', False, GRAY),
    ('  └ 意图分类：知识查询 · 风险识别 · 举报 · 法律咨询等', False, GRAY),
    ('', False, BLACK),
    ('2. 规则引擎路由', True, BLACK),
    ('  ├ 风险关键词 → 风险分析引擎 → 劝阻话术', False, GRAY),
    ('  ├ 链接检测 → URL分析引擎 → 安全报告', False, GRAY),
    ('  ├ 法律关键词 → 法律知识检索 → 法律建议', False, GRAY),
    ('  └ 知识查询 → 知识库匹配 → 结构化回答', False, GRAY),
    ('', False, BLACK),
    ('3. 快速接入机制', True, BLACK),
    ('  └ JSON配置驱动，新增骗局类型无需修改核心代码', False, GRAY),
], font_size=11)

add_footer(slide5, 5)

# ============================================================
# Slide 6: 完成度(二) — 风险劝阻 + 举报功能 (5分)
# ============================================================
slide6 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide6, WHITE)
add_top_bar(slide6, '完成度(二)：风险行为劝阻 + 可疑链接举报', 'RISK INTERVENTION & REPORT SYSTEM', score_tag='完成度 5/20分')

# 左：风险劝阻
add_rect(slide6, 0.5, 1.7, 6.0, 5.3, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
add_rect(slide6, 0.5, 1.7, 6.0, 0.06, PRIMARY)
add_textbox(slide6, 0.8, 1.85, 5.5, 0.3, '风险行为实时劝阻', font_size=16, bold=True, color=PRIMARY)

add_multiline(slide6, 0.8, 2.3, 5.4, 4.5, [
    ('评分要求：', True, PRIMARY),
    ('具备风险行为实时劝阻能力，结合风险特征规则对疑似', False, GRAY),
    ('受骗行为进行研判，输出场景化、个性化劝阻话术', False, GRAY),
    ('', False, BLACK),
    ('我们的实现：', True, GREEN),
    ('', False, BLACK),
    ('1. 多维度风险研判', True, BLACK),
    ('  ├ 行为层面：用户描述中的"已转账""加好友""投资"等关键行为词', False, GRAY),
    ('  ├ 场景层面：刷单返利 · 杀猪盘 · 冒充公检法等场景匹配', False, GRAY),
    ('  ├ 金额层面：涉及金额自动触发高风险标记', False, GRAY),
    ('  └ 人群层面：老年用户自动切换大白话劝阻模式', False, GRAY),
    ('', False, BLACK),
    ('2. 场景化劝阻话术', True, BLACK),
    ('  ├ 一般风险 → 风险提示 + 防骗知识 + 建议核实', False, GRAY),
    ('  ├ 高风险 → 明确劝阻 + 话术拆解 + 法律后果说明', False, GRAY),
    ('  └ 紧急场景 → 情绪安抚 + 止损建议 + 报警引导', False, GRAY),
    ('', False, BLACK),
    ('3. 适老化设计', True, BLACK),
    ('  └ 自动检测用户年龄 → 切换通俗语言 → 大字版提示 → 耐心重复关键信息', False, GRAY),
], font_size=11)

# 右：举报功能
add_rect(slide6, 6.8, 1.7, 6.0, 5.3, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
add_rect(slide6, 6.8, 1.7, 6.0, 0.06, ACCENT_BLUE)
add_textbox(slide6, 7.1, 1.85, 5.5, 0.3, '可疑链接/内容一键举报', font_size=16, bold=True, color=ACCENT_BLUE)

add_multiline(slide6, 7.1, 2.3, 5.4, 4.5, [
    ('评分要求：', True, PRIMARY),
    ('提供可疑链接/内容一键举报入口，通过URL特征匹配、', False, GRAY),
    ('关键词黑名单等规则进行初步研判与反馈', False, GRAY),
    ('', False, BLACK),
    ('我们的实现：', True, GREEN),
    ('', False, BLACK),
    ('1. 举报入口与流程', True, BLACK),
    ('  ├ 侧边栏一键进入举报中心', False, GRAY),
    ('  ├ 表单：URL输入 + 描述信息 + 一键提交', False, GRAY),
    ('  └ 提交后即时反馈研判结果', False, GRAY),
    ('', False, BLACK),
    ('2. URL智能研判', True, BLACK),
    ('  ├ 域名特征库：可疑TLD、变形域名、相似域名检测', False, GRAY),
    ('  ├ 关键词黑名单：login/verify/secure/bank等钓鱼常用词', False, GRAY),
    ('  ├ 结构分析：异常端口、IP直连、多层重定向检测', False, GRAY),
    ('  └ 综合风险评级：安全 · 可疑 · 高危 · 恶意', False, GRAY),
    ('', False, BLACK),
    ('3. 举报数据处理', True, BLACK),
    ('  ├ 记录持久化存储 + 审计日志', False, GRAY),
    ('  ├ 举报积分奖励（游戏化联动）', False, GRAY),
    ('  └ 用户可查看举报历史', False, GRAY),
], font_size=11)

add_footer(slide6, 6)

# ============================================================
# Slide 7: 完成度(三) — 游戏化交互 + 泛终端适配 (5分)
# ============================================================
slide7 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide7, WHITE)
add_top_bar(slide7, '完成度(三)：游戏化交互 + 情景模拟 + 泛终端适配', 'GAMIFICATION & SCENARIO SIMULATION', score_tag='完成度 5/20分')

# 游戏化体系
add_rect(slide7, 0.4, 1.7, 4.0, 5.4, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
add_rect(slide7, 0.4, 1.7, 4.0, 0.06, ACCENT_GOLD)
add_textbox(slide7, 0.7, 1.85, 3.4, 0.3, '游戏化激励体系', font_size=15, bold=True, color=ACCENT_GOLD)

add_multiline(slide7, 0.7, 2.3, 3.4, 4.5, [
    ('积分系统', True, BLACK),
    ('  ● 签到获取积分', False, GRAY),
    ('  ● 情景模拟通关奖励', False, GRAY),
    ('  ● 举报贡献积分', False, GRAY),
    ('', False, BLACK),
    ('等级体系（Lv.1 ~ Lv.10）', True, BLACK),
    ('  ● 经验值累积升级', False, GRAY),
    ('  ● 等级名称递进：反诈新兵→', False, GRAY),
    ('     火眼金睛→守护先锋→', False, GRAY),
    ('     反诈达人→安全卫士', False, GRAY),
    ('', False, BLACK),
    ('成就勋章', True, BLACK),
    ('  ● 初次举报 / 连续签到', False, GRAY),
    ('  ● 情景满分 / 知识达人', False, GRAY),
    ('  ● 安全守护者 / 反诈先锋', False, GRAY),
    ('', False, BLACK),
    ('排行榜', True, BLACK),
    ('  ● 实时用户积分排名', False, GRAY),
    ('  ● 勋章数量展示', False, GRAY),
    ('  ● 个人排名高亮', False, GRAY),
    ('', False, BLACK),
    ('每日任务', True, BLACK),
    ('  ● 每日签到打卡', False, GRAY),
    ('  ● 每日知识学习推送', False, GRAY),
], font_size=10)

# 情景模拟
add_rect(slide7, 4.7, 1.7, 4.3, 5.4, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
add_rect(slide7, 4.7, 1.7, 4.3, 0.06, PRIMARY)
add_textbox(slide7, 5.0, 1.85, 3.7, 0.3, '情景模拟训练（亮点）', font_size=15, bold=True, color=PRIMARY)

add_multiline(slide7, 5.0, 2.3, 3.7, 4.5, [
    ('评分要求：融入积分、勋章、闯关、', True, PRIMARY),
    ('情景模拟等游戏化元素，鼓励设计', False, GRAY),
    ('典型骗局情景模拟模块', False, GRAY),
    ('', False, BLACK),
    ('5大情景训练：', True, BLACK),
    ('  ● 刷单陷阱（★☆☆ 入门）', False, GRAY),
    ('  ● 游戏交易诈骗（★☆☆ 入门）', False, GRAY),
    ('  ● 虚假投资理财（★★☆ 进阶）', False, GRAY),
    ('  ● 校园贷危局（★★☆ 进阶）', False, GRAY),
    ('  ● 冒充公检法（★★★ 挑战）', False, GRAY),
    ('', False, BLACK),
    ('训练流程（每情景3步递进）：', True, BLACK),
    ('  1. NPC模拟骗子发消息', False, GRAY),
    ('  2. 用户从3个选项中选择应对', False, GRAY),
    ('  3. 即时反馈：✅/❌ + 评分 + 解释', False, GRAY),
    ('  4. 进入下一步 → 通关评等级', False, GRAY),
    ('', False, BLACK),
    ('评级体系：', True, BLACK),
    ('  🛡️ 反诈达人(≥80%)  ⚠️ 还需警惕', False, GRAY),
    ('  (≥60%)  ❌ 需要提高(<60%)', False, GRAY),
], font_size=10)

# 泛终端适配
add_rect(slide7, 9.3, 1.7, 3.6, 5.4, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
add_rect(slide7, 9.3, 1.7, 3.6, 0.06, GREEN)
add_textbox(slide7, 9.6, 1.85, 3.0, 0.3, '泛终端适配', font_size=15, bold=True, color=GREEN)

add_multiline(slide7, 9.6, 2.3, 3.0, 4.5, [
    ('评分要求：适配网页、小程序、', True, PRIMARY),
    ('移动端等泛终端接入', False, GRAY),
    ('', False, BLACK),
    ('当前适配：', True, BLACK),
    ('  ✓ 桌面Web端（主要平台）', False, GRAY),
    ('  ✓ 响应式布局，支持平板浏览', False, GRAY),
    ('  ✓ RESTful API设计，便于移动端', False, GRAY),
    ('    接入', False, GRAY),
    ('', False, BLACK),
    ('扩展规划：', True, BLACK),
    ('  ○ 移动端PWA渐进式应用', False, GRAY),
    ('  ○ 微信小程序版本', False, GRAY),
    ('  ○ 语音交互接口（ASR+TTS）', False, GRAY),
    ('', False, BLACK),
    ('技术保障：', True, BLACK),
    ('  ● 前后端分离，API标准化', False, GRAY),
    ('  ● JWT无状态认证，跨端通用', False, GRAY),
    ('  ● 低延迟响应设计', False, GRAY),
    ('  ● CDN静态资源加速', False, GRAY),
], font_size=10)

add_footer(slide7, 7)

# ============================================================
# Slide 8: 创新性 (20分)
# ============================================================
slide8 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide8, WHITE)
add_top_bar(slide8, '创新性 — 算法 · 架构 · 交互方式的独创性', 'INNOVATION HIGHLIGHTS', score_tag='创新性 20分')

innovations = [
    ('多模态融合架构', '文本对话、URL链接分析、结构化知识库检索、知识图谱推理四项能力在同一对话系统中深度融合。区别于传统单一文本问答，本系统在用户输入URL时自动触发链接分析，在讨论诈骗类型时自动调度知识图谱关联查询，实现"一次对话、多维响应"。', '架构创新'),
    ('8引擎模块化协同', '独创的"意图识别→风险分析→知识检索→URL分析→LLM对话→响应生成→隐私守护→知识图谱"八引擎流水线。各引擎松耦合、可独立升级，通过统一调度总线协同工作。新增反诈能力只需添加新引擎模块，无需重构。', '架构创新'),
    ('游戏化反诈教育闭环', '将"学知识→练情景→获积分→升等级→得勋章→查排名"设计为完整的游戏化闭环。突破了传统反诈宣传"发传单、贴海报"的被动模式，通过情景模拟闯关让用户从"被动接收"变为"主动参与"，建立沉浸式学习体验。', '交互创新'),
    ('知识图谱驱动的关联推理', '构建诈骗类型关联网络，支持"刷单诈骗和杀猪盘有什么关联"等跨类型推理查询。不同于简单的关键词匹配，知识图谱能揭示不同诈骗类型之间的演化关系、共同特征和溯源路径。', '算法创新'),
    ('适老化智能对话', '自动检测用户年龄，动态调整语言风格、文字大小和劝阻策略。70岁以上用户触发"大白话模式"，用通俗语言替代专业术语，重复关键风险信息，耐心引导操作。', '交互创新'),
    ('隐私优先的对话架构', '将隐私保护从"附加功能"提升为"架构级设计"。PII实时检测在消息发送前即完成脱敏，AES-256-GCM加密覆盖存储全生命周期，隐私状态面板让用户可视化了解数据保护状态。', '设计创新'),
]

for i, (title, desc, tag) in enumerate(innovations):
    row = i // 2
    col = i % 2
    x = 0.4 + col * 6.3
    y = 1.7 + row * 1.85
    tag_color = PRIMARY if '架构' in tag else (ACCENT_GOLD if '交互' in tag else (ACCENT_BLUE if '算法' in tag else GREEN))
    add_rect(slide8, x, y, 6.1, 1.7, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
    add_rect(slide8, x, y, 0.06, 1.7, tag_color)
    # tag
    tag_shape = add_rect(slide8, x + 4.8, y + 0.1, 1.1, 0.3, tag_color)
    tf = tag_shape.text_frame
    p = tf.paragraphs[0]
    p.text = tag
    p.font.size = Pt(8)
    p.font.color.rgb = WHITE
    p.font.name = FONT_BODY
    p.alignment = PP_ALIGN.CENTER
    add_textbox(slide8, x + 0.25, y + 0.1, 4.5, 0.3, title, font_size=14, bold=True, color=BLACK)
    add_textbox(slide8, x + 0.25, y + 0.5, 5.6, 1.1, desc, font_size=10, color=GRAY)

add_footer(slide8, 8)

# ============================================================
# Slide 9: 实用性 (20分)
# ============================================================
slide9 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide9, WHITE)
add_top_bar(slide9, '实用性 — 落地可行性与工程化实现', 'PRACTICALITY & ENGINEERING', score_tag='实用性 20分')

# 左侧大卡片
add_rect(slide9, 0.4, 1.7, 6.0, 5.4, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
add_rect(slide9, 0.4, 1.7, 6.0, 0.06, ACCENT_BLUE)
add_textbox(slide9, 0.7, 1.85, 5.4, 0.3, '真实可运行系统', font_size=16, bold=True, color=ACCENT_BLUE)

add_multiline(slide9, 0.7, 2.3, 5.4, 4.5, [
    ('我们交付的不只是设计方案，更是完整可运行的系统：', True, BLACK),
    ('', False, BLACK),
    ('✓ Flask 3.0 Web应用，已部署可演示', True, GREEN),
    ('  ├ 启动命令：python run.py → http://localhost:5000', False, GRAY),
    ('  ├ 15+ 核心Python源文件，总计5000+行代码', False, GRAY),
    ('  └ 8个功能引擎模块 + 完整的前端SPA界面', False, GRAY),
    ('', False, BLACK),
    ('✓ 完整的API体系（40+ RESTful接口）', True, GREEN),
    ('  ├ POST /api/chat — 智能对话', False, GRAY),
    ('  ├ GET /api/knowledge/<type> — 知识查询', False, GRAY),
    ('  ├ POST /api/scenario/start|step — 情景训练', False, GRAY),
    ('  ├ POST /api/report/url — 举报提交', False, GRAY),
    ('  ├ GET /api/user/leaderboard|profile — 用户系统', False, GRAY),
    ('  └ 更多：签到、历史、隐私状态、URL分析等', False, GRAY),
    ('', False, BLACK),
    ('✓ 完整的前端交互界面', True, GREEN),
    ('  ├ 侧边栏导航 + 多模态弹窗系统', False, GRAY),
    ('  ├ 实时聊天界面 + 打字机效果', False, GRAY),
    ('  └ 5个模态界面（知识库·情景·举报·排行·历史）', False, GRAY),
], font_size=11)

# 右侧
add_rect(slide9, 6.7, 1.7, 6.2, 2.5, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
add_rect(slide9, 6.7, 1.7, 6.2, 0.06, ACCENT_GOLD)
add_textbox(slide9, 7.0, 1.85, 5.6, 0.3, '业务场景覆盖', font_size=16, bold=True, color=ACCENT_GOLD)
add_multiline(slide9, 7.0, 2.3, 5.6, 1.7, [
    ('适配真实金融反诈业务场景：', True, BLACK),
    ('', False, BLACK),
    ('  ▸ 银行/支付机构：交易风险教育、钓鱼预警', False, GRAY),
    ('  ▸ 电商平台：刷单诈骗识别与劝阻', False, GRAY),
    ('  ▸ 社交平台：杀猪盘/虚假投资场景训练', False, GRAY),
    ('  ▸ 校园：学生群体反诈教育第一道防线', False, GRAY),
    ('  ▸ 社区：老年人反诈科普与实时求助', False, GRAY),
    ('  ▸ 公安/反诈中心：辅助劝阻与知识传播', False, GRAY),
], font_size=11)

add_rect(slide9, 6.7, 4.5, 6.2, 2.6, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
add_rect(slide9, 6.7, 4.5, 6.2, 0.06, GREEN)
add_textbox(slide9, 7.0, 4.65, 5.6, 0.3, '落地部署方案', font_size=16, bold=True, color=GREEN)
add_multiline(slide9, 7.0, 5.05, 5.6, 1.8, [
    ('生产环境部署架构：', True, BLACK),
    ('', False, BLACK),
    ('  用户端（网页/PWA/小程序）', False, GRAY),
    ('    → Nginx（HTTPS + 静态资源 + 反向代理）', False, GRAY),
    ('      → Gunicorn（WSGI，多worker）', False, GRAY),
    ('        → Flask App + 8引擎', False, GRAY),
    ('          → SQLite / PostgreSQL', False, GRAY),
    ('', False, BLACK),
    ('  支持Docker容器化部署，一键启动', False, GREEN),
    ('  支持混合云架构，适配赛事要求', False, GREEN),
], font_size=11)

add_footer(slide9, 9)

# ============================================================
# Slide 10: 安全性 (20分) ★ 新增重点
# ============================================================
slide10 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide10, WHITE)
add_top_bar(slide10, '安全性 — 全生命周期数据加密与隐私保护', 'SECURITY & PRIVACY PROTECTION', score_tag='安全性 20分')

# 四个安全维度
sec_items = [
    ('AES-256-GCM\n端到端加密', '#C62828',
     ['使用行业标准的AES-256-GCM算法',
      '认证加密模式，同时保证机密性与完整性',
      '每条消息独立加密密钥派生',
      '覆盖存储全生命周期，即使数据库泄露也无法解密',
      '密钥通过PBKDF2派生，抗暴力破解']),
    ('PII实时检测\n与自动脱敏', '#F57C00',
     ['正则+规则引擎实时扫描用户输入',
      '支持身份证号/手机号/银行卡号/邮箱/地址',
      '检测到敏感信息→发送前即自动脱敏(***替换)',
      '脱敏处理不可逆，前端+后端双重校验',
      '隐私状态面板可视化展示当前会话保护状态']),
    ('JWT身份认证\n与访问控制', '#1565C0',
     ['JWT Token无状态认证机制',
      '用户首次访问即分配唯一ID并签发Token',
      'Token过期自动刷新，防重放攻击',
      'API接口统一鉴权中间件',
      '无需密码即可安全识别用户身份']),
    ('审计日志\n与合规保障', '#2E7D32',
     ['全程操作审计：对话/举报/情景/登录',
      '日志包含时间戳+操作类型+去敏后摘要',
      '支持金融数据安全合规相关要求',
      '违规操作可追溯、可定位、可问责',
      '日志定期归档，防止篡改']),
]

for i, (title, color_hex, points) in enumerate(sec_items):
    x = 0.3 + i * 3.25
    color = RGBColor(int(color_hex[1:3], 16), int(color_hex[3:5], 16), int(color_hex[5:7], 16))
    add_rect(slide10, x, 1.7, 3.1, 3.6, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
    add_rect(slide10, x, 1.7, 3.1, 1.0, color)
    add_textbox(slide10, x + 0.15, 1.82, 2.8, 0.8, title, font_size=15, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    for j, pt in enumerate(points):
        add_textbox(slide10, x + 0.15, 2.85 + j * 0.38, 2.8, 0.35, f'▸ {pt}', font_size=9, color=GRAY)

# 底部安全架构图
add_textbox(slide10, 0.5, 5.55, 12, 0.3, '数据安全全生命周期保护', font_size=14, bold=True, color=BLACK)

lifecycle = [
    ('采集', '用户输入\n即检测', LIGHT_RED),
    ('传输', 'HTTPS\n加密通道', LIGHT_BLUE),
    ('处理', 'PII实时\n脱敏处理', RGBColor(0xFF, 0xF3, 0xE0)),
    ('存储', 'AES-256-GCM\n加密存储', LIGHT_GREEN),
    ('访问', 'JWT认证\n权限控制', RGBColor(0xF3, 0xE5, 0xF5)),
    ('审计', '全链路\n操作日志', LIGHT_GRAY),
    ('销毁', '支持数据\n安全删除', RGBColor(0xE8, 0xE8, 0xE8)),
]
for i, (phase, desc, bg) in enumerate(lifecycle):
    x = 0.4 + i * 1.8
    add_rect(slide10, x, 6.0, 1.65, 1.15, bg, border=RGBColor(0xDD, 0xDD, 0xDD))
    add_textbox(slide10, x + 0.05, 6.08, 1.55, 0.3, phase, font_size=12, bold=True, color=BLACK, align=PP_ALIGN.CENTER)
    add_textbox(slide10, x + 0.05, 6.42, 1.55, 0.5, desc, font_size=10, color=GRAY, align=PP_ALIGN.CENTER)

add_footer(slide10, 10)

# ============================================================
# Slide 11: 成熟度 (20分) ★ 新增重点
# ============================================================
slide11 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide11, WHITE)
add_top_bar(slide11, '成熟度 — 系统稳定性 · 可扩展性 · 文档规范性', 'MATURITY & QUALITY', score_tag='成熟度 20分')

# 三列
col_data = [
    ('代码质量与工程规范', GREEN,
     ['模块化8引擎架构，单一职责原则',
      '每个引擎独立文件，接口清晰统一',
      '配置集中管理(config.py)，环境变量隔离',
      '异常处理完善，关键路径有错误兜底',
      '代码注释率合理，命名遵循Python规范',
      '前后端分离，RESTful API设计标准',
      '使用SQLAlchemy ORM，避免SQL注入',
      '15+核心源文件，结构清晰可维护']),
    ('系统稳定性与可扩展性', ACCENT_BLUE,
     ['松耦合引擎设计，新增反诈能力只需添加模块',
      'JSON配置文件驱动，新骗局类型零代码接入',
      '数据库支持SQLite→PostgreSQL平滑迁移',
      'JWT无状态认证，支持水平扩展多实例',
      '审计日志独立存储，不影响主业务性能',
      '前端组件化设计，弹窗系统易扩展新功能',
      '知识库JSON结构化，支持热更新',
      'API版本化管理，向后兼容']),
    ('文档与配套资料完整性', ACCENT_GOLD,
     ['完整的RAICOM参赛作品文档(.docx 152KB)',
      '├ 项目概述 · 系统架构 · 功能设计',
      '├ 技术实现 · 创新亮点 · 源码附录',
      '└ 15个核心源文件完整收录',
      '项目介绍PPT(本文件，14页)',
      '完整功能演示视频(2分36秒，1280x720)',
      '演示视频配音讲解稿(.docx)',
      'README使用说明 · API接口文档',
      'python-docx自动生成文档脚本',
      'Playwright自动录制演示视频脚本']),
]

for i, (title, color, points) in enumerate(col_data):
    x = 0.3 + i * 4.3
    add_rect(slide11, x, 1.7, 4.1, 5.5, WHITE, border=RGBColor(0xE0, 0xE0, 0xE0))
    add_rect(slide11, x, 1.7, 4.1, 0.06, color)
    add_textbox(slide11, x + 0.2, 1.85, 3.7, 0.3, title, font_size=14, bold=True, color=color)
    for j, pt in enumerate(points):
        c = GREEN if pt.startswith('├') or pt.startswith('└') else (BLACK if pt.startswith('完整') or pt.startswith('项目') else GRAY)
        b = pt.startswith('模块化') or pt.startswith('松耦合') or pt.startswith('JSON') or pt.startswith('完整的')
        add_textbox(slide11, x + 0.2, 2.3 + j * 0.48, 3.7, 0.45, f'✓ {pt}', font_size=10, bold=b, color=c)

add_footer(slide11, 11)

# ============================================================
# Slide 12: 功能演示概览
# ============================================================
slide12 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide12, WHITE)
add_top_bar(slide12, '功能演示概览 — 2分36秒完整视频', 'DEMO HIGHLIGHTS')

add_textbox(slide12, 0.5, 1.65, 12, 0.35, '演示视频覆盖以下功能模块（与评分维度一一对应）：', font_size=14, bold=True, color=BLACK)

chapters = [
    ('1', '智能对话系统', '11轮多场景交互', '刷单识别·杀猪盘·老年人模式·紧急劝阻·URL分析·PII检测·法律咨询·知识图谱', PRIMARY, '完成度'),
    ('2', '反诈知识库(深入)', '3种类型查询', '刷单返利→冒充公检法→虚假投资，每种展示详细知识点与防范建议', ACCENT_BLUE, '完成度'),
    ('3', '情景模拟(完整通关)', '3步闯关全流程', 'NPC对话→选择应对→评分反馈→下一步→通关评级→积分勋章奖励', ACCENT_GOLD, '完成度'),
    ('4', '举报中心+排行榜', '举报+游戏化', 'URL提交+研判反馈 / 积分排名·等级·勋章展示', GREEN, '完成度'),
    ('5', '隐私保护+历史', '安全+可追溯', '隐私状态面板·加密状态展示 / 历史对话回溯', PURPLE, '安全性'),
    ('6', '全功能总结', '系统能力回顾', 'AI自动总结反诈卫士所有功能模块', PRIMARY, '综合'),
]

for i, (num, title, sub, desc, color, score_dim) in enumerate(chapters):
    y = 2.15 + i * 0.85
    add_rect(slide12, 0.5, y, 12.3, 0.72, LIGHT_GRAY if i % 2 == 0 else WHITE)
    add_circle(slide12, 0.7, y + 0.15, 0.4, color)
    add_textbox(slide12, 0.7, y + 0.18, 0.4, 0.3, num, font_size=12, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_textbox(slide12, 1.3, y + 0.03, 2.0, 0.3, title, font_size=14, bold=True, color=BLACK)
    add_textbox(slide12, 1.3, y + 0.33, 2.0, 0.25, sub, font_size=9, color=GRAY)
    add_textbox(slide12, 3.4, y + 0.08, 7.5, 0.55, desc, font_size=11, color=GRAY)
    # 评分维度标签
    tag = add_rect(slide12, 11.1, y + 0.2, 1.4, 0.3, color)
    tf = tag.text_frame
    p = tf.paragraphs[0]
    p.text = score_dim
    p.font.size = Pt(8)
    p.font.bold = True
    p.font.color.rgb = WHITE
    p.font.name = FONT_BODY
    p.alignment = PP_ALIGN.CENTER

add_footer(slide12, 12)

# ============================================================
# Slide 13: 总结
# ============================================================
slide13 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide13, WHITE)
add_top_bar(slide13, '项目总结 — 评分维度全覆盖', 'SCORING SUMMARY')

# 5维度雷达总结
score_summary = [
    ('完成度 20分', PRIMARY,
     ['知识库：5类骗局结构化管理', '意图识别：关键词+句式+上下文',
      '风险劝阻：场景化分级话术', '举报功能：URL研判+一键提交',
      '游戏化：积分/等级/勋章/闯关', '泛终端：响应式Web+PWA规划']),
    ('创新性 20分', ACCENT_GOLD,
     ['8引擎模块化协同架构', '多模态融合(文本+URL+知识图谱)',
      '游戏化反诈教育闭环', '知识图谱诈骗关联推理',
      '适老化智能对话', '隐私优先的架构设计']),
    ('实用性 20分', ACCENT_BLUE,
     ['真实可运行Flask Web应用', '40+RESTful API完整体系',
      '6大业务场景适配', 'Docker容器化部署方案',
      '15+核心源文件，5000+行代码']),
    ('安全性 20分', PURPLE,
     ['AES-256-GCM端到端加密', 'PII实时检测自动脱敏',
      'JWT身份认证+鉴权中间件', '全链路审计日志',
      '数据安全全生命周期保护']),
    ('成熟度 20分', GREEN,
     ['模块化松耦合可扩展架构', '完整参赛文档+源码附录',
      '功能演示视频+配音讲解稿', 'PPT针对性评分优化',
      '自动化文档与视频生成脚本']),
]

for i, (title, color, points) in enumerate(score_summary):
    x = 0.2 + i * 2.65
    add_rect(slide13, x, 1.65, 2.5, 0.5, color)
    add_textbox(slide13, x, 1.7, 2.5, 0.4, title, font_size=13, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    for j, pt in enumerate(points):
        add_textbox(slide13, x + 0.1, 2.3 + j * 0.52, 2.3, 0.5, f'✓ {pt}', font_size=9, color=BLACK if j < 2 else GRAY)

# 团队表现提示
add_rect(slide13, 0.5, 6.0, 12.3, 1.1, LIGHT_GRAY)
add_multiline(slide13, 0.8, 6.1, 11.8, 0.9, [
    ('附加分项：团队表现（10分）— 答辩逻辑清晰度 · 团队协作默契度 · 问题应答能力', True, ACCENT_GOLD),
    ('本作品已准备完整演示链路：PPT讲解 → 2分36秒演示视频 → 现场Live Demo → Q&A应答，确保答辩流程流畅、重点突出', False, GRAY),
], font_size=12)

add_footer(slide13, 13)

# ============================================================
# Slide 14: 致谢
# ============================================================
slide14 = prs.slides.add_slide(prs.slide_layouts[6])
add_bg(slide14, DARK_BG)
add_rect(slide14, 0, 0, 13.333, 0.12, PRIMARY)
add_rect(slide14, 0, 7.38, 13.333, 0.12, PRIMARY)

add_textbox(slide14, 0, 1.8, 13.333, 1.2, '感谢聆听', font_size=48, bold=True, color=WHITE, align=PP_ALIGN.CENTER, font_name=FONT_TITLE)
add_textbox(slide14, 0, 3.0, 13.333, 0.55, 'THANK YOU', font_size=20, color=RGBColor(0x88, 0x88, 0x88), align=PP_ALIGN.CENTER)
add_rect(slide14, 5.5, 3.8, 2.3, 0.04, ACCENT_GOLD)
add_textbox(slide14, 0, 4.1, 13.333, 0.5, '多模态智能反诈对话系统', font_size=18, color=RGBColor(0xCC, 0xCC, 0xCC), align=PP_ALIGN.CENTER)
add_textbox(slide14, 0, 4.7, 13.333, 0.5, 'RAICOM 睿抗机器人开发者大赛 · CAIP强脑赛道 · 智能算法及应用赛项', font_size=13, color=GRAY, align=PP_ALIGN.CENTER)
add_textbox(slide14, 0, 5.2, 13.333, 0.5, '金融反诈智能守护 — 方向三：面向反诈教育的智能客服', font_size=13, color=GRAY, align=PP_ALIGN.CENTER)
add_textbox(slide14, 0, 5.9, 13.333, 0.5, '用AI技术守护每一位用户的财产安全', font_size=14, color=ACCENT_GOLD, align=PP_ALIGN.CENTER)

# 保存
output_path = os.path.join(BASE_DIR, '项目介绍PPT_反诈卫士.pptx')
prs.save(output_path)
print(f'[OK] PPT已生成: {output_path}')
print(f'[OK] 共 {len(prs.slides)} 页幻灯片')
print(f'[OK] 全面对齐评分细则五维度(100分) + 团队表现(10分)')
