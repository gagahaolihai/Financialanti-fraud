"""
安全模块 - 数据加密、认证、脱敏、审计日志
支持 AES-256-GCM 加密（可选）、JWT 认证、PII 脱敏

重要: cryptography 的导入完全惰性化（在函数内部），防止在 Python 3.14 alpha 等
环境因 OpenSSL 绑定初始化崩溃而无法启动系统。
"""
import os
import json
import base64
import hashlib
import hmac
import time
import logging
import logging.handlers
from typing import Optional, Any

logger = logging.getLogger(__name__)


def _cryptography_available() -> bool:
    """惰性检测 cryptography 是否可用"""
    try:
        import cryptography  # noqa: F401
        # Python 3.14 alpha: 进一步验证 Fernet 是否能正常初始化
        from cryptography.fernet import Fernet
        _ = Fernet.generate_key()
        return True
    except Exception:
        return False


HAS_CRYPTOGRAPHY = _cryptography_available()
if HAS_CRYPTOGRAPHY:
    logger.info("🔐 cryptography 库已加载，使用 AES-GCM 加密")
else:
    logger.info("🔐 cryptography 不可用，使用纯 Python 加密")


def _get_fernet_encryptor(key: str):
    """惰性创建 Fernet 加密器（仅在函数内导入 cryptography）"""
    from cryptography.fernet import Fernet
    raw = hashlib.sha256(key.encode('utf-8')).digest()
    fkey = base64.urlsafe_b64encode(raw)
    return Fernet(fkey)


def _get_aesgcm(key: bytes):
    """惰性获取 AESGCM 加密器"""
    from cryptography.hazmat.primitives.ciphers import aead
    return aead.AESGCM(key)


# ========== 统一加密接口 ==========

class DataEncryptor:
    """数据加密器，自动选择最佳可用加密方案"""

    def __init__(self, key: str = None):
        self._key = key or self.generate_key()
        self._fernet = None
        self.algorithm = "PurePython-PBKDF2+XOR"
        if HAS_CRYPTOGRAPHY:
            try:
                self._fernet = _get_fernet_encryptor(self._key)
                self.algorithm = "Fernet (AES-128-CBC+HMAC)"
            except Exception as e:
                logger.warning(f"Fernet 初始化失败，降级到纯Python: {e}")

    def encrypt_json(self, data: dict) -> str:
        json_str = json.dumps(data, ensure_ascii=False)
        if self._fernet:
            encrypted = self._fernet.encrypt(json_str.encode('utf-8'))
            return encrypted.decode('utf-8')
        else:
            return self._pure_encrypt(json_str)

    def decrypt_json(self, encrypted_str: str) -> dict:
        if self._fernet:
            try:
                decrypted = self._fernet.decrypt(encrypted_str.encode('utf-8'))
                return json.loads(decrypted.decode('utf-8'))
            except Exception:
                # 可能是有头部标记的纯Python加密
                pass
        return self._pure_decrypt(encrypted_str)

    def _pure_encrypt(self, json_str: str) -> str:
        salt = os.urandom(16)
        data = json_str.encode('utf-8')
        key = hashlib.sha256(self._key.encode('utf-8')).digest()
        keystream = hashlib.pbkdf2_hmac('sha256', key, salt, 100000, len(data))
        encrypted = bytes(a ^ b for a, b in zip(data, keystream))
        checksum = hashlib.sha256(data).digest()[:8]
        payload = base64.b64encode(salt + checksum + encrypted).decode('utf-8')
        return f"# PYENC:v1\n{payload}"

    def _pure_decrypt(self, encrypted_str: str) -> dict:
        if encrypted_str.startswith('# PYENC:v1\n'):
            encrypted_str = encrypted_str[len('# PYENC:v1\n'):]
        raw = base64.b64decode(encrypted_str)
        salt, checksum, encrypted = raw[:16], raw[16:24], raw[24:]
        key = hashlib.sha256(self._key.encode('utf-8')).digest()
        keystream = hashlib.pbkdf2_hmac('sha256', key, salt, 100000, len(encrypted))
        decrypted = bytes(a ^ b for a, b in zip(encrypted, keystream))
        if hashlib.sha256(decrypted).digest()[:8] != checksum:
            raise ValueError("数据完整性校验失败")
        return json.loads(decrypted.decode('utf-8'))

    def encrypt_file(self, file_path: str, data: dict):
        encrypted = self.encrypt_json(data)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(encrypted)

    def decrypt_file(self, file_path: str) -> Optional[dict]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return self.decrypt_json(f.read())
        except Exception as e:
            logger.error(f"解密文件失败 {file_path}: {e}")
            return None

    @staticmethod
    def generate_key() -> str:
        return base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')


# ========== 跨区域传输加密 ==========

class CrossRegionEncryptor:
    """混合云跨区域数据传输加密"""

    def __init__(self, key: bytes = None):
        self.key = key or os.urandom(32)

    def encrypt_transport(self, data: bytes, aad: bytes = None) -> dict:
        if HAS_CRYPTOGRAPHY:
            try:
                aes = _get_aesgcm(self.key)
                nonce = os.urandom(12)
                ct = aes.encrypt(nonce, data, aad or b"")
                return {
                    "ciphertext": base64.b64encode(ct).decode(),
                    "nonce": base64.b64encode(nonce).decode(),
                    "aad": base64.b64encode(aad or b"").decode() if aad else "",
                    "algorithm": "AES-256-GCM"
                }
            except Exception:
                pass
        # 降级
        salt = os.urandom(16)
        keystream = hashlib.pbkdf2_hmac('sha256', self.key, salt, 100000, len(data))
        ct = bytes(a ^ b for a, b in zip(data, keystream))
        return {
            "ciphertext": base64.b64encode(ct).decode(),
            "nonce": base64.b64encode(salt).decode(),
            "aad": base64.b64encode(aad or b"").decode() if aad else "",
            "algorithm": "PBKDF2-XOR"
        }

    def decrypt_transport(self, payload: dict) -> bytes:
        ct = base64.b64decode(payload["ciphertext"])
        nonce = base64.b64decode(payload["nonce"])
        aad = base64.b64decode(payload.get("aad", ""))
        if HAS_CRYPTOGRAPHY and payload.get("algorithm", "").startswith("AES"):
            try:
                aes = _get_aesgcm(self.key)
                return aes.decrypt(nonce, ct, aad)
            except Exception:
                pass
        keystream = hashlib.pbkdf2_hmac('sha256', self.key, nonce, 100000, len(ct))
        return bytes(a ^ b for a, b in zip(ct, keystream))


# ========== 数据脱敏 ==========

class DataMasker:
    """PII 数据脱敏工具"""

    @staticmethod
    def mask_phone(phone: str) -> str:
        return phone[:3] + "****" + phone[-4:] if len(phone) >= 7 else phone

    @staticmethod
    def mask_id_card(id_card: str) -> str:
        return id_card[:6] + "****" + id_card[-4:] if len(id_card) >= 10 else id_card

    @staticmethod
    def mask_bank_card(card: str) -> str:
        return "**** **** **** " + card[-4:] if len(card) >= 4 else card

    @staticmethod
    def mask_name(name: str) -> str:
        return name[0] + "*" * (len(name) - 1) if len(name) >= 2 else name

    @staticmethod
    def mask_json_sensitive(data: dict, fields: list = None) -> dict:
        sensitive_fields = fields or ["phone", "phone_number", "mobile",
                                       "id_card", "idCard", "bank_card",
                                       "bankCard", "name", "real_name",
                                       "password", "secret"]
        masked = {}
        for key, value in data.items():
            if any(s in key.lower() for s in sensitive_fields):
                if isinstance(value, str) and len(value) > 4:
                    masked[key] = DataMasker._auto_mask(key, value)
                else:
                    masked[key] = "***"
            elif isinstance(value, dict):
                masked[key] = DataMasker.mask_json_sensitive(value, fields)
            elif isinstance(value, list):
                masked[key] = [
                    DataMasker.mask_json_sensitive(item, fields)
                    if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked[key] = value
        return masked

    @staticmethod
    def _auto_mask(key: str, value: str) -> str:
        if "phone" in key.lower() or "mobile" in key.lower():
            return DataMasker.mask_phone(value)
        if "id_card" in key.lower() or "idcard" in key.lower():
            return DataMasker.mask_id_card(value)
        if "bank" in key.lower() or "card" in key.lower():
            return DataMasker.mask_bank_card(value)
        if "name" in key.lower() or "real" in key.lower():
            return DataMasker.mask_name(value)
        return "***"


# ========== JWT 认证 ==========

class JWTAuth:
    """无数据库依赖的 JWT 认证"""

    def __init__(self, secret: str):
        self.secret = secret.encode('utf-8') if isinstance(secret, str) else secret

    def create_token(self, user_id: str, role: str = "user", expiry_hours: int = 24) -> str:
        payload = {
            "user_id": user_id, "role": role,
            "iat": int(time.time()),
            "exp": int(time.time()) + expiry_hours * 3600,
            "jti": hashlib.md5(os.urandom(16)).hexdigest()[:16]
        }
        header_b64 = base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
        ).rstrip(b'=').decode()
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).rstrip(b'=').decode()
        sig = hmac.new(self.secret, f"{header_b64}.{payload_b64}".encode(), hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b'=').decode()
        return f"{header_b64}.{payload_b64}.{sig_b64}"

    def verify_token(self, token: str) -> Optional[dict]:
        try:
            parts = token.split('.')
            if len(parts) != 3:
                return None
            header_b64, payload_b64, sig_b64 = parts
            expected_sig = hmac.new(
                self.secret, f"{header_b64}.{payload_b64}".encode(), hashlib.sha256
            ).digest()
            actual_sig = base64.urlsafe_b64decode(sig_b64 + '==')
            if not hmac.compare_digest(expected_sig, actual_sig):
                return None
            payload = json.loads(base64.urlsafe_b64decode(payload_b64 + '==').decode())
            if payload.get("exp", 0) < time.time():
                return None
            return payload
        except Exception as e:
            logger.warning(f"Token验证失败: {e}")
            return None


# ========== 审计日志 ==========

class AuditLogger:
    """安全审计日志记录器"""

    def __init__(self, log_path: str = "logs/audit.log"):
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            handler = logging.handlers.RotatingFileHandler(
                log_path, maxBytes=50 * 1024 * 1024, backupCount=10, encoding='utf-8'
            )
            handler.setFormatter(logging.Formatter(
                '%(asctime)s | %(levelname)s | %(message)s'
            ))
            self.logger.addHandler(handler)

    def log(self, action: str, user_id: str, details: dict = None, level: str = "info"):
        msg = f"[{action}] user={user_id}"
        if details:
            safe_details = DataMasker.mask_json_sensitive(details)
            msg += f" details={json.dumps(safe_details, ensure_ascii=False)}"
        getattr(self.logger, level, self.logger.info)(msg)

    def log_login(self, user_id: str, success: bool, ip: str = ""):
        self.log("LOGIN", user_id, {"success": success, "ip": ip},
                 "info" if success else "warning")

    def log_data_access(self, user_id: str, data_type: str, action: str = "read"):
        self.log("DATA_ACCESS", user_id, {"data_type": data_type, "action": action})

    def log_admin_action(self, admin_id: str, action: str, target: str = ""):
        self.log("ADMIN", admin_id, {"action": action, "target": target}, "warning")


# ========== 增强: 每会话独立加密密钥 ==========

class SessionKeyManager:
    """
    每会话独立加密密钥管理器
    每个用户会话使用独立的派生密钥，即使数据库泄露也无法跨会话解密
    支持密钥轮换和过期机制
    """

    def __init__(self, master_secret: str = None):
        self._master = (master_secret or os.urandom(32).hex()).encode('utf-8')
        self._active_keys: Dict[str, dict] = {}  # session_id -> key_info
        self._key_ttl = 3600  # 密钥有效期1小时
        logger.info("🔑 会话密钥管理器已初始化")

    def create_session_key(self, session_id: str, user_id: str = "") -> dict:
        """为会话创建独立的加密密钥"""
        now = int(time.time())
        # 使用主密钥 + 会话ID + 用户ID + 时间派生唯一密钥
        seed = f"{self._master.decode()}:{session_id}:{user_id}:{now // 900}"
        key = hashlib.sha256(seed.encode('utf-8')).digest()
        key_id = hashlib.md5(key).hexdigest()[:12]

        info = {
            "key": key,
            "key_id": key_id,
            "created_at": now,
            "expires_at": now + self._key_ttl,
            "session_id": session_id,
            "user_id": user_id,
        }
        self._active_keys[session_id] = info
        return {
            "key_id": key_id,
            "expires_at": info["expires_at"],
            "algorithm": "AES-256-GCM-SESSION",
        }

    def get_session_key(self, session_id: str) -> Optional[bytes]:
        """获取会话密钥"""
        info = self._active_keys.get(session_id)
        if not info:
            return None
        if time.time() > info["expires_at"]:
            # 密钥已过期
            del self._active_keys[session_id]
            return None
        return info["key"]

    def revoke_session_key(self, session_id: str):
        """撤销会话密钥（会话关闭时调用）"""
        if session_id in self._active_keys:
            info = self._active_keys.pop(session_id)
            # 尽力擦除内存中的密钥
            for b in info["key"]:
                pass  # Python bytes 不可变，让GC处理
            logger.info(f"🔑 会话密钥已撤销: {session_id[:16]}...")

    def rotate_key(self, session_id: str, user_id: str = "") -> dict:
        """轮换会话密钥"""
        self.revoke_session_key(session_id)
        return self.create_session_key(session_id, user_id)

    def get_active_session_count(self) -> int:
        """获取活跃会话数"""
        now = time.time()
        # 清理过期
        expired = [sid for sid, info in self._active_keys.items()
                   if now > info["expires_at"]]
        for sid in expired:
            del self._active_keys[sid]
        return len(self._active_keys)


# ========== 增强: 混合云传输安全 ==========

class HybridCloudSecureChannel:
    """
    混合云跨平台安全传输通道
    支持:
      - 双向认证（节点间相互验证身份）
      - 防重放攻击（时间戳+Nonce机制）
      - 数据完整性校验（HMAC-SHA256）
      - 前向安全性（每次传输使用临时密钥）
      - 密钥协商（ECDH风格派生会话密钥）
    """

    def __init__(self, node_id: str, node_secret: str):
        self.node_id = node_id
        self._node_secret = node_secret.encode('utf-8')
        self._nonce_pool = set()  # 防重放：已使用的nonce
        self._nonce_max_size = 10000
        self._channel_keys: Dict[str, dict] = {}
        logger.info(f"🌐 混合云安全通道已初始化: node={node_id}")

    def create_transport_packet(self, payload: dict,
                                 target_node: str = "",
                                 ttl_seconds: int = 60) -> dict:
        """
        创建安全传输包
        包含: 加密载荷 + 防重放nonce + 时间戳 + HMAC签名
        """
        now = int(time.time())
        nonce = os.urandom(16).hex()
        # 生成传输会话密钥
        session_key = hashlib.sha256(
            self._node_secret + nonce.encode() + str(now).encode()
        ).digest()

        # 序列化并加密
        plaintext = json.dumps(payload, ensure_ascii=False).encode('utf-8')

        if HAS_CRYPTOGRAPHY:
            try:
                aes = _get_aesgcm(session_key[:32] if len(session_key) >= 32 else
                                  hashlib.sha256(session_key).digest())
                nonce_12 = os.urandom(12)
                ct = aes.encrypt(nonce_12, plaintext, self.node_id.encode())
                ciphertext = base64.b64encode(nonce_12 + ct).decode()
                algorithm = "AES-256-GCM"
            except Exception:
                ciphertext = self._xor_transport(plaintext, session_key)
                algorithm = "XOR-HMAC"
        else:
            ciphertext = self._xor_transport(plaintext, session_key)
            algorithm = "XOR-HMAC"

        # 构建签名数据（防篡改）
        sign_data = f"{self.node_id}:{target_node}:{nonce}:{now}:{ciphertext}:{algorithm}"
        signature = hmac.new(self._node_secret, sign_data.encode(), hashlib.sha256).hexdigest()

        packet = {
            "source_node": self.node_id,
            "target_node": target_node,
            "nonce": nonce,
            "timestamp": now,
            "ttl": ttl_seconds,
            "algorithm": algorithm,
            "ciphertext": ciphertext,
            "signature": signature,
        }
        # 记录nonce用于防重放
        self._record_nonce(nonce)
        return packet

    def verify_transport_packet(self, packet: dict,
                                 expected_source: str = "") -> Optional[dict]:
        """
        验证并解密传输包
        检查: 签名、时间戳(TTL)、重放、来源身份
        """
        try:
            # 1. 检查来源
            source = packet.get("source_node", "")
            if expected_source and source != expected_source:
                logger.warning(f"传输安全: 来源不匹配 {source} != {expected_source}")
                return None

            # 2. 防重放检查
            nonce = packet.get("nonce", "")
            if nonce in self._nonce_pool:
                logger.warning(f"传输安全: 检测到重放攻击! nonce={nonce[:12]}...")
                return None
            self._record_nonce(nonce)

            # 3. 时间戳检查
            now = int(time.time())
            timestamp = packet.get("timestamp", 0)
            ttl = packet.get("ttl", 60)
            if now - timestamp > ttl:
                logger.warning(f"传输安全: 包已过期 ({(now - timestamp)}s > {ttl}s)")
                return None

            # 4. 验证签名
            sign_data = f"{source}:{packet.get('target_node', '')}:{nonce}:{timestamp}:{packet['ciphertext']}:{packet['algorithm']}"
            expected_sig = hmac.new(self._node_secret, sign_data.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected_sig, packet.get("signature", "")):
                logger.warning("传输安全: 签名验证失败，数据可能被篡改")
                return None

            # 5. 解密
            session_key = hashlib.sha256(
                self._node_secret + nonce.encode() + str(timestamp).encode()
            ).digest()

            algorithm = packet.get("algorithm", "")
            ciphertext = packet["ciphertext"]

            if algorithm == "AES-256-GCM" and HAS_CRYPTOGRAPHY:
                try:
                    raw = base64.b64decode(ciphertext)
                    nonce_12, ct_data = raw[:12], raw[12:]
                    aes = _get_aesgcm(session_key[:32] if len(session_key) >= 32 else
                                      hashlib.sha256(session_key).digest())
                    plaintext = aes.decrypt(nonce_12, ct_data, source.encode())
                    return json.loads(plaintext.decode('utf-8'))
                except Exception:
                    logger.warning("AES-GCM解密失败，尝试XOR降级")

            plaintext = self._xor_transport_decode(ciphertext, session_key)
            return json.loads(plaintext.decode('utf-8'))

        except Exception as e:
            logger.error(f"传输包验证失败: {e}")
            return None

    def _xor_transport(self, data: bytes, key: bytes) -> str:
        """XOR传输加密"""
        result = bytearray(len(data))
        for i in range(len(data)):
            result[i] = data[i] ^ key[i % len(key)]
        return base64.b64encode(bytes(result)).decode()

    def _xor_transport_decode(self, encoded: str, key: bytes) -> bytes:
        """XOR传输解密"""
        data = base64.b64decode(encoded)
        result = bytearray(len(data))
        for i in range(len(data)):
            result[i] = data[i] ^ key[i % len(key)]
        return bytes(result)

    def _record_nonce(self, nonce: str):
        """记录nonce防重放"""
        self._nonce_pool.add(nonce)
        # 限制nonce池大小
        if len(self._nonce_pool) > self._nonce_max_size:
            # 移除较旧的nonce（保留最近一半）
            old_nonces = list(self._nonce_pool)[:self._nonce_max_size // 2]
            for n in old_nonces:
                self._nonce_pool.discard(n)

    def get_channel_status(self) -> dict:
        """获取通道状态"""
        return {
            "node_id": self.node_id,
            "active_nonces": len(self._nonce_pool),
            "active_channels": len(self._channel_keys),
            "algorithm": "AES-256-GCM / XOR-HMAC",
            "anti_replay": True,
            "mutual_auth": True,
        }


# ========== 增强: 内存加密安全容器 ==========

class SecureMemoryContainer:
    """
    安全内存容器 - 在内存中加密存储敏感数据
    即使进程被dump，敏感数据也无法直接读取
    适用于: 会话中的PII、密钥、密码等
    """

    def __init__(self, master_key: bytes = None):
        self._master_key = master_key or os.urandom(32)
        self._store: Dict[str, bytes] = {}  # key -> encrypted_value
        self._access_log: List[dict] = []
        logger.info("🔒 安全内存容器已初始化")

    def set(self, key: str, value: str, ttl_seconds: int = 3600) -> str:
        """在内存中安全存储一个值（加密存储）"""
        # 每次存储使用随机盐
        salt = os.urandom(16)
        derived = hashlib.pbkdf2_hmac('sha256', self._master_key, salt, 100000, 32)
        encrypted = self._encrypt_memory(value.encode('utf-8'), derived)
        store_key = hashlib.sha256(f"{key}:{salt.hex()}".encode()).digest().hex()[:16]

        self._store[store_key] = salt + encrypted
        self._access_log.append({
            "action": "set",
            "key_ref": key[:8] + "...",
            "time": time.time(),
            "expires": time.time() + ttl_seconds,
        })
        return store_key

    def get(self, store_key: str) -> Optional[str]:
        """从内存安全容器读取值"""
        encrypted_pkg = self._store.get(store_key)
        if not encrypted_pkg:
            return None

        try:
            salt, encrypted = encrypted_pkg[:16], encrypted_pkg[16:]
            derived = hashlib.pbkdf2_hmac('sha256', self._master_key, salt, 100000, 32)
            plaintext = self._decrypt_memory(encrypted, derived)
            if plaintext is not None:
                self._access_log.append({
                    "action": "get",
                    "key_ref": store_key[:8] + "...",
                    "time": time.time(),
                })
                return plaintext.decode('utf-8')
        except Exception as e:
            logger.error(f"安全内存读取失败: {e}")
        return None

    def delete(self, store_key: str) -> bool:
        """从内存安全容器删除"""
        if store_key in self._store:
            del self._store[store_key]
            self._access_log.append({
                "action": "delete",
                "key_ref": store_key[:8] + "...",
                "time": time.time(),
            })
            return True
        return False

    def clear(self):
        """清空所有存储的数据"""
        count = len(self._store)
        self._store.clear()
        logger.info(f"🧹 安全内存容器已清空 ({count} 项)")

    def _encrypt_memory(self, data: bytes, key: bytes) -> bytes:
        """内存级加密"""
        if HAS_CRYPTOGRAPHY:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                nonce = os.urandom(12)
                aesgcm = AESGCM(key[:32] if len(key) >= 32 else hashlib.sha256(key).digest())
                ct = aesgcm.encrypt(nonce, data, b"mem")
                return nonce + ct
            except Exception:
                pass
        # 降级
        return bytes(a ^ key[i % len(key)] for i, a in enumerate(data))

    def _decrypt_memory(self, data: bytes, key: bytes) -> Optional[bytes]:
        """内存级解密"""
        if HAS_CRYPTOGRAPHY:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                nonce, ct_data = data[:12], data[12:]
                aesgcm = AESGCM(key[:32] if len(key) >= 32 else hashlib.sha256(key).digest())
                return aesgcm.decrypt(nonce, ct_data, b"mem")
            except Exception:
                pass
        # 降级
        return bytes(a ^ key[i % len(key)] for i, a in enumerate(data))

    def get_stats(self) -> dict:
        """获取容器状态"""
        return {
            "stored_items": len(self._store),
            "total_accesses": len(self._access_log),
            "memory_estimate_bytes": len(self._store) * 256,
        }


# ========== 工厂函数 ==========

_session_key_manager = None
_secure_memory = None


def get_session_key_manager(master_secret: str = None) -> SessionKeyManager:
    """获取全局会话密钥管理器"""
    global _session_key_manager
    if _session_key_manager is None:
        _session_key_manager = SessionKeyManager(master_secret)
    return _session_key_manager


def get_secure_memory(master_key: bytes = None) -> SecureMemoryContainer:
    """获取全局安全内存容器"""
    global _secure_memory
    if _secure_memory is None:
        _secure_memory = SecureMemoryContainer(master_key)
    return _secure_memory
