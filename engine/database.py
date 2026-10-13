"""
数据持久化层 - SQLite + SQLAlchemy
支持对话历史持久化、用户数据管理、数据保留策略
增强特性:
  - 隐私过滤存储（PII自动脱敏后再存）
  - 对话历史记忆（下次打开显示上次对话）
  - 隐私记录独立存储（会话关闭后自动清除）
  - 加密存储敏感字段
"""
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from contextlib import contextmanager

from sqlalchemy import create_engine, Column, String, Text, Integer, Float, DateTime, JSON, Boolean
from sqlalchemy.orm import sessionmaker, declarative_base

logger = logging.getLogger(__name__)

Base = declarative_base()


# ========== ORM 模型 ==========

class Conversation(Base):
    """对话记录持久化（已脱敏，安全存储）"""
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), index=True, nullable=False)
    role = Column(String(16), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)       # 已过滤PII的安全内容
    msg_type = Column(String(32), default="chat")
    risk_level = Column(String(16), default="none")
    fraud_type = Column(String(32), default="")
    has_privacy_alert = Column(Integer, default=0)   # 该条是否触发过隐私告警
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "role": self.role,
            "content": self.content,
            "msg_type": self.msg_type,
            "risk_level": self.risk_level,
            "fraud_type": self.fraud_type,
            "has_privacy_alert": bool(self.has_privacy_alert),
            "created_at": self.created_at.isoformat() if self.created_at else ""
        }


class PrivacyRecord(Base):
    """隐私数据记录（加密存储，按会话生命周期自动清除）"""
    __tablename__ = "privacy_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), index=True, nullable=False)
    session_id = Column(String(64), index=True, nullable=False, default="")
    pii_type = Column(String(32), nullable=False)   # phone / id_card / bank_card / etc.
    encrypted_data = Column(Text, nullable=False)    # 加密后的PII数据
    masked_display = Column(String(128), default="") # 掩码显示版本（如 138****1234）
    source_message_id = Column(Integer, default=0)   # 关联的对话ID
    created_at = Column(DateTime, default=datetime.utcnow)
    auto_delete_at = Column(DateTime, nullable=True) # 自动删除时间（会话关闭后）


class ReportRecord(Base):
    """举报记录持久化"""
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), index=True, nullable=False)
    url = Column(Text, nullable=False)
    domain = Column(String(256), default="")
    risk_level = Column(String(16), default="none")
    is_suspicious = Column(Integer, default=0)
    details = Column(Text, default="")
    advice = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "url": self.url,
            "domain": self.domain,
            "risk_level": self.risk_level,
            "is_suspicious": bool(self.is_suspicious),
            "created_at": self.created_at.isoformat() if self.created_at else ""
        }


class RiskEvent(Base):
    """风险事件持久化"""
    __tablename__ = "risk_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(64), index=True, nullable=False)
    risk_level = Column(String(16), nullable=False)
    risk_score = Column(Float, default=0.0)
    triggered_rules = Column(Text, default="[]")  # JSON list
    user_input = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class UserProfile(Base):
    """用户画像持久化"""
    __tablename__ = "user_profiles"

    user_id = Column(String(64), primary_key=True)
    points = Column(Integer, default=0)
    level = Column(Integer, default=1)
    badges = Column(Text, default="[]")  # JSON list
    total_conversations = Column(Integer, default=0)
    risk_identifications = Column(Integer, default=0)
    reports_submitted = Column(Integer, default=0)
    login_streak = Column(Integer, default=0)
    last_active = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


# ========== 数据库管理器 ==========

class DatabaseManager:
    """数据库管理器，封装 SQLAlchemy 会话管理"""

    def __init__(self, db_url: str = "sqlite:///data/antifraud.db"):
        self.engine = create_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        self._create_tables()

    def _create_tables(self):
        """创建所有表"""
        Base.metadata.create_all(self.engine)
        logger.info("✅ 数据库表已创建")

    @contextmanager
    def session(self):
        """获取数据库会话（上下文管理器）"""
        s = self.SessionLocal()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    # ---------- 对话（隐私安全版） ----------

    def save_message_safe(self, user_id: str, role: str, content: str,
                          msg_type: str = "chat", risk_level: str = "none",
                          fraud_type: str = "", has_privacy_alert: bool = False) -> int:
        """保存一条对话消息（已脱敏，安全存储）

        返回新消息的自增 ID（int）。

        注意：本方法**不能**返回 ORM 对象。内部的 self.session() 在返回前
        会 commit + close，而 SQLAlchemy 默认 expire_on_commit=True，对象属性
        会被标记过期；会话已关闭时再访问属性会抛 DetachedInstanceError。
        因此在会话关闭前就把标量 ID 取出并返回。
        """
        with self.session() as s:
            msg = Conversation(
                user_id=user_id,
                role=role,
                content=content,
                msg_type=msg_type,
                risk_level=risk_level,
                fraud_type=fraud_type,
                has_privacy_alert=1 if has_privacy_alert else 0,
            )
            s.add(msg)
            s.flush()  # 获取ID
            msg_id = msg.id  # 在会话关闭前取出标量，避免 detached 访问
            return msg_id

    def get_conversation_history_safe(self, user_id: str, limit: int = 50,
                                       include_privacy_alerts: bool = True) -> List[dict]:
        """获取用户对话历史（安全版本，仅返回无PII的内容）"""
        with self.session() as s:
            query = (s.query(Conversation)
                     .filter(Conversation.user_id == user_id))
            if not include_privacy_alerts:
                query = query.filter(Conversation.has_privacy_alert == 0)
            msgs = (query
                    .order_by(Conversation.id.desc())
                    .limit(limit)
                    .all())
            return list(reversed([m.to_dict() for m in msgs]))

    def get_last_conversation_session(self, user_id: str, max_messages: int = 30) -> List[dict]:
        """获取最近一次对话会话的历史（用于记忆恢复）
        返回最近一段时间内的对话记录，按时间正序"""
        with self.session() as s:
            msgs = (s.query(Conversation)
                    .filter(Conversation.user_id == user_id)
                    .order_by(Conversation.id.desc())
                    .limit(max_messages)
                    .all())
            return list(reversed([m.to_dict() for m in msgs]))

    # ---------- 隐私记录 ----------

    def save_privacy_record(self, user_id: str, session_id: str,
                            pii_type: str, encrypted_data: str,
                            masked_display: str = "",
                            source_message_id: int = 0) -> int:
        """保存隐私记录（加密后存储，会话关闭后自动清除）

        返回新记录的自增 ID（int）。与 save_message_safe 同理：本方法的会话
        在返回前已 commit + close，不能返回 ORM 对象，否则调用方访问其属性
        会抛 DetachedInstanceError。
        """
        with self.session() as s:
            # 设置自动清除时间：默认7天后（以防会话非正常关闭）
            auto_delete = datetime.utcnow() + timedelta(days=7)
            record = PrivacyRecord(
                user_id=user_id,
                session_id=session_id,
                pii_type=pii_type,
                encrypted_data=encrypted_data,
                masked_display=masked_display,
                source_message_id=source_message_id,
                auto_delete_at=auto_delete,
            )
            s.add(record)
            s.flush()  # 获取ID
            record_id = record.id  # 在会话关闭前取出标量，避免 detached 访问
            return record_id

    def delete_session_privacy_records(self, session_id: str) -> int:
        """删除指定会话的所有隐私记录（会话关闭时调用）"""
        with self.session() as s:
            deleted = (s.query(PrivacyRecord)
                       .filter(PrivacyRecord.session_id == session_id)
                       .delete())
            if deleted:
                logger.info(f"🧹 已清除会话 {session_id[:16]}... 的 {deleted} 条隐私记录")
            return deleted

    def cleanup_expired_privacy_records(self) -> int:
        """清理过期的隐私记录（定时任务）"""
        with self.session() as s:
            deleted = (s.query(PrivacyRecord)
                       .filter(PrivacyRecord.auto_delete_at < datetime.utcnow())
                       .delete())
            if deleted:
                logger.info(f"🧹 已清理 {deleted} 条过期隐私记录")
            return deleted

    def get_privacy_stats(self, user_id: str = "") -> dict:
        """获取隐私保护统计"""
        with self.session() as s:
            query = s.query(PrivacyRecord)
            if user_id:
                query = query.filter(PrivacyRecord.user_id == user_id)
            total = query.count()
            # 按类型统计（复用同一个已过滤的 query，避免统计到其他用户的数据）
            type_stats = {}
            for r in query.all():
                type_stats[r.pii_type] = type_stats.get(r.pii_type, 0) + 1
            return {
                "total_protected": total,
                "by_type": type_stats,
                "user_id": user_id or "all"
            }

    def clear_conversation(self, user_id: str):
        """清空用户对话"""
        with self.session() as s:
            s.query(Conversation).filter(Conversation.user_id == user_id).delete()

    # ---------- 举报 ----------

    def save_report(self, user_id: str, url: str, result: dict) -> int:
        """保存举报记录

        返回新记录的自增 ID（int）。理由同 save_message_safe：会话在返回前
        已 commit + close，返回 ORM 对象会导致调用方 detached 访问报错。
        """
        with self.session() as s:
            report = ReportRecord(
                user_id=user_id,
                url=url,
                domain=result.get("domain", ""),
                risk_level=result.get("risk_level", "none"),
                is_suspicious=1 if result.get("is_suspicious") else 0,
                details=json.dumps(result.get("details", []), ensure_ascii=False),
                advice=result.get("advice", "")
            )
            s.add(report)
            s.flush()  # 获取ID
            report_id = report.id  # 在会话关闭前取出标量，避免 detached 访问
            return report_id

    def get_reports(self, user_id: str, limit: int = 20) -> List[dict]:
        with self.session() as s:
            reports = (s.query(ReportRecord)
                       .filter(ReportRecord.user_id == user_id)
                       .order_by(ReportRecord.id.desc())
                       .limit(limit)
                       .all())
            return [r.to_dict() for r in reports]

    def get_report_stats(self, user_id: str) -> dict:
        with self.session() as s:
            total = s.query(ReportRecord).filter(ReportRecord.user_id == user_id).count()
            suspicious = (s.query(ReportRecord)
                          .filter(ReportRecord.user_id == user_id,
                                  ReportRecord.is_suspicious == 1)
                          .count())
            return {"total": total, "suspicious": suspicious, "safe": total - suspicious}

    # ---------- 风险事件 ----------

    def save_risk_event(self, user_id: str, risk_level: str, risk_score: float,
                        triggered_rules: list, user_input: str = ""):
        with self.session() as s:
            event = RiskEvent(
                user_id=user_id,
                risk_level=risk_level,
                risk_score=risk_score,
                triggered_rules=json.dumps(triggered_rules, ensure_ascii=False),
                user_input=user_input
            )
            s.add(event)

    # ---------- 数据保留策略 ----------

    def enforce_retention_policy(self, days: int = 90):
        """执行数据保留策略，删除超过指定天数的数据"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        with self.session() as s:
            deleted_msgs = s.query(Conversation).filter(
                Conversation.created_at < cutoff
            ).delete()
            deleted_reports = s.query(ReportRecord).filter(
                ReportRecord.created_at < cutoff
            ).delete()
            deleted_risks = s.query(RiskEvent).filter(
                RiskEvent.created_at < cutoff
            ).delete()
            logger.info(f"🧹 数据保留策略执行: 删除了 {deleted_msgs} 条对话, "
                        f"{deleted_reports} 条举报, {deleted_risks} 条风险事件")

    # ---------- 统计数据 ----------

    def get_system_stats(self) -> dict:
        """获取系统统计数据"""
        with self.session() as s:
            return {
                "total_conversations": s.query(Conversation).count(),
                "total_users": (s.query(Conversation.user_id)
                                .distinct().count()),
                "total_reports": s.query(ReportRecord).count(),
                "total_risk_events": s.query(RiskEvent).count(),
                "suspicious_reports": s.query(ReportRecord).filter(
                    ReportRecord.is_suspicious == 1).count(),
                "high_risk_events": s.query(RiskEvent).filter(
                    RiskEvent.risk_level.in_(["high", "critical"])).count(),
            }

    def get_daily_stats(self, days: int = 7) -> List[dict]:
        """获取每日统计数据"""
        stats = []
        for i in range(days - 1, -1, -1):
            day = datetime.utcnow() - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            with self.session() as s:
                conv_count = s.query(Conversation).filter(
                    Conversation.created_at >= day_start,
                    Conversation.created_at < day_end
                ).count()
                risk_count = s.query(RiskEvent).filter(
                    RiskEvent.created_at >= day_start,
                    RiskEvent.created_at < day_end
                ).count()
            stats.append({
                "date": day_start.strftime("%Y-%m-%d"),
                "conversations": conv_count,
                "risk_events": risk_count
            })
        return stats

    def export_user_data(self, user_id: str) -> Optional[dict]:
        """导出用户所有数据（GDPR 数据可携带性）"""
        conversations = self.get_conversation_history(user_id, limit=1000)
        reports = self.get_reports(user_id)
        return {
            "export_time": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "conversations": conversations,
            "reports": reports,
            "total_conversations": len(conversations),
            "total_reports": len(reports)
        }

    def delete_user_data(self, user_id: str) -> bool:
        """删除用户所有数据（GDPR 被遗忘权 + 隐私记录）"""
        try:
            self.clear_conversation(user_id)
            with self.session() as s:
                s.query(ReportRecord).filter(ReportRecord.user_id == user_id).delete()
                s.query(RiskEvent).filter(RiskEvent.user_id == user_id).delete()
                s.query(PrivacyRecord).filter(PrivacyRecord.user_id == user_id).delete()
                s.query(UserProfile).filter(UserProfile.user_id == user_id).delete()
            return True
        except Exception as e:
            logger.error(f"删除用户数据失败 {user_id}: {e}")
            return False
