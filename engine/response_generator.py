"""对话响应生成器 - 整合意图识别、风险分析、知识检索和游戏化"""

import json
import random
import os
import re
from .intent_recognizer import IntentRecognizer
from .risk_analyzer import RiskAnalyzer
from .url_analyzer import URLAnalyzer
from .knowledge_retriever import KnowledgeRetriever


class ResponseGenerator:
    """对话响应生成器，整合意图识别、风险分析、知识库"""

    def __init__(self):
        self.recognizer = IntentRecognizer()
        self.risk_analyzer = RiskAnalyzer()
        self.url_analyzer = URLAnalyzer()
        self.knowledge_retriever = KnowledgeRetriever()
        self.patterns = self._load_patterns()

    def _load_patterns(self):
        path = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base', 'dialog_patterns.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"dialog_patterns": {}, "response_templates": {}}

    def generate_response(self, user_input: str, user_id: str = "default",
                          dialog_history: list = None,
                          intent_result: dict = None) -> dict:
        """生成对话响应（增强版，整合知识检索和上下文）

        intent_result: 可选。若调用方已用 recognize_enhanced 算好意图，可传入以避免重复计算。
        """
        if not user_input or user_input in ('__init__', ''):
            return {
                "response": "👋 你好！我是**反诈卫士**——你的AI反诈助手！\n\n"
                            "我可以帮你：\n"
                            "1️⃣ **🔍 识别骗局** - 告诉我你遇到的情况\n"
                            "2️⃣ **📚 学习知识** - 了解各类诈骗手法\n"
                            "3️⃣ **🎮 情景闯关** - 互动模拟防骗训练\n"
                            "4️⃣ **📢 举报中心** - 可疑链接一键分析\n\n"
                            "有什么可以帮你的吗？",
                "type": "greeting"
            }

        # 1. 意图识别（带上下文）
        # 使用 recognize_enhanced：规则优先、语义兜底，使语义意图（含 provide_info 等）
        # 能真正参与 handler 路由；若规则置信度 >=0.7 则内部直接返回规则结果，行为与原来一致。
        if intent_result is None:
            try:
                intent_result = self.recognizer.recognize_enhanced(
                    user_input, user_id, dialog_history
                )
            except Exception:
                intent_result = self.recognizer.recognize(user_input, user_id, dialog_history)

        # 2. 风险分析（传入意图：知识咨询类意图会抑制"话题类"风险规则，避免误报）
        risk_result = self.risk_analyzer.analyze_risk(
            user_input, user_id, dialog_history,
            intent=intent_result.get("intent")
        )

        # 3. URL/内容检测
        url_result = self._detect_urls(user_input)
        content_analysis = None
        if url_result and url_result.get("is_suspicious"):
            content_analysis = self.url_analyzer.analyze_content(user_input)

        # 4. 知识检索增强
        knowledge_results = self.knowledge_retriever.search(user_input, top_k=2)
        fraud_indicators = self.knowledge_retriever.check_fraud_indicators(user_input)

        # v3.0 意图修正：检测到诈骗特征但意图被误判为 feedback/greetings 时修正
        if fraud_indicators and intent_result.get("intent") in ("feedback", "greetings"):
            intent_result["intent"] = "self_check"
            intent_result["confidence"] = max(intent_result.get("confidence", 0), 0.5)

        # 5. 根据意图生成响应
        response_data = self._generate_by_intent(
            intent_result, user_input, risk_result,
            knowledge_results, fraud_indicators
        )

        # 6. 高风险时添加劝阻信息
        intervention = ""
        if risk_result.get("has_risk"):
            fraud_type = intent_result.get("fraud_type", "")
            if not fraud_type and fraud_indicators:
                fraud_type = fraud_indicators[0].get("fraud_id", "")
            intervention = self.risk_analyzer.generate_intervention(
                risk_result, fraud_type, user_id
            )

        # 7. URL警告
        url_warning = ""
        if url_result and url_result.get("is_suspicious"):
            url_warning = self._format_url_warning(url_result)

        # 8. 构建完整响应
        full_response = response_data.get("text", "")

        # 如果命中已知骗局特征，追加知识信息
        if fraud_indicators and response_data.get("type") not in ("scenario_list", "report"):
            top_indicator = fraud_indicators[0]
            if top_indicator.get("confidence", 0) >= 0.6 and not risk_result.get("has_risk"):
                fraud_id = top_indicator.get("fraud_id", "")
                fraud_info = self.knowledge_retriever.get_fraud_by_id(fraud_id)
                if fraud_info and response_data.get("type") in ("fallback", "self_check", "describe_situation"):
                    full_response += (
                        f"\n\n📋 **根据您的描述，疑似涉及『{fraud_id}』类型诈骗**\n\n"
                        f"**识别要点：**\n"
                        + "\n".join(f"• {p}" for p in fraud_info.get("common_patterns", [])[:3])
                        + "\n\n**防范建议：**\n"
                        + "\n".join(f"• {a}" for a in fraud_info.get("prevention_advice", [])[:3])
                    )

        return {
            "response": full_response,
            "type": response_data.get("type", "chat"),
            "intervention": intervention,
            "url_warning": url_warning,
            "risk_level": risk_result.get("risk_level", "none"),
            "fraud_type": intent_result.get("fraud_type", ""),
            "extra_data": response_data.get("extra_data", {}),
            "risk_details": {
                "rule_count": risk_result.get("rule_count", 0),
                "triggered_categories": list(set(r.get("category", "") for r in risk_result.get("triggered_rules", [])))
            } if risk_result.get("has_risk") else None,
            "suggestions": self._get_suggestions(intent_result, risk_result)
        }

    def _get_suggestions(self, intent: dict, risk: dict) -> list:
        """根据当前状态生成快捷建议"""
        suggestions = []

        if risk.get("has_risk"):
            if risk["risk_level"] in ("high", "critical"):
                suggestions = ["拨打110报警", "拨打96110咨询", "停止转账", "联系银行"]
            else:
                suggestions = ["这是诈骗吗", "我该怎么办", "举报这个链接"]

        intent_name = intent.get("intent", "")
        if intent_name == "greetings":
            suggestions = ["什么是刷单诈骗", "帮我识别骗局", "情景模拟", "举报中心"]
        elif intent_name == "help_requests":
            suggestions = ["我可能被骗了", "举报一个链接", "学习反诈知识"]
        elif intent_name == "knowledge_queries":
            suggestions = ["刷单返利诈骗", "冒充公检法", "虚假投资", "校园贷"]
        elif intent_name == "scenario_requests":
            suggestions = ["刷单陷阱", "游戏交易诈骗", "冒充公检法"]

        return suggestions[:6]

    def _detect_urls(self, text: str) -> dict:
        """检测文本中的URL"""
        url_pattern = r'https?://[^\s<>"\'，。；；！？、]+|www\.[^\s<>"\'，。；；！？、]+'
        urls = re.findall(url_pattern, text)
        if urls:
            return self.url_analyzer.analyze_url(urls[0])
        return None

    def _generate_by_intent(self, intent: dict, user_input: str, risk: dict,
                            knowledge_results: list = None,
                            fraud_indicators: list = None) -> dict:
        """根据意图生成对应的响应内容"""
        intent_name = intent.get("intent", "unknown")

        intent_handlers = {
            "greetings": self._handle_greeting,
            "help_requests": self._handle_help,
            "report_intents": self._handle_report,
            "knowledge_queries": self._handle_knowledge,
            "scenario_requests": self._handle_scenario,
            "self_check": self._handle_self_check,
            "legal_queries": self._handle_legal,
            "fraud_inquiry": self._handle_fraud_inquiry,
            "emergency": self._handle_emergency,
            "describe_situation": self._handle_situation,
            "provide_info": self._handle_provide_info,
            "feedback": self._handle_feedback,
            "confusion": self._handle_confusion,
            "fear_anxiety": self._handle_fear_anxiety,
            "elderly_identity": self._handle_elderly,
            "thanks": self._handle_thanks,
            "fallback": self._handle_fallback,
        }

        handler = intent_handlers.get(intent_name, self._handle_fallback)
        return handler(intent, user_input, risk, knowledge_results, fraud_indicators)

    def _handle_greeting(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        is_elderly = self._is_elderly_user(user_input)
        if is_elderly:
            return {
                "text": (
                    "🙏 **大爷/大娘，您好！欢迎您！**\n\n"
                    "我是反诈卫士，专门帮大家识别骗局、学习防骗知识。\n\n"
                    "😊 您有什么问题尽管问我，我说话尽量简单清楚！\n\n"
                    "**比如您可以问我：**\n"
                    "• '有人让我转账，是不是骗子？'\n"
                    "• '接到陌生电话说我犯事了，怎么办？'\n"
                    "• '我想了解怎么防骗'\n\n"
                    "遇到拿不准的事，先来问问我，咱们一起分析！"
                ),
                "type": "greeting"
            }
        templates = self.patterns.get("response_templates", {}).get("greeting", [])
        if not templates:
            templates = ["你好！我是你的反诈助手，有什么可以帮助的吗？"]
        return {"text": random.choice(templates), "type": "greeting"}

    def _handle_help(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        return {
            "text": (
                "🛡️ **反诈卫士 - 我能帮你做什么？**\n\n"
                "🔍 **识别骗局**\n"
                "告诉我你遇到的具体情况，我帮你判断是否遇到诈骗。\n\n"
                "📚 **学习知识**\n"
                "了解刷单返利、冒充公检法、虚假投资等常见骗局。\n\n"
                "🎮 **情景闯关**\n"
                "通过互动模拟，在安全环境中学会识别诈骗。\n\n"
                "📢 **举报中心**\n"
                "发送可疑链接或信息，一键分析风险。\n\n"
                "⚖️ **法律咨询**\n"
                "了解反诈相关法律法规。\n\n"
                "💡 **快捷指令：**\n"
                "说'我遇到个情况'开始求助\n"
                "说'什么是XX诈骗'学习知识\n"
                "说'情景模拟'开始闯关\n"
                "说'举报'进入举报中心\n"
                "说'帮我分析'进行风险检测"
            ),
            "type": "help"
        }

    def _handle_report(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        # 如果输入中包含URL，直接分析
        url_pattern = r'https?://[^\s<>"\'，。；；！？、]+'
        urls = re.findall(url_pattern, user_input)
        if urls:
            result = self.url_analyzer.analyze_url(urls[0])
            content_result = self.url_analyzer.analyze_content(user_input)
            self.url_analyzer.record_report("default", urls[0], result, content_result)

            return {
                "text": (
                    f"🔗 **链接分析报告**\n\n"
                    f"**分析结果：** {'⚠️ 可疑链接！' if result['is_suspicious'] else '✅ 未发现明显风险'}\n"
                    f"**风险等级：** {result['risk_level']}\n"
                    f"**域名：** {result.get('domain', '未知')}\n\n"
                    + ("**风险详情：**\n" + "\n".join(f"• {d}" for d in result["details"]) if result["details"] else "**未发现异常特征**\n\n")
                    + f"\n**{result.get('advice', '')}**"
                    + "\n\n📢 如需正式举报，请点击下方的'提交举报'按钮。"
                ),
                "type": "url_report",
                "extra_data": {"url_analysis": result, "url": urls[0]}
            }

        return {
            "text": (
                "📢 **举报中心**\n\n"
                "你可以举报以下内容：\n\n"
                "1️⃣ **诈骗链接** — 直接将链接发给我分析\n"
                "2️⃣ **可疑内容** — 发送可疑信息文本\n"
                "3️⃣ **诈骗号码** — 发送电话号码\n\n"
                "**举报后我会：**\n"
                "✅ 自动分析链接/内容风险\n"
                "✅ 给出风险等级和处置建议\n"
                "✅ 记录举报获取积分\n\n"
                "**官方举报渠道：**\n"
                "• 📞 **110** 报警电话\n"
                "• 📞 **96110** 反诈专线\n"
                "• 🌐 **12321.cn** 网络举报中心\n"
                "• 📱 **国家反诈中心APP**\n\n"
                "你可以直接把可疑链接发给我分析 👇"
            ),
            "type": "report"
        }

    def _handle_knowledge(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        fraud_type = intent.get("fraud_type", "")

        if fraud_type:
            return self._query_fraud_info(fraud_type)

        # 通过知识检索匹配
        if knowledge_results:
            best_match = knowledge_results[0]
            if best_match.get("similarity", 0) > 0.2:
                return self._query_fraud_info(best_match["fraud_id"])

        return {
            "text": (
                "📚 **反诈知识库**\n\n"
                "我为你整理了以下常见骗局类型：\n\n"
                "1️⃣ **💰 刷单返利诈骗**\n"
                "   虚假兼职、点赞返利、连单陷阱\n\n"
                "2️⃣ **🎮 游戏交易诈骗**\n"
                "   低价充值、账号交易、解冻骗局\n\n"
                "3️⃣ **👮 冒充公检法诈骗**\n"
                "   冒充警察、安全账户、屏幕共享\n\n"
                "4️⃣ **📈 虚假投资诈骗**\n"
                "   杀猪盘、虚拟货币、稳赚不赔\n\n"
                "5️⃣ **🏫 校园贷诈骗**\n"
                "   低息贷款、裸贷、培训贷\n\n"
                "直接告诉我想了解哪种，例如：'讲讲刷单诈骗'"
            ),
            "type": "knowledge"
        }

    def _handle_self_check(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        # 检测是否为老年人用户
        is_elderly = self._is_elderly_user(user_input)

        # 如果有知识匹配结果，直接给出分析
        if fraud_indicators:
            if is_elderly:
                text = "🔍 **大爷/大妈，我来帮您分析！**\n\n"
                text += "根据您说的情况，我们发现以下几个风险：\n\n"
            else:
                text = "🔍 **风险分析结果**\n\n"
                text += "根据您的描述，我们检测到以下风险：\n\n"

            for indicator in fraud_indicators[:3]:
                icon = {"critical": "🔴", "high": "🔴", "medium": "🟡", "low": "🟢"}.get(indicator.get("risk_level", ""), "⚪")
                if is_elderly:
                    fraud_name_cn = {
                        "刷单返利": "刷单兼职诈骗", "游戏交易": "游戏交易诈骗",
                        "冒充公检法": "冒充公检法诈骗", "虚假投资": "虚假投资诈骗",
                        "校园贷": "非法校园贷", "冒充客服退款": "冒充客服退款诈骗",
                        "虚假征信": "征信诈骗", "冒充熟人": "冒充熟人诈骗",
                        "交友诈骗": "交友诈骗"
                    }
                    display_name = fraud_name_cn.get(indicator['fraud_id'], indicator['fraud_id'])
                    text += f"{icon} **{display_name}**\n"
                else:
                    text += f"{icon} **{indicator['fraud_id']}** (置信度: {indicator.get('confidence', 0)*100:.0f}%)\n"
                if indicator.get("matched_keywords"):
                    if is_elderly:
                        text += f"  您说的话里提到: {', '.join(indicator['matched_keywords'][:3])}，这些都是骗子常用的说法\n"
                    else:
                        text += f"  匹配关键词: {', '.join(indicator['matched_keywords'][:3])}\n"

            # 根据风险等级添加关怀提示
            top_level = fraud_indicators[0].get("risk_level", "")
            if top_level in ("critical", "high"):
                if is_elderly:
                    text += (
                        "\n⚠️ **这种情况风险很高，您听我说：**\n"
                        "• **先别转钱！** 不管对方怎么说都别转\n"
                        "• **给子女打个电话** 跟他们说说\n"
                        "• **打110报警** 让警察帮忙\n\n"
                        "别担心，遇到这种情况主动查问是正确的！👍"
                    )
                else:
                    text += (
                        "\n⚠️ **高风险警示！** 您描述的情况具有明显的诈骗特征。\n"
                        "请立即停止相关操作，必要时拨打110报警！\n"
                        "📞 110（报警） | 96110（反诈专线）"
                    )
            return {"text": text, "type": "self_check"}

        # v3.0 语义兜底：关键词无匹配时，尝试语义 NLP 分析
        user_text_len = len(user_input.strip())
        if user_text_len > 10:
            semantic_found = False
            try:
                from engine.nlp_pipeline import get_nlp_pipeline
                nlp = get_nlp_pipeline()
                if nlp.ready:
                    fraud_matches = nlp.match_fraud_type(user_input)
                    semantic_intent, sem_conf = nlp.classify_intent(user_input)
                    
                    if fraud_matches and fraud_matches[0][1] > 0.3:
                        semantic_found = True
                        top = fraud_matches[0]
                        fraud_type = top[0]
                        
                        # 获取该诈骗类型的详细信息
                        fraud_info = self.knowledge_retriever.get_fraud_by_id(fraud_type)
                        text = "🔍 **智能风险分析**\n\n"
                        text += f"根据语义分析，您描述的情况**高度疑似涉及「{fraud_type}」诈骗**。\n\n"
                        
                        if fraud_info:
                            text += f"**骗局特征：**\n"
                            patterns = fraud_info.get("common_patterns", [])[:3]
                            for p in patterns:
                                text += f"• {p}\n"
                            
                            text += f"\n**防范建议：**\n"
                            advice = fraud_info.get("prevention_advice", [])[:3]
                            for a in advice:
                                text += f"• {a}\n"
                        
                        text += "\n⚠️ **请立即停止所有转账操作！**"
                        text += "\n📞 如已转账，请立刻拨打 **110** 报警！"
                        return {"text": text, "type": "self_check", "semantic_detected": True}
            except Exception:
                pass

        # 即使用户已提供了详细描述但无法匹配，也要给出有实质内容的回复
        if user_text_len > 15:
            text = "🔍 **智能分析中…**\n\n"
            text += "您描述的情况包含以下需要警惕的要素：\n\n"
            
            # 提取并高亮可疑关键词
            suspicious_keywords = []
            checks = [
                (lambda t: "银行" in t and any(w in t for w in ["自称","冒充","打电话","联系"]), 
                 "⚠️ 有人冒充银行人员联系您 — 正规银行不会通过电话要求客户转账到私人/指定账户"),
                (lambda t: any(w in t for w in ["打款","转账","汇款","转钱"]), 
                 "⚠️ 涉及向他人账户转账 — 正规业务不会要求您向个人账户打款"),
                (lambda t: any(w in t for w in ["返利","返现","返款","回本","连本带利","利息","高回报"]), 
                 "⚠️ 承诺返利/高回报 — '低风险高回报'是经典诈骗话术"),
                (lambda t: any(w in t for w in ["指定账户","安全账户","验证账户"]), 
                 "⚠️ 要求转入指定账户 — 正规机构没有所谓的'指定账户''安全账户'"),
            ]
            
            findings = 0
            for check_fn, msg in checks:
                if check_fn(user_input):
                    text += f"{msg}\n\n"
                    findings += 1
            
            if findings > 0:
                text += "**结论：您遇到的情况具有明显的诈骗特征！**\n"
                text += "📞 如有疑问，请拨打 **96110** 反诈专线咨询。"
            else:
                text += "请告诉我更多细节，比如：\n"
                text += "• 对方具体说了什么？\n"
                text += "• 是通过什么方式联系你的？（电话/微信/短信）\n"
                text += "• 是否已经进行了转账？"
            
            return {"text": text, "type": "self_check"}

        return {
            "text": (
                "🔍 **我来帮你分析！**\n\n"
                "请告诉我具体情况，我帮你判断是否遇到诈骗。你可以描述：\n"
                "• 对方是谁、怎么联系你的\n"
                "• 对方让你做什么（转账、点链接、下载APP等）\n"
                "• 是否涉及金钱或个人信息\n\n"
                "**🛡️ 快速自查清单：**\n"
                "□ 要求转'安全账户'？ → ❌ 诈骗！\n"
                "□ 声称'稳赚不赔'？ → ❌ 诈骗！\n"
                "□ 贷款前要先交钱？ → ❌ 诈骗！\n"
                "□ 刷单兼职高回报？ → ❌ 诈骗！\n"
                "□ 自称警察要求保密？ → ❌ 诈骗！\n"
                "□ 网恋对象带你投资？ → ❌ 诈骗！\n\n"
                "符合以上任意一条，基本可判断为诈骗！"
            ),
            "type": "self_check"
        }

    def _handle_legal(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        # 尝试检索相关法律
        law_text = ""
        for kw in ["诈骗罪", "帮信罪", "反电信网络诈骗法", "套路贷", "催收"]:
            if kw in user_input:
                law = self.knowledge_retriever.get_law_by_id(kw) if kw in ["帮信罪"] else None
                if not law:
                    law = self.knowledge_retriever.get_law_by_id(f"law_刑法_266") if "诈骗" in kw else None
                if law:
                    law_text += f"**{law['title']}**\n{law['summary']}\n\n"

        if not law_text:
            law_text = (
                "⚖️ **反诈相关法律法规**\n\n"
                "**1. 《刑法》第266条【诈骗罪】**\n"
                "   📌 数额较大→3年以下；巨大→3-10年；特别巨大→10年以上至无期\n\n"
                "**2. 《反电信网络诈骗法》(2022.12.1施行)**\n"
                "   📌 电信、金融、互联网机构需履行反诈责任\n\n"
                "**3. 《刑法》第287条之二【帮信罪】**\n"
                "   📌 出租出借两卡，情节严重→3年以下\n\n"
                "**4. 《刑法》第293条之一【催收非法债务罪】**\n"
                "   📌 暴力/软暴力催收→3年以下\n\n"
                "**举报电话：** 110（报警） | 96110（反诈专线）\n"
                "**举报平台：** 12321.cn"
            )

        return {"text": law_text, "type": "legal"}

    def _handle_scenario(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        scenarios_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base', 'scenarios.json')
        try:
            with open(scenarios_path, 'r', encoding='utf-8') as f:
                scenarios_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {"text": "抱歉，情景模拟加载失败。", "type": "fallback"}

        scenes = []
        for s in scenarios_data.get("scenarios", []):
            scenes.append({
                "id": s["id"],
                "title": s["title"],
                "fraud_type": s["fraud_type"],
                "difficulty": s["difficulty"],
                "description": s["description"]
            })

        return {
            "text": "🎮 **情景模拟训练**\n\n选择以下情景进行防骗闯关训练，在安全环境中学习识别诈骗！",
            "type": "scenario_list",
            "extra_data": {"scenarios": scenes}
        }

    def _handle_fraud_inquiry(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        fraud_type = intent.get("fraud_type", "")
        if fraud_type:
            return self._query_fraud_info(fraud_type)

        # 知识检索匹配
        if knowledge_results:
            best = knowledge_results[0]
            if best.get("similarity", 0) > 0.15:
                return self._query_fraud_info(best["fraud_id"])

        return {
            "text": "请告诉我你想了解哪种诈骗类型，例如：'什么是刷单诈骗'",
            "type": "knowledge"
        }

    def _handle_emergency(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        is_elderly = self._is_elderly_user(user_input)

        if is_elderly:
            return {
                "text": (
                    "🚨 **大爷/大娘，您别慌！听我说！**\n\n"
                    "我理解您现在很着急，但越是这样越要冷静。按我说的做，一步一步来：\n\n"
                    "**1️⃣ 先不要再转钱了！❌**\n"
                    "   不管对方说什么，都不要继续转账\n\n"
                    "**2️⃣ 马上拨打110报警 📞**\n"
                    "   跟警察说清楚情况，要求'紧急止付'\n"
                    "   （转账后30分钟内是黄金时间，越快越好！）\n\n"
                    "**3️⃣ 给您孩子打个电话 📞**\n"
                    "   告诉家人发生了什么，让他们帮忙处理\n\n"
                    "**4️⃣ 联系银行 📞**\n"
                    "   打电话给银行客服，申请冻结对方账户\n\n"
                    "**5️⃣ 保存好证据 📱**\n"
                    "   聊天记录、转账凭证、对方电话都不要删\n\n"
                    "😊 **别害怕！被骗了不是您的错，是骗子太坏了！**\n"
                    "及时报警是挽回损失的最好办法，现在就去！\n\n"
                    "📞 **110**（报警）| **96110**（反诈专线）"
                ),
                "type": "emergency"
            }

        return {
            "text": (
                "🚨 **紧急求助通道**\n\n"
                "检测到您可能正在遭遇诈骗或已经受骗，请保持冷静！\n\n"
                "**请立即采取以下行动：**\n\n"
                "**1️⃣ 立即拨打110报警**\n"
                "   📞 **110** — 告知警方被骗情况\n"
                "   要求**紧急止付**（转账后30分钟内黄金时间）\n\n"
                "**2️⃣ 拨打96110反诈专线**\n"
                "   📞 **96110** — 获取专业指导\n\n"
                "**3️⃣ 联系银行**\n"
                "   立即联系转账银行，申请冻结对方账户\n\n"
                "**4️⃣ 保存证据**\n"
                "   • 聊天记录截图\n"
                "   • 转账凭证\n"
                "   • 对方联系方式\n\n"
                "**不要慌张！** 及时报警是挽回损失的最好方式！\n"
                "您主动来求助是非常正确的选择，接下来的事交给警察来处理！"
            ),
            "type": "emergency"
        }

    def _handle_situation(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        # 描述情景：分析内容并给出初步研判
        is_elderly = self._is_elderly_user(user_input)

        if is_elderly:
            text = "📋 **收到您说的情况了，我帮您分析分析...**\n\n"
        else:
            text = "📋 **收到您的情况描述，正在分析中...**\n\n"

        if fraud_indicators:
            top = fraud_indicators[0]
            if is_elderly:
                fraud_name_cn = {
                    "刷单返利": "刷单兼职", "游戏交易": "游戏交易",
                    "冒充公检法": "冒充公检法", "虚假投资": "虚假投资",
                    "校园贷": "非法校园贷", "冒充客服退款": "冒充客服退款",
                    "虚假征信": "征信", "冒充熟人": "冒充熟人",
                    "交友诈骗": "交友诈骗"
                }
                display_name = fraud_name_cn.get(top['fraud_id'], top['fraud_id'])
                text += f"⚠️ **初步判断：** 您遇到的情况和『{display_name}诈骗』的特征很像。\n\n"
                text += "**他们的套路是这样的：**\n"
            else:
                text += f"⚠️ **初步研判：** 您描述的情况与『{top['fraud_id']}』诈骗特征较为吻合。\n\n"
                text += "**常见手法：**\n"

            fraud_info = self.knowledge_retriever.get_fraud_by_id(top["fraud_id"])
            if fraud_info:
                if is_elderly:
                    # 简化版模式描述
                    simplified = fraud_info.get("common_patterns", [])[:3]
                    for p in simplified:
                        # 简化语言
                        p_simple = p.replace("声称", "骗子跟您说").replace("诱导", "骗您").replace("以...为由", "说是因为")
                        text += f"• {p_simple}\n"
                    text += f"\n**🛡️ 您要这么做：**\n"
                    for a in fraud_info.get("prevention_advice", [])[:3]:
                        text += f"• {a}\n"
                else:
                    for i, p in enumerate(fraud_info.get("common_patterns", [])[:3], 1):
                        text += f"{i}. {p}\n"
                    text += f"\n**🛡️ 防范建议：**\n"
                    for i, a in enumerate(fraud_info.get("prevention_advice", [])[:3], 1):
                        text += f"{i}. {a}\n"

            if is_elderly:
                text += (
                    "\n😊 您别着急，遇到这种情况主动来问是好事！\n"
                    "**记住：** 不管对方说什么，先**不要转钱**，给子女打个电话说说，或者打**96110**问一问。"
                )
        else:
            if is_elderly:
                text += (
                    "根据您说的，我暂时还不太确定是哪一种骗局。\n\n"
                    "**您再跟我说详细一些好吗？比如：**\n"
                    "• 对方是怎么联系您的？（电话、微信还是短信？）\n"
                    "• 对方有没有让您转钱、点链接或者下载东西？\n"
                    "• 有没有涉及银行卡、密码或者验证码？\n\n"
                    "您慢慢说，我帮您分析！😊"
                )
            else:
                text += (
                    "基于现有信息，暂未明确匹配到已知诈骗类型。\n\n"
                    "**为了帮你更准确判断，请补充以下信息：**\n"
                    "• 对方是通过什么方式联系你的？\n"
                    "• 对方是否要求你转账、点链接或下载APP？\n"
                    "• 是否涉及金钱或个人敏感信息？\n\n"
                    "你也可以直接发送可疑链接给我分析 🔍"
                )

        # 如果有风险检测结果，添加
        if risk.get("has_risk"):
            if is_elderly:
                text += "\n\n⚠️ 系统发现您说的情况里有风险信号，您要多加小心！拿不准的可以打96110问问。"
            else:
                text += "\n\n⚠️ 注意：系统检测到您的描述中存在风险行为特征，请提高警惕！"

        return {"text": text, "type": "self_check"}

    def _handle_provide_info(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        """处理用户单纯提供个人信息（手机号 / 身份证 / 银行卡 / 验证码等）的情况"""
        is_elderly = self._is_elderly_user(user_input)
        if is_elderly:
            text = (
                "🙏 **收到您发的信息了。**\n\n"
                "🔒 您发的个人信息，系统已经**自动打码保护**，不会泄露出去，您放心。\n\n"
                "**不过要提醒您：**\n"
                "• 不要把自己的手机号、身份证号、银行卡号、验证码告诉陌生人\n"
                "• 尤其是**验证码**，谁问都不能给，包括自称『客服』『警察』的人\n\n"
                "您是想问什么呢？比如『有人让我转账是不是骗子』，我帮您看看。"
            )
        else:
            text = (
                "📥 **已收到您提供的信息。**\n\n"
                "🔒 其中的个人信息已由系统**自动加密并脱敏**（如 `138****5678`），不会明文留存。\n\n"
                "**安全提示：**\n"
                "• 手机号、身份证号、银行卡号、验证码都属于敏感信息，请勿透露给陌生人\n"
                "• 特别是**短信验证码**，任何正规机构都不会向你索要\n\n"
                "你想让我帮你做什么？可以直接描述遇到的情况，比如「有人让我转账」「帮我看看这个链接」。"
            )
        return {"text": text, "type": "provide_info"}

    def _handle_feedback(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        return {
            "text": "谢谢你的反馈！我们会持续改进，更好地为大家提供反诈服务。🛡️",
            "type": "feedback"
        }

    def _handle_confusion(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        """处理用户表示不理解/困惑的情况 - 用简单温暖的语言重新解释"""
        # 判断是否是老年人
        is_elderly = self._is_elderly_user(user_input)

        # 从对话历史中获取上一个话题
        last_context = intent.get("context", {})
        last_intent = last_context.get("last_intent", "")

        if is_elderly:
            prefix = (
                "😊 别着急，大爷/大妈，我给您用大白话说说：\n\n"
            )
            closing = (
                "\n\n您看这样说能明白吗？要是还有不清楚的，您接着问我就行，咱们慢慢说 📞"
            )
        else:
            prefix = (
                "😊 没关系，别着急，我用简单的话再给您说一遍：\n\n"
            )
            closing = (
                "\n\n这样说是不是清楚多了？如果还有不明白的地方，随时告诉我，我换个方式给您讲！"
            )

        # 根据上一轮对话语气决定回复内容
        if last_intent in ("knowledge_queries", "fraud_inquiry"):
            fraud_type = intent.get("fraud_type", "") or (fraud_indicators[0]["fraud_id"] if fraud_indicators else "")
            if fraud_type:
                text = self._simplify_fraud_explanation(fraud_type)
            else:
                text = "防诈骗最重要的就是记住：**凡是让您先交钱的，都要多留个心眼！** 不管是刷单兼职、客服退款还是安全账户，说到底都是让您掏钱。只要涉及到转账汇款，一定要先核实！"
        elif last_intent in ("self_check", "describe_situation"):
            text = (
                "判断是不是诈骗，记住这几点就可以了：\n\n"
                "✅ **要您先交钱的** → 大概率是骗子\n"
                "✅ **说稳赚不赔的** → 肯定是骗人的\n"
                "✅ **让您别告诉家人的** → 就是诈骗\n"
                "✅ **要求共享屏幕的** → 绝对不要信\n\n"
                "总之，只要陌生人让您**转钱**、**点链接**、**下载APP**、**给验证码**，十有八九是骗子！"
            )
        elif last_intent in ("emergency",):
            text = (
                "您现在的情况比较紧急，我简单直说：\n\n"
                "**第一步：马上停止转账！**\n"
                "**第二步：立刻拨打110报警！**\n"
                "**第三步：联系银行冻结账户！**\n\n"
                "其他事情先不要管，按这三步走就行！"
            )
        else:
            # 通用简单解释
            text = (
                "简单点说就是：**凡是陌生人让您转钱、点链接、给验证码的，基本都是诈骗！**\n\n"
                "🛡️ 您记住这几条：\n"
                "• **不轻信** — 陌生电话别全信\n"
                "• **不转账** — 让您转钱的先核实\n"
                "• **不透露** — 验证码谁都不能给\n"
                "• **不点链接** — 不明链接不要点\n\n"
                "不管遇到什么事，拿不准的随时来问我！"
            )

        return {
            "text": prefix + text + closing,
            "type": "confusion"
        }

    def _handle_fear_anxiety(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        """处理用户感到害怕/焦虑的情况 - 给予温暖安抚和明确指导"""
        # 检测紧急程度
        has_risk = risk.get("has_risk", False)
        risk_level = risk.get("risk_level", "none")

        if has_risk and risk_level in ("high", "critical"):
            # 高风险+害怕情绪：先安抚，再给行动指引
            text = (
                "🤗 **别慌，有我在！**\n\n"
                "您现在感到害怕和担心是非常正常的，谁遇到这种情况都会紧张。但是请放心，我们一步一步来解决！\n\n"
                "**您现在最需要做的三件事：**\n"
                "1️⃣ **立即停止任何转账或付费操作**\n"
                "2️⃣ **保存好所有聊天和转账记录**\n"
                "3️⃣ **拨打110报警** — 警察会帮助您的！\n\n"
                "💪 您已经做得很好了——主动来咨询就是保护自己的第一步！不管遇到什么问题，都有办法解决，不要一个人扛着。"
            )
        else:
            text = (
                "🤗 **别担心，我来帮您！**\n\n"
                "您主动来咨询是非常正确的做法！很多人遇到可疑情况都会紧张，但请放心，我会帮您分析清楚。\n\n"
                "您可以把您遇到的情况详细告诉我，我们一起分析是不是有问题。\n\n"
                "**请记住：** 不管遇到什么事，都不要一个人闷着，跟家人说说，或者来问我，我们一起应对！🛡️"
            )

        return {
            "text": text,
            "type": "comfort"
        }

    def _handle_elderly(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        """处理老年人用户 - 特别温暖、简单、耐心的响应"""
        if risk.get("has_risk") and risk.get("risk_level") in ("high", "critical"):
            text = (
                "🙏 **大爷/大妈，您听我说！**\n\n"
                "您遇到的这个情况很可能是骗局！但别担心，有我们在！\n\n"
                "**您听我的，先做这三件事：**\n"
                "1️⃣ **千万别转账！** 不管对方说什么，都不要给钱\n"
                "2️⃣ **给子女打个电话**，跟他们说说这个情况\n"
                "3️⃣ **打110报警**，让警察来帮您\n\n"
                "😊 记住啊，**公检法不会电话办案，没有安全账户，刷单就是诈骗**。\n"
                "如果拿不准，您就打96110反诈专线问一问，这个电话是免费的！\n\n"
                "📞 **紧急电话：** 110（报警）| 96110（反诈专线）"
            )
        else:
            text = (
                "😊 **大爷/大妈您好！**\n\n"
                "欢迎来反诈卫士咨询！我来给您简单说说防骗的知识：\n\n"
                "🛡️ **记住四个'不'就行了：**\n"
                "• **不轻信** — 陌生电话、短信别信\n"
                "• **不转账** — 让您转钱的都是骗子\n"
                "• **不透露** — 银行卡号、密码、验证码谁也不能给\n"
                "• **不点链接** — 不认识的人发的链接别点\n\n"
                "📞 **有事就打这两个电话：**\n"
                "• **110** — 报警电话\n"
                "• **96110** — 反诈专线（免费咨询）\n\n"
                "遇到拿不准的事，您先问问子女，或者来问我！我会给您说得清清楚楚、明明白白的！"
            )

        return {
            "text": text,
            "type": "elderly_care"
        }

    def _handle_thanks(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        """用户感谢时的温暖回应"""
        warm_responses = [
            "不客气！能帮到您我很高兴 😊 记住遇到可疑情况随时来找我，拿不准的时候多问问总没错！🛡️",
            "您太客气了！保护大家的钱袋子就是我的职责 😊 记得把这些防骗知识也告诉家人朋友哦！",
            "很高兴能帮到您！反诈路上我们一起努力 💪 下次遇到拿不准的事情，随时来找我！",
            "应该的！您能主动了解防骗知识，这本身就非常棒 👏 祝您生活愉快，远离诈骗！🛡️",
        ]
        import random
        return {
            "text": random.choice(warm_responses),
            "type": "thanks"
        }

    def _is_elderly_user(self, text: str) -> bool:
        """判断用户是否为老年人"""
        elderly_patterns = [
            "我老了", "年纪大了", "老年人", "老人", "老同志",
            "上了年纪", "岁数大了", "不年轻了", "老人家",
            "退休", "六十几", "七十几", "八十多", "老头", "老太太"
        ]
        return any(p in text for p in elderly_patterns)

    def _simplify_fraud_explanation(self, fraud_type: str) -> str:
        """用简单白话解释诈骗类型"""
        simple_explanations = {
            "刷单返利": (
                "什么叫刷单诈骗呢？🤔\n\n"
                "就是骗子和您说：'您帮我刷刷单、做做任务，不用出门，动动手指就能赚钱，日赚几百没问题！'\n"
                "一开始他真的会给您几块钱，让您觉得是真的。\n"
                "等您相信了，他就让您做大单、连单，让您先垫钱。\n"
                "等您转了大钱过去，他就消失了，钱也要不回来了。\n\n"
                "**记住：凡是让您先垫钱再返利的，都是骗子！**"
            ),
            "游戏交易": (
                "游戏交易诈骗就是骗子和您说：'我有便宜的皮肤、装备，低价卖给你'或者'你的账号需要解冻，交个保证金'。\n"
                "等您付了钱，东西没拿到，人也找不到了。\n\n"
                "**记住：游戏交易要走官方平台，不要私下转账！**"
            ),
            "冒充公检法": (
                "这种骗子最坏！他们冒充公安局、检察院的人，说您'涉嫌洗钱'、'有通缉令'，吓唬您。\n"
                "然后让您把存款转到'安全账户'，还说'不能告诉家人'。\n\n"
                "**记住：公安局不会打电话办案！没有什么'安全账户'！遇到这种情况直接挂掉打110核实！**"
            ),
            "虚假投资": (
                "骗子和您说有个好项目，稳赚不赔，月收益百分之三四十。\n"
                "刚开始让您投一点，真的给您返钱。等您投了大钱，平台就打不开了。\n\n"
                "**记住：哪有稳赚不赔的好事？真有这种好事，别人为什么要告诉您？**"
            ),
            "校园贷": (
                "骗子跟学生说可以低利息贷款，不用抵押。\n"
                "等您借了钱，各种手续费、逾期费就来了，越欠越多。\n"
                "还不上就威胁您，把照片发给学校、家人。\n\n"
                "**记住：学生缺钱找家长、找学校，不要碰非法贷款！**"
            ),
            "冒充客服退款": (
                "骗子假装是淘宝、京东的客服，说您买的商品有问题要退款，或者快递丢了要赔偿。\n"
                "然后让您点链接、输银行卡号和验证码，或者开屏幕共享。\n"
                "等您操作完，卡里的钱就被转走了。\n\n"
                "**记住：真有退款，在APP里自己操作就行，客服不会主动打电话让您退款的！**"
            ),
            "虚假征信": (
                "骗子说您以前开通的贷款账户影响征信，不注销就不能贷款买房买车。\n"
                "让您在借呗、白条上借钱转给他们，说会帮您还上。\n"
                "结果钱转过去，人就消失了。\n\n"
                "**记住：征信是央行统一管理的，没有'花钱修复'这一说！**"
            ),
            "冒充熟人": (
                "骗子冒充您的朋友、孩子、领导，说换了新号，急用钱让您帮忙转一下。\n"
                "有些人甚至用AI技术模仿您家人的声音和样子。\n\n"
                "**记住：只要涉及到借钱转账，一定要打电话或当面确认是不是本人！**"
            ),
            "交友诈骗": (
                "一种是在网上和您谈恋爱，然后以各种理由要钱。\n"
                "另一种是诱导您视频裸聊，录下来敲诈您。\n\n"
                "**记住：没见过面就提钱的，100%是骗子！不要和陌生人视频裸聊！**"
            ),
        }
        return simple_explanations.get(fraud_type, "防诈骗最重要的就是记住一句话：**凡是陌生人让您转钱、点链接、给验证码的都是诈骗！**")

    def _get_simplified_prevention(self) -> str:
        """返回超级简化的防骗指南"""
        return (
            "🛡️ **简单防骗口诀：**\n\n"
            "**陌生人让您做的这几件事，全都是诈骗：**\n\n"
            "🚫 **转账汇款** → 先核实，不打钱\n"
            "🚫 **点链接/扫码** → 不要点，不要扫\n"
            "🚫 **下载APP** → 官方商店才有保障\n"
            "🚫 **给验证码** → 谁都不能给\n"
            "🚫 **屏幕共享** → 关掉！别开！\n\n"
            "📞 **拿不准？打电话问！**\n"
            "• **110** - 报警\n"
            "• **96110** - 反诈专线"
        )

    def _handle_fallback(self, intent, user_input, risk, knowledge_results=None, fraud_indicators=None):
        # 检测是否包含URL → 自动分析
        url_pattern = r'https?://[^\s<>"\'，。；；！？、]+'
        import re
        urls = re.findall(url_pattern, user_input)
        if urls:
            return self._handle_url_report(urls[0])

        # 知识检索兜底
        if knowledge_results:
            best = knowledge_results[0]
            if best.get("similarity", 0) > 0.3:
                return self._query_fraud_info(best["fraud_id"])
            # 即使相似度不高，但如果有明显的诈骗特征描述，也尝试返回信息
            if fraud_indicators and fraud_indicators[0].get("confidence", 0) >= 0.5:
                return self._query_fraud_info(fraud_indicators[0]["fraud_id"])

        # 诈骗短语直接匹配（即使知识检索没找到）
        fraud_type = intent.get("fraud_type", "")
        if fraud_type:
            return self._query_fraud_info(fraud_type)

        # 检查诈骗指示器（直接关键词匹配）
        if fraud_indicators and fraud_indicators[0].get("confidence", 0) >= 0.5:
            return self._query_fraud_info(fraud_indicators[0]["fraud_id"])

        # 检测是否为老年人
        is_elderly = self._is_elderly_user(user_input)

        if is_elderly:
            return {
                "text": (
                    "😊 **大爷/大娘，您能再说详细一些吗？**\n\n"
                    "我有点儿没完全明白您的意思，您可以跟我说说：\n\n"
                    "• 🤔 **您遇到了什么事？**（有人给您打电话、发短信还是微信？）\n"
                    "• 💰 **有没有涉及钱？**（对方有没有让您转账、汇款？）\n"
                    "• 📱 **有没有让您点链接或下载东西？**\n\n"
                    "您慢慢说，想到什么说什么，我帮您分析！\n"
                    "如果事儿比较急，您也可以直接打 **96110** 反诈专线问问！"
                ),
                "type": "elderly_care"
            }

        confusion_patterns = ["不懂", "不理解", "不太懂", "没明白", "说明白", "什么意思"]
        if any(p in user_input for p in confusion_patterns):
            return self._handle_confusion(intent, user_input, risk, knowledge_results, fraud_indicators)

        templates = self.patterns.get("response_templates", {}).get("fallback", [])
        text = random.choice(templates) if templates else (
            "我理解你的问题，但不太确定你具体想了解什么。你可以试试：\n"
            "• 说'帮我识别骗局' 让我分析你的情况\n"
            "• 说'我想了解XX诈骗' 获取相关知识\n"
            "• 说'情景模拟' 进行防骗闯关训练\n"
            "• 直接描述你遇到的情况"
        )
        return {"text": text, "type": "fallback"}

    def _handle_url_report(self, url: str):
        result = self.url_analyzer.analyze_url(url)
        content_result = self.url_analyzer.analyze_content(url)
        self.url_analyzer.record_report("default", url, result, content_result)

        return {
            "text": (
                f"🔗 **链接分析报告**\n\n"
                f"**风险等级：** {'⚠️ 高危' if result['risk_level'] == 'critical' else '🔴 高风险' if result['risk_level'] == 'high' else '🟡 中风险' if result['risk_level'] == 'medium' else '🟢 低风险'}\n"
                f"**域名：** {result.get('domain', '未知')}\n\n"
                + ("**风险详情：**\n" + "\n".join(f"• {d}" for d in result["details"]) if result["details"] else "**未发现异常特征**")
                + f"\n\n**{result.get('advice', '')}**"
                + "\n\n📢 如需举报，请使用页面的举报功能提交。"
            ),
            "type": "url_report",
            "extra_data": {"url_analysis": result}
        }

    def _query_fraud_info(self, fraud_type: str) -> dict:
        """查询特定诈骗类型的信息（增强版，使用知识库）"""
        fraud = self.knowledge_retriever.get_fraud_by_id(fraud_type)
        if not fraud:
            return {"text": "抱歉，我暂时没有找到该类型的诈骗信息。你可以试试其他关键词。", "type": "fallback"}

        # 获取关联骗局
        related = self.knowledge_retriever.get_related_frauds(fraud_type)
        related_text = ""
        if related:
            related_text = "\n\n**🔗 关联骗局：** " + "、".join(r["id"] for r in related)

        # 典型案例
        case_text = ""
        if fraud.get("case_studies"):
            case = fraud["case_studies"][0]
            case_text = f"\n\n**📋 典型案例：**\n{case.get('title', '')}\n{case.get('process', '')[:200]}...\n教训：{case.get('lesson', '')}"

        text = (
            f"🔍 **{fraud['id']}诈骗**\n"
            f"风险等级: {'🔴 高危' if fraud['risk_level'] == 'critical' else '🔴 高风险' if fraud['risk_level'] == 'high' else '🟡 中风险'}\n\n"
            f"**骗局描述：**\n{fraud['description']}\n\n"
            f"**常见手法：**\n"
        )
        for i, pattern in enumerate(fraud.get("common_patterns", []), 1):
            text += f"{i}. {pattern}\n"

        text += f"\n**🎯 受害群体：**\n"
        targets = fraud.get("victim_analysis", {}).get("target_groups", [])
        text += "、".join(targets) + "\n"

        text += f"\n**🛡️ 防范建议：**\n"
        for i, advice in enumerate(fraud.get("prevention_advice", []), 1):
            text += f"{i}. {advice}\n"

        text += case_text + related_text
        text += "\n\n💡 如有疑问，请拨打 **96110** 反诈专线咨询。"

        return {"text": text, "type": "knowledge", "extra_data": {"fraud": fraud}}

    def _format_url_warning(self, url_result: dict) -> str:
        return (
            f"\n\n🚨 **链接安全警告！**\n"
            f"风险等级: {'⚠️ 高危' if url_result['risk_level'] == 'critical' else '🔴 高风险' if url_result['risk_level'] == 'high' else '🟡 中风险'}\n"
            + "\n".join(f"• {d}" for d in url_result["details"][:3])
            + f"\n\n{url_result.get('advice', '')}"
        )

    # ========== 情景模拟 ==========

    def start_scenario(self, scenario_id: str) -> dict:
        """开始一个情景模拟"""
        scenarios_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base', 'scenarios.json')
        try:
            with open(scenarios_path, 'r', encoding='utf-8') as f:
                scenarios_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

        for s in scenarios_data.get("scenarios", []):
            if s["id"] == scenario_id:
                steps = s.get("steps", [])
                if not steps:
                    return None
                step = steps[0]
                return {
                    "scenario": s["title"],
                    "fraud_type": s["fraud_type"],
                    "step": step["order"],
                    "npc_message": step["npc_message"],
                    "choices": step["choices"],
                    "total_steps": len(steps),
                    "completion_message": s.get("completion_message", ""),
                    "stats": s.get("statistics", {})
                }
        return None

    def process_scenario_step(self, scenario_id: str, step_order: int,
                               choice_index: int) -> dict:
        """处理情景模拟的一步"""
        scenarios_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base', 'scenarios.json')
        try:
            with open(scenarios_path, 'r', encoding='utf-8') as f:
                scenarios_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

        for s in scenarios_data.get("scenarios", []):
            if s["id"] == scenario_id:
                steps = s.get("steps", [])
                if step_order < 1 or step_order > len(steps):
                    return None
                step = steps[step_order - 1]
                choices = step.get("choices", [])
                if choice_index < 0 or choice_index >= len(choices):
                    return None
                choice = choices[choice_index]

                result = {
                    "chosen_text": choice["text"],
                    "score": choice["score"],
                    "feedback": choice["feedback"],
                    "is_safe": choice["is_safe"]
                }

                # 是否有下一步
                if step_order < len(steps):
                    next_step = steps[step_order]
                    result["has_next"] = True
                    result["next_step"] = {
                        "step": next_step["order"],
                        "npc_message": next_step["npc_message"],
                        "choices": next_step["choices"]
                    }
                else:
                    result["has_next"] = False
                    result["completed"] = True
                    result["completion_message"] = s.get("completion_message", "")

                return result
        return None

    # ========== v3.0 RAG 增强生成 ==========

    def _build_knowledge_sources(self, user_input: str, top_k: int = 3) -> dict:
        """
        生成「依据来源」归属信息 —— 回答"这条结论是查了知识库哪几条得到的"。

        纯本地检索，不依赖 LLM：即使外部 API 关着（默认的本地模式）也能用，
        前端可据此展示命中的诈骗类型、相似度与关键词，让回复可追溯、可解释。
        """
        try:
            results = self.knowledge_retriever.semantic_search(user_input, top_k=top_k)
        except Exception:
            return {}

        if not results:
            return {}

        matched = []
        for r in results:
            fid = r.get("fraud_id", "")
            item = {
                "id": fid,
                "score": round(float(r.get("similarity", 0) or 0), 4),
                "match_type": r.get("match_type", "keyword"),
                "risk_level": r.get("risk_level", ""),
            }
            # 关键词命中项便于"为什么匹配上"的解释，语义命中时可能为空
            fraud = self.knowledge_retriever.get_fraud_by_id(fid)
            if fraud:
                hit = [kw for kw in fraud.get("keywords", [])
                       if kw and kw in user_input]
                if hit:
                    item["hit_keywords"] = hit[:5]
            matched.append(item)

        return {
            "matched_fraud_types": matched,
            # score 是「本次检索内归一化」的相对匹配度（Top-1 恒为 1.0），不是绝对置信度。
            # 命名用 score 而非 similarity —— 语义路才算余弦，关键词路是归一化命中分。
            "score_type": "relative",
            "retrieval_mode": matched[0].get("match_type", "keyword") if matched else "",
            "source": "本地知识库（16 类诈骗 / 293 关键词 / 79 话术模板）",
        }

    def generate_response_enhanced(self, user_input: str, user_id: str = "default",
                                    dialog_history: list = None) -> dict:
        """
        v3.0 增强响应生成 — 规则引擎 + RAG/LLM 双模

        策略:
        - 简单/高置信度 → 规则引擎快速响应
        - 复杂/模糊/开放问题 → RAG+LLM 深度回复
        """
        # 1. 先获取增强意图识别结果（规则 + 语义融合）
        try:
            intent_result = self.recognizer.recognize_enhanced(
                user_input, user_id, dialog_history
            )
        except Exception:
            intent_result = self.recognizer.recognize(user_input, user_id, dialog_history)

        # 2. 复用同一份意图结果生成基础响应，避免重复做语义编码
        base_result = self.generate_response(
            user_input, user_id, dialog_history, intent_result=intent_result
        )

        confidence = intent_result.get("confidence", 0)
        mode = intent_result.get("recognition_mode", "rule")

        # 2.5 依据来源归属（纯本地，不依赖 LLM）
        knowledge_sources = self._build_knowledge_sources(user_input)

        # 3. 判断是否使用 RAG
        try:
            from engine.rag_engine import get_rag_engine
            rag = get_rag_engine()

            if rag.is_available and rag.should_use_rag(user_input, confidence):
                rag_response = rag.generate(user_input, dialog_history)

                if rag_response:
                    # 合并规则分析 + RAG 回复
                    risk = base_result.get("risk_analysis", {})
                    return {
                        "response": rag_response,
                        "type": "rag_enhanced",
                        "recognition_mode": "rag",
                        "semantic_enhanced": True,
                        "risk_analysis": risk,
                        "suggestions": base_result.get("suggestions", []),
                        "intent": intent_result.get("intent", "unknown"),
                        "fraud_type": intent_result.get("fraud_type", ""),
                        "knowledge_sources": knowledge_sources,
                    }
        except Exception:
            pass

        # 4. RAG 不可用或不需要时，返回增强的规则引擎结果
        base_result["recognition_mode"] = mode
        base_result["semantic_enhanced"] = (mode != "rule")
        base_result["_engine"] = "v3.0-20260731"
        if knowledge_sources:
            base_result["knowledge_sources"] = knowledge_sources
        return base_result
