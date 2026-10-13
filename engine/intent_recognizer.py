"""增强意图识别引擎 - 多轮上下文追踪、加权规则、模糊匹配、状态机"""

import json
import re
import os
from typing import Optional


# 诈骗类型知识库缓存（避免每条消息重复读文件）
_FRAUD_KB_CACHE = None


def _load_fraud_kb() -> dict:
    """加载诈骗类型知识库（进程内缓存一次）"""
    global _FRAUD_KB_CACHE
    if _FRAUD_KB_CACHE is None:
        path = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base', 'fraud_types.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                _FRAUD_KB_CACHE = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _FRAUD_KB_CACHE = {"fraud_types": []}
    return _FRAUD_KB_CACHE


class IntentRecognizer:
    """轻量级意图识别引擎，支持多轮上下文、加权规则、模糊匹配"""

    def __init__(self):
        self.patterns = {}
        self._load_patterns()

        # 多轮对话上下文追踪
        self.context_store = {}  # user_id -> ConversationContext

        # 意图权重配置
        self.INTENT_WEIGHTS = {
            "greetings": 1.0,
            "help_requests": 1.2,
            "report_intents": 1.5,
            "knowledge_queries": 1.3,
            "scenario_requests": 1.4,
            "self_check": 1.8,
            "legal_queries": 1.2,
            "fraud_inquiry": 1.6,
            "emergency": 2.0,
            "describe_situation": 1.7,
            "provide_info": 1.0,
            "confusion": 1.5,
            "fear_anxiety": 1.8,
            "elderly_identity": 1.3,
            "thanks": 0.8,
            "feedback": 0.8,
            "unknown": 0.5
        }

        # 同义词扩展
        self.SYNONYM_MAP = {
            "刷单": ["兼职", "刷信誉", "刷流水", "做任务", "试玩", "点赞赚钱", "关注返利", "刷票", "冲量"],
            "转账": ["汇款", "打款", "转钱", "付钱", "交钱", "给钱", "付款", "转出"],
            "举报": ["投诉", "拉黑", "举报链接", "举报号码", "举报网址", "报警", "检举"],
            "被骗": ["上当", "受骗", "被坑", "被忽悠", "被套路", "被诈骗", "被宰", "被割韭菜"],
            "链接": ["网址", "网站", "网页", "链接地址", "URL", "二维码", "链结"],
            "验证码": ["短信验证码", "动态码", "安全码", "校验码", "验证码"],
            "贷款": ["借贷", "借款", "网贷", "小额贷", "贷款", "借钱"],
            "投资": ["理财", "炒股", "基金", "数字货币", "虚拟币", "外汇", "币圈", "基金", "股票"],
            "下载": ["安装", "下", "装", "下载安装"],
            "注销": ["注销账户", "取消账户", "关闭账户", "注销账号", "销户"],
            "退款": ["退钱", "返款", "返还", "退回", "退费"],
            "足不出户": ["在家", "不出门", "不用出门", "躺着", "动动手指"],
            "高回报": ["高收益", "赚大钱", "发大财", "暴富", "翻倍", "赚翻了"],
            "紧急": ["着急", "马上", "尽快", "赶紧", "赶快", "来不及了", "急用"],
            "兼职赚钱": ["赚钱", "挣钱", "搞钱", "赚外快", "赚零花", "日结"],
            "征信": ["信用", "信用报告", "信誉", "黑名单", "失信"],
        }

    def _load_patterns(self):
        patterns_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base', 'dialog_patterns.json')
        try:
            with open(patterns_path, 'r', encoding='utf-8') as f:
                self.patterns = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.patterns = {"dialog_patterns": {}, "response_templates": {}}

    # ========== 对话上下文管理 ==========

    class ConversationContext:
        """多轮对话上下文"""

        def __init__(self):
            self.history = []  # 历史意图
            self.last_intent = None
            self.last_fraud_type = None
            self.turn_count = 0
            self.mentioned_fraud_types = []
            self.risk_history = []  # 历史风险等级
            self.consecutive_unknown = 0
            self.conversation_flow = None  # 当前对话流程

        def update(self, intent: str, fraud_type: str = None, risk_level: str = "none"):
            self.history.append(intent)
            self.last_intent = intent
            self.turn_count += 1
            if fraud_type and fraud_type not in self.mentioned_fraud_types:
                self.mentioned_fraud_types.append(fraud_type)
            if risk_level != "none":
                self.risk_history.append(risk_level)

            if intent == "unknown":
                self.consecutive_unknown += 1
            else:
                self.consecutive_unknown = 0

        def get_context_summary(self) -> dict:
            return {
                "turn_count": self.turn_count,
                "last_intent": self.last_intent,
                "mentioned_frauds": self.mentioned_fraud_types,
                "consecutive_unknown": self.consecutive_unknown,
                "has_risk_history": len(self.risk_history) > 0,
                "flow": self.conversation_flow
            }

    # ========== 核心识别逻辑 ==========

    def recognize(self, text: str, user_id: str = "default",
                  dialog_history: list = None) -> dict:
        """识别用户意图，支持多轮上下文"""
        if not text or not text.strip():
            return {"intent": "unknown", "confidence": 0, "entities": {}}

        # 初始化上下文
        if user_id not in self.context_store:
            self.context_store[user_id] = self.ConversationContext()
        ctx = self.context_store[user_id]

        text = text.strip()
        results = []

        # 1. 检测诈骗类型（提前做，使紧急路径也能带出类型）
        _ft = self.detect_fraud_type_hybrid(text, top_k=1)
        fraud_type = _ft[0][0] if _ft else ""
        if fraud_type:
            ctx.last_fraud_type = fraud_type

        # 2. 紧急意图优先检测
        emergency = self._check_emergency(text)
        if emergency:
            ctx.update("emergency")
            _r = {
                "intent": "emergency",
                "confidence": 1.0,
                "matched_keywords": [emergency],
                "context": ctx.get_context_summary()
            }
            if fraud_type:
                _r["fraud_type"] = fraud_type
            return _r

        # 3. 逐类意图识别（加权评分，排除emergency由独立检测处理）
        all_patterns = {k: v for k, v in self.patterns.get("dialog_patterns", {}).items() if k != "emergency"}
        for intent, keywords in all_patterns.items():
            score = 0
            matched = []
            total_weight = len(keywords)

            for kw in keywords:
                # 精确匹配
                if kw.lower() in text:
                    score += 1.0
                    matched.append(kw)
                    continue

                # 同义词扩展匹配
                for synonym_key, synonyms in self.SYNONYM_MAP.items():
                    if kw == synonym_key or kw in synonyms:
                        if any(syn in text for syn in synonyms):
                            score += 0.8
                            matched.append(f"{kw}(同义)")
                            break

                # 部分匹配（关键词包含在用户输入中）
                if len(kw) >= 2 and kw in text:
                    score += 0.6
                    matched.append(kw)

            if score > 0:
                # 计算置信度，考虑意图权重
                weight = self.INTENT_WEIGHTS.get(intent, 1.0)
                base_confidence = min(score / max(total_weight, 1) * 1.5, 1.0)
                adjusted_confidence = min(base_confidence * weight, 1.0)

                results.append({
                    "intent": intent,
                    "confidence": adjusted_confidence,
                    "matched_keywords": matched[:5],
                    "score": score,
                    "total_weight": total_weight
                })

        # 4. 按置信度排序
        results.sort(key=lambda x: x["confidence"], reverse=True)

        # 5. 综合多轮上下文修正
        if results:
            best = results[0]
            # 如果上一轮是fraud_inquiry且本轮置信度偏低，继承上轮意图
            if ctx.last_intent in ("fraud_inquiry", "knowledge_queries") and best["confidence"] < 0.5:
                best["intent"] = ctx.last_intent
                best["confidence"] = max(best["confidence"], 0.4)
                best["from_context"] = True

            # 连续未知意图 → 降级为fallback
            if best["intent"] == "unknown" and ctx.consecutive_unknown >= 2:
                best["intent"] = "fallback"
                best["confidence"] = 0.3

            result = {
                "intent": best["intent"],
                "confidence": best["confidence"],
                "all_intents": [r["intent"] for r in results[:3]],
                "matched_keywords": best.get("matched_keywords", []),
                "from_context": best.get("from_context", False),
                "context": ctx.get_context_summary()
            }

            if fraud_type:
                result["fraud_type"] = fraud_type

            ctx.update(result["intent"], fraud_type)
            return result

        # 6. 未匹配 → 检测是否为情景描述
        if self._is_situation_description(text):
            ctx.update("describe_situation")
            return {
                "intent": "describe_situation",
                "confidence": 0.5,
                "fraud_type": fraud_type or "",
                "context": ctx.get_context_summary()
            }

        # 7. 完全未匹配（但仍传递检测到的诈骗类型）
        ctx.update("unknown")
        result = {
            "intent": "unknown",
            "confidence": 0,
            "entities": {},
            "context": ctx.get_context_summary()
        }
        if fraud_type:
            result["fraud_type"] = fraud_type
        return result

    def _check_emergency(self, text: str) -> Optional[str]:
        """检测紧急情况（仅明确的紧急状态才触发）"""
        emergency_patterns = [
            # 拆成精确模式：原 `[转汇打].*[钱了已经]` 的 .* 过贪婪，
            # 会把"打电话让我去银行转钱"误判为"已转账"
            (r"已[经经].{0,8}[转汇打]", "已转账"),
            (r"[转汇打][了过].{0,8}(钱|款|账|元|块|万|\d)", "已转账"),
            (r"把钱.{0,6}[转汇打].{0,6}了", "已转账"),
            (r"紧急|马上.*[被骗转汇]", "紧急求助"),
            (r"[正现在].*[转账汇].*[给到去]", "正在转账"),
            (r"报警.*[了过]", "已报警"),
            # 数字前后不能再接数字，避免身份证/银行卡号中的 "110" 误触发
            (r"(?<!\d)(96110|110)(?!\d)", "拨打专线"),
        ]
        # "被骗了" 作为一般查询，不触发紧急
        if text.strip() in ("被骗了", "我被骗了", "我是不是被骗了"):
            return None
        for pattern, label in emergency_patterns:
            if re.search(pattern, text):
                return label
        return None

    def _is_situation_description(self, text: str) -> bool:
        """判断是否为情景描述（增强版）"""
        # 包含具体场景的叙述
        indicators = [
            r"有[个人]?.*[加联找让叫说]",
            r"[收接].*[短信电话消息]",
            r"[说讲问让叫].*[钱款转账投资刷汇赚]",
            r"[让叫].*[转汇下载安装申刷给交]",
            r"在.*[上里].*[让叫找]",
            r".{4,}说.{2,}",
            r".{6,}[转账汇打刷给交]",
            r"[刷兼职投资转账].*[赚返投汇转]",
            r"微信|QQ|短信.*[人说让]",
            r"足不出户|日赚.*[数百千万]|月入.*[万过]|轻松.*[赚]",
            r"[让叫请].*[帮帮忙看看分析]",
        ]
        for pattern in indicators:
            if re.search(pattern, text):
                return True
        # 长度较长的非问句
        if len(text) > 15 and not text.endswith("？") and not text.endswith("?"):
            return True
        # 包含典型的诈骗话术特征（短文本也检测）
        fraud_phrases = ["足不出户", "日赚", "月入过万", "动动手指", "稳赚不赔", "安全账户",
                         "刷单", "高回报", "低风险", "投多少", "先垫付", "解冻金"]
        if any(phrase in text for phrase in fraud_phrases):
            return True
        return False

    def _detect_fraud_type(self, text: str) -> str:
        """检测文本中提到的诈骗类型（关键词/别名匹配，高精度）"""
        kb = _load_fraud_kb()
        if not kb:
            return ""

        best_match = ""
        best_score = 0

        for fraud in kb["fraud_types"]:
            score = 0
            # 检查别名
            for alias in fraud.get("aliases", []):
                if alias in text:
                    score += 2
            # 检查关键词
            for kw in fraud.get("keywords", []):
                if kw in text:
                    score += 1
            # 检查典型话术
            for dialog in fraud.get("typical_dialogs", []):
                if any(kw in text for kw in dialog.split()):
                    score += 1.5

            if score > best_score:
                best_score = score
                best_match = fraud["id"]

        return best_match if best_score >= 1 else ""

    def detect_fraud_type_hybrid(self, text: str, top_k: int = 3) -> list:
        """诈骗类型匹配：关键词/别名命中优先，命中后用语义补充候选。

        返回 [(fraud_id, score), ...]，关键词结果置顶（score=1.0）。
        `top_k=1` 且关键词命中时**不触发语义编码**（性能友好）。

        ⚠️ **关键词未命中时返回空列表，不做语义兜底**。
        实测语义匹配**无法区分"有诈骗类型"与"无诈骗类型"**：
        知识/法律类查询（"诈骗罪的量刑标准是什么"）的语义最高分 0.775，
        反而高于真实诈骗描述的最低分 0.410，任何阈值都无法分开。
        若用语义单独兜底，真实数据 41 条无类型样本会 **100% 误报**。

        语义仅在关键词已命中时作为 Top-3 候选补充
        （真实集 Top-3 77.8%、自建集 Top-3 92.2%，且零新增误报）。
        """
        kw = self._detect_fraud_type(text)
        if not kw:
            return []

        ranked = [(kw, 1.0)]
        if len(ranked) >= top_k:
            return ranked[:top_k]

        # 语义补充（仅在关键词已命中时）
        try:
            from engine.nlp_pipeline import get_nlp_pipeline
            nlp = get_nlp_pipeline()
            if nlp.ready:
                for tid, sc in (nlp.match_fraud_type(text) or []):
                    if tid not in {r[0] for r in ranked}:
                        ranked.append((tid, float(sc)))
                    if len(ranked) >= top_k:
                        break
        except Exception:
            pass

        return ranked[:top_k]

    def reset_context(self, user_id: str):
        """重置用户对话上下文"""
        if user_id in self.context_store:
            del self.context_store[user_id]

    def get_context(self, user_id: str) -> Optional[dict]:
        """获取用户上下文"""
        ctx = self.context_store.get(user_id)
        return ctx.get_context_summary() if ctx else None

    def get_supported_fraud_types(self) -> list:
        """获取当前支持的骗局类型列表（用于快速接入检测）"""
        kb = _load_fraud_kb()
        return [f["id"] for f in kb.get("fraud_types", [])]

    # ========== v3.0 NLP 增强识别 ==========

    def recognize_enhanced(self, text: str, user_id: str = "default",
                           dialog_history: list = None) -> dict:
        """
        v3.0 增强意图识别 — 规则引擎 + 语义分类双模
        
        规则引擎做首轮快速匹配（高精度），
        语义分类做兜底（高召回），
        两者结果融合输出。
        """
        # 1. 先用规则引擎
        rule_result = self.recognize(text, user_id, dialog_history)

        # 2. 如果规则引擎高置信度，直接返回
        if rule_result["confidence"] >= 0.7:
            rule_result["recognition_mode"] = "rule"
            return rule_result

        # 3. 尝试语义增强
        try:
            from engine.intent_classifier import get_intent_classifier
            classifier = get_intent_classifier()
            if classifier.ready:
                sem_intent, sem_conf = classifier.classify_top1(text, min_confidence=0.35)

                # 识别映射（语义意图 → 系统意图）
                intent_map = {
                    "greetings": "greetings",
                    "help_requests": "help_requests",
                    "report_intents": "report_intents",
                    "knowledge_queries": "knowledge_queries",
                    "scenario_requests": "scenario_requests",
                    "self_check": "self_check",
                    "fraud_inquiry": "fraud_inquiry",
                    "legal_queries": "legal_queries",
                    "emergency": "emergency",
                    "describe_situation": "describe_situation",
                    "confusion": "confusion",
                    "fear_anxiety": "fear_anxiety",
                    "elderly_identity": "elderly_identity",
                    "thanks": "thanks",
                }
                mapped_intent = intent_map.get(sem_intent, sem_intent)

                rule_conf = rule_result.get("confidence", 0)
                rule_matched = bool(rule_result.get("matched_keywords"))

                # 融合策略（v3.0-P1 修正）：
                # 规则层有**显式关键词证据**时，视为高精度判断，只有语义高度自信
                # (>=0.7) 才允许覆盖；否则保留规则判定。
                # 原因：规则置信度公式为 匹配数/关键词总数*1.5，天然偏低（0.2~0.4），
                # 若按 "sem_conf > rule_conf" 就覆盖，几乎总被语义层（短文本噪声大）
                # 用 emergency/greetings 等低信息意图覆盖掉正确的知识查询判定。
                # 规则层无任何证据时，语义层作为兜底直接接管。
                sem_can_override = (sem_conf >= 0.7) or (not rule_matched)

                if sem_can_override and sem_conf > rule_conf:
                    rule_result["intent"] = mapped_intent
                    rule_result["confidence"] = sem_conf
                    rule_result["semantic_intent"] = sem_intent
                    rule_result["recognition_mode"] = "semantic"
                elif sem_conf > 0.4:
                    # 中等置信度，标注但不覆盖
                    rule_result["semantic_intent"] = sem_intent
                    rule_result["semantic_confidence"] = sem_conf
                    if rule_result["recognition_mode"] not in ("rule", "semantic"):
                        rule_result["recognition_mode"] = "hybrid"
        except Exception:
            pass

        if "recognition_mode" not in rule_result:
            rule_result["recognition_mode"] = "rule"

        return rule_result
