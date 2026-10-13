"""URL/内容分析引擎单元测试"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from engine.url_analyzer import URLAnalyzer


@pytest.fixture
def analyzer():
    return URLAnalyzer()


class TestURLAnalyzer:
    """URL分析引擎测试"""

    def test_safe_url(self, analyzer):
        result = analyzer.analyze_url("https://www.baidu.com")
        assert result["is_suspicious"] is False

    def test_suspicious_tld(self, analyzer):
        result = analyzer.analyze_url("http://example.xyz")
        assert result["is_suspicious"] is True

    def test_short_url(self, analyzer):
        """短链接检测（短链接单独不足以判定suspicious，但应降低风险评级）"""
        result = analyzer.analyze_url("https://t.cn/abc123")
        assert result["risk_level"] != "none"  # 短链接导致风险上升
        assert len(result["details"]) > 0

    def test_blacklist_domain(self, analyzer):
        result = analyzer.analyze_url("http://anquan-zhongxin.com")
        assert result["is_suspicious"] is True

    def test_ip_address_url(self, analyzer):
        result = analyzer.analyze_url("http://192.168.1.1/login")
        assert result["is_suspicious"] is True

    def test_empty_url(self, analyzer):
        result = analyzer.analyze_url("")
        assert result["is_suspicious"] is False
        assert result["risk_level"] == "none"

    def test_suspicious_keywords(self, analyzer):
        result = analyzer.analyze_url("http://anquan-verify.com")
        assert result["is_suspicious"] is True

    def test_risk_level_critical(self, analyzer):
        """多特征同时触发 → 高危"""
        result = analyzer.analyze_url("http://anquan-zhongxin.com.xyz/login/verify")
        assert result["risk_level"] in ("high", "critical")

    def test_no_protocol_url(self, analyzer):
        result = analyzer.analyze_url("anquan-zhongxin.com")
        assert result["is_suspicious"] is True

    def test_domain_pattern_match(self, analyzer):
        result = analyzer.analyze_url("https://shua-fanli.com")
        assert result.get("matched_pattern") is not None

    def test_content_analysis_suspicious(self, analyzer):
        """内容含诈骗关键词"""
        result = analyzer.analyze_content("日赚500，稳赚不赔，联系我")
        assert result["is_suspicious"] is True

    def test_content_analysis_phone(self, analyzer):
        """内容含可疑手机号（单个手机号风险较低，但应被标记）"""
        result = analyzer.analyze_content("请联系我 13812345678")
        assert result["is_suspicious"] is False  # 单条手机号分数不足0.6
        assert result["risk_score"] > 0  # 但确实有检出
        # 多个诈骗特征组合应触发suspicious
        result2 = analyzer.analyze_content("日赚500，稳赚不赔，联系 13812345678")
        assert result2["is_suspicious"] is True

    def test_content_analysis_safe(self, analyzer):
        result = analyzer.analyze_content("今天天气真好")
        assert result["is_suspicious"] is False

    def test_report_history(self, analyzer):
        analyzer.record_report("test_user", "http://evil.com", {
            "is_suspicious": True, "risk_level": "high", "domain": "evil.com"
        })
        history = analyzer.get_report_history("test_user")
        assert len(history) == 1
        assert history[0]["domain"] == "evil.com"

    def test_report_stats(self, analyzer):
        analyzer.record_report("test_user2", "http://safe.com", {
            "is_suspicious": False, "risk_level": "none", "domain": "safe.com"
        })
        stats = analyzer.get_report_stats("test_user2")
        assert stats["total"] == 1

    def test_content_keyword_count(self, analyzer):
        result = analyzer.analyze_content(
            "日赚500，月入过万，稳赚不赔，安全账户"
        )
        assert result["keyword_count"] >= 3

    def test_https_check(self, analyzer):
        result = analyzer.analyze_url("http://example.com")
        # 非HTTPS应该有一个细节提醒
        details_text = " ".join(result["details"])
        assert "HTTPS" in details_text or "https" in details_text \
               or "加密" in details_text or "http" in details_text.lower()
