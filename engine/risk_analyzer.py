"""增强风险行为研判引擎 - 多维度规则 + 时序分析 + 个性化劝阻"""

import json
import re
import os
import time
from typing import Optional


class RiskAnalyzer:
    """风险行为研判引擎，支持多维度规则匹配、时序分析、个性化劝阻"""

    RISK_RULES = {
        "转账到陌生账户": {
            "patterns": [
                r"转[账款].*[陌生他人].*[账户卡号]",
                r"向.*[转汇].*[钱款].*[陌生]",
                r"打[钱款].*给.*[不认识不认识]",
                r"[转汇打]了.*[钱].*给.*[他人陌陌]",
                r"转账.*[到去].*[账户卡号].*[个人]",
                r"(向|给|往|朝).{0,6}(陌生|不认识的?).{0,6}(账户|账号|卡号|卡).{0,8}(汇|转|打|寄)",
                r"(陌生|不认识的?).{0,6}(账户|账号|卡号).{0,8}(转账|汇款|打款|转钱|汇钱|打钱)",
            ],
            "weight": 1.0,
            "category": "资金风险",
            "intervention": "资金转出风险"
        },
        "提供验证码": {
            "patterns": [
                r"[发给告诉透露提供索要].{0,6}验证码",
                r"验证码.{0,6}[告诉发给透露提供索要报念读]",
                r"短信.{0,6}验证码.{0,6}[发给提供报]",
                r"把验证码.{0,4}(过去|给他|给她|发)",
                r"验证码.{0,4}[报念读].{0,4}[他她它人方]",
                r"(让|要|叫|要求|让我).{0,8}(提供|给|发|报|说|念).{0,6}验证码",
            ],
            "weight": 1.0,
            "category": "信息泄露",
            "intervention": "验证码泄露风险"
        },
        "泄露银行卡密码": {
            "patterns": [
                r"(银行卡|卡).{0,4}(密码|取款密码|支付密码).{0,8}(告诉|发给|说|泄露|提供|给|报)",
                r"(告诉|发给|说|泄露|提供|报).{0,8}(银行卡|卡).{0,4}(密码|取款密码|支付密码)",
                r"(把|将).{0,4}(银行卡|卡).{0,4}密码.{0,6}(告诉|发给|说|给|报)",
            ],
            "weight": 1.0,
            "category": "信息泄露",
            "intervention": "银行卡密码泄露风险"
        },
        "点击不明链接": {
            "patterns": [
                r"点[击开].*[链接网址]",
                r"[链接网址].*[点打开]",
                r"下[载].*APP.*[链接网址]",
                r"扫码.*下[载安装]",
                r"二维码.*[扫识别]",
            ],
            "weight": 0.7,
            "category": "恶意链接",
            "intervention": "点击不明链接风险"
        },
        "屏幕共享": {
            "patterns": [
                r"屏幕[共享分享]",
                r"共享屏幕",
                r"远程[操作控制协帮]",
                r"分享屏幕",
                r"[下安].*会议[软件APP]",
                r"zoom.*[会直]", "腾讯会议.*共享", "钉钉.*共享",
            ],
            "weight": 1.0,
            "category": "信息泄露",
            "intervention": "屏幕共享风险"
        },
        "下载不明APP": {
            "patterns": [
                r"下[载].*APP",
                r"安装.*[软件应用]",
                r"扫码.*下[载安装]",
                r"APK.*下[载]",
                r"通过.*链接.*下[载]",
            ],
            "weight": 0.65,
            "category": "恶意软件",
            "intervention": "下载不明软件风险"
        },
        "提供身份证照片": {
            "patterns": [
                r"[身份].*[证照].*[拍发给]",
                r"手持.*身份[证照]",
                r"银行卡.*照片",
                r"身份证.*正反面",
                r"拍[了].*身份",
                r"(拍|发|提供|给|上传).{0,8}(身份证|身份).{0,6}(正反面|照片|图片|照)",
            ],
            "weight": 1.0,
            "category": "信息泄露",
            "intervention": "证件信息泄露风险"
        },
        "网贷诱导": {
            "patterns": [
                r"贷[款].*[学无抵押低息]",
                r"[学美容培训].*贷",
                r"网贷.*[学生无抵押]",
                r"借款.*[学手续费]",
                r"以贷养贷",
            ],
            "weight": 0.75,
            "category": "诱导借贷",
            "intervention": "网贷诱导风险"
        },
        "刷单/兼职": {
            "patterns": [
                r"刷[单信誉].*[赚钱返利]",
                r"兼职.*[日赚轻松]",
                r"[点赞关注].*[返利赚钱]",
                r"做任务.*[返利佣金]",
                r"试[单单玩].*[返利佣金]",
                r"联单|连单.*[任务]",
            ],
            "weight": 0.7,
            "category": "刷单诈骗",
            "intervention": "刷单返利风险"
        },
        "冒充公检法": {
            "patterns": [
                r"[公安检察院法院警察].*[涉嫌犯罪案]",
                r"安全账户",
                r"通缉[令]",
                r"逮捕[令]",
                r"资金清查",
                r"资金(核查|审查|清查)",
                r"涉嫌.{0,6}(洗钱|诈骗|犯罪|违法)",
                r"视频笔录",
                r"保密.*[案件案情]",
                r"洗钱.*[涉嫌]",
                r"(自称|说是|号称|冒充)?(派出所|公安局|检察院|法院|警察|公安).{0,12}(让|要|叫|要求).{0,6}(转|汇|打)",
                r"(让|要|叫|要求)我.{0,8}(转钱|转账|汇款|打款|打钱).{0,12}(派出所|公安局|检察院|法院|警察|公安)",
            ],
            "weight": 1.0,
            "category": "冒充公检法",
            "intervention": "冒充公检法风险"
        },
        "虚假投资诱导": {
            "patterns": [
                r"稳赚不赔",
                r"内幕消息.*[股票投资]",
                r"保证收益.*[%倍]",
                r"[导师老师专家].*[荐带操盘]",
                r"杀猪盘",
                r"原始股.*[内部分配]",
                r"[导师老师专家高手].{0,6}(带|领|教|指导|荐).{0,6}(投资|理财|炒股|买|操作)",
                r"(带|领|教).{0,4}我.{0,6}(投资|理财|炒股|赚钱|操作)",
            ],
            "weight": 1.0,
            "category": "投资诈骗",
            "intervention": "虚假投资风险"
        },
        "高额回报承诺": {
            "patterns": [
                r"日[赚入收].*[千百]",
                r"月[入收].*[万过]",
                r"[百分之几].*[回报收益利润]",
                r"[翻倍倍增].*[赚收利]",
            ],
            "weight": 0.6,
            "category": "虚假承诺",
            "intervention": "高额回报风险"
        },
        "冒充客服退款": {
            "patterns": [
                r"退款.*[链接网址]",
                r"双倍退款|三倍退款",
                r"质量[问题].*退款",
                r"快递丢失.*赔偿",
                r"理赔.*[链接扫码]",
            ],
            "weight": 0.7,
            "category": "冒充客服",
            "intervention": "冒充客服退款风险"
        },
        "注销账户": {
            "patterns": [
                r"注销.*[账户贷款]",
                r"贷款记录.*[消除注销]",
                r"校园贷.*[记录注销]",
                r"征信.*[修复消除洗白]",
            ],
            "weight": 1.0,
            "category": "注销账户诈骗",
            "intervention": "注销账户诈骗风险"
        },
        "杀猪盘恋爱诱导": {
            "patterns": [
                r"网恋.*[投资理财]",
                r"对象.*[带让].*[投资赚钱]",
                r"女朋友.*[投资理财赚]",
                r"男朋友.*[投资理财赚]",
                r"相亲.*[投资理财平台]",
            ],
            "weight": 1.0,
            "category": "杀猪盘",
            "intervention": "杀猪盘诈骗风险"
        },
        "冒充银行诱导转账": {
            "patterns": [
                r"自称.*(银行|客服|工作人员).*(打款|转账|汇款|转钱)",
                r"(银行|客服|工作人员).*(打款|转账).*返",
                r"(银行|客服).*指定.*(账户|卡号).*(转账|打款)",
                r"自称.*(农业|建设|工商|中国|招商|交通|邮储).*银行",
                r"(银行|客服|工作人员).{0,15}(让|要|叫|要求).{0,6}(转|汇|打)",
            ],
            "weight": 1.0,
            "category": "冒充银行诈骗",
            "intervention": "冒充银行诱导转账风险"
        },
        "连本带利返利承诺": {
            "patterns": [
                r"连本带利",
                r"(投入|转入|存入|转账).*(返利|返现|返款)",
                r"给.*(账户|账号|卡号).*打.*钱.*(返|回)",
                r"(投资|转账).*(翻倍|高额返|高利息)",
            ],
            "weight": 1.0,
            "category": "虚假返利承诺",
            "intervention": "诱导转账返利风险"
        },
        "冒充客服诱导操作": {
            "patterns": [
                r"客服.*(指导|协助|帮助).*(操作|转账|下载)",
                r"(微信|QQ|电话).*(客服|工作人员).*(退|赔|返)",
                r"(关闭|取消).*(服务|业务).*(否则|不然)",
                r"客服.{0,10}(让|要|叫|要求|指导|引导).{0,8}(下载|安装|点|打开|操作|转账|退款)",
                r"(下载|安装).{0,6}(APP|软件|应用).{0,8}(退款|理赔|注销|解冻|验证)",
            ],
            "weight": 1.0,
            "category": "冒充客服诈骗",
            "intervention": "冒充客服诱导操作风险"
        },
        "被要求转账": {
            "patterns": [
                r"(让|要|叫|要求|指示|催)我.{0,6}(转钱|转账|打款|汇款|打钱|转过去)",
                r"(让|要|叫|要求)我.{0,4}去.{0,4}银行.{0,4}(转|汇|打)",
                r"(对方|他们|客服|银行|警察|派出所).{0,10}(让|要|叫|要求).{0,6}(转|汇|打款|打钱)",
            ],
            "weight": 0.6,
            "category": "资金风险",
            "intervention": "被要求转账风险"
        },
        "追加投入诱导": {
            "patterns": [
                r"(再|又|继续|追加|补).{0,3}(投|加|充|转).{0,6}(万|千|百|钱|块|元)",
                r"(让|要|叫|要求)我.{0,4}(再|继续).{0,3}(加|投|充|转)",
                r"(加大|追加).{0,4}(投入|投资|资金|金额)",
            ],
            "weight": 0.6,
            "category": "诱导追加投入",
            "intervention": "诱导追加投入风险"
        },
        "小额获利诱饵": {
            "patterns": [
                r"(投|充|入|存).{0,4}\d+.{0,12}(赚|挣|盈利|收益).{0,4}\d+",
                r"赚了.{0,8}(现在|又|却|就).{0,6}(让|要|叫).{0,4}(加|投|充|转)",
                r"(一单|每单|做完|刷完).{0,4}(返|赚|得|给).{0,4}\d+",
            ],
            "weight": 0.5,
            "category": "返利诱饵",
            "intervention": "小额返利诱饵风险"
        },
        "提现门槛诱导": {
            "patterns": [
                r"(完成|做完|刷完|凑够|达到).{0,8}(单|任务|笔|金额|额度|要求).{0,10}(才能|就能|即可|才可|可以).{0,4}(提现|结算|返还|取出)",
                r"(提现|结算|取款).{0,8}(需要|要|得|必须).{0,8}(完成|做完|再|先).{0,8}(单|任务|充值|投入|金额|操作)",
                r"(三单|五单|十单|几单|多单|连单|联单).{0,8}(提现|结算|返)",
            ],
            "weight": 0.5,
            "category": "刷单诈骗",
            "intervention": "提现门槛诱导风险"
        }
    }

    # 劝阻话术模板库（按风险等级+场景）
    INTERVENTION_LIBRARY = {
        "critical": {
            "通用": (
                "🚨 **紧急风险警告！**\n"
                "您当前的行为存在极高的被骗风险！请立即停止操作并核实对方身份。\n\n"
                "**立即行动：**\n"
                "1️⃣ 停止所有转账和操作\n"
                "2️⃣ 不要提供任何个人信息\n"
                "3️⃣ 拨打 **110** 报警\n"
                "4️⃣ 拨打 **96110** 反诈专线咨询\n\n"
                "**记住：** 骗子会利用你的恐惧/贪婪心理，冷静下来，寻求帮助！"
            ),
            "资金风险": (
                "🚨 **资金安全紧急预警！**\n"
                "检测到您正在向陌生账户转账汇款！\n\n"
                "⚠️ 请先确认以下问题：\n"
                "• 你认识收款方吗？见过面吗？\n"
                "• 对方是否催促你尽快转账？\n"
                "• 收款账户是否是个人账户？\n\n"
                "**建议：** 延迟24小时再转账，先与家人朋友商量！"
            ),
            "信息泄露": (
                "🚨 **信息泄露紧急预警！**\n"
                "您正在向他人提供重要的个人敏感信息！\n\n"
                "⚠️ 注意：\n"
                "• **验证码** = 资金账户的最后一道防线，绝不透露！\n"
                "• **屏幕共享** = 对方可以看到你的一切操作！\n"
                "• **身份证照片** = 可用于网贷和注册公司！\n\n"
                "立即关闭屏幕共享！不要发送任何验证码！"
            ),
        },
        "high": {
            "通用": (
                "🔴 **高风险提醒！**\n"
                "当前情况存在明显诈骗特征，请提高警惕！\n\n"
                "**建议：**\n"
                "1️⃣ 暂停当前操作\n"
                "2️⃣ 通过官方渠道核实对方身份\n"
                "3️⃣ 与家人朋友商量\n"
                "4️⃣ 如有疑问拨打 **96110**"
            ),
            "刷单诈骗": (
                "🔴 **刷单诈骗高风险！**\n\n"
                "【识别要点】\n"
                "• 任何要求先垫付资金的兼职都是诈骗\n"
                "• '小额返利'是诱饵，'连单'是陷阱\n"
                "• 群里除了你，其他全是托\n\n"
                "【建议】立即停止所有操作！不要相信'再转一笔就能提现'！"
            ),
            "冒充公检法": (
                "🔴 **冒充公检法诈骗高风险！**\n\n"
                "【识别要点】\n"
                "• 公检法**不会**通过电话办案\n"
                "• **没有**所谓的'安全账户'\n"
                "• 要求'保密'是为了隔离你的求助渠道\n\n"
                "【建议】挂断电话，自行拨打110核实！"
            ),
            "投资诈骗": (
                "🔴 **虚假投资诈骗高风险！**\n\n"
                "【识别要点】\n"
                "• 宣称'稳赚不赔'的一定是诈骗\n"
                "• 不明链接下载的APP是假平台\n"
                "• '导师''内幕消息'都是骗人的\n\n"
                "【建议】立即停止充值，尝试提现确认！"
            ),
        },
        "medium": {
            "通用": (
                "🟡 **注意！** 发现一些可疑迹象。\n\n"
                "• 不要轻易转账或提供个人信息\n"
                "• 核实信息来源的真实性\n"
                "• 如需帮助可以继续问我"
            ),
        },
        "low": {
            "通用": (
                "🟢 **提示：** 存在一些需要注意的地方，但风险较低。\n\n"
                "请继续保持警惕，遇到可疑情况随时咨询。"
            ),
        }
    }

    def __init__(self):
        self.risk_history = {}  # user_id -> list of risk events

    # 知识咨询类意图：此类输入是在"问知识"，不是在"报告自己正在遭遇"
    KNOWLEDGE_INTENTS = {"knowledge_queries", "fraud_inquiry", "legal_queries"}

    # 行为类规则白名单：只有这些"受害者实际行为特征"规则，
    # 在知识咨询意图下仍然生效；其余"话题/骗局类型"类规则一律抑制。
    ACTION_RULES = {
        "转账到陌生账户",
        "提供验证码",
        "屏幕共享",
        "提供身份证照片",
        "被要求转账",
        "点击不明链接",
        "下载不明APP",
    }

    def analyze_risk(self, user_input: str, user_id: str = "default",
                     dialog_history: list = None, intent: str = None) -> dict:
        """分析用户输入的风险等级（增强版，支持时序分析）

        intent: 可选。意图分类结果。当意图为知识咨询类（knowledge_queries /
                fraud_inquiry / legal_queries）时，仅保留行为类规则，
                抑制"话题/骗局类型"类规则 —— 避免"给我讲讲刷单诈骗"这类
                纯咨询被误判为高危。
        """
        if not user_input:
            return {"risk_level": "none", "risk_score": 0, "triggered_rules": []}

        # 知识咨询意图门控
        knowledge_mode = intent in self.KNOWLEDGE_INTENTS

        triggered = []
        total_score = 0

        # 1. 当前输入匹配规则
        for rule_name, rule in self.RISK_RULES.items():
            if knowledge_mode and rule_name not in self.ACTION_RULES:
                continue  # 知识咨询下抑制话题类规则
            for pattern in rule["patterns"]:
                if re.search(pattern, user_input):
                    triggered.append({
                        "rule": rule_name,
                        "category": rule["category"],
                        "weight": round(rule["weight"], 2),
                        "intervention_type": rule.get("intervention", ""),
                        "from_history": False
                    })
                    total_score += rule["weight"]
                    break

        # 2. 对话历史分析（时序累积）
        # 知识咨询意图下跳过：用户是在"问知识"，历史中的风险词不应叠加到本次咨询上
        if dialog_history and not knowledge_mode:
            history_text = " ".join(dialog_history[-6:])
            for rule_name, rule in self.RISK_RULES.items():
                for pattern in rule["patterns"]:
                    if re.search(pattern, history_text):
                        matched_in_current = rule_name in [t["rule"] for t in triggered]
                        if not matched_in_current:
                            triggered.append({
                                "rule": rule_name,
                                "category": rule["category"],
                                "weight": round(rule["weight"] * 0.5, 2),
                                "intervention_type": rule.get("intervention", ""),
                                "from_history": True
                            })
                            total_score += rule["weight"] * 0.5
                        else:
                            # 历史中多次出现 → 风险累加
                            occurrence = len(re.findall(pattern, history_text))
                            if occurrence > 1:
                                total_score += rule["weight"] * 0.2
                        break

        # 3. 最近历史风险衰减
        # 同样在知识咨询意图下跳过，避免历史高分把纯咨询"顶"成高危
        if (not knowledge_mode) and user_id in self.risk_history:
            recent_events = self.risk_history[user_id][-5:]
            for event in recent_events:
                time_diff = time.time() - event.get("timestamp", time.time())
                if time_diff < 300:  # 5分钟内
                    total_score += event.get("score", 0) * 0.1  # 衰减因子

        # 4. 风险等级判定（动态阈值）
        risk_level = "none"
        if total_score >= 2.0:
            risk_level = "critical"
        elif total_score >= 1.0:
            risk_level = "high"
        elif total_score >= 0.4:
            risk_level = "medium"
        elif total_score > 0:
            risk_level = "low"

        # 5. 记录风险事件
        if risk_level in ("high", "critical"):
            if user_id not in self.risk_history:
                self.risk_history[user_id] = []
            self.risk_history[user_id].append({
                "timestamp": time.time(),
                "score": total_score,
                "risk_level": risk_level,
                "rules": [t["rule"] for t in triggered]
            })

        return {
            "risk_level": risk_level,
            "risk_score": round(total_score, 2),
            "triggered_rules": triggered,
            "has_risk": risk_level in ("high", "critical"),
            "rule_count": len(triggered)
        }

    def generate_intervention(self, risk_result: dict, fraud_type: str = None,
                              user_id: str = "default") -> str:
        """根据风险分析结果生成劝阻话术（场景化+个性化）"""
        if risk_result["risk_level"] == "none":
            return ""

        risk_level = risk_result["risk_level"]
        triggered = risk_result.get("triggered_rules", [])

        # 确定最佳匹配的场景分类
        categories = set(t["category"] for t in triggered)
        intervention_type = None

        # 骗局类型优先匹配
        if fraud_type:
            fraud_to_category = {
                "刷单返利": "刷单诈骗",
                "游戏交易": "通用",
                "冒充公检法": "冒充公检法",
                "虚假投资": "投资诈骗",
                "校园贷": "通用",
            }
            intervention_type = fraud_to_category.get(fraud_type)

        # 如果无法从骗局类型匹配，从规则类别匹配
        if not intervention_type:
            category_to_type = {
                "资金风险": "资金风险",
                "信息泄露": "信息泄露",
                "刷单诈骗": "刷单诈骗",
                "冒充公检法": "冒充公检法",
                "投资诈骗": "投资诈骗",
                "恶意软件": "通用",
                "恶意链接": "通用",
                "诱导借贷": "通用",
                "杀猪盘": "投资诈骗",
            }
            for cat in categories:
                intervention_type = category_to_type.get(cat)
                if intervention_type:
                    break
            if not intervention_type:
                intervention_type = "通用"

        # 获取话术
        level_lib = self.INTERVENTION_LIBRARY.get(risk_level, {})
        msg = level_lib.get(intervention_type) or level_lib.get("通用", "")

        # 添加个性化信息
        if fraud_type:
            msg += f"\n\n**疑似骗局类型：** {fraud_type}"

        # 添加触发的风险规则详情
        if triggered:
            msg += "\n\n**触发风险项：**"
            seen_categories = set()
            for r in triggered:
                cat = r['category']
                if cat not in seen_categories:
                    msg += f"\n• [{cat}] {r.get('intervention_type', r['rule'])}"
                    seen_categories.add(cat)

        return msg

    def get_risk_profile(self, user_id: str) -> Optional[dict]:
        """获取用户风险画像"""
        events = self.risk_history.get(user_id, [])
        if not events:
            return None
        return {
            "total_events": len(events),
            "recent_events": events[-3:] if events else [],
            "last_risk_time": events[-1]["timestamp"] if events else None,
            "highest_risk": max((e.get("risk_level", "none") for e in events),
                                key=lambda x: ["none", "low", "medium", "high", "critical"].index(x))
            if events else "none"
        }

    def get_risk_assessment_questions(self, risk_level: str) -> list:
        """根据风险等级返回评估问题"""
        questions = {
            "critical": [
                "对方是否要求你'保密'不告诉家人？",
                "对方是否出示了'工作证''警官证'？",
                "你是否已经向对方转账？",
                "对方是否发来了不明链接？",
            ],
            "high": [
                "你和对方见过面吗？",
                "对方是否催促你尽快操作？",
                "你是否下载了不明来源的APP？",
            ],
            "medium": [
                "对方是通过什么方式联系你的？",
                "你是否核实过对方身份？",
            ]
        }
        return questions.get(risk_level, [])

    def get_quick_actions(self, risk_level: str) -> list:
        """根据风险等级返回快速操作建议"""
        actions = {
            "critical": [
                {"action": "拨打110报警", "icon": "🚔", "type": "phone"},
                {"action": "拨打96110咨询", "icon": "📞", "type": "phone"},
                {"action": "联系银行冻结账户", "icon": "🏦", "type": "advice"},
            ],
            "high": [
                {"action": "拨打96110咨询", "icon": "📞", "type": "phone"},
                {"action": "与家人朋友商量", "icon": "👨‍👩‍👧‍👦", "type": "advice"},
            ],
            "medium": [
                {"action": "继续向我咨询", "icon": "💬", "type": "chat"},
            ]
        }
        return actions.get(risk_level, [])
