"""URL/内容分析引擎 - 多维度特征检测 + 黑名单 + 智能研判"""

import re
import json
import os
from urllib.parse import urlparse


class URLAnalyzer:
    """URL/内容分析引擎，支持多维度特征检测、短链接分析、内容研判"""

    SUSPICIOUS_TLDS = {
        '.xyz', '.top', '.club', '.online', '.site', '.win', '.bid',
        '.loan', '.date', '.download', '.men', '.party', '.tk', '.ml',
        '.ga', '.cf', '.gq', '.icu', '.cyou', '.shop', '.click',
        '.link', '.live', '.info', '.pro', '.cc', '.tv'
    }

    SUSPICIOUS_KEYWORDS = [
        'login', 'verify', 'account', 'secure', 'update', 'confirm',
        'bank', 'pay', 'alipay', 'weixin', 'wechat', 'taobao', 'zhifubao',
        'free', 'bonus', 'lottery', 'prize', 'winner', 'cashback',
        'jingdong', 'pinduoduo', 'meituan', 'dianping',
        'anquan', 'shenfen', 'renzheng', 'tixian', 'zhanghu',
        'guandan', 'fadan', 'jianzhi', 'shua', 'fanli', 'yongjin',
        'login', 'verify', 'secure', 'confirm', 'update',
        '客服', '售后', '退款', '理赔',
    ]

    # 短链接服务
    SHORT_DOMAINS = {
        'bit.ly', 'tinyurl.com', 't.cn', 'dwz.cn', 'url.cn',
        'shorturl', 'goo.gl', 'is.gd', 'cli.im', 'u.jd.com',
        '6.cn', '0.cn', 'sina.lt', 'suo.im', 'xiaohua.fun',
        'kz.lc', 'b23.tv', 'v.t.qq.com', 'short.ink'
    }

    # 诈骗类域名模式
    DOMAIN_PATTERNS = [
        (r'(anquan|安全|zhongxin|中心|verify|认证).*(com|cn|net)', '安全认证类钓鱼'),
        (r'(tixian|提现|zhuan|转|pay|支付).*(com|cn)', '资金操作类钓鱼'),
        (r'(jianzhi|兼职|shua|刷|fanli|返利).*(com|cn)', '刷单诈骗网站'),
        (r'(gongjianfa|公检法|jingcha|警察|tongji|通缉).*(com|cn)', '冒充公检法诈骗'),
        (r'(touzi|投资|lica|理财|gupiao|股票|waihui|外汇).*(com|cn)', '虚假投资平台'),
        (r'(game|游戏|jiaoyi|交易|daolian|代练|皮|皮肤|zhuangbei|装备).*(com|cn|cc|top)', '游戏交易诈骗'),
    ]

    def __init__(self):
        self.blacklist = self._load_blacklist()
        self.report_history = {}  # user_id -> list of reports

    def _load_blacklist(self) -> set:
        """加载黑名单域名"""
        return {
            'anquan-zhongxin.com', 'tixian-bao.com', 'zhifubao-verify.com',
            'weixin-safe.com', 'taobao-fanli.com', 'jianzhi-99.com',
            'shuadan-88.com', 'game-jiaoyi.cc', 'wangluo-touzi.com',
            'anquan-verify.cn', 'pay-safe.top', 'gongjianfa-case.xyz',
            'touzi-licai.vip', 'game-skin.club', 'dianpu-fanli.com',
        }

    def analyze_url(self, url: str) -> dict:
        """分析URL的可疑程度（增强版）"""
        if not url:
            return {"is_suspicious": False, "risk_level": "none", "details": [], "risk_score": 0}

        url = url.strip()
        details = []
        score = 0
        matched_domain_pattern = None

        try:
            # 统一添加协议
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            full_url = url
        except Exception:
            domain = url
            parsed = None
            full_url = url

        if not domain:
            return {"is_suspicious": False, "risk_level": "none", "details": [], "risk_score": 0}

        # 1. 短链接检测
        for sd in self.SHORT_DOMAINS:
            if sd in domain:
                details.append("🔗 链接使用了短网址服务，可能隐藏真实目标地址")
                score += 0.35
                break

        # 2. 可疑TLD检测
        for tld in self.SUSPICIOUS_TLDS:
            if domain.endswith(tld):
                details.append(f"⚠️ 使用了可疑顶级域名 {tld}，正规网站较少使用此类域名")
                score += 0.45
                break

        # 3. URL关键词检测
        matched_kws = []
        for kw in self.SUSPICIOUS_KEYWORDS:
            if kw in full_url.lower():
                matched_kws.append(kw)
                score += 0.3
        if matched_kws:
            details.append(f"🔍 URL包含可疑关键词: {', '.join(matched_kws[:4])}")
            # 对同时匹配多个关键词的情况加分
            if len(matched_kws) >= 3:
                score += 0.3

        # 4. 诈骗域名模式匹配
        for pattern, pattern_name in self.DOMAIN_PATTERNS:
            if re.search(pattern, domain):
                matched_domain_pattern = pattern_name
                details.append(f"🚩 域名模式匹配: '{pattern_name}'")
                score += 0.6
                break

        # 5. IP地址直连
        ip_pattern = r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'
        if re.search(ip_pattern, domain):
            details.append("🌐 链接使用了IP地址而非域名，正规网站极少使用IP直连")
            score += 0.55

        # 6. 黑名单匹配
        for black in self.blacklist:
            if black in domain:
                details.append(f"⛔ 域名在黑名单中，已被标记为诈骗/钓鱼网站")
                score += 0.9
                break

        # 7. HTTPS检查
        if parsed and parsed.scheme != 'https':
            details.append("🔒 链接未使用HTTPS加密，信息传输可能被窃取")
            score += 0.25

        # 8. 域名长度异常
        if len(domain) > 30:
            details.append(f"📏 域名长度偏长 ({len(domain)}字符)，诈骗网站常使用长域名迷惑用户")
            score += 0.2

        # 9. 特殊字符检测
        if re.search(r'[@\[\]{}()【】（）《》]', domain):
            details.append("❓ 域名包含特殊字符，可能是伪造的钓鱼网站")
            score += 0.35

        # 10. 数字占比分析
        digit_count = sum(c.isdigit() for c in domain)
        if len(domain) > 0 and digit_count / len(domain) > 0.4:
            details.append("🔢 域名中数字比例偏高，可能是自动生成的恶意域名")
            score += 0.25

        # 综合评分
        risk_level = "none"
        if score >= 1.8:
            risk_level = "critical"
        elif score >= 1.0:
            risk_level = "high"
        elif score >= 0.4:
            risk_level = "medium"
        elif score > 0:
            risk_level = "low"

        # 生成处置建议
        advice = self._generate_url_advice(risk_level, details)

        return {
            "is_suspicious": score >= 0.6,
            "risk_level": risk_level,
            "risk_score": round(score, 2),
            "domain": domain,
            "details": details,
            "matched_pattern": matched_domain_pattern,
            "matched_keywords": matched_kws[:5],
            "advice": advice
        }

    def _generate_url_advice(self, risk_level: str, details: list) -> str:
        """根据风险生成处置建议"""
        if risk_level == "critical":
            return ("🚨 **高度危险！** 请立即关闭页面，不要输入任何信息。\n"
                    "• 已确认或高度疑似诈骗网站\n"
                    "• 建议通过12321.cn举报该网址\n"
                    "• 如已输入个人信息，请立即修改相关账户密码\n"
                    "• 如已转账，请立即拨打110申请紧急止付")
        elif risk_level == "high":
            return ("🔴 **高风险！** 该链接存在明显的诈骗特征。\n"
                    "• 不要输入个人信息\n"
                    "• 不要下载任何文件\n"
                    "• 建议通过官方渠道核实网站真实性")
        elif risk_level == "medium":
            return ("🟡 **中等风险** 该链接存在一些可疑特征，请谨慎处理。\n"
                    "• 核实域名是否为官方网站\n"
                    "• 不要轻易输入个人信息")
        else:
            return ("🟢 **未发现明显风险**，但请保持警惕。\n"
                    "• 只从官方渠道访问网站\n"
                    "• 注意检查网址是否正确")

    def analyze_content(self, content: str) -> dict:
        """分析文本内容是否包含诈骗信息（增强版）"""
        if not content:
            return {"is_suspicious": False, "risk_level": "none", "details": [], "risk_score": 0}

        details = []
        score = 0

        # 诈骗关键词权重表
        fraud_keywords = {
            "中奖": 0.5, "免费领取": 0.4, "点击领取": 0.3,
            "一元抢购": 0.4, "限时秒杀": 0.2, "内部价": 0.3,
            "日赚": 0.5, "月入过万": 0.5, "稳赚不赔": 0.7,
            "安全账户": 0.85, "资金清查": 0.75, "解冻金": 0.65,
            "保证金": 0.4, "手续费": 0.3, "验证费": 0.4,
            "无抵押贷款": 0.4, "不看征信": 0.5, "学生贷款": 0.3,
            "安全账户": 0.9, "资金核查": 0.7, "视频办案": 0.8,
            "刷单": 0.6, "联单": 0.55, "连单": 0.55,
            "原始股": 0.6, "内幕消息": 0.6,
            "限时特惠": 0.2, "仅限今天": 0.3,
            "提供银行卡": 0.6, "跑分": 0.7, "洗钱": 0.5,
        }

        for kw, weight in fraud_keywords.items():
            if kw in content:
                details.append(f"包含诈骗特征词: '{kw}'")
                score += weight

        # 可疑联系方式识别
        # 手机号
        phone_pattern = r'1[3-9]\d{9}'
        phones = re.findall(phone_pattern, content)
        if phones:
            details.append(f"包含可疑手机号码: {phones[0]}")
            score += 0.3 * len(phones)

        # QQ号
        qq_pattern = r'[Qq]{1,2}[ :：]*\d{5,12}'
        if re.search(qq_pattern, content):
            qq_match = re.search(r'\d{5,12}', content)
            qq_num = qq_match.group() if qq_match else ""
            details.append(f"包含QQ联系方式 ({qq_num})")
            score += 0.25

        # 微信号
        wx_pattern = r'[微vV][信xX].{0,5}[a-zA-Z][a-zA-Z0-9_-]{5,19}'
        if re.search(wx_pattern, content):
            details.append("包含微信联系方式")
            score += 0.25

        # 银行卡号
        bank_pattern = r'\d{16,19}'
        bank_matches = re.findall(bank_pattern, content)
        if bank_matches and not re.match(r'^\d{16,19}$', str(phones[0] if phones else '')):
            details.append("包含疑似银行卡号")
            score += 0.4

        # 综合评分
        risk_level = "none"
        if score >= 2.0:
            risk_level = "critical"
        elif score >= 1.0:
            risk_level = "high"
        elif score >= 0.4:
            risk_level = "medium"
        elif score > 0:
            risk_level = "low"

        return {
            "is_suspicious": score >= 0.6,
            "risk_level": risk_level,
            "risk_score": round(score, 2),
            "details": details,
            "keyword_count": sum(1 for kw in fraud_keywords if kw in content),
            "phone_count": len(phones)
        }

    def record_report(self, user_id: str, url: str, result: dict, content_analysis: dict = None):
        """记录举报历史"""
        if user_id not in self.report_history:
            self.report_history[user_id] = []
        self.report_history[user_id].append({
            "url": url,
            "domain": result.get("domain", ""),
            "risk_level": result.get("risk_level", ""),
            "is_suspicious": result.get("is_suspicious", False),
            "has_suspicious_content": content_analysis.get("is_suspicious", False) if content_analysis else False,
            "timestamp": __import__('time').time()
        })

    def get_report_history(self, user_id: str) -> list:
        """获取用户举报历史"""
        return self.report_history.get(user_id, [])[-20:]

    def get_report_stats(self, user_id: str) -> dict:
        """获取用户举报统计"""
        history = self.report_history.get(user_id, [])
        if not history:
            return {"total": 0, "suspicious": 0, "safe": 0}
        suspicious = sum(1 for r in history if r.get("is_suspicious"))
        return {
            "total": len(history),
            "suspicious": suspicious,
            "safe": len(history) - suspicious,
            "last_report": history[-1]["url"] if history else None
        }
