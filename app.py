"""
多模态智能反诈对话系统 v2.1
Anti-Fraud Intelligent Dialogue System

增强特性:
  - AES-256-GCM 数据加密存储
  - JWT 认证 / 速率限制 / 安全头
  - 对话持久化 (SQLite)
  - 管理后台 / 审计日志
  - LLM 集成 (DeepSeek/Qwen/OpenAI)
  - 诈骗知识图谱
  - Swagger API 文档
  - Docker 部署 / 混合云安全传输
"""
import json
import os
import sys
import io
import uuid
import time
import logging
from datetime import datetime
from functools import wraps

from flask import (Flask, request, jsonify, render_template,
                   session, redirect, url_for, abort)
from flask_cors import CORS

# 框架库（可选导入，缺失时降级）
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    HAS_LIMITER = True
except ImportError:
    HAS_LIMITER = False

try:
    from flask_talisman import Talisman
    HAS_TALISMAN = True
except ImportError:
    HAS_TALISMAN = False

try:
    from flask_swagger_ui import get_swaggerui_blueprint
    HAS_SWAGGER = True
except ImportError:
    HAS_SWAGGER = False

# 配置
from config import Config

# 引擎模块
from engine.response_generator import ResponseGenerator
from engine.url_analyzer import URLAnalyzer
from engine.knowledge_retriever import KnowledgeRetriever
from engine.intent_recognizer import IntentRecognizer

# 增强模块
from engine.security import (DataEncryptor, DataMasker, JWTAuth, AuditLogger,
                              SessionKeyManager, HybridCloudSecureChannel,
                              SecureMemoryContainer, get_session_key_manager)
from engine.log_setup import setup_logging
from engine.llm_client import LLMClient, normalize_api_url
from engine.llm_config_store import get_llm_config_store, mask_api_key
from engine.privacy_guard import PrivacyGuard, get_privacy_guard

try:
    from engine.knowledge_graph import FraudKnowledgeGraph
    HAS_KG = True
except ImportError:
    HAS_KG = False

# 数据库 - 惰性导入
try:
    import sqlalchemy  # noqa: F401
    HAS_DB = True
except Exception:
    HAS_DB = False

db_manager = None


def get_db():
    """惰性获取数据库管理器"""
    global db_manager
    if db_manager is not None:
        return db_manager
    if not HAS_DB:
        return None
    try:
        from engine.database import DatabaseManager
        db_manager = DatabaseManager(Config.DATABASE_URL)
        logger.info("[DB] 数据库管理器已初始化")
    except Exception as e:
        logger.warning(f"[DB] 数据库初始化失败（内存模式运行）: {e}")
    return db_manager


# ========== 初始化配置 & 日志 ==========
Config.init_app(None)
setup_logging(
    log_level=Config.LOG_LEVEL,
    log_file=Config.LOG_FILE,
    max_bytes=Config.LOG_MAX_BYTES,
    backup_count=Config.LOG_BACKUP_COUNT,
)

logger = logging.getLogger(__name__)
logger.info("🛡️  反诈卫士 v3.0 启动中...")


# ========== Flask 应用初始化 ==========
app = Flask(__name__)
app.secret_key = Config.SECRET_KEY
app.config['TESTING'] = Config.DEBUG
app.config['WTF_CSRF_ENABLED'] = True

# CORS
CORS(app, origins=Config.CORS_ORIGINS.split(',') if Config.CORS_ORIGINS != '*' else '*',
     supports_credentials=True)

# 安全头 (Talisman)
if HAS_TALISMAN and not Config.DEBUG:
    talisman = Talisman(
        app,
        force_https=Config.HTTPS_ONLY,
        strict_transport_security=True,
        session_cookie_secure=Config.HTTPS_ONLY,
        content_security_policy={
            'default-src': "'self'",
            'script-src': "'self' 'unsafe-inline'",
            'style-src': "'self' 'unsafe-inline'",
            'img-src': "'self' data:",
        } if Config.CSP_DIRECTIVES else None,
    )
    logger.info("🔒 Talisman 安全头已启用")

# 速率限制
limiter = None
if HAS_LIMITER and Config.ENABLE_RATE_LIMIT:
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[f"{Config.RATE_LIMIT_PER_MINUTE} per minute"],
        storage_uri="memory://" if "sqlite" in Config.DATABASE_URL else Config.DATABASE_URL,
    )
    logger.info(f"⏱️  速率限制已启用: {Config.RATE_LIMIT_PER_MINUTE}/分钟")


# ========== 全局初始化 ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# 核心引擎
response_gen = ResponseGenerator()
url_analyzer = URLAnalyzer()
knowledge_retriever = KnowledgeRetriever()

# 加密
encryptor = DataEncryptor(Config.ENCRYPTION_KEY)
data_masker = DataMasker()

# 认证
jwt_auth = JWTAuth(Config.JWT_SECRET)

# 审计日志
audit_logger = AuditLogger(
    log_path=os.path.join(BASE_DIR, 'logs', 'audit.log')
) if Config.ENABLE_AUDIT_LOG else None

# LLM
# 默认纯本地模式（不联网）；是否接入外部大模型由管理后台「外部大模型接入」决定，
# 保存后调用 apply_llm_config() 热生效，无需重启进程。
llm_client = LLMClient(
    provider=Config.LLM_PROVIDER,
    api_key=Config.LLM_API_KEY,
    api_url=Config.LLM_API_URL,
    model=Config.LLM_MODEL,
    fallback_to_rules=Config.LLM_FALLBACK_TO_RULES,
) if (Config.LLM_ENABLED and not Config.SAFE_MODE) else LLMClient(fallback_to_rules=True)


def apply_llm_config() -> dict:
    """
    把当前生效的外部大模型配置应用到全局 llm_client，并同步给 RAG 引擎。

    启动时调用一次；管理后台保存/关闭配置后再次调用即为热切换。

    Returns:
        生效后的配置（含明文判断结果，不含 Key 明文）
    """
    store = get_llm_config_store()
    cfg = store.load()
    active = bool(cfg.get("enabled") and cfg.get("api_key")) and not Config.SAFE_MODE

    if active:
        llm_client.configure(
            provider=cfg.get("provider") or "custom",
            api_key=cfg.get("api_key"),
            api_url=cfg.get("api_url") or None,
            model=cfg.get("model") or None,
        )
    else:
        # Key 置空 => enabled=False => 全链路回落到本地语义 + 规则引擎
        llm_client.configure(api_key="")

    # RAG 引擎默认会自建一个 LLMClient，这里让它复用同一个实例，
    # 否则热切换只会刷新其中一个，出现「后台已启用、RAG 仍走规则」的不一致。
    try:
        from engine.rag_engine import get_rag_engine
        get_rag_engine().set_llm_client(llm_client)
    except Exception as e:
        logger.warning(f"[LLM] RAG 引擎客户端同步失败: {e}")

    if active:
        logger.info(
            f"🌐 外部大模型已接入: {cfg.get('provider')} / {llm_client.model}"
        )
    else:
        reason = "SAFE_MODE" if Config.SAFE_MODE else "未启用外部 API"
        logger.info(f"🔒 本地模式（{reason}）: 使用本地语义模型 + 规则引擎，零联网")

    return {
        "enabled": active,
        "mode": "enhanced" if active else "local",
        "provider": cfg.get("provider"),
        "model": llm_client.model if active else None,
    }


apply_llm_config()

# 知识图谱
knowledge_graph = None
if HAS_KG:
    try:
        knowledge_graph = FraudKnowledgeGraph()
        knowledge_graph.build()
        logger.info("🧠 知识图谱已构建")
    except Exception as e:
        logger.warning(f"知识图谱构建失败: {e}")

# 隐私卫士
privacy_guard = PrivacyGuard(master_key=Config.ENCRYPTION_KEY)
privacy_sessions = {}  # user_id -> session_id

# 会话密钥管理器
session_key_mgr = get_session_key_manager(Config.JWT_SECRET)

# 混合云安全通道
hybrid_channel = None
if Config.CLOUD_DEPLOYMENT == "hybrid":
    hybrid_channel = HybridCloudSecureChannel(
        node_id=Config.ADMIN_USERNAME,
        node_secret=Config.JWT_SECRET,
    )
    logger.info("🌐 混合云安全通道已就绪")

# 内存对话缓存（兼容旧方案，但优先走数据库）
conversations_cache = {}


# ========== 认证装饰器 ==========

def require_auth(optional=False):
    """认证装饰器（支持可选认证）"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = request.headers.get('Authorization', '').replace('Bearer ', '')
            if token:
                payload = jwt_auth.verify_token(token)
                if payload:
                    request.user = payload
                    return f(*args, **kwargs)
            if optional:
                request.user = {"user_id": "anonymous", "role": "guest"}
                return f(*args, **kwargs)
            return jsonify({"error": "未授权，请提供有效的认证令牌"}), 401
        return decorated
    return decorator


def admin_required(f):
    """
    管理员认证装饰器。

    降级策略：未配置 ADMIN_PASSWORD_HASH 时放行（本地演示/单机模式）。
    若一上来就强制鉴权，而默认配置里根本没有可用的管理员密码，
    用户将永远进不去管理后台。一旦通过 .env 或 /api/admin/set-password
    设定了密码，这里即转为严格校验管理员令牌。
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not Config.ADMIN_PASSWORD_HASH:
            request.user = {"user_id": "local-admin", "role": "admin"}
            return f(*args, **kwargs)

        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        payload = jwt_auth.verify_token(token) if token else None
        if not payload or payload.get("role") != "admin":
            return jsonify({"error": "需要管理员权限"}), 403
        request.user = payload
        return f(*args, **kwargs)
    return decorated


# ========== 辅助函数 ==========

def get_user_id():
    """获取当前用户ID（支持多来源）"""
    # 1. 请求参数
    user_id = request.args.get('user_id')
    if not user_id:
        try:
            json_data = request.get_json(silent=True)
            if json_data:
                user_id = json_data.get('user_id')
        except Exception:
            user_id = None
    # 2. Session
    if not user_id:
        user_id = session.get('user_id')
    # 3. JWT
    if not user_id:
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if token:
            payload = jwt_auth.verify_token(token)
            if payload:
                user_id = payload.get("user_id")
    # 4. 默认
    if not user_id:
        user_id = session.get('user_id') or str(uuid.uuid4())[:8]
        session['user_id'] = user_id

    return user_id


def audit(action: str, details: dict = None, level: str = "info"):
    """审计日志辅助"""
    if audit_logger:
        user_id = getattr(request, 'user', {}).get("user_id", get_user_id())
        audit_logger.log(action, user_id, details, level)


# ========== 页面路由 ==========

@app.route('/')
def index():
    user_id = get_user_id()
    return render_template('index.html', user_id=user_id)


@app.route('/admin')
def admin_page():
    """管理后台页面"""
    # 简单管理后台认证（查询参数方式，生产中请使用JWT）
    token = request.args.get('token') or \
            request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        payload = jwt_auth.verify_token(token)
        if payload and payload.get("role") == "admin":
            # 生产环境中应重定向到管理后台
            return render_template('admin.html')
    return render_template('admin.html')


# ========== API 文档 ==========

API_DOCS = {
    "swagger": "2.0",
    "info": {
        "title": "反诈卫士 API",
        "description": "多模态智能反诈对话系统 v3.0 API 文档 — 支持语义理解、RAG智能问答、多模态诈骗检测",
        "version": "3.0.0",
        "contact": {"name": "反诈卫士团队"}
    },
    "basePath": "/api",
    "schemes": ["http", "https"],
    "tags": [
        {"name": "对话", "description": "对话咨询与风险分析（v3.0: 语义增强 + RAG双模）"},
        {"name": "情景模拟", "description": "反诈闯关训练（12个关卡）"},
        {"name": "举报", "description": "可疑链接/内容举报"},
        {"name": "知识库", "description": "反诈知识查询（16种诈骗类型）"},
        {"name": "用户", "description": "用户信息与游戏化"},
        {"name": "系统", "description": "系统健康与管理"},
        {"name": "v3.0 多模态分析", "description": "语义深度分析 / 截图识别 / 语音检测（v3.0新增）"},
    ],
    "paths": {
        "/chat": {
            "post": {
                "tags": ["对话"],
                "summary": "发送对话消息（v3.0语义增强）",
                "description": "支持语义NLP引擎增强的智能对话，自动识别诈骗类型并给出劝阻建议",
                "parameters": [{"in": "body", "name": "body", "schema": {
                    "type": "object", "properties": {
                        "message": {"type": "string", "description": "用户输入"},
                        "user_id": {"type": "string", "description": "用户ID（可选）"}
                    }
                }}],
                "responses": {"200": {"description": "返回智能分析结果，含 fraud_type / risk_level / semantic_enhanced"}}
            }
        },
        "/health": {
            "get": {
                "tags": ["系统"],
                "summary": "健康检查（v3.0）",
                "description": "返回系统状态及 v3.0 功能就绪情况（nlp_semantic / rag_engine / multimodal_ocr）",
                "responses": {"200": {"description": "系统状态"}}
            }
        },
        "/analyze/text": {
            "post": {
                "tags": ["v3.0 多模态分析"],
                "summary": "语义深度分析",
                "description": "输入任意文本，语义NLP引擎深度分析诈骗风险，返回意图分类+诈骗类型匹配+风险特征",
                "parameters": [{"in": "body", "name": "body", "schema": {
                    "type": "object", "properties": {
                        "text": {"type": "string", "description": "待分析文本"}
                    }
                }}],
                "responses": {"200": {"description": "语义分析结果（intent / fraud_matches / detections）"}}
            }
        },
        "/analyze/image": {
            "post": {
                "tags": ["v3.0 多模态分析"],
                "summary": "截图诈骗识别",
                "description": "上传可疑聊天截图/APP界面，OCR识别文字后检测诈骗特征（需安装 easyocr）",
                "parameters": [{"in": "formData", "name": "file", "type": "file", "description": "图片文件"}],
                "responses": {"200": {"description": "分析结果（has_fraud_indicators / detections / extracted_text）"}}
            }
        },
        "/analyze/audio": {
            "post": {
                "tags": ["v3.0 多模态分析"],
                "summary": "语音诈骗检测",
                "description": "粘贴可疑通话文字记录，或上传音频文件转文字后检测诈骗话术特征",
                "parameters": [{"in": "body", "name": "body", "schema": {
                    "type": "object", "properties": {
                        "text": {"type": "string", "description": "通话文本（与file二选一）"}
                    }
                }}],
                "responses": {"200": {"description": "诈骗话术分析结果（has_fraud_indicators / detections / risk_level）"}}
            }
        },
        "/scenario/list": {
            "get": {
                "tags": ["情景模拟"],
                "summary": "获取情景模拟列表",
                "description": "返回12个防骗闯关关卡（含7个2025-2026新型诈骗场景）",
                "responses": {"200": {"description": "情景列表"}}
            }
        },
        "/knowledge/types": {
            "get": {
                "tags": ["知识库"],
                "summary": "获取诈骗类型列表",
                "description": "返回16种诈骗类型（含AI换脸、FaceTime、虚拟货币等最新类型）",
                "responses": {"200": {"description": "诈骗类型列表"}}
            }
        },
    }
}


@app.route('/api/docs')
def api_docs():
    return jsonify(API_DOCS)


@app.route('/api/docs/ui')
def api_docs_ui():
    return f'''<!DOCTYPE html>
<html><head><title>反诈卫士 API 文档</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head><body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({{url:"/api/docs",dom_id:"#swagger-ui"}})</script>
</body></html>'''


# ========== 对话 API ==========

@app.route('/api/chat', methods=['POST'])
def chat():
    """对话API（持久化 + 加密 + LLM增强 + 隐私保护）"""
    data = request.json
    user_input = data.get('message', '').strip()
    user_id = get_user_id()

    # 审计日志
    audit("CHAT", {"msg_length": len(user_input)})

    # ========== 隐私保护: 检测并加密PII ==========
    privacy_alerts = []
    privacy_clean_input = user_input
    has_privacy_alert = False

    # 为当前用户创建/获取隐私会话
    if user_id not in privacy_sessions:
        privacy_sessions[user_id] = privacy_guard.create_session(f"user_{user_id}")
    privacy_session_id = privacy_sessions[user_id]

    if user_input and user_input != '__init__':
        pii_result = privacy_guard.detect_and_protect(
            user_input, privacy_session_id, user_id
        )
        if pii_result.has_pii:
            privacy_alerts = pii_result.alert_messages
            # 使用脱敏后的文本进行后续处理
            privacy_clean_input = pii_result.clean_text
            has_privacy_alert = True
            audit("PRIVACY_DETECTED", {
                "types": list(set(d.type for d in pii_result.detections)),
                "count": len(pii_result.detections)
            }, "warning")

    # ========== 初始对话 / 空消息 ==========
    if not user_input or user_input == '__init__':
        response_data = response_gen.generate_response('', user_id, [])
        # 添加隐私保护状态
        response_data["privacy_protected"] = privacy_guard.get_session_pii_count(privacy_session_id)
        return jsonify(response_data)

    # 获取对话历史（优先数据库，使用安全版本）
    if get_db():
        history_raw = get_db().get_conversation_history_safe(user_id, limit=10)
        dialog_history = [h["content"] for h in history_raw if h["role"] == "user"][-10:]
    else:
        if user_id not in conversations_cache:
            conversations_cache[user_id] = []
        conversations_cache[user_id].append({"role": "user", "content": privacy_clean_input})
        if len(conversations_cache[user_id]) > 50:
            conversations_cache[user_id] = conversations_cache[user_id][-50:]
        dialog_history = [msg["content"] for msg in conversations_cache[user_id][-10:]]

    # 生成响应（使用脱敏后的输入）
    # v3.0: 使用增强管道（规则引擎 + 语义NLP + RAG/LLM 双模）
    response_data = response_gen.generate_response_enhanced(
        privacy_clean_input, user_id,
        dialog_history if isinstance(dialog_history, list) else
        [{"role": "user", "content": h} for h in (dialog_history or [])]
    )
    # 标记版本，方便确认是否加载了新代码
    response_data["_engine"] = "v3.0-20260731"

    # LLM 增强
    if llm_client.enabled and response_data.get("recognition_mode") != "rag":
        try:
            risk_result = response_data.get("risk_details", {}) or {}
            response_data = llm_client.enhance_response(
                response_data, privacy_clean_input,
                {"risk_level": response_data.get("risk_level", "none"),
                 "triggered_rules": risk_result.get("triggered_rules", []) if isinstance(risk_result, dict) else []}
            )
        except Exception as e:
            logger.warning(f"LLM 增强失败 (降级到规则引擎): {e}")

    # ========== 持久化到数据库（隐私安全版） ==========
    # 注意：持久化属于"副作用"，失败绝不能影响主流程 —— 尤其是隐私告警，
    # 必须照常返回给用户。因此整段用 try/except 兜底，只记日志、不向上抛。
    if get_db():
        try:
            # 用户消息: 存储脱敏后的版本
            safe_content = privacy_guard.filter_text_for_storage(privacy_clean_input, privacy_session_id)
            msg_id = get_db().save_message_safe(
                user_id, "user", safe_content, "chat",
                response_data.get("risk_level", "none"),
                response_data.get("fraud_type", ""),
                has_privacy_alert=has_privacy_alert,
            )
            # 助手回复: 也做脱敏处理（以防AI回复中带出隐私信息）
            safe_reply = privacy_guard.filter_text_for_storage(
                response_data.get("response", ""), privacy_session_id
            )
            get_db().save_message_safe(
                user_id, "assistant", safe_reply,
                response_data.get("type", "chat"),
                has_privacy_alert=False,
            )

            # 如果有PII检测，加密存储隐私记录
            if has_privacy_alert and pii_result.detections:
                for d in pii_result.detections:
                    get_db().save_privacy_record(
                        user_id=user_id,
                        session_id=privacy_session_id,
                        pii_type=d.type,
                        encrypted_data=d.encrypted,
                        masked_display=d.masked,
                        source_message_id=msg_id or 0,
                    )

            # 记录风险事件
            if response_data.get("risk_level") in ("high", "critical"):
                risk_details = response_data.get("risk_details", {})
                triggered_rules = risk_details.get("triggered_rules", []) if isinstance(risk_details, dict) else []
                get_db().save_risk_event(
                    user_id, response_data["risk_level"],
                    risk_details.get("risk_score", 0) if isinstance(risk_details, dict) else 0,
                    triggered_rules, safe_content
                )
        except Exception as e:
            logger.error(f"对话持久化失败（不影响本次响应）: {e}", exc_info=True)
    else:
        # 内存缓存模式（使用脱敏内容）
        if user_id not in conversations_cache:
            conversations_cache[user_id] = []
        conversations_cache[user_id].append({"role": "assistant", "content": response_data.get("response", "")})

    # ========== 将隐私告警加入响应 ==========
    if privacy_alerts:
        response_data["privacy_alerts"] = privacy_alerts
        response_data["has_privacy_alert"] = True
        # 如果有隐私告警，在回复前添加提醒
        alert_header = "🔒 **隐私保护已启动**\n\n" + "\n\n".join(privacy_alerts) + "\n\n---\n\n"
        response_data["response"] = alert_header + response_data.get("response", "")
        response_data["privacy_protected"] = privacy_guard.get_session_pii_count(privacy_session_id)

    # 游戏化（精简调用）
    from gamification.gamification import GamificationSystem
    gamification = getattr(app, '_gamification', None)
    if not gamification:
        gamification = GamificationSystem(data_dir=os.path.join(BASE_DIR, 'data'))
        app._gamification = gamification

    gamification.record_conversation(user_id)
    if response_data.get("risk_level") in ("high", "critical"):
        gamification.record_risk_identification(user_id)

    # 添加知识图谱关联信息
    if knowledge_graph and response_data.get("fraud_type"):
        related = knowledge_graph.get_related_frauds_deep(response_data["fraud_type"])
        if related:
            response_data["related_frauds"] = [
                {"id": r["fraud_id"], "relation": r["relation"]}
                for r in related[:3]
            ]

    return jsonify(response_data)


# ========== 情景模拟 API（保持不变） ==========

@app.route('/api/scenario/list', methods=['GET'])
def scenario_list():
    user_id = get_user_id()
    scenarios_path = os.path.join(BASE_DIR, 'knowledge_base', 'scenarios.json')
    try:
        with open(scenarios_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return jsonify({"scenarios": []})

    from gamification.gamification import GamificationSystem
    gamification = GamificationSystem(data_dir=os.path.join(BASE_DIR, 'data'))
    user_info = gamification.get_user_info(user_id)
    completed = user_info.get("completed_scenarios", [])
    scores = user_info.get("scenario_scores", {})

    scenarios = []
    for s in data.get("scenarios", []):
        scenarios.append({
            "id": s["id"], "title": s["title"],
            "fraud_type": s["fraud_type"], "difficulty": s["difficulty"],
            "description": s["description"],
            "completed": s["id"] in completed,
            "best_score": scores.get(s["id"], 0)
        })
    return jsonify({"scenarios": scenarios})


@app.route('/api/scenario/start', methods=['POST'])
def scenario_start():
    data = request.json
    result = response_gen.start_scenario(data.get('scenario_id', ''))
    if not result:
        return jsonify({"error": "未找到该情景"}), 404
    return jsonify(result)


@app.route('/api/scenario/step', methods=['POST'])
def scenario_step():
    data = request.json
    scenario_id = data.get('scenario_id', '')
    step_order = data.get('step', 1)
    choice_index = data.get('choice', 0)
    user_id = get_user_id()

    result = response_gen.process_scenario_step(scenario_id, step_order, choice_index)
    if not result:
        return jsonify({"error": "参数错误"}), 400

    if result.get("completed"):
        from gamification.gamification import GamificationSystem
        gamification = GamificationSystem(data_dir=os.path.join(BASE_DIR, 'data'))
        final_score = max(0, data.get('total_score', 0))
        result["total_score"] = final_score
        gamification_result = gamification.record_scenario_complete(user_id, scenario_id, final_score)
        result["gamification"] = gamification_result
        audit("SCENARIO_COMPLETE", {"scenario_id": scenario_id, "score": final_score})

    return jsonify(result)


# ========== 举报 API ==========

@app.route('/api/report/url', methods=['POST'])
def report_url():
    data = request.json
    url = data.get('url', '').strip()
    user_id = get_user_id()

    if not url:
        return jsonify({"error": "请提供链接"}), 400

    audit("REPORT_URL", {"url_length": len(url), "has_url": bool(url)})

    result = url_analyzer.analyze_url(url)
    content = data.get('description', '')
    content_result = url_analyzer.analyze_content(content) if content else None

    url_analyzer.record_report(user_id, url, result, content_result)

    # 持久化举报记录
    if get_db():
        get_db().save_report(user_id, url, result)

    from gamification.gamification import GamificationSystem
    gamification_object = GamificationSystem(data_dir=os.path.join(BASE_DIR, 'data'))
    gamification_object.record_report(user_id)

    report = {
        "url_analysis": result,
        "content_analysis": content_result,
        "advice": result.get("advice", ""),
        "is_suspicious": result.get("is_suspicious", False),
        "risk_level": result.get("risk_level", "none"),
        "domain": result.get("domain", ""),
        "details": result.get("details", []),
        "reference_id": str(uuid.uuid4())[:12].upper()
    }
    return jsonify(report)


@app.route('/api/report/submit', methods=['POST'])
def submit_report():
    user_id = get_user_id()
    from gamification.gamification import GamificationSystem
    gamification_object = GamificationSystem(data_dir=os.path.join(BASE_DIR, 'data'))
    gamification_object.record_report(user_id)
    audit("REPORT_SUBMIT", {})
    return jsonify({
        "status": "success",
        "message": "举报已受理！建议同步拨打96110反诈专线。",
        "reference_id": str(uuid.uuid4())[:12].upper()
    })


@app.route('/api/report/history', methods=['GET'])
def report_history():
    user_id = get_user_id()
    if get_db():
        history = get_db().get_reports(user_id)
        stats = get_db().get_report_stats(user_id)
    else:
        history = url_analyzer.get_report_history(user_id)
        stats = url_analyzer.get_report_stats(user_id)
    return jsonify({"history": history, "stats": stats})


# ========== 知识库 API ==========

@app.route('/api/knowledge/types', methods=['GET'])
def knowledge_types():
    fraud_list = knowledge_retriever.get_fraud_list()
    return jsonify({"fraud_types": fraud_list})


@app.route('/api/knowledge/detail', methods=['GET'])
def knowledge_detail():
    fraud_id = request.args.get('type', '')
    fraud = knowledge_retriever.get_fraud_by_id(fraud_id)
    if not fraud:
        return jsonify({"error": "未找到"}), 404
    return jsonify(fraud)


@app.route('/api/knowledge/search', methods=['POST'])
def knowledge_search():
    data = request.json
    query = data.get('query', '')
    results = knowledge_retriever.search(query)
    indicators = knowledge_retriever.check_fraud_indicators(query)
    qa = knowledge_retriever.get_common_qa(query)
    return jsonify({
        "search_results": results,
        "fraud_indicators": indicators,
        "qa_results": qa
    })


@app.route('/api/knowledge/laws', methods=['GET'])
def knowledge_laws():
    return jsonify({"laws": knowledge_retriever._laws.get("laws", [])})


# ========== 用户/游戏化 API ==========

@app.route('/api/user/profile', methods=['GET'])
def user_profile():
    user_id = get_user_id()
    from gamification.gamification import GamificationSystem
    gamification = getattr(app, '_gamification', None)
    if not gamification:
        gamification = GamificationSystem(data_dir=os.path.join(BASE_DIR, 'data'))
        app._gamification = gamification

    info = gamification.get_user_info(user_id)
    risk_profile = response_gen.risk_analyzer.get_risk_profile(user_id)

    if get_db():
        report_stats = get_db().get_report_stats(user_id)
        info["conversation_count"] = len(get_db().get_conversation_history_safe(user_id, limit=1000))
    else:
        report_stats = url_analyzer.get_report_stats(user_id)
        info["conversation_count"] = len(conversations_cache.get(user_id, []))

    info["risk_profile"] = risk_profile
    info["report_stats"] = report_stats

    return jsonify(info)


@app.route('/api/user/leaderboard', methods=['GET'])
def leaderboard():
    from gamification.gamification import GamificationSystem
    gamification = GamificationSystem(data_dir=os.path.join(BASE_DIR, 'data'))
    user_id = get_user_id()
    top_users = gamification.get_leaderboard(top_n=20)
    user_rank = gamification.get_user_rank(user_id)
    return jsonify({"leaderboard": top_users, "user_rank": user_rank})


@app.route('/api/user/daily-tasks', methods=['GET'])
def daily_tasks():
    user_id = get_user_id()
    from gamification.gamification import GamificationSystem
    gamification = GamificationSystem(data_dir=os.path.join(BASE_DIR, 'data'))
    tasks = gamification.get_daily_tasks(user_id)
    return jsonify({"tasks": tasks})


@app.route('/api/user/complete-task', methods=['POST'])
def complete_task():
    data = request.json
    user_id = get_user_id()
    task_id = data.get('task_id', '')
    from gamification.gamification import GamificationSystem
    gamification = GamificationSystem(data_dir=os.path.join(BASE_DIR, 'data'))
    result = gamification.complete_daily_task(user_id, task_id)
    return jsonify(result or {"error": "任务不存在"})


# ========== 历史 API ==========

@app.route('/api/history', methods=['GET'])
def get_history():
    """获取对话历史（隐私安全版，PII已脱敏）"""
    user_id = get_user_id()
    include_privacy = request.args.get('include_alerts', 'true').lower() == 'true'
    if get_db():
        hist = get_db().get_conversation_history_safe(user_id, limit=30, include_privacy_alerts=include_privacy)
    else:
        hist = conversations_cache.get(user_id, [])[-30:]
    return jsonify({"history": hist})


@app.route('/api/history/memory', methods=['GET'])
def get_memory_history():
    """获取对话记忆（下次打开对话框时调用，加载上次的对话历史，不含隐私信息）"""
    user_id = get_user_id()
    if get_db():
        hist = get_db().get_last_conversation_session(user_id, max_messages=30)
    else:
        hist = conversations_cache.get(user_id, [])[-30:]
    return jsonify({
        "history": hist,
        "has_history": len(hist) > 0,
        "memory_loaded": True,
    })


# ========== 隐私保护 API ==========

@app.route('/api/privacy/status', methods=['GET'])
def privacy_status():
    """获取隐私保护状态"""
    user_id = get_user_id()
    privacy_session_id = privacy_sessions.get(user_id)
    if not privacy_session_id:
        # 自动创建会话
        privacy_session_id = privacy_guard.create_session(f"user_{user_id}")
        privacy_sessions[user_id] = privacy_session_id

    summary = privacy_guard.get_privacy_summary(privacy_session_id)
    if get_db():
        db_stats = get_db().get_privacy_stats(user_id)
        summary["database_protected"] = db_stats["total_protected"]
    else:
        summary["database_protected"] = 0

    summary["session_active"] = True
    return jsonify(summary)


@app.route('/api/privacy/clear-session', methods=['POST'])
def privacy_clear_session():
    """主动清除当前会话的隐私数据（用户关闭对话时调用）"""
    user_id = get_user_id()
    if user_id in privacy_sessions:
        session_id = privacy_sessions[user_id]
        stats = privacy_guard.close_session(session_id)
        if get_db():
            get_db().delete_session_privacy_records(session_id)
        # 创建新会话
        privacy_sessions[user_id] = privacy_guard.create_session(f"user_{user_id}")
        audit("PRIVACY_SESSION_CLEARED", stats, "info")
        return jsonify({
            "status": "cleared",
            "cleared_count": stats["cleared"],
            "types_found": stats.get("types_found", []),
            "message": "🔒 您的隐私数据已安全清除"
        })
    return jsonify({"status": "no_data", "message": "当前没有隐私数据"})


@app.route('/api/privacy/settings', methods=['GET', 'POST'])
def privacy_settings():
    """获取/设置隐私偏好"""
    user_id = get_user_id()
    if request.method == 'POST':
        data = request.json or {}
        # 存储隐私偏好（未来可扩展）
        audit("PRIVACY_SETTINGS", {"user_id": user_id, **data})
        return jsonify({"status": "saved", "message": "隐私设置已保存"})

    return jsonify({
        "auto_detect_pii": True,
        "auto_encrypt": True,
        "alert_on_detection": True,
        "history_memory": True,
        "auto_clear_on_close": True,
    })


@app.route('/api/clear', methods=['POST'])
def clear_history():
    user_id = get_user_id()
    if get_db():
        get_db().clear_conversation(user_id)
    else:
        conversations_cache[user_id] = []

    # 清除隐私会话数据
    if user_id in privacy_sessions:
        session_id = privacy_sessions[user_id]
        stats = privacy_guard.close_session(session_id)
        # 同时清除数据库中的隐私记录
        if get_db():
            get_db().delete_session_privacy_records(session_id)
        del privacy_sessions[user_id]
        audit("PRIVACY_CLEARED", stats, "info")

    response_gen.recognizer.reset_context(user_id)
    audit("CLEAR_HISTORY", {})
    return jsonify({"status": "ok", "privacy_cleared": True})


# ========== 认证 API ==========

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    """获取 JWT Token"""
    data = request.json
    username = data.get('username', '')
    password = data.get('password', '')

    # 简单认证（生产环境应使用数据库验证）
    if username == Config.ADMIN_USERNAME and password:
        # 首次登录设置密码
        if not Config.ADMIN_PASSWORD_HASH:
            import hashlib
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            logger.warning("⚠️ 管理员初始密码已设置，请及时修改")

        import hashlib
        if hashlib.sha256(password.encode()).hexdigest() == Config.ADMIN_PASSWORD_HASH \
                or not Config.ADMIN_PASSWORD_HASH:
            token = jwt_auth.create_token(username, role="admin",
                                          expiry_hours=Config.JWT_EXPIRY_HOURS)
            audit_logger.log_login(username, True, request.remote_addr)
            return jsonify({"token": token, "role": "admin", "expires_in": f"{Config.JWT_EXPIRY_HOURS}h"})

    audit_logger.log_login(username, False, request.remote_addr) if audit_logger else None
    return jsonify({"error": "用户名或密码错误"}), 401


@app.route('/api/auth/verify', methods=['POST'])
def auth_verify():
    """验证 Token 有效性"""
    data = request.json
    token = data.get('token', '')
    payload = jwt_auth.verify_token(token)
    if payload:
        return jsonify({"valid": True, "user_id": payload["user_id"],
                        "role": payload["role"]})
    return jsonify({"valid": False}), 401


# ========== 管理后台 API ==========

@app.route('/api/admin/stats')
def admin_stats():
    """管理后台概览统计数据"""
    from gamification.gamification import GamificationSystem
    gamification = GamificationSystem(data_dir=os.path.join(BASE_DIR, 'data'))

    db_stats = get_db().get_system_stats() if get_db() else {}
    daily_stats = get_db().get_daily_stats(days=7) if get_db() else []
    settings = {k: getattr(Config, k) for k in dir(Config)
                if not k.startswith('_') and k.isupper()}

    return jsonify({
        **db_stats,
        "daily_stats": daily_stats,
        "security_status": {
            "data_encryption": Config.ENCRYPT_DATA,
            "rate_limiting": Config.ENABLE_RATE_LIMIT,
            "cors_configured": Config.CORS_ORIGINS != "*",
            "audit_log_enabled": Config.ENABLE_AUDIT_LOG,
            "https_enforced": Config.HTTPS_ONLY or HAS_TALISMAN,
            "llm_enabled": llm_client.enabled,
        },
        "settings": settings,
        "version": "2.1.0",
        "uptime": time.time() - app._start_time if hasattr(app, '_start_time') else 0,
    })


@app.route('/api/admin/security-checks')
def admin_security_checks():
    """安全检查清单"""
    checks = [
        {"name": "数据加密 (AES-256-GCM)", "pass": Config.ENCRYPT_DATA,
         "status": "已启用" if Config.ENCRYPT_DATA else "未启用"},
        {"name": "速率限制", "pass": Config.ENABLE_RATE_LIMIT and HAS_LIMITER,
         "status": f"已启用 ({Config.RATE_LIMIT_PER_MINUTE}/分钟)" if Config.ENABLE_RATE_LIMIT else "未启用"},
        {"name": "CORS 跨域配置", "pass": Config.CORS_ORIGINS != "*",
         "status": Config.CORS_ORIGINS if Config.CORS_ORIGINS != "*" else "通配符(*) 不安全"},
        {"name": "HTTPS 强制", "pass": Config.HTTPS_ONLY or HAS_TALISMAN,
         "status": "已启用" if Config.HTTPS_ONLY else "未启用"},
        {"name": "审计日志", "pass": Config.ENABLE_AUDIT_LOG,
         "status": "已启用" if Config.ENABLE_AUDIT_LOG else "未启用"},
        {"name": "CSRF 防护", "pass": True,
         "status": "Flask 内置"},
        {"name": "数据脱敏", "pass": True,
         "status": "自动脱敏敏感字段"},
        {"name": "安全响应头", "pass": HAS_TALISMAN,
         "status": "已启用" if HAS_TALISMAN else "未安装 flask-talisman"},
        {"name": "SQL 注入防护", "pass": True,
         "status": "SQLAlchemy ORM 参数化查询"},
        {"name": "XSS 防护", "pass": True,
         "status": "前端 HTML 转义 + 后端过滤"},
        {"name": "密钥管理", "pass": Config.SECRET_KEY != os.urandom(32).hex(),
         "status": "已在 .env 中配置" if Config.SECRET_KEY else "警告: 使用随机密钥，重启会失效",
         "warn": not Config.SECRET_KEY},
        {"name": "依赖安全", "pass": True,
         "status": f"已安装 {len(open('requirements.txt').readlines())} 个依赖"},
        {"name": "数据保留策略", "pass": Config.DATA_RETENTION_DAYS > 0,
         "status": f"{Config.DATA_RETENTION_DAYS} 天自动清理"},
    ]
    return jsonify(checks)


@app.route('/api/admin/cloud-config')
def admin_cloud_config():
    """混合云部署配置"""
    configs = [
        {"name": "部署模式", "value": "单机" if Config.CLOUD_DEPLOYMENT == "single" else "混合云",
         "icon": "☁️"},
        {"name": "跨区域传输加密", "value": "AES-256-GCM" if Config.DATA_CROSS_REGION_ENCRYPT else "未加密",
         "icon": "🔐"},
        {"name": "TLS 证书", "value": "已配置" if Config.TLS_CERT_PATH else "未配置（可使用自签名证书）",
         "icon": "🔒"},
        {"name": "数据存储加密", "value": "AES-256-GCM" if Config.ENCRYPT_DATA else "明文存储",
         "icon": "💾"},
        {"name": "数据库", "value": Config.DATABASE_URL.replace("sqlite:///", "SQLite: "),
         "icon": "🗄️"},
        {"name": "日志位置", "value": Config.LOG_FILE,
         "icon": "📝"},
        {"name": "LLM 集成", "value": f"{Config.LLM_PROVIDER} ({Config.LLM_MODEL})" if llm_client.enabled else "未启用",
         "icon": "🤖"},
    ]
    return jsonify(configs)


@app.route('/api/admin/users')
def admin_users():
    """用户列表"""
    from gamification.gamification import GamificationSystem
    gamification = GamificationSystem(data_dir=os.path.join(BASE_DIR, 'data'))
    leaderboard = gamification.get_leaderboard(top_n=50)

    # 扩展用户信息（如果数据库可用）
    if get_db():
        for u in leaderboard:
            conv_count = len(get_db().get_conversation_history(u["user_id"]))
            u["conversations"] = conv_count

    return jsonify({"leaderboard": leaderboard})


@app.route('/api/admin/knowledge')
def admin_knowledge():
    """知识库管理信息"""
    fraud_list = knowledge_retriever.get_fraud_list()
    from engine.knowledge_retriever import KnowledgeRetriever
    graph_stats = knowledge_graph.get_graph_stats() if knowledge_graph else {"built": False}

    return jsonify({
        "fraud_types": fraud_list,
        "total_laws": len(knowledge_retriever._laws.get("laws", [])),
        "graph_stats": graph_stats,
    })


@app.route('/api/admin/settings')
def admin_settings():
    """系统配置（脱敏后）"""
    sensitive_keys = {"SECRET_KEY", "JWT_SECRET", "ENCRYPTION_KEY",
                      "LLM_API_KEY", "ADMIN_PASSWORD_HASH"}
    settings = {}
    for k in dir(Config):
        if not k.startswith('_') and k.isupper():
            v = getattr(Config, k)
            if k in sensitive_keys and v:
                settings[k] = v[:8] + "****" if len(v) > 8 else "****"
            else:
                settings[k] = v
    return jsonify(settings)


# ========== 外部大模型接入（运行时热配置）==========
# 默认不接入任何外部 API；用户在此自行决定是否接入，保存后立即生效，无需重启。

@app.route('/api/admin/llm/config')
@admin_required
def admin_llm_config():
    """当前外部大模型接入配置（API Key 仅回显掩码）"""
    view = get_llm_config_store().public_view()
    view["active"] = llm_client.enabled
    view["safe_mode"] = Config.SAFE_MODE
    view["providers"] = [
        {"key": k, "url": v.get("url", ""), "model": v.get("model", "")}
        for k, v in LLMClient.PROVIDER_CONFIGS.items()
    ]
    return jsonify(view)


@app.route('/api/admin/llm/config', methods=['POST'])
@admin_required
def admin_llm_config_save():
    """
    保存并启用外部大模型接入（热生效）。

    请求体: {provider, api_url, model, api_key}
    api_key 留空 = 沿用已保存的 Key（前端回显的是掩码，不重填就不该抹掉）。
    """
    data = request.get_json(silent=True) or {}
    provider = (data.get('provider') or 'custom').strip()
    api_url = (data.get('api_url') or '').strip()
    model = (data.get('model') or '').strip()
    api_key = (data.get('api_key') or '').strip()

    if Config.SAFE_MODE:
        return jsonify({"error": "SAFE_MODE 已开启，请先在 .env 中关闭后再接入外部 API"}), 400
    if not api_url:
        return jsonify({"error": "请填写 API 地址"}), 400
    if not model:
        return jsonify({"error": "请填写模型名称"}), 400

    store = get_llm_config_store()
    if not api_key and not store.load().get("api_key"):
        return jsonify({"error": "请填写 API Key"}), 400

    try:
        store.save(provider=provider, api_url=api_url, model=model, api_key=api_key)
    except Exception as e:
        logger.error(f"[LLM] 配置保存失败: {e}")
        return jsonify({"error": f"保存失败: {e}"}), 500

    state = apply_llm_config()
    audit("llm_config_save", {"provider": provider, "model": model}, "warn")
    view = store.public_view()
    view.update(state)
    return jsonify({"ok": True, **view})


@app.route('/api/admin/llm/test', methods=['POST'])
@admin_required
def admin_llm_test():
    """
    连通性测试。

    优先用请求体里的**未保存**配置探测，让用户能先验证填得对不对再保存。
    """
    data = request.get_json(silent=True) or {}
    saved = get_llm_config_store().load()

    probe = LLMClient(
        provider=(data.get('provider') or saved.get('provider') or 'deepseek'),
        api_key=(data.get('api_key') or '').strip() or saved.get('api_key', ''),
        api_url=(data.get('api_url') or '').strip() or saved.get('api_url', ''),
        model=(data.get('model') or '').strip() or saved.get('model', ''),
    )
    result = probe.test_connection()
    audit("llm_config_test", {"ok": result.get("ok")}, "info")
    return jsonify(result), (200 if result.get("ok") else 400)


@app.route('/api/admin/llm/disable', methods=['POST'])
@admin_required
def admin_llm_disable():
    """关闭外部 API，回到纯本地模式（已填字段保留，便于再次启用）"""
    get_llm_config_store().disable()
    state = apply_llm_config()
    audit("llm_config_disable", {}, "warn")
    return jsonify({"ok": True, **state})


@app.route('/api/admin/export/<user_id>')
def admin_export_user(user_id):
    """导出用户数据（管理员）"""
    if get_db():
        data = get_db().export_user_data(user_id)
        return jsonify(data or {"error": "未找到"})
    return jsonify({"error": "数据库未启用"}), 400


@app.route('/api/admin/delete-user', methods=['POST'])
def admin_delete_user():
    """删除用户数据（GDPR 被遗忘权）"""
    data = request.json
    user_id = data.get('user_id', '')
    if not user_id:
        return jsonify({"error": "请提供 user_id"}), 400
    if get_db():
        get_db().delete_user_data(user_id)
        # 同时删除游戏化数据
        from gamification.gamification import GamificationSystem
        gamification = GamificationSystem(data_dir=os.path.join(BASE_DIR, 'data'))
        user_path = os.path.join(BASE_DIR, 'data', f"user_{user_id}.json")
        if os.path.exists(user_path):
            os.remove(user_path)
        audit("DELETE_USER", {"user_id": user_id}, "warning")
        return jsonify({"status": "success", "message": f"用户 {user_id} 数据已删除"})
    return jsonify({"error": "数据库未启用"}), 400


# ========== 知识图谱 API ==========

@app.route('/api/knowledge-graph/data')
def knowledge_graph_data():
    """获取知识图谱可视化数据"""
    if not knowledge_graph:
        return jsonify({"error": "知识图谱未启用"}), 400
    return jsonify(knowledge_graph.to_vis_json())


@app.route('/api/knowledge-graph/stats')
def knowledge_graph_stats():
    """获取知识图谱统计"""
    if not knowledge_graph:
        return jsonify({"built": False})
    return jsonify(knowledge_graph.get_graph_stats())


@app.route('/api/knowledge-graph/related/<fraud_id>')
def knowledge_graph_related(fraud_id):
    """获取某骗局的深度关联"""
    if not knowledge_graph:
        return jsonify({"related": []})
    related = knowledge_graph.get_related_frauds_deep(fraud_id)
    channels = knowledge_graph.get_hot_channels(top_n=3)
    return jsonify({"related": related, "hot_channels": channels})


# ========== 混合云同步 API ==========

@app.route('/api/sync/export', methods=['POST'])
def sync_export():
    """跨区域数据导出（加密传输）"""
    if Config.CLOUD_DEPLOYMENT != "hybrid":
        return jsonify({"error": "非混合云模式"}), 400

    data = request.json
    user_id = data.get('user_id', '')

    if get_db():
        user_data = get_db().export_user_data(user_id)
        if user_data:
            from engine.security import CrossRegionEncryptor
            encryptor_cr = CrossRegionEncryptor()
            encrypted = encryptor_cr.encrypt_transport(
                json.dumps(user_data, ensure_ascii=False).encode()
            )
            return jsonify({
                "status": "encrypted",
                "payload": encrypted,
                "timestamp": datetime.utcnow().isoformat()
            })
    return jsonify({"error": "未找到数据"}), 404


@app.route('/api/sync/import', methods=['POST'])
def sync_import():
    """跨区域数据导入（解密接收）"""
    if Config.CLOUD_DEPLOYMENT != "hybrid":
        return jsonify({"error": "非混合云模式"}), 400

    data = request.json
    try:
        from engine.security import CrossRegionEncryptor
        encryptor_cr = CrossRegionEncryptor()
        decrypted = encryptor_cr.decrypt_transport(data.get("payload", {}))
        import_data = json.loads(decrypted.decode())
        return jsonify({"status": "imported", "records": len(import_data.get("conversations", []))})
    except Exception as e:
        logger.error(f"跨区域数据导入失败: {e}")
        return jsonify({"error": "数据导入失败"}), 400


# ========== 安全 API ==========

@app.route('/api/security/encrypt', methods=['POST'])
@require_auth(optional=True)
def security_encrypt():
    """手动加密数据（测试用）"""
    data = request.json
    if not data:
        return jsonify({"error": "请提供待加密数据"}), 400
    encrypted = encryptor.encrypt_json(data)
    return jsonify({"encrypted": encrypted, "algorithm": "AES-256-GCM"})


@app.route('/api/security/decrypt', methods=['POST'])
@require_auth(optional=True)
def security_decrypt():
    """手动解密数据（测试用）"""
    data = request.json
    encrypted_str = data.get('encrypted', '')
    if not encrypted_str:
        return jsonify({"error": "请提供加密数据"}), 400
    try:
        decrypted = encryptor.decrypt_json(encrypted_str)
        return jsonify({"decrypted": decrypted})
    except Exception as e:
        return jsonify({"error": f"解密失败: {e}"}), 400


# ========== 系统 API ==========

@app.route('/api/health', methods=['GET'])
def health():
    """增强健康检查"""
    fraud_count = len(knowledge_retriever.get_fraud_list())

    checks = {
        "status": "ok",
        "version": "3.0.0",
        "fraud_types": fraud_count,
        "features": {
            "database": HAS_DB and get_db() is not None,
            "rate_limiting": HAS_LIMITER,
            "talisman": HAS_TALISMAN,
            "llm": llm_client.enabled,
            "knowledge_graph": HAS_KG and knowledge_graph is not None,
            "encryption": True,
            "nlp_semantic": False,  # 运行时动态检测
            "rag_engine": False,
            "multimodal_ocr": False,
        },
        # 外部大模型接入状态：local = 纯本地零联网；enhanced = 已接入外部 API
        "llm": {
            "mode": "enhanced" if llm_client.enabled else "local",
            "provider": llm_client.provider if llm_client.enabled else None,
            "model": llm_client.model if llm_client.enabled else None,
            "safe_mode": Config.SAFE_MODE,
        },
    }

    # v3.0 功能检测
    try:
        from engine.nlp_pipeline import get_nlp_pipeline
        checks["features"]["nlp_semantic"] = get_nlp_pipeline().ready
    except Exception:
        pass
    try:
        from engine.rag_engine import get_rag_engine
        checks["features"]["rag_engine"] = get_rag_engine().is_available
    except Exception:
        pass
    try:
        from engine.multimodal_detector import get_image_detector
        checks["features"]["multimodal_ocr"] = get_image_detector().load()
    except Exception:
        pass

    if get_db():
        checks["users_active"] = get_db().get_system_stats().get("total_users", 0)
    else:
        checks["users_active"] = len(conversations_cache)

    # 检查关键组件
    if get_db():
        try:
            get_db().get_system_stats()
        except Exception as e:
            checks["status"] = "degraded"
            checks["issues"] = [f"数据库: {e}"]

    return jsonify(checks)


# ========== v3.0 多模态分析 API ==========

@app.route('/api/analyze/image', methods=['POST'])
def analyze_image():
    """v3.0 诈骗截图分析 — 上传图片，OCR 识别 + 诈骗特征检测"""
    from engine.multimodal_detector import get_image_detector

    if 'file' not in request.files:
        return jsonify({"error": "请上传图片文件 (字段名: file)"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "未选择文件"}), 400

    # 保存临时文件
    import tempfile
    suffix = os.path.splitext(file.filename)[1] or '.png'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        detector = get_image_detector()
        result = detector.analyze(tmp_path)
        audit("IMAGE_ANALYSIS", {"risk_level": result.get("risk_level")})
        return jsonify(result)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@app.route('/api/analyze/audio', methods=['POST'])
def analyze_audio():
    """v3.0 语音诈骗分析 — 上传音频文件，转文字 + 特征检测"""
    from engine.multimodal_detector import get_audio_detector

    if 'file' not in request.files:
        # 也支持直接传文本
        data = request.get_json(silent=True)
        if data and data.get('text'):
            detector = get_audio_detector()
            result = detector.analyze_text_for_fraud_calls(data['text'])
            audit("AUDIO_TEXT_ANALYSIS", {"risk_level": result.get("risk_level")})
            return jsonify(result)
        return jsonify({"error": "请上传音频文件 (字段名: file) 或提供文本 (字段名: text)"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "未选择文件"}), 400

    import tempfile
    suffix = os.path.splitext(file.filename)[1] or '.wav'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        detector = get_audio_detector()
        result = detector.analyze_audio_file(tmp_path)
        audit("AUDIO_ANALYSIS", {"risk_level": result.get("risk_level")})
        return jsonify(result)
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


@app.route('/api/analyze/text', methods=['POST'])
def analyze_text_multimodal():
    """v3.0 文本多维度诈骗分析（结合语义NLP）"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "请提供 JSON 数据"}), 400

    text = data.get('text', '').strip()
    if not text:
        return jsonify({"error": "请提供待分析文本"}), 400

    # 语音诈骗文本分析
    from engine.multimodal_detector import get_audio_detector
    audio_detector = get_audio_detector()
    audio_result = audio_detector.analyze_text_for_fraud_calls(text)

    # 语义 NLP 增强
    try:
        from engine.nlp_pipeline import get_nlp_pipeline
        nlp = get_nlp_pipeline()
        fraud_matches = nlp.match_fraud_type(text) if nlp.ready else []
        semantic_intent = nlp.classify_intent(text) if nlp.ready else ("unknown", 0)
    except Exception:
        fraud_matches = []
        semantic_intent = ("unknown", 0)

    return jsonify({
        "text": text[:200],
        "audio_style_analysis": audio_result,
        "semantic_analysis": {
            "intent": semantic_intent[0] if isinstance(semantic_intent, tuple) else semantic_intent,
            "confidence": semantic_intent[1] if isinstance(semantic_intent, tuple) else 0,
            "fraud_matches": [
                {"type": ftype, "confidence": round(score, 3)}
                for ftype, score in (fraud_matches or [])[:3]
            ] if fraud_matches else [],
        },
    })


# ========== 错误处理 ==========

@app.errorhandler(404)
def not_found(e):
    return jsonify({"error": "Not Found", "status": 404}), 404


@app.errorhandler(415)
def unsupported_media(e):
    """捕获 415 错误并返回 JSON，记录详细信息"""
    logger.warning(f"415 错误: {e} | 路径: {request.path} | 方法: {request.method} | Content-Type: {request.content_type}")
    if request.method == 'GET':
        # GET 请求的 415 通常是 request.json 在非 JSON 请求中误触
        logger.warning(f"GET 请求收到 415，请检查视图函数是否误调了 request.json")
    return jsonify({"error": "不支持的媒体类型", "message": str(e)}), 415


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({"error": "请求过于频繁，请稍后再试",
                    "retry_after": e.description}), 429


@app.errorhandler(500)
def server_error(e):
    logger.error(f"服务器内部错误: {e}")
    audit("SERVER_ERROR", {"error": str(e)}, "error")
    return jsonify({"error": "服务器内部错误，请稍后重试"}), 500


# ========== 启动 ==========

if __name__ == '__main__':
    # Windows GBK 终端 UTF-8 兼容
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

    app._start_time = time.time()

    # 启动前检查
    print("=" * 60)
    print("  [Anti-Fraud] 多模态智能反诈对话系统 v3.0")
    print("  Anti-Fraud Intelligent Dialogue System")
    print("=" * 60)
    print(f"  [LOCK] 数据加密: {'AES-256-GCM' if Config.ENCRYPT_DATA else '未加密'}")
    print(f"  [DB]   数据库: {'SQLite' if HAS_DB else '内存'}")
    print(f"  [CLOCK] 速率限制: {'已启用' if HAS_LIMITER and Config.ENABLE_RATE_LIMIT else '未启用'}")
    print(f"  [GRAPH] 知识图谱: {'已构建' if HAS_KG else '未安装 networkx'}")
    print(f"  [BOT]   LLM集成: {'已启用' if llm_client.enabled else '未启用（使用规则引擎）'}")
    print(f"  [LOG]  审计日志: {'已启用' if Config.ENABLE_AUDIT_LOG else '未启用'}")

    # v3.0 新功能状态
    try:
        from engine.nlp_pipeline import get_nlp_pipeline
        nlp_ok = get_nlp_pipeline().ready
        print(f"  [NLP]  语义引擎: {'已就绪 (sentence-transformers)' if nlp_ok else '未加载'}")
    except Exception:
        print(f"  [NLP]  语义引擎: 未加载")
    try:
        from engine.rag_engine import get_rag_engine
        rag_ok = get_rag_engine().is_available
        print(f"  [RAG]  检索增强: {'已就绪' if rag_ok else '未启用（需配置LLM_API_KEY）'}")
    except Exception:
        print(f"  [RAG]  检索增强: 未加载")
    try:
        from engine.multimodal_detector import get_image_detector
        ocr_ok = get_image_detector().load()
        print(f"  [OCR]  图像分析: {'已就绪' if ocr_ok else '未安装依赖 (pip install easyocr)'}")
    except Exception:
        print(f"  [OCR]  图像分析: 未加载")

    print(f"  [DOCS]  API文档: http://localhost:{Config.PORT}/api/docs/ui")
    print(f"  [ADMIN] 管理后台: http://localhost:{Config.PORT}/admin")
    print(f"  [DETECT] 反诈类型: {len(knowledge_retriever.get_fraud_list())} 种")
    print(f"  [LAW]  法律法规: {len(knowledge_retriever._laws.get('laws', []))} 条")
    print("=" * 60)

    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG, threaded=True)
