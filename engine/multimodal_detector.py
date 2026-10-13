"""
多模态诈骗检测引擎 v3.0
支持:
  1. 诈骗截图 OCR 分析 — 识别假通缉令、假客服界面、假 APP 截图中的诈骗特征
  2. 语音诈骗检测 — 音频转文字 + 诈骗特征分析
"""
import os
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ===== 诈骗截图特征规则 =====

# 已知诈骗 APP 名称
FRAUD_APP_PATTERNS = [
    r"公安防护", r"安全防护", r"资金清算", r"安全守护",
    r"远程协助", r"屏幕共享", r"向日葵", r"TeamViewer", r"AnyDesk",
    r"数字人民币.*测试", r"数字钱包.*测试",
    r"借贷宝", r"分期乐.*提额", r"京东金融.*注销",
    r"腾讯会议.*安全", r"Zoom.*安全",
    r"Bit\w*钱包", r"Meta\w*钱包",
    r"USDT.*交易", r"虚拟币.*投资",
    r"刷单.*APP", r"兼职.*APP", r"任务.*APP",
]

# 假通缉令/法律文书特征
FAKE_LEGAL_DOC_PATTERNS = [
    r"通缉令", r"逮捕令", r"冻结令", r"拘捕令",
    r"刑事拘捕令", r"冻结管制令", r"刑事逮捕令",
    r"协查通报", r"案件编号", r"涉案编号",
    r"公安局", r"检察院", r"人民法院",
    r"涉嫌洗钱", r"非法入境", r"涉嫌诈骗",
    r"资金核查", r"安全账户",
    r"保密", r"不得告诉", r"泄露追责",
]

# 虚假客服/退款界面特征
FAKE_CUSTOMER_SERVICE_PATTERNS = [
    r"退款理赔", r"快递理赔", r"运费险",
    r"质量.*问题.*退款", r"商品.*问题.*赔偿",
    r"屏幕共享.*指导", r"远程.*协助.*操作",
    r"转账.*激活", r"交.*保证金", r"解冻.*账户",
    r"关闭.*百万保障", r"取消.*自动扣费",
    r"微粒贷.*关闭", r"花呗.*提额", r"借呗.*关闭",
    r"京东.*金条.*关闭", r"白条.*注销",
]

# 虚假投资界面特征
FAKE_INVESTMENT_PATTERNS = [
    r"日收益", r"日利率", r"稳赚不赔",
    r"保本.*高收益", r"低风险.*高回报",
    r"内部.*渠道", r"内幕.*消息", r"老师.*带单",
    r"跟着.*操作", r"带单.*老师", r"理财.*导师",
    r"充值.*返利", r"入金.*赠送",
    r"USDT", r"BTC", r"ETH", r"数字货币",
    r"原始股", r"新股.*申购", r"涨停.*推荐",
]

# 诈骗性二维码/链接
FRAUD_LINK_PATTERNS = [
    r"扫码.*领取", r"扫码.*退款", r"扫码.*激活",
    r"http://(?!.*\.gov\.cn)(?!.*\.com$).*\d{5,}",  # 可疑短链接/IP地址
]


class ImageFraudDetector:
    """诈骗截图分析器 — OCR + 特征检测"""

    def __init__(self):
        self._ocr = None
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def load(self) -> bool:
        """惰性加载 OCR 引擎"""
        if self._ready:
            return True
        try:
            # 优先使用 EasyOCR（中文支持好）
            import easyocr
            logger.info("[ImageFraud] 加载 EasyOCR (中文)...")
            self._ocr = easyocr.Reader(['ch_sim', 'en'], gpu=False)
            self._ready = True
            logger.info("[ImageFraud] OCR 引擎就绪")
            return True
        except ImportError:
            logger.warning("[ImageFraud] EasyOCR 未安装，尝试 Tesseract...")
        except Exception as e:
            logger.warning(f"[ImageFraud] EasyOCR 加载失败: {e}")

        # 回退到 Tesseract
        try:
            import pytesseract
            from PIL import Image
            self._ocr = "tesseract"
            self._ready = True
            logger.info("[ImageFraud] 使用 Tesseract OCR")
            return True
        except ImportError:
            logger.warning("[ImageFraud] Tesseract 未安装，OCR 不可用")
        return False

    def extract_text(self, image_path: str) -> str:
        """从图片提取文字"""
        if not self.load():
            return ""

        try:
            if hasattr(self._ocr, 'readtext'):
                # EasyOCR —— 用 PIL 读图转 ndarray 再传入，
                # 兼容中文/非 ASCII 路径（cv2.imread 无法读取此类路径）
                import numpy as np
                from PIL import Image
                img = np.array(Image.open(image_path).convert("RGB"))
                results = self._ocr.readtext(img)
                return "\n".join(text for _, text, conf in results if conf > 0.3)
            elif self._ocr == "tesseract":
                import pytesseract
                from PIL import Image
                img = Image.open(image_path)
                return pytesseract.image_to_string(img, lang='chi_sim+eng')
        except Exception as e:
            logger.error(f"[ImageFraud] OCR 提取失败: {e}")
            return ""

        return ""

    def analyze(self, image_path: str) -> Dict:
        """
        分析截图是否包含诈骗特征
        
        Returns:
            {
                "has_fraud_indicators": bool,
                "extracted_text": str,
                "detections": [{"type": "通缉令", "confidence": 0.9, "matched_text": "..."}],
                "risk_level": "none/low/medium/high/critical",
                "summary": str,
            }
        """
        if not os.path.exists(image_path):
            return {"error": "文件不存在", "has_fraud_indicators": False}

        text = self.extract_text(image_path)
        if not text:
            return {
                "has_fraud_indicators": False,
                "extracted_text": "",
                "detections": [],
                "risk_level": "none",
                "summary": "无法识别图片中的文字，请确保图片清晰。",
            }

        detections = []

        # 检测假法律文书
        for pattern in FAKE_LEGAL_DOC_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches[:3]:
                detections.append({
                    "type": "假法律文书",
                    "risk": "critical",
                    "matched_text": m,
                    "category": "冒充公检法",
                })

        # 检测诈骗 APP
        for pattern in FRAUD_APP_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches[:3]:
                detections.append({
                    "type": "可疑APP/软件",
                    "risk": "high",
                    "matched_text": m,
                    "category": "恶意软件",
                })

        # 检测虚假客服
        for pattern in FAKE_CUSTOMER_SERVICE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches[:3]:
                detections.append({
                    "type": "虚假客服/退款",
                    "risk": "high",
                    "matched_text": m,
                    "category": "冒充客服退款",
                })

        # 检测虚假投资
        for pattern in FAKE_INVESTMENT_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches[:3]:
                detections.append({
                    "type": "虚假投资诱导",
                    "risk": "high",
                    "matched_text": m,
                    "category": "虚假投资",
                })

        # 检测可疑链接
        for pattern in FRAUD_LINK_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for m in matches[:3]:
                detections.append({
                    "type": "可疑链接/二维码",
                    "risk": "medium",
                    "matched_text": m,
                    "category": "恶意链接",
                })

        # 去重
        seen = set()
        unique_detections = []
        for d in detections:
            key = (d["type"], d["matched_text"])
            if key not in seen:
                seen.add(key)
                unique_detections.append(d)

        # 风险评估
        has_fraud = len(unique_detections) > 0
        if has_fraud:
            risks = [d["risk"] for d in unique_detections]
            if "critical" in risks:
                risk_level = "critical"
            elif risks.count("high") >= 2:
                risk_level = "critical"
            elif "high" in risks:
                risk_level = "high"
            elif risks.count("medium") >= 3:
                risk_level = "high"
            else:
                risk_level = "medium"
        else:
            risk_level = "none"

        # 生成摘要
        if has_fraud:
            categories = list(set(d["category"] for d in unique_detections))
            summary = f"⚠️ 检测到 {len(unique_detections)} 个诈骗特征，涉及类型: {', '.join(categories)}。请高度警惕！"
        else:
            summary = "未检测到明显的诈骗特征，但建议进一步核实。"

        return {
            "has_fraud_indicators": has_fraud,
            "extracted_text": text[:500],
            "detections": unique_detections[:10],
            "risk_level": risk_level,
            "summary": summary,
        }


class AudioFraudDetector:
    """语音诈骗检测器"""

    def __init__(self):
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def load(self) -> bool:
        """检查依赖是否可用"""
        try:
            import pydub
            self._ready = True
            return True
        except ImportError:
            logger.warning("[AudioFraud] pydub 未安装，语音检测不可用")
            return False

    def analyze_text_for_fraud_calls(self, text: str) -> Dict:
        """
        分析语音转文字后的内容
        
        Returns:
            诈骗特征分析结果
        """
        detections = []

        # 冒充公检法话术
        authority_patterns = [
            (r"公安局|派出所|刑侦|经侦|检察院|法院", "自称公检法"),
            (r"涉嫌.*(洗钱|诈骗|非法|走私)", "指控犯罪"),
            (r"安全账户|资金核查|资金清算", "安全账户骗局"),
            (r"保密.*不得.*告诉|不能.*让.*知道", "要求保密"),
            (r"通缉令|逮捕令|协查通知", "伪造法律文书"),
            (r"下载.*(APP|软件).*(配合|协助|调查)", "诱导下载APP"),
            (r"屏幕共享|共享屏幕", "屏幕共享诈骗"),
            # v3.0 新增：FaceTime/客服冒充
            (r"FaceTime|facetime|苹果.*客服", "FaceTime诈骗"),
            (r"百万保障.*(到期|关闭|扣费)", "百万保障骗局"),
            (r"微信客服.*(FaceTime|视频|来电)", "冒充微信客服"),
        ]

        for pattern, desc in authority_patterns:
            if re.search(pattern, text):
                detections.append({
                    "type": "冒充公检法",
                    "detail": desc,
                    "risk": "critical",
                })

        # 刷单/兼职话术
        scam_job_patterns = [
            (r"刷单|刷信誉|做任务|点赞.*赚钱|关注.*返利", "刷单诈骗"),
            (r"足不出户.*日赚|在家.*赚钱|手机.*兼职", "兼职诈骗话术"),
            (r"先.*垫付|先.*交钱|保证金|解冻金|激活金", "要求垫付资金"),
        ]

        for pattern, desc in scam_job_patterns:
            if re.search(pattern, text):
                detections.append({
                    "type": "刷单/兼职诈骗",
                    "detail": desc,
                    "risk": "high",
                })

        # v3.0: 虚假投资/虚拟币话术
        investment_patterns = [
            (r"稳赚不赔|保证收益|日收益|月收益|高回报", "虚假收益承诺"),
            (r"内部.*(渠道|消息)|内幕.*消息", "声称内幕消息"),
            (r"老师.*带单|导师.*推荐|专家.*指导", "老师带单套路"),
            (r"USDT|虚拟币|数字货币|比特币|以太坊", "虚拟货币诱导"),
        ]

        for pattern, desc in investment_patterns:
            if re.search(pattern, text):
                detections.append({
                    "type": "虚假投资/虚拟币",
                    "detail": desc,
                    "risk": "high",
                })

        # 恐吓/紧迫感
        urgency_patterns = [
            (r"马上|立即|赶紧|赶快|尽快.*否则", "制造紧迫感"),
            (r"最后.*机会|限时|过期.*后果", "限时威胁"),
            (r"不然.*(抓|逮捕|通缉|冻结|扣)", "恐吓威胁"),
        ]

        for pattern, desc in urgency_patterns:
            if re.search(pattern, text):
                detections.append({
                    "type": "心理操控",
                    "detail": desc,
                    "risk": "medium",
                })

        has_fraud = len(detections) > 0
        risk_level = "critical" if any(d["risk"] == "critical" for d in detections) else \
                     "high" if any(d["risk"] == "high" for d in detections) else \
                     "medium" if has_fraud else "none"

        return {
            "has_fraud_indicators": has_fraud,
            "detections": detections,
            "risk_level": risk_level,
            "text_snippet": text[:300],
        }

    def analyze_audio_file(self, audio_path: str) -> Dict:
        """
        分析音频文件 — 先转文字再检测
        
        注意: 需要 whisper 或类似 ASR 模型来做语音转文字。
        这里做框架设计，实际部署时需安装 openai-whisper 或使用云API。
        """
        if not os.path.exists(audio_path):
            return {"error": "音频文件不存在", "has_fraud_indicators": False}

        # 尝试使用 whisper
        try:
            import whisper
            model = whisper.load_model("tiny")
            result = model.transcribe(audio_path, language="zh")
            text = result["text"]
            return self.analyze_text_for_fraud_calls(text)
        except ImportError:
            return {
                "has_fraud_indicators": False,
                "risk_level": "none",
                "summary": "语音转文字引擎未安装。请安装 openai-whisper: pip install openai-whisper",
                "note": "框架已就绪，安装依赖后即可使用。"
            }
        except Exception as e:
            logger.error(f"[AudioFraud] 分析失败: {e}")
            return {"error": str(e), "has_fraud_indicators": False}


# 全局单例
_image_detector: Optional[ImageFraudDetector] = None
_audio_detector: Optional[AudioFraudDetector] = None


def get_image_detector() -> ImageFraudDetector:
    global _image_detector
    if _image_detector is None:
        _image_detector = ImageFraudDetector()
    return _image_detector


def get_audio_detector() -> AudioFraudDetector:
    global _audio_detector
    if _audio_detector is None:
        _audio_detector = AudioFraudDetector()
    return _audio_detector
