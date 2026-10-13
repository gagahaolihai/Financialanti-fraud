"""v3.0 多模态检测器单元测试"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from engine.multimodal_detector import AudioFraudDetector, ImageFraudDetector


class TestAudioFraudDetector:
    """语音诈骗检测器测试（文本模式）"""

    def setup_method(self):
        self.detector = AudioFraudDetector()

    def test_bank_impersonation(self):
        """银行冒充检测"""
        result = self.detector.analyze_text_for_fraud_calls(
            '我是农业银行的客服，您的账户出现异常，请立即将资金转入安全账户进行核查'
        )
        assert result['has_fraud_indicators']
        assert result['risk_level'] in ('critical', 'high')
        detections = result['detections']
        types = [d['type'] for d in detections]
        assert any('公检法' in t or '安全账户' in t for t in types)

    def test_scam_job(self):
        """刷单兼职检测"""
        result = self.detector.analyze_text_for_fraud_calls(
            '足不出户日赚500，手机就能做，先垫付100元马上返150'
        )
        assert result['has_fraud_indicators']
        types = [d['type'] for d in result['detections']]
        assert any('刷单' in t for t in types)

    def test_urgency_tactics(self):
        """紧迫感话术检测"""
        result = self.detector.analyze_text_for_fraud_calls(
            '马上转账！最后10分钟，否则你的账户会被冻结！限时操作！'
        )
        assert result['has_fraud_indicators']
        types = [d['type'] for d in result['detections']]
        assert any('心理' in t for t in types)

    def test_safe_text(self):
        """正常通话不误报"""
        result = self.detector.analyze_text_for_fraud_calls(
            '你好，明天下午3点开会，请准时参加'
        )
        assert not result['has_fraud_indicators']
        assert result['risk_level'] == 'none'

    def test_empty_text(self):
        """空文本不崩溃"""
        result = self.detector.analyze_text_for_fraud_calls('')
        assert not result['has_fraud_indicators']

    def test_facetime_scam(self):
        """FaceTime诈骗话术"""
        result = self.detector.analyze_text_for_fraud_calls(
            '您好我是微信客服，您的百万保障免费期已到期，不关闭的话每月扣2000'
        )
        # 应检测到至少一个特征
        assert len(result['detections']) > 0 or result['has_fraud_indicators']


class TestImageFraudDetector:
    """图像诈骗检测器测试（规则模式）"""

    def test_patterns_exist(self):
        """规则模式定义完整"""
        from engine.multimodal_detector import (
            FAKE_LEGAL_DOC_PATTERNS, FRAUD_APP_PATTERNS,
            FAKE_CUSTOMER_SERVICE_PATTERNS, FAKE_INVESTMENT_PATTERNS
        )
        assert len(FAKE_LEGAL_DOC_PATTERNS) >= 5
        assert len(FRAUD_APP_PATTERNS) >= 5
        assert len(FAKE_CUSTOMER_SERVICE_PATTERNS) >= 5
        assert len(FAKE_INVESTMENT_PATTERNS) >= 5

    def test_text_analysis_via_audio_detector(self):
        """通过文本分析检测诈骗截图特征（模拟OCR提取后的文本）"""
        detector = AudioFraudDetector()
        # 模拟从假通缉令截图中OCR提取的文字
        fake_doc_text = '通缉令 涉嫌洗钱案件 安全账户 资金核查 保密不得告诉任何人'
        result = detector.analyze_text_for_fraud_calls(fake_doc_text)
        assert result['has_fraud_indicators']
        assert result['risk_level'] in ('critical', 'high')

    def test_fake_investment_text(self):
        """虚假投资文本检测"""
        detector = AudioFraudDetector()
        fake_invest = '日收益5% 稳赚不赔 内部渠道 老师带单 USDT入金'
        result = detector.analyze_text_for_fraud_calls(fake_invest)
        # 应检测到至少一个特征（刷单/投资类）
        assert result['has_fraud_indicators'] or len(result['detections']) > 0
