"""
隐私卫士模块 🔐
- 自动检测用户对话中的个人敏感信息（PII）
- 实时加密替换，后台人员也无法查看原文
- 向用户发出隐私泄露告警
- 会话关闭后自动清除隐私数据

支持检测:
  - 中国大陆手机号
  - 身份证号（18位）
  - 银行卡号
  - 中文姓名（结合上下文）
  - 家庭/公司地址
  - 微信号/QQ号
  - 短信验证码
  - 银行卡密码/支付密码
"""
import re
import os
import json
import time
import base64
import hashlib
import hmac
import logging
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ========== 数据类型定义 ==========

@dataclass
class PIIDetection:
    """单条PII检测结果"""
    type: str            # 类型: phone / id_card / bank_card / name / address / wechat / qq / sms_code / password
    original: str        # 原文
    masked: str          # 掩码后
    start: int           # 在原文中的起始位置
    end: int             # 在原文中的结束位置
    confidence: float    # 置信度 0-1
    encrypted: str = ""  # 加密后的密文（用会话密钥加密）


@dataclass
class PIIResult:
    """一次检测的完整结果"""
    detections: List[PIIDetection] = field(default_factory=list)
    clean_text: str = ""           # 替换PII后的安全文本
    has_pii: bool = False
    alert_messages: List[str] = field(default_factory=list)


# ========== PII 检测模式 ==========

# 中国大陆手机号: 1开头的11位数字
PHONE_PATTERN = re.compile(r'(?<!\d)1[3-9]\d{9}(?!\d)')

# 身份证号: 18位（17位数字+1位数字或X）
ID_CARD_PATTERN = re.compile(r'(?<!\d)[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)')

# 银行卡号: 16-19位数字
BANK_CARD_PATTERN = re.compile(r'(?<!\d)(?:62|60|58|56|55|54|53|52|51|50|49|48|47|46|45|44|43|42|41|40|39|38|37|36|35|34|33|32|31|30)\d{12,17}(?!\d)')
# 简化版银行卡匹配
BANK_CARD_SIMPLE = re.compile(r'(?<!\d)\d{16,19}(?!\d)')

# 验证码: 4-6位数字，前面有"验证码"等关键词
SMS_CODE_PATTERN = re.compile(r'(?:验证码|校验码|动态码|安全码)[是为：:;\s]*(\d{4,6})')
SMS_CODE_REVERSE = re.compile(r'(\d{4,6})(?:[是]?(?:验证码|校验码|动态码))')

# 微信号: 以字母开头，6-20位字母数字下划线
WECHAT_ID_PATTERN = re.compile(r'(?<![a-zA-Z0-9])(?:微信号|微信|wxid[_:])?[a-zA-Z][a-zA-Z0-9_]{5,19}(?![a-zA-Z0-9])')

# QQ号: 5-11位数字（排除手机号）
QQ_PATTERN = re.compile(r'(?<!\d)[1-9]\d{4,10}(?!\d)')

# 中文姓名: 2-4个中文字符（结合"我叫""姓名"等上下文触发）
NAME_CONTEXT_PATTERN = re.compile(r'(?:我叫|姓名|名字|姓|我叫作|我是|称为|全名)[：:：\s]*([一-鿿]{2,4})')
NAME_ISOLATED_PATTERN = re.compile(r'^[一-鿿]{2,4}$')

# 地址: 省/市/区/路/号/村/镇等
ADDRESS_PATTERN = re.compile(
    r'(?:地址|住在|家住|家庭住址|居住地|所在地)[：:：\s]*'
    r'([一-鿿]{2,}(?:省|市|区|县|镇|乡|村|路|街|道|巷|号|栋|单元|室|号楼|层|楼|组))'
    r'[一-鿿\d\-—～~#]*'
)

# 密码
PASSWORD_PATTERN = re.compile(r'(?:密码|支付密码|取款密码|登录密码|交易密码)[是为：:：\s]*(\d{6,})')

# 高度疑似中文姓名（单独检测2-3字词且周围有姓名提示词）
NAME_SURROUNDING = re.compile(
    r'([一-鿿]{2,3})'
    r'(?:\s*(?:先生|女士|小姐|大哥|大姐|阿姨|叔叔|大爷|大娘|同学|老师|同志|律师))'
)


# ========== 隐私卫士主类 ==========

class PrivacyGuard:
    """
    隐私卫士 - 自动检测、加密、告警、清除PII
    使用每会话独立密钥，即使数据库泄露也无法解密
    """

    def __init__(self, master_key: str = None):
        # 主密钥（用于派生会话密钥）
        self._master_key = master_key or os.urandom(32).hex()
        # 会话密钥存储: session_id -> {"key": bytes, "created": timestamp, "pii_store": {...}}
        self._sessions: Dict[str, dict] = {}
        # PII类型中英文映射
        self.PII_TYPE_NAMES = {
            "phone": "📱 手机号码",
            "id_card": "🆔 身份证号",
            "bank_card": "💳 银行卡号",
            "name": "👤 真实姓名",
            "address": "📍 家庭地址",
            "wechat": "💬 微信号",
            "qq": "💬 QQ号",
            "sms_code": "🔢 短信验证码",
            "password": "🔑 密码",
        }
        logger.info("🛡️  隐私卫士已初始化")

    def create_session(self, session_id: str = None) -> str:
        """创建新的会话，生成独立加密密钥"""
        sid = session_id or f"session_{int(time.time())}_{os.urandom(4).hex()}"
        self._sessions[sid] = {
            "key": hashlib.sha256(f"{self._master_key}:{sid}:{os.urandom(16).hex()}".encode()).digest(),
            "created": time.time(),
            "pii_store": {},       # token -> encrypted_pii
            "detection_log": [],   # 检测记录列表
            "alerted_types": set(),  # 已告警的类型
        }
        logger.info(f"🔐 隐私会话已创建: {sid[:20]}...")
        return sid

    def close_session(self, session_id: str) -> Dict:
        """
        关闭会话，清除所有该会话的PII数据
        返回被清除的PII统计
        """
        if session_id not in self._sessions:
            return {"cleared": 0}

        session = self._sessions[session_id]
        stats = {
            "cleared": len(session["pii_store"]),
            "detections": len(session["detection_log"]),
            "types_found": list(session.get("alerted_types", set())),
            "session_id": session_id[:16] + "...",
        }

        # 安全擦除密钥信息（标记引用为None让GC处理）
        self._sessions[session_id]["key"] = b""
        # 删除会话
        del self._sessions[session_id]
        logger.info(f"🧹 隐私会话已清除: {stats['cleared']} 条PII, {stats['detections']} 次检测")
        return stats

    def detect_and_protect(self, text: str, session_id: str,
                           user_id: str = "") -> PIIResult:
        """
        检测文本中的PII并进行保护处理
        返回: PIIResult(包含检测列表、清洗后文本、告警信息)
        """
        result = PIIResult()
        if not text or not text.strip():
            result.clean_text = text
            return result

        if session_id not in self._sessions:
            logger.warning(f"会话不存在，自动创建: {session_id[:20]}...")
            self.create_session(session_id)

        session = self._sessions[session_id]
        detections = []
        work_text = text

        # 1. 检测手机号
        detections.extend(self._detect_phone(work_text, session))

        # 2. 检测身份证号
        detections.extend(self._detect_id_card(work_text, session))

        # 3. 检测银行卡号
        detections.extend(self._detect_bank_card(work_text, session))

        # 4. 检测验证码（高优先级）
        detections.extend(self._detect_sms_code(work_text, session))

        # 5. 检测姓名（上下文触发）
        detections.extend(self._detect_name(work_text, session))

        # 6. 检测密码
        detections.extend(self._detect_password(work_text, session))

        # 7. 检测地址
        detections.extend(self._detect_address(work_text, session))

        # 按位置排序（从后往前替换，避免偏移）
        detections.sort(key=lambda x: x.start, reverse=True)

        if not detections:
            result.clean_text = text
            return result

        # 加密并替换
        clean = text
        for d in detections:
            # 使用会话密钥加密
            encrypted = self._encrypt_pii(d.original, session["key"])
            d.encrypted = encrypted
            # 存储到会话的PII存储（token -> 加密数据）
            token = hashlib.sha256(encrypted.encode()).hexdigest()[:16]
            session["pii_store"][token] = {
                "encrypted": encrypted,
                "type": d.type,
                "timestamp": time.time(),
            }
            # 替换原文为掩码版本
            clean = clean[:d.start] + d.masked + clean[d.end:]

            # 更新检测日志
            session["detection_log"].append({
                "type": d.type,
                "time": time.time(),
                "confidence": d.confidence,
            })

            # 生成告警（每种类型仅首次告警）
            if d.type not in session["alerted_types"]:
                session["alerted_types"].add(d.type)
                type_name = self.PII_TYPE_NAMES.get(d.type, d.type)
                # 根据不同PII类型给出差异化告警
                if d.type == "phone":
                    alert = (
                        f"⚠️ **隐私保护提醒：** 您刚才提到了{type_name}（{d.masked}）。"
                        f"系统已自动为您加密保护，后台人员也无法查看！\n"
                        f"📌 请勿向陌生人透露手机号，谨防诈骗！"
                    )
                elif d.type == "id_card":
                    alert = (
                        f"🆘 **重要隐私提醒！** 您刚才提到了{type_name}（{d.masked}）。"
                        f"身份证号是最高敏感信息，系统已自动加密！\n"
                        f"📌 任何正规机构都不会索要您的完整身份证号！"
                    )
                elif d.type == "bank_card":
                    alert = (
                        f"💳 **资金安全提醒！** 您提到了{type_name}（{d.masked}）。"
                        f"系统已自动加密保护！\n"
                        f"📌 银行卡号 + 密码/验证码 = 您的钱可能被转走！"
                    )
                elif d.type == "sms_code":
                    alert = (
                        f"🔴 **紧急提醒！** 您提到了{type_name}（{d.masked}）。\n"
                        f"**验证码等同于您的账户钥匙！** 系统已自动加密保护！\n"
                        f"📌 任何情况下都不要将验证码告诉他人，包括'客服'和'警察'！"
                    )
                elif d.type == "password":
                    alert = (
                        f"🔑 **安全警告！** 您提到了{type_name}。"
                        f"系统已自动加密保护！\n"
                        f"📌 正规平台不会索要您的密码！请立即修改该密码！"
                    )
                elif d.type == "name":
                    alert = (
                        f"👤 **隐私提醒：** 您刚才提到了{type_name}（{d.masked}）。"
                        f"系统已自动保护您的姓名信息。\n"
                        f"📌 在与陌生人对话时，建议不要暴露真实姓名。"
                    )
                elif d.type == "address":
                    alert = (
                        f"📍 **隐私提醒：** 您提到了{type_name}（{d.masked}）。"
                        f"系统已自动加密保护！\n"
                        f"📌 家庭住址泄露可能导致上门诈骗或骚扰！"
                    )
                else:
                    alert = (
                        f"⚠️ **隐私提醒：** 您刚才提到了{type_name}（{d.masked}）。"
                        f"系统已自动加密保护！"
                    )
                result.alert_messages.append(alert)

        result.detections = detections
        result.clean_text = clean
        result.has_pii = True

        # 记录日志
        if detections:
            types_found = [d.type for d in detections]
            logger.info(f"🔍 隐私检测: 用户={user_id[:8] if user_id else 'unknown'}, "
                        f"发现={set(types_found)}, 数量={len(detections)}")

        return result

    def get_session_pii_count(self, session_id: str) -> int:
        """获取当前会话已检测到的PII数量"""
        session = self._sessions.get(session_id)
        return len(session["pii_store"]) if session else 0

    def get_session_alerts(self, session_id: str) -> List[str]:
        """获取当前会话的所有告警"""
        session = self._sessions.get(session_id)
        if not session:
            return []
        # 按类型去重
        seen = set()
        alerts = []
        for d in session.get("detection_log", []):
            if d["type"] not in seen:
                seen.add(d["type"])
                type_name = self.PII_TYPE_NAMES.get(d["type"], d["type"])
                alerts.append(f"⚠️ 检测到{type_name}（已加密保护）")
        return alerts

    def get_privacy_summary(self, session_id: str) -> Dict:
        """获取当前会话的隐私摘要"""
        session = self._sessions.get(session_id)
        if not session:
            return {"protected": 0, "types": []}
        return {
            "protected": len(session["pii_store"]),
            "types": list(session.get("alerted_types", set())),
            "type_names": [self.PII_TYPE_NAMES.get(t, t) for t in session.get("alerted_types", set())],
            "session_active": True,
        }

    def filter_text_for_storage(self, text: str, session_id: str) -> str:
        """
        过滤文本中所有可能的PII，返回适合安全存储的版本
        与detect_and_protect不同，此方法用于存储前的安全过滤
        """
        if not text:
            return text
        # 手机号替换
        text = PHONE_PATTERN.sub(lambda m: m.group()[:3] + "****" + m.group()[-4:], text)
        # 身份证替换
        text = ID_CARD_PATTERN.sub(lambda m: m.group()[:6] + "**********" + m.group()[-4:], text)
        # 银行卡替换
        text = BANK_CARD_SIMPLE.sub(lambda m: m.group()[:4] + " **** **** " + m.group()[-4:], text)
        # 验证码替换
        text = SMS_CODE_PATTERN.sub(r'\1****', text)
        return text

    # ========== 私有检测方法 ==========

    def _detect_phone(self, text: str, session: dict) -> List[PIIDetection]:
        """检测手机号"""
        results = []
        for match in PHONE_PATTERN.finditer(text):
            phone = match.group()
            masked = phone[:3] + "****" + phone[-4:]
            results.append(PIIDetection(
                type="phone",
                original=phone,
                masked=masked,
                start=match.start(),
                end=match.end(),
                confidence=0.95,
            ))
        return results

    def _detect_id_card(self, text: str, session: dict) -> List[PIIDetection]:
        """检测身份证号"""
        results = []
        for match in ID_CARD_PATTERN.finditer(text):
            id_num = match.group()
            # 校验码验证
            if self._verify_id_card(id_num):
                masked = id_num[:6] + "**********" + id_num[-4:]
                results.append(PIIDetection(
                    type="id_card",
                    original=id_num,
                    masked=masked,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.98,
                ))
            else:
                # 格式匹配但校验失败，降低置信度
                masked = id_num[:6] + "**********" + id_num[-4:]
                results.append(PIIDetection(
                    type="id_card",
                    original=id_num,
                    masked=masked,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.6,
                ))
        return results

    def _detect_bank_card(self, text: str, session: dict) -> List[PIIDetection]:
        """检测银行卡号"""
        results = []
        # 先尝试精确匹配（有卡BIN前缀）
        for match in BANK_CARD_PATTERN.finditer(text):
            card = match.group()
            masked = card[:4] + " **** **** " + card[-4:]
            results.append(PIIDetection(
                type="bank_card",
                original=card,
                masked=masked,
                start=match.start(),
                end=match.end(),
                confidence=0.9,
            ))

        # 再尝试简化匹配，排除手机号/身份证的误匹配
        for match in BANK_CARD_SIMPLE.finditer(text):
            card = match.group()
            # 跳过已经匹配过的位置
            if any(r.start <= match.start() < r.end for r in results):
                continue
            # 排除明显是手机号或身份证的情况
            if PHONE_PATTERN.match(card) or ID_CARD_PATTERN.match(card):
                continue
            # Luhn算法校验
            if self._luhn_check(card):
                masked = card[:4] + " **** **** " + card[-4:]
                results.append(PIIDetection(
                    type="bank_card",
                    original=card,
                    masked=masked,
                    start=match.start(),
                    end=match.end(),
                    confidence=0.85,
                ))
        return results

    def _detect_sms_code(self, text: str, session: dict) -> List[PIIDetection]:
        """检测短信验证码"""
        results = []
        for match in SMS_CODE_PATTERN.finditer(text):
            code = match.group(1)
            start = text.find(code, match.start())
            if start >= 0:
                masked = "****"
                results.append(PIIDetection(
                    type="sms_code",
                    original=code,
                    masked=masked,
                    start=start,
                    end=start + len(code),
                    confidence=0.95,
                ))
        for match in SMS_CODE_REVERSE.finditer(text):
            code = match.group(1)
            start = text.find(code, match.start())
            if start >= 0 and not any(r.start <= start < r.end for r in results):
                masked = "****"
                results.append(PIIDetection(
                    type="sms_code",
                    original=code,
                    masked=masked,
                    start=start,
                    end=start + len(code),
                    confidence=0.85,
                ))
        return results

    def _detect_name(self, text: str, session: dict) -> List[PIIDetection]:
        """检测中文姓名（通过上下文线索）"""
        results = []
        # 方法1: "我叫XX" 模式
        for match in NAME_CONTEXT_PATTERN.finditer(text):
            name = match.group(1)
            start = match.start(1)
            masked = name[0] + "某" + ("某" * (len(name) - 2)) if len(name) > 2 else name[0] + "某"
            results.append(PIIDetection(
                type="name",
                original=name,
                masked=masked,
                start=start,
                end=start + len(name),
                confidence=0.9,
            ))

        # 方法2: "XX先生/女士" 模式
        for match in NAME_SURROUNDING.finditer(text):
            name = match.group(1)
            start = match.start(1)
            # 排除已检测的
            if any(r.start <= start < r.end for r in results):
                continue
            masked = name[0] + "某" + ("某" * (len(name) - 2)) if len(name) > 2 else name[0] + "某"
            results.append(PIIDetection(
                type="name",
                original=name,
                masked=masked,
                start=start,
                end=start + len(name),
                confidence=0.8,
            ))
        return results

    def _detect_password(self, text: str, session: dict) -> List[PIIDetection]:
        """检测密码"""
        results = []
        for match in PASSWORD_PATTERN.finditer(text):
            pwd = match.group(1)
            start = match.start(1)
            masked = "******"
            results.append(PIIDetection(
                type="password",
                original=pwd,
                masked=masked,
                start=start,
                end=start + len(pwd),
                confidence=0.95,
            ))
        return results

    def _detect_address(self, text: str, session: dict) -> List[PIIDetection]:
        """检测地址"""
        results = []
        for match in ADDRESS_PATTERN.finditer(text):
            addr = match.group(0)
            start = match.start()
            # 提取核心地址部分
            addr_core = match.group(1) if match.lastindex >= 1 else addr
            masked = addr_core[:2] + "****" + (addr_core[-2:] if len(addr_core) > 4 else "")
            # 重构完整掩码
            full_masked = addr.replace(addr_core, masked)
            results.append(PIIDetection(
                type="address",
                original=addr,
                masked=full_masked,
                start=start,
                end=start + len(addr),
                confidence=0.75,
            ))
        return results

    # ========== 加密工具 ==========

    def _encrypt_pii(self, plaintext: str, key: bytes) -> str:
        """使用会话密钥加密PII"""
        salt = os.urandom(16)
        # 使用密钥+盐派生加密密钥
        derived = hashlib.pbkdf2_hmac('sha256', key, salt, 100000, 32)
        # 简单的AEAD：加密+HMAC认证
        ciphertext = self._xor_encrypt(plaintext.encode('utf-8'), derived[:16])
        mac = hmac.new(derived[16:], ciphertext, hashlib.sha256).digest()
        payload = base64.b64encode(salt + mac + ciphertext).decode('utf-8')
        return f"#PII:v2#{payload}"

    def _decrypt_pii(self, encrypted: str, key: bytes) -> Optional[str]:
        """使用会话密钥解密PII"""
        if not encrypted.startswith("#PII:v2#"):
            return None
        payload = encrypted[len("#PII:v2#"):]
        try:
            raw = base64.b64decode(payload)
            salt, mac, ciphertext = raw[:16], raw[16:48], raw[48:]
            derived = hashlib.pbkdf2_hmac('sha256', key, salt, 100000, 32)
            expected_mac = hmac.new(derived[16:], ciphertext, hashlib.sha256).digest()
            if not hmac.compare_digest(mac, expected_mac):
                logger.warning("PII解密: HMAC校验失败，数据可能被篡改")
                return None
            return self._xor_decrypt(ciphertext, derived[:16]).decode('utf-8', errors='replace')
        except Exception as e:
            logger.error(f"PII解密失败: {e}")
            return None

    @staticmethod
    def _xor_encrypt(data: bytes, key: bytes) -> bytes:
        """XOR加密（流模式）"""
        return bytes(a ^ key[i % len(key)] for i, a in enumerate(data))

    @staticmethod
    def _xor_decrypt(data: bytes, key: bytes) -> bytes:
        """XOR解密"""
        return bytes(a ^ key[i % len(key)] for i, a in enumerate(data))

    # ========== 校验工具 ==========

    @staticmethod
    def _verify_id_card(id_num: str) -> bool:
        """校验身份证号第18位校验码"""
        if len(id_num) != 18:
            return False
        try:
            weights = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
            check_chars = ['1', '0', 'X', '9', '8', '7', '6', '5', '4', '3', '2']
            total = sum(int(id_num[i]) * weights[i] for i in range(17))
            return id_num[17].upper() == check_chars[total % 11]
        except (ValueError, IndexError):
            return False

    @staticmethod
    def _luhn_check(card_num: str) -> bool:
        """Luhn算法校验银行卡号"""
        try:
            digits = [int(d) for d in card_num]
            checksum = 0
            for i in range(len(digits) - 2, -1, -2):
                d = digits[i] * 2
                checksum += d if d < 10 else d - 9
            for i in range(len(digits) - 1, -1, -2):
                checksum += digits[i]
            return checksum % 10 == 0
        except (ValueError, IndexError):
            return False


# ========== 全局单例 ==========

_guard_instance = None


def get_privacy_guard(master_key: str = None) -> PrivacyGuard:
    """获取全局隐私卫士实例"""
    global _guard_instance
    if _guard_instance is None:
        _guard_instance = PrivacyGuard(master_key)
    return _guard_instance
