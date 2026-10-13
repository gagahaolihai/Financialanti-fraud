"""
外部大模型接入配置存储

设计目标
--------
让「是否接入外部大模型 API」成为**运行时可配置**的能力，而不是写死在 .env 里：

- 默认关闭 = 纯本地模式（本地语义模型 + 规则引擎），零联网、数据不出本机
- 用户可在管理后台自行填写厂商 / 地址 / Key / 模型，保存后**热生效**，无需重启
- API Key 以 AES 加密后落盘（复用 engine.security.DataEncryptor），
  对外接口一律只回显掩码，明文只在进程内存与真实调用时存在

配置优先级：管理后台保存的运行时配置 > .env > 内置默认值
"""
import json
import logging
import os
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# 掩码保留的首尾字符数
_MASK_HEAD = 6
_MASK_TAIL = 4


def mask_api_key(key: str) -> str:
    """把 API Key 掩码成 sk-abc****wxyz 形式，用于对外展示"""
    if not key:
        return ""
    if len(key) <= _MASK_HEAD + _MASK_TAIL:
        return "*" * len(key)
    return f"{key[:_MASK_HEAD]}{'*' * 8}{key[-_MASK_TAIL:]}"


class LLMConfigStore:
    """
    外部大模型接入配置的持久化与读取。

    线程安全：Flask 默认 threaded=True，读写加锁避免并发写坏 JSON。
    """

    def __init__(self, path: str, encryptor=None):
        self._path = path
        self._encryptor = encryptor
        # RLock：save()/disable() 持有锁后还会调用 load()，用普通 Lock 会自锁死
        self._lock = threading.RLock()
        self._cache: Optional[dict] = None

    # ---------- 内部读写 ----------

    def _defaults(self) -> dict:
        """无运行时配置时的兜底：回落到 .env / 内置默认值"""
        try:
            from config import Config
            return {
                "enabled": bool(Config.LLM_ENABLED and not Config.SAFE_MODE),
                "provider": Config.LLM_PROVIDER,
                "api_url": Config.LLM_API_URL,
                "model": Config.LLM_MODEL,
                "api_key": Config.LLM_API_KEY,
                "source": "env",
            }
        except Exception:
            return {
                "enabled": False, "provider": "deepseek", "api_url": "",
                "model": "", "api_key": "", "source": "default",
            }

    def load(self) -> dict:
        """
        读取完整配置（**含明文 Key**，仅供内部投喂给 LLMClient 使用，切勿直接返回给前端）。
        """
        with self._lock:
            if self._cache is not None:
                return dict(self._cache)

            if not os.path.exists(self._path):
                self._cache = self._defaults()
                return dict(self._cache)

            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    raw = json.load(f)

                api_key = ""
                enc = raw.get("api_key_enc")
                if enc and self._encryptor:
                    try:
                        api_key = self._encryptor.decrypt_json(enc).get("api_key", "")
                    except Exception as e:
                        # 解密失败常见于 ENCRYPTION_KEY 被改过 —— 报清楚，别静默吞掉
                        logger.error(
                            f"[LLMConfig] API Key 解密失败（ENCRYPTION_KEY 是否变更过？）: {e}"
                        )
                        api_key = ""
                elif enc:
                    logger.warning("[LLMConfig] 存在加密 Key 但无可用加密器，已忽略")

                self._cache = {
                    "enabled": bool(raw.get("enabled", False)),
                    "provider": raw.get("provider", "deepseek"),
                    "api_url": raw.get("api_url", ""),
                    "model": raw.get("model", ""),
                    "api_key": api_key,
                    "source": "runtime",
                }
                return dict(self._cache)

            except Exception as e:
                logger.error(f"[LLMConfig] 配置文件读取失败，回落到 .env: {e}")
                self._cache = self._defaults()
                return dict(self._cache)

    def public_view(self) -> dict:
        """对外安全视图：Key 只回显掩码，供 /api/admin/llm/config 使用"""
        cfg = self.load()
        view = {k: v for k, v in cfg.items() if k != "api_key"}
        view["api_key_masked"] = mask_api_key(cfg.get("api_key", ""))
        view["has_api_key"] = bool(cfg.get("api_key"))
        return view

    # ---------- 写入 ----------

    def _write(self, cfg: dict) -> None:
        """落盘。Key 加密；其余字段明文（不含敏感信息）"""
        api_key = cfg.pop("api_key", "")

        payload = dict(cfg)
        if api_key:
            if not self._encryptor:
                raise RuntimeError("加密器不可用，拒绝以明文形式存储 API Key")
            payload["api_key_enc"] = self._encryptor.encrypt_json({"api_key": api_key})
        else:
            payload["api_key_enc"] = ""

        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        # 先写临时文件再替换，避免写一半崩溃导致配置损坏
        tmp = self._path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)

        # 缓存同步为明文形态，省去下次解密
        self._cache = dict(cfg, api_key=api_key)

    def save(self, provider: str, api_url: str = "", model: str = "",
             api_key: str = "") -> dict:
        """
        保存并启用外部 API。

        api_key 传空串时表示「保持原 Key 不变」（前端回显的是掩码，
        用户不重填就不该把 Key 抹掉）。
        """
        with self._lock:
            current = self.load()
            effective_key = api_key if api_key else current.get("api_key", "")

            cfg = {
                "enabled": True,
                "provider": provider or "custom",
                "api_url": api_url or "",
                "model": model or "",
                "api_key": effective_key,
                "source": "runtime",
            }
            self._write(cfg)
            logger.info(
                f"[LLMConfig] 已保存并启用: provider={cfg['provider']}, "
                f"model={cfg['model']}, key={'已配置' if effective_key else '空'}"
            )
            return dict(cfg)

    def disable(self) -> dict:
        """关闭外部 API，回到纯本地模式（保留已填字段便于下次快速启用）"""
        with self._lock:
            current = self.load()
            cfg = {
                "enabled": False,
                "provider": current.get("provider", "deepseek"),
                "api_url": current.get("api_url", ""),
                "model": current.get("model", ""),
                "api_key": current.get("api_key", ""),
                "source": "runtime",
            }
            self._write(cfg)
            logger.info("[LLMConfig] 已关闭外部 API，回到纯本地模式")
            return dict(cfg)

    def invalidate(self) -> None:
        """丢弃内存缓存，强制下次 load() 重新读盘"""
        with self._lock:
            self._cache = None


# ---------- 全局单例 ----------

_store: Optional[LLMConfigStore] = None


def get_llm_config_store() -> LLMConfigStore:
    global _store
    if _store is None:
        from config import Config
        from engine.security import DataEncryptor

        path = os.path.join(Config.DATA_DIR, "llm_config.json")
        _store = LLMConfigStore(path, encryptor=DataEncryptor(Config.ENCRYPTION_KEY))
    return _store
