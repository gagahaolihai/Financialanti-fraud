"""v3.0 语义意图分类器单元测试"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest


@pytest.fixture(scope="module")
def classifier():
    from engine.intent_classifier import SemanticIntentClassifier
    clf = SemanticIntentClassifier()
    assert clf.load(), "意图分类器加载失败"
    return clf


class TestIntentClassifier:
    """意图分类器测试"""

    def test_loaded(self, classifier):
        assert classifier.ready

    def test_classify_self_check(self, classifier):
        """自检意图识别"""
        results = classifier.classify('这是诈骗吗？帮我判断一下')
        assert len(results) > 0
        top = results[0][0]
        assert top in ('self_check', 'help_requests', 'fraud_inquiry', 'report_intents')

    def test_classify_emergency(self, classifier):
        """紧急意图识别"""
        results = classifier.classify('有人冒充警察要我转钱到安全账户')
        top = results[0][0]
        assert top in ('emergency', 'describe_situation', 'self_check')

    def test_classify_knowledge(self, classifier):
        """知识查询意图"""
        results = classifier.classify('什么是刷单诈骗，给我讲讲')
        top = results[0][0]
        assert top in ('knowledge_queries', 'fraud_inquiry')

    def test_classify_fear(self, classifier):
        """恐惧/紧急情绪识别"""
        results = classifier.classify('我好害怕，刚才有人打电话说我的银行卡被盗刷了')
        top = results[0][0]
        # 紧急或恐惧都是合法结果
        assert top in ('fear_anxiety', 'self_check', 'describe_situation', 'emergency')

    def test_classify_thanks(self, classifier):
        """感谢意图识别"""
        results = classifier.classify('谢谢你帮了我')
        assert results[0][0] == 'thanks'

    def test_classify_greeting(self, classifier):
        """问候意图"""
        results = classifier.classify('你好，在吗')
        assert results[0][0] == 'greetings'

    def test_top1_with_threshold(self, classifier):
        """top1带阈值分类"""
        # 高置信度
        intent, conf = classifier.classify_top1('你好我想问问题')
        assert intent != 'unknown' or conf < 0.6

        # 低置信度应返回 unknown
        intent, conf = classifier.classify_top1('xyz123abc', min_confidence=0.5)
        assert intent == 'unknown' or conf < 0.5

    def test_fraud_type_scores(self, classifier):
        """诈骗类型匹配"""
        import json, os
        kb_path = os.path.join(os.path.dirname(__file__), '..', 'knowledge_base', 'fraud_types.json')
        with open(kb_path, 'r', encoding='utf-8') as f:
            kb = json.load(f)

        scores = classifier.get_fraud_type_scores(
            '有人用AI换脸冒充我女儿视频通话要我转钱',
            kb['fraud_types']
        )
        assert len(scores) > 0
        # AI换脸应该是高分
        top_type = scores[0][0]
        assert top_type in ('AI换脸诈骗', '冒充熟人')

    def test_classify_empty(self, classifier):
        """空输入不崩溃"""
        results = classifier.classify('')
        assert len(results) == 0 or results[0][0] != 'unknown'
