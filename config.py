"""
中央配置管理 - 从环境变量加载配置，支持 .env 文件
"""
import os
from pathlib import Path

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

# ⚠️ 必须在 Config 类体求值「之前」加载 .env。
# 类体里的 os.getenv() 是在 import 时立即执行的，若把 load_dotenv 放在文件末尾，
# 所有默认值都会先于 .env 被写死，导致 .env 完全失效（历史 bug）。
_DOTENV_LOADED = False
try:
    from dotenv import load_dotenv
    # override=False：真实环境变量优先级仍高于 .env，与下方 Config 注释的优先级一致
    _DOTENV_LOADED = load_dotenv(BASE_DIR / '.env')
except ImportError:  # python-dotenv 为可选依赖
    pass


class Config:
    """应用配置，优先级：环境变量 > .env文件 > 默认值"""

    # ---------- 基础 ----------
    SECRET_KEY: str = os.getenv("SECRET_KEY", os.urandom(32).hex())
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    PORT: int = int(os.getenv("PORT", "5000"))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    # ---------- 数据库 ----------
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'data' / 'antifraud.db'}"
    )

    # ---------- 加密 ----------
    ENCRYPTION_KEY: str = os.getenv(
        "ENCRYPTION_KEY",
        "default-dev-key-change-in-production-32bytes!"  # 生产环境务必修改
    )
    # 数据文件加密存储路径
    DATA_DIR: str = os.getenv("DATA_DIR", str(BASE_DIR / "data"))
    ENCRYPT_DATA: bool = os.getenv("ENCRYPT_DATA", "true").lower() == "true"

    # ---------- 安全 ----------
    ENABLE_RATE_LIMIT: bool = os.getenv("ENABLE_RATE_LIMIT", "true").lower() == "true"
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "30"))
    JWT_SECRET: str = os.getenv("JWT_SECRET", os.urandom(32).hex())
    JWT_EXPIRY_HOURS: int = int(os.getenv("JWT_EXPIRY_HOURS", "24"))
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
    HTTPS_ONLY: bool = os.getenv("HTTPS_ONLY", "false").lower() == "true"
    CSP_DIRECTIVES: str = os.getenv(
        "CSP_DIRECTIVES",
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    )

    # ---------- LLM集成 ----------
    LLM_ENABLED: bool = os.getenv("LLM_ENABLED", "false").lower() == "true"
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "deepseek")  # deepseek | openai | qwen
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_API_URL: str = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "deepseek-chat")
    LLM_FALLBACK_TO_RULES: bool = os.getenv("LLM_FALLBACK_TO_RULES", "true").lower() == "true"

    # ---------- 混合云部署 ----------
    CLOUD_DEPLOYMENT: str = os.getenv("CLOUD_DEPLOYMENT", "single")  # single | hybrid
    DATA_CROSS_REGION_ENCRYPT: bool = os.getenv("DATA_CROSS_REGION_ENCRYPT", "true").lower() == "true"
    TLS_CERT_PATH: str = os.getenv("TLS_CERT_PATH", "")
    TLS_KEY_PATH: str = os.getenv("TLS_KEY_PATH", "")

    # ---------- 日志 ----------
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "antifraud.log"))
    LOG_MAX_BYTES: int = int(os.getenv("LOG_MAX_BYTES", "10485760"))  # 10MB
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))

    # ---------- 管理后台 ----------
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD_HASH: str = os.getenv(
        "ADMIN_PASSWORD_HASH",
        ""  # 首次启动时通过 /api/admin/set-password 设置
    )

    # ---------- 合规 ----------
    DATA_RETENTION_DAYS: int = int(os.getenv("DATA_RETENTION_DAYS", "90"))
    ENABLE_AUDIT_LOG: bool = os.getenv("ENABLE_AUDIT_LOG", "true").lower() == "true"
    GDPR_COMPLIANCE: bool = os.getenv("GDPR_COMPLIANCE", "false").lower() == "true"

    # ---------- v3.0 运行模式 ----------
    # SAFE_MODE=true: 纯规则引擎，零网络依赖，100%稳定（比赛兜底方案）
    SAFE_MODE: bool = os.getenv("SAFE_MODE", "false").lower() == "true"
    # NLP_OFFLINE_MODE=true: 使用项目内 models/ 中的本地模型，不从网络下载
    NLP_OFFLINE_MODE: bool = os.getenv("NLP_OFFLINE_MODE", "true").lower() == "true"

    @classmethod
    def init_app(cls, app):
        """初始化应用配置"""
        if app is not None:
            app.config.from_object(cls)

        # 确保必要目录存在
        os.makedirs(cls.DATA_DIR, exist_ok=True)
        os.makedirs(os.path.dirname(cls.LOG_FILE), exist_ok=True)

    _env_path = BASE_DIR / '.env'
    if _DOTENV_LOADED:
        print(f"[OK] 配置: 已加载 {_env_path.name}（环境变量 > .env > 默认值）")
    else:
        print(f"[--] 配置: 未找到 {_env_path.name}，使用内置默认值")
