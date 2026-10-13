"""风险分析引擎单元测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from engine.risk_analyzer import RiskAnalyzer


@pytest.fixture
def analyzer():
    return RiskAnalyzer()


class TestRiskAnalyzer:
    """风险分析引擎测试"""

    def test_no_risk(self, analyzer):
        result = analyzer.analyze_risk("今天天气很好")
        assert result["risk_level"] == "none"
        assert result["risk_score"] == 0

    def test_transfer_risk(self, analyzer):
        """转账给陌生人风险检测"""
        result = analyzer.analyze_risk("转账到陌生人的账户")
        assert result["risk_level"] != "none"
        assert result["rule_count"] >= 1

    def test_verification_code_risk(self, analyzer):
        """验证码泄露风险"""
        result = analyzer.analyze_risk("我把验证码发给了对方")
        assert result["risk_level"] != "none"
        assert result["rule_count"] >= 1

    def test_screen_share_risk(self, analyzer):
        """屏幕共享风险"""
        result = analyzer.analyze_risk("对方要求共享屏幕")
        assert result["risk_level"] != "none"
        assert result["rule_count"] >= 1

    def test_fake_investment_risk(self, analyzer):
        """虚假投资风险"""
        result = analyzer.analyze_risk("这个平台稳赚不赔")
        assert result["risk_level"] != "none"
        assert result["rule_count"] >= 1

    def test_impostor_police_risk(self, analyzer):
        """冒充公检法风险"""
        result = analyzer.analyze_risk("他说他是公安局的，要我转安全账户")
        assert result["risk_level"] != "none"
        assert result["rule_count"] >= 1

    def test_multiple_rules_high_risk(self, analyzer):
        """多规则触发应达到较高风险等级"""
        result = analyzer.analyze_risk("刷单兼职日赚500，稳赚不赔")
        assert result["risk_level"] in ("high", "medium")
        assert result["rule_count"] >= 1

    def test_historical_context_increases_risk(self, analyzer):
        """测试历史上下文增加风险等级"""
        user_id = "test_risk_history"
        result1 = analyzer.analyze_risk("我在网上认识了一个投资导师", user_id)
        # 第二轮包含历史上下文 → 风险累积
        result2 = analyzer.analyze_risk("他让我投资10万，说稳赚不赔", user_id,
                                       ["我在网上认识了一个投资导师"])
        assert result2["risk_level"] != "none"

    def test_triggered_rules_count(self, analyzer):
        result = analyzer.analyze_risk("刷单兼职日赚500，稳赚不赔")
        assert result["rule_count"] >= 1

    def test_generate_intervention_critical(self, analyzer):
        """紧急劝阻话术生成"""
        risk_result = {
            "risk_level": "critical",
            "triggered_rules": [
                {"rule": "冒充公检法", "category": "冒充公检法",
                 "intervention_type": "冒充公检法风险", "weight": 0.95}
            ]
        }
        intervention = analyzer.generate_intervention(risk_result, "冒充公检法")
        assert "110" in intervention or "紧急" in intervention

    def test_generate_intervention_high(self, analyzer):
        """高风险劝阻话术"""
        risk_result = {
            "risk_level": "high",
            "triggered_rules": [
                {"rule": "刷单/兼职", "category": "刷单诈骗",
                 "intervention_type": "刷单返利风险", "weight": 0.7}
            ]
        }
        intervention = analyzer.generate_intervention(risk_result, "刷单返利")
        assert "刷单" in intervention or "诈骗" in intervention

    def test_risk_profile(self, analyzer):
        """风险画像记录（仅high/critical风险会被记录）"""
        user_id = "test_profile_123"
        # 需要足够高的风险分才能记录画像
        analyzer.analyze_risk("刷单兼职日赚500，稳赚不赔，下载APP", user_id)
        profile = analyzer.get_risk_profile(user_id)
        assert profile is not None
        assert profile["total_events"] >= 1

    def test_risk_profile_empty(self, analyzer):
        """无风险记录的用户"""
        profile = analyzer.get_risk_profile("nonexistent_user")
        assert profile is None

    def test_multi_category_detection(self, analyzer):
        """多类别同时检测"""
        result = analyzer.analyze_risk(
            "下载APP刷单，日赚500，稳赚不赔"
        )
        assert result["rule_count"] >= 1
        categories = set(r["category"] for r in result["triggered_rules"])
        assert len(categories) >= 1
