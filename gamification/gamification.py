"""增强游戏化系统 - 积分、等级、勋章、每日任务、排行榜、连续签到"""
import json
import os
import time
import math
import hashlib
import base64
from typing import Optional


class GamificationSystem:
    """游戏化系统 - 积分、等级、勋章、每日任务、排行榜"""

    # 勋章定义（增强版）
    BADGES = {
        "first_chat": {
            "name": "初识反诈", "description": "首次使用反诈助手",
            "icon": "🌟", "points": 10, "category": "基础"
        },
        "chat_10": {
            "name": "勤学好问", "description": "完成10次对话咨询",
            "icon": "💬", "points": 30, "category": "活跃"
        },
        "chat_50": {
            "name": "反诈达人", "description": "完成50次对话咨询",
            "icon": "🗣️", "points": 80, "category": "活跃"
        },
        "knowledge_master": {
            "name": "知识达人", "description": "学习完所有诈骗类型的知识",
            "icon": "📚", "points": 50, "category": "学习"
        },
        "scenario_beginner": {
            "name": "闯关新手", "description": "完成第一个情景模拟",
            "icon": "🎮", "points": 30, "category": "闯关"
        },
        "scenario_intermediate": {
            "name": "闯关能手", "description": "完成3个情景模拟",
            "icon": "🏆", "points": 100, "category": "闯关"
        },
        "scenario_all": {
            "name": "反诈卫士", "description": "完成所有情景模拟",
            "icon": "🛡️", "points": 200, "category": "闯关"
        },
        "report_first": {
            "name": "正义举报", "description": "首次提交举报",
            "icon": "📢", "points": 20, "category": "举报"
        },
        "report_5": {
            "name": "举报先锋", "description": "累计举报5次",
            "icon": "🔔", "points": 60, "category": "举报"
        },
        "perfect_score": {
            "name": "完美通关", "description": "在情景模拟中获得高分",
            "icon": "💯", "points": 80, "category": "闯关"
        },
        "risk_spotter": {
            "name": "风险猎手", "description": "成功识别10次风险行为",
            "icon": "🔍", "points": 60, "category": "风险"
        },
        "streak_3": {
            "name": "连续学习", "description": "连续3天登录学习",
            "icon": "🔥", "points": 30, "category": "活跃"
        },
        "streak_7": {
            "name": "一周坚持", "description": "连续7天登录学习",
            "icon": "💪", "points": 100, "category": "活跃"
        },
        "first_risk_avoid": {
            "name": "成功避险", "description": "首次成功识别诈骗并避免损失",
            "icon": "✅", "points": 50, "category": "风险"
        },
        "law_learner": {
            "name": "法律通", "description": "查阅过反诈法律法规",
            "icon": "⚖️", "points": 20, "category": "学习"
        },
    }

    # 等级体系
    LEVELS = [
        {"level": 1, "name": "反诈新手", "min_points": 0},
        {"level": 2, "name": "反诈学徒", "min_points": 100},
        {"level": 3, "name": "反诈能手", "min_points": 250},
        {"level": 4, "name": "反诈精英", "min_points": 500},
        {"level": 5, "name": "反诈卫士", "min_points": 800},
        {"level": 6, "name": "反诈专家", "min_points": 1200},
        {"level": 7, "name": "反诈大师", "min_points": 1800},
        {"level": 8, "name": "反诈传奇", "min_points": 2500},
        {"level": 9, "name": "反诈巅峰", "min_points": 3500},
        {"level": 10, "name": "反诈神话", "min_points": 5000},
    ]

    # 每日任务定义
    DAILY_TASKS = [
        {"id": "daily_chat", "name": "每日咨询", "description": "与反诈助手对话3次",
         "icon": "💬", "points": 10, "target": 3, "type": "conversation"},
        {"id": "daily_knowledge", "name": "学习知识", "description": "学习一种诈骗类型",
         "icon": "📖", "points": 15, "target": 1, "type": "knowledge"},
        {"id": "daily_scenario", "name": "闯关训练", "description": "完成一次情景模拟",
         "icon": "🎮", "points": 20, "target": 1, "type": "scenario"},
        {"id": "daily_report", "name": "举报练习", "description": "分析一个可疑链接",
         "icon": "🔍", "points": 10, "target": 1, "type": "report"},
        {"id": "daily_check", "name": "风险自查", "description": "进行一次风险自查",
         "icon": "✅", "points": 10, "target": 1, "type": "self_check"},
    ]

    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)

    # ========== 用户数据管理 ==========

    def _get_user_path(self, user_id: str) -> str:
        safe_id = user_id.replace('/', '_').replace('\\', '_')
        return os.path.join(self.data_dir, f"user_{safe_id}.json")

    def _load_user(self, user_id: str) -> dict:
        path = self._get_user_path(user_id)
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                pass
        return self._new_user(user_id)

    def _new_user(self, user_id: str) -> dict:
        today = self._today_str()
        return {
            "user_id": user_id,
            "points": 0,
            "badges": [],
            "completed_scenarios": [],
            "scenario_scores": {},
            "total_conversations": 0,
            "risk_identifications": 0,
            "reports_submitted": 0,
            "knowledge_learned": [],
            "daily_tasks_completed": {},
            "daily_tasks_date": today,
            "daily_tasks_progress": {},
            "login_streak": 0,
            "last_login_date": today,
            "total_days_active": 1,
            "streak_badges_awarded": [],
            "self_checks_done": 0,
            "last_active": int(time.time()),
            "created_at": int(time.time())
        }

    def _save_user(self, user_data: dict):
        user_data["last_active"] = int(time.time())
        path = self._get_user_path(user_data["user_id"])
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(user_data, f, ensure_ascii=False, indent=2)

    def _today_str(self) -> str:
        return time.strftime("%Y-%m-%d", time.localtime())

    # ========== 用户信息 ==========

    def get_user_info(self, user_id: str) -> dict:
        """获取用户信息（增强版）"""
        user = self._load_user(user_id)
        self._update_login_streak(user)
        self._reset_daily_tasks_if_needed(user)

        current_level = self._get_level(user["points"])
        next_level = self._get_next_level(current_level)

        info = {
            "user_id": user["user_id"],
            "points": user["points"],
            "level": current_level,
            "next_level": next_level,
            "badges": [self.BADGES[b] for b in user["badges"] if b in self.BADGES],
            "badge_ids": user["badges"],
            "completed_scenarios": user["completed_scenarios"],
            "scenario_count": len(user["completed_scenarios"]),
            "total_conversations": user["total_conversations"],
            "risk_identifications": user["risk_identifications"],
            "reports_submitted": user["reports_submitted"],
            "login_streak": user["login_streak"],
            "total_days_active": user["total_days_active"],
            "progress": self._get_progress(user),
            "daily_tasks": self.get_daily_tasks(user_id),
        }
        return info

    def _get_level(self, points: int) -> dict:
        current = self.LEVELS[0]
        for level_info in self.LEVELS:
            if points >= level_info["min_points"]:
                current = level_info
            else:
                break
        return current

    def _get_next_level(self, current_level: dict) -> Optional[dict]:
        for i, level in enumerate(self.LEVELS):
            if level["level"] == current_level["level"] and i + 1 < len(self.LEVELS):
                return self.LEVELS[i + 1]
        return None

    def _get_progress(self, user: dict) -> dict:
        current_level = self._get_level(user["points"])
        next_level = self._get_next_level(current_level)

        if next_level:
            current_min = current_level["min_points"]
            next_min = next_level["min_points"]
            progress = (user["points"] - current_min) / (next_min - current_min) * 100
        else:
            progress = 100.0

        return {
            "current_level_progress": round(min(progress, 100), 1),
            "points_to_next": (next_level["min_points"] - user["points"]) if next_level else 0,
            "total_badges": len(user["badges"]),
            "available_badges": len(self.BADGES)
        }

    # ========== 连续签到 ==========

    def _update_login_streak(self, user: dict):
        """更新连续签到"""
        today = self._today_str()
        last = user.get("last_login_date", "")

        if last == today:
            return  # 今天已更新

        if last:
            last_dt = time.strptime(last, "%Y-%m-%d")
            today_dt = time.strptime(today, "%Y-%m-%d")
            days_diff = (time.mktime(today_dt) - time.mktime(last_dt)) / 86400

            if days_diff == 1.0:  # 连续
                user["login_streak"] = user.get("login_streak", 0) + 1
            elif days_diff > 1.0:  # 中断
                user["login_streak"] = 1
        else:
            user["login_streak"] = 1

        user["last_login_date"] = today
        user["total_days_active"] = user.get("total_days_active", 0) + 1

        # 连续签到奖励
        streak = user["login_streak"]
        if streak == 3 and "streak_3" not in user.get("streak_badges_awarded", []):
            user["points"] += 30
            user.setdefault("streak_badges_awarded", []).append("streak_3")
            self.add_badge(user, "streak_3")
        elif streak == 7 and "streak_7" not in user.get("streak_badges_awarded", []):
            user["points"] += 100
            user.setdefault("streak_badges_awarded", []).append("streak_7")
            self.add_badge(user, "streak_7")

        # 每日签到积分（随连续天数递增）
        streak_bonus = min(streak, 7)  # 连续奖励上限7天
        user["points"] += streak_bonus

        self._save_user(user)

    # ========== 每日任务 ==========

    def _reset_daily_tasks_if_needed(self, user: dict):
        """重置每日任务"""
        today = self._today_str()
        if user.get("daily_tasks_date") != today:
            user["daily_tasks_completed"] = {}
            user["daily_tasks_progress"] = {}
            user["daily_tasks_date"] = today

    def get_daily_tasks(self, user_id: str) -> list:
        """获取每日任务列表"""
        user = self._load_user(user_id)
        self._reset_daily_tasks_if_needed(user)
        self._save_user(user)

        tasks = []
        for task_def in self.DAILY_TASKS:
            task_id = task_def["id"]
            progress = user.get("daily_tasks_progress", {}).get(task_id, 0)
            completed = user.get("daily_tasks_completed", {}).get(task_id, False)

            tasks.append({
                "id": task_id,
                "name": task_def["name"],
                "description": task_def["description"],
                "icon": task_def["icon"],
                "points": task_def["points"],
                "target": task_def["target"],
                "progress": min(progress, task_def["target"]),
                "completed": completed
            })

        return tasks

    def _update_task_progress(self, user: dict, task_type: str, increment: int = 1):
        """更新任务进度"""
        self._reset_daily_tasks_if_needed(user)
        today = self._today_str()

        if user.get("daily_tasks_date") != today:
            user["daily_tasks_date"] = today

        for task_def in self.DAILY_TASKS:
            if task_def["type"] == task_type:
                task_id = task_def["id"]
                if user.get("daily_tasks_completed", {}).get(task_id, False):
                    continue

                user.setdefault("daily_tasks_progress", {})[task_id] = \
                    user["daily_tasks_progress"].get(task_id, 0) + increment

                if user["daily_tasks_progress"][task_id] >= task_def["target"]:
                    user.setdefault("daily_tasks_completed", {})[task_id] = True
                    user["points"] += task_def["points"]

        self._save_user(user)

    def complete_daily_task(self, user_id: str, task_id: str) -> Optional[dict]:
        """主动完成每日任务"""
        user = self._load_user(user_id)
        self._reset_daily_tasks_if_needed(user)

        if user.get("daily_tasks_completed", {}).get(task_id, False):
            return {"status": "already_completed"}

        for task_def in self.DAILY_TASKS:
            if task_def["id"] == task_id:
                user.setdefault("daily_tasks_completed", {})[task_id] = True
                user.setdefault("daily_tasks_progress", {})[task_id] = task_def["target"]
                user["points"] += task_def["points"]
                self._save_user(user)
                return {
                    "status": "completed",
                    "task": task_def,
                    "points_awarded": task_def["points"],
                    "total_points": user["points"]
                }
        return None

    # ========== 积分与勋章 ==========

    def add_points(self, user_id: str, points: int, reason: str = "") -> dict:
        """为用户增加积分"""
        user = self._load_user(user_id)
        user["points"] += points

        old_level = self._get_level(user["points"] - points)
        new_level = self._get_level(user["points"])

        result = {
            "points_added": points,
            "total_points": user["points"],
            "reason": reason,
            "leveled_up": old_level["level"] != new_level["level"],
            "new_level": new_level if old_level["level"] != new_level["level"] else None
        }

        self._save_user(user)
        return result

    def add_badge(self, user_data: dict, badge_id: str) -> Optional[dict]:
        """直接授予勋章（内部使用）"""
        if badge_id not in self.BADGES:
            return None
        if badge_id in user_data.get("badges", []):
            return None
        badge_info = self.BADGES[badge_id]
        user_data.setdefault("badges", []).append(badge_id)
        user_data["points"] += badge_info["points"]
        return {"badge": badge_info, "points_awarded": badge_info["points"]}

    def check_and_award_badge(self, user_id: str, badge_id: str) -> Optional[dict]:
        """检查并授予勋章"""
        if badge_id not in self.BADGES:
            return None

        user = self._load_user(user_id)
        if badge_id in user.get("badges", []):
            return None

        grant_conditions = {
            "first_chat": lambda u: u.get("total_conversations", 0) >= 1,
            "chat_10": lambda u: u.get("total_conversations", 0) >= 10,
            "chat_50": lambda u: u.get("total_conversations", 0) >= 50,
            "knowledge_master": lambda u: len(u.get("knowledge_learned", [])) >= 5,
            "scenario_beginner": lambda u: len(u.get("completed_scenarios", [])) >= 1,
            "scenario_intermediate": lambda u: len(u.get("completed_scenarios", [])) >= 3,
            "scenario_all": lambda u: len(u.get("completed_scenarios", [])) >= 5,
            "report_first": lambda u: u.get("reports_submitted", 0) >= 1,
            "report_5": lambda u: u.get("reports_submitted", 0) >= 5,
            "perfect_score": lambda u: any(v >= 80 for v in u.get("scenario_scores", {}).values()),
            "risk_spotter": lambda u: u.get("risk_identifications", 0) >= 10,
            "first_risk_avoid": lambda u: u.get("risk_identifications", 0) >= 1,
            "law_learner": lambda u: len(u.get("knowledge_learned", [])) >= 1,
        }

        condition = grant_conditions.get(badge_id)
        if condition and condition(user):
            result = self.add_badge(user, badge_id)
            self._save_user(user)
            return result
        return None

    # ========== 事件记录 ==========

    def record_conversation(self, user_id: str):
        """记录一次对话"""
        user = self._load_user(user_id)
        self._update_login_streak(user)
        self._reset_daily_tasks_if_needed(user)
        user["total_conversations"] = user.get("total_conversations", 0) + 1
        self._update_task_progress(user, "conversation")
        self._save_user(user)
        self.check_and_award_badge(user_id, "first_chat")
        self.check_and_award_badge(user_id, "chat_10")

    def record_scenario_complete(self, user_id: str, scenario_id: str, score: int) -> dict:
        """记录情景模拟完成"""
        user = self._load_user(user_id)
        self._update_login_streak(user)
        self._reset_daily_tasks_if_needed(user)

        if scenario_id not in user.get("completed_scenarios", []):
            user.setdefault("completed_scenarios", []).append(scenario_id)
        user.setdefault("scenario_scores", {})[scenario_id] = max(
            user["scenario_scores"].get(scenario_id, 0), score
        )

        points_awarded = max(score, 0)
        user["points"] += points_awarded

        self._update_task_progress(user, "scenario")
        self._save_user(user)

        badges_awarded = []
        for badge_id in ["scenario_beginner", "scenario_intermediate", "scenario_all", "perfect_score"]:
            result = self.check_and_award_badge(user_id, badge_id)
            if result:
                badges_awarded.append(result)

        return {
            "points_awarded": points_awarded,
            "total_points": user["points"],
            "badges_awarded": badges_awarded
        }

    def record_risk_identification(self, user_id: str):
        """记录一次风险识别"""
        user = self._load_user(user_id)
        user["risk_identifications"] = user.get("risk_identifications", 0) + 1
        self._save_user(user)
        self.check_and_award_badge(user_id, "risk_spotter")
        self.check_and_award_badge(user_id, "first_risk_avoid")

    def record_report(self, user_id: str):
        """记录一次举报"""
        user = self._load_user(user_id)
        user["reports_submitted"] = user.get("reports_submitted", 0) + 1
        self._update_task_progress(user, "report")
        self._save_user(user)
        self.check_and_award_badge(user_id, "report_first")
        self.check_and_award_badge(user_id, "report_5")

    def record_knowledge_learned(self, user_id: str, fraud_type: str):
        """记录学过的知识"""
        user = self._load_user(user_id)
        user.setdefault("knowledge_learned", [])
        if fraud_type not in user["knowledge_learned"]:
            user["knowledge_learned"].append(fraud_type)
        self._update_task_progress(user, "knowledge")
        self._save_user(user)
        self.check_and_award_badge(user_id, "knowledge_master")
        self.check_and_award_badge(user_id, "law_learner")

    def record_self_check(self, user_id: str):
        """记录一次风险自查"""
        user = self._load_user(user_id)
        self._update_task_progress(user, "self_check")
        user["self_checks_done"] = user.get("self_checks_done", 0) + 1
        self._save_user(user)

    # ========== 排行榜 ==========

    def get_leaderboard(self, top_n: int = 20) -> list:
        """获取排行榜（扫描所有用户数据）"""
        users = []
        try:
            for fname in os.listdir(self.data_dir):
                if fname.startswith("user_") and fname.endswith(".json"):
                    path = os.path.join(self.data_dir, fname)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                        level = self._get_level(data.get("points", 0))
                        users.append({
                            "user_id": data["user_id"][:8],
                            "points": data.get("points", 0),
                            "level": level["name"],
                            "level_num": level["level"],
                            "badges": len(data.get("badges", [])),
                            "scenarios": len(data.get("completed_scenarios", [])),
                        })
                    except (json.JSONDecodeError, KeyError):
                        continue
        except FileNotFoundError:
            return []

        users.sort(key=lambda x: x["points"], reverse=True)
        for i, u in enumerate(users, 1):
            u["rank"] = i

        return users[:top_n]

    def get_user_rank(self, user_id: str) -> Optional[dict]:
        """获取用户排名"""
        leaderboard = self.get_leaderboard(top_n=1000)
        for u in leaderboard:
            if u["user_id"] == user_id[:8]:
                return u
        return None

    # ========== 数据导出 ==========

    def export_user_data(self, user_id: str) -> Optional[dict]:
        """导出用户数据（数据可携带性）"""
        user = self._load_user(user_id)
        if not user:
            return None
        return {
            "export_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "user_data": {
                "user_id": user["user_id"],
                "points": user["points"],
                "level": self._get_level(user["points"]),
                "badges": [self.BADGES[b]["name"] for b in user.get("badges", []) if b in self.BADGES],
                "scenarios_completed": user.get("completed_scenarios", []),
                "scenario_scores": user.get("scenario_scores", {}),
                "total_conversations": user.get("total_conversations", 0),
                "risk_identifications": user.get("risk_identifications", 0),
                "reports_submitted": user.get("reports_submitted", 0),
                "knowledge_learned": user.get("knowledge_learned", []),
                "login_streak": user.get("login_streak", 0),
                "total_days_active": user.get("total_days_active", 0),
                "created_at": user.get("created_at", 0)
            }
        }
