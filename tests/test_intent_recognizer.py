"""意图识别引擎单元测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from engine.intent_recognizer import IntentRecognizer


@pytest.fixture
def recognizer():
    return IntentRecognizer()


class TestIntentRecognizer:
    """意图识别引擎测试"""

    def test_greeting(self, recognizer):
        result = recognizer.recognize("你好")
        assert result["intent"] == "greetings"
        assert result["confidence"] > 0

    def test_emergency(self, recognizer):
        result = recognizer.recognize("我已经转账了，紧急！")
        assert result["intent"] == "emergency"
        assert result["confidence"] == 1.0

    def test_knowledge_query(self, recognizer):
        result = recognizer.recognize("什么是刷单诈骗")
        assert result["intent"] in ("knowledge_queries", "fraud_inquiry")

    def test_report_intent(self, recognizer):
        result = recognizer.recognize("我要举报一个链接")
        assert result["intent"] == "report_intents"

    def test_self_check(self, recognizer):
        result = recognizer.recognize("我是不是被骗了")
        assert result["intent"] == "self_check"

    def test_scenario_request(self, recognizer):
        result = recognizer.recognize("我想做情景模拟")
        assert result["intent"] == "scenario_requests"

    def test_legal_query(self, recognizer):
        """法律查询意图测试"""
        result = recognizer.recognize("我想了解法律知识")
        assert result["intent"] in ("legal_queries", "knowledge_queries")
        # 带有明确法律关键词
        result2 = recognizer.recognize("刑法对诈骗罪的规定是什么")
        assert result2["intent"] in ("legal_queries", "knowledge_queries")

    def test_feedback(self, recognizer):
        result = recognizer.recognize("谢谢，很有用")
        assert result["intent"] == "feedback"

    def test_unknown(self, recognizer):
        """完全无关联输入应返回 unknown 或 describe_situation"""
        result = recognizer.recognize("量子力学的基本原理")
        assert result["intent"] in ("unknown", "describe_situation")

    def test_fraud_type_detection(self, recognizer):
        result = recognizer.recognize("刷单赚钱是真的吗")
        assert result.get("fraud_type") == "刷单返利"

    def test_empty_input(self, recognizer):
        result = recognizer.recognize("")
        assert result["intent"] == "unknown"
        assert result["confidence"] == 0

    def test_context_tracking(self, recognizer):
        """测试多轮上下文追踪"""
        user_id = "test_user_context"
        result1 = recognizer.recognize("什么是刷单", user_id)
        assert result1.get("fraud_type") == "刷单返利"
        # 第二轮应该继承上下文或至少正确识别
        result2 = recognizer.recognize("讲讲这个", user_id)
        assert result2["intent"] != "unknown"

    def test_synonym_matching(self, recognizer):
        """测试同义词扩展匹配"""
        result = recognizer.recognize("点赞赚钱是真的吗")
        assert result["intent"] in ("self_check", "fraud_inquiry")

    def test_emergency_not_false_positive(self, recognizer):
        """测试不要误触发紧急"""
        result = recognizer.recognize("我被骗了")
        assert result["intent"] != "emergency"

    def test_describe_situation(self, recognizer):
        """长文本应被识别为情景描述"""
        result = recognizer.recognize(
            "有个陌生人加我微信，说可以带我做投资，让我下载一个APP"
        )
        assert result["intent"] in ("describe_situation", "self_check",
                                    "fraud_inquiry", "unknown")
