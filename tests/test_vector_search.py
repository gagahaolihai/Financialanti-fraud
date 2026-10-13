"""v3.0 向量检索引擎单元测试"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest


@pytest.fixture(scope="module")
def vs_engine():
    from engine.vector_search import VectorSearchEngine
    engine = VectorSearchEngine()
    docs = engine.load_knowledge_base()
    assert len(docs) >= 9, f"知识库应有>=9种类型，实际{len(docs)}"
    engine.build_index(docs)
    return engine


class TestVectorSearch:
    """向量检索引擎测试"""

    def test_index_built(self, vs_engine):
        """索引构建成功"""
        assert vs_engine.is_ready
        assert vs_engine.documents is not None

    def test_semantic_search_related(self, vs_engine):
        """语义搜索找到相关结果"""
        results = vs_engine.search('刷单兼职日赚数百', top_k=3)
        assert len(results) > 0
        assert any('刷单' in r.get('id', '') for r in results)

    def test_semantic_search_facetime(self, vs_engine):
        """FaceTime诈骗搜索"""
        results = vs_engine.search('FaceTime客服说百万保障到期', top_k=3)
        assert len(results) > 0
        assert any('FaceTime' in r.get('id', '') for r in results)

    def test_semantic_search_ai_face(self, vs_engine):
        """AI换脸诈骗搜索"""
        results = vs_engine.search('视频通话里是我女儿吗还是AI合成的', top_k=3)
        assert len(results) > 0

    def test_hybrid_search(self, vs_engine):
        """混合检索"""
        results = vs_engine.hybrid_search('银行客服让我转账到指定账户', top_k=3)
        assert len(results) > 0

    def test_keyword_fallback(self, vs_engine):
        """关键词回退检索"""
        results = vs_engine._keyword_fallback('指定账户打款返利', top_k=3)
        assert len(results) > 0

    def test_empty_query(self, vs_engine):
        """空查询不崩溃"""
        results = vs_engine.search('')
        assert results == []

    def test_search_result_structure(self, vs_engine):
        """搜索结果结构完整"""
        results = vs_engine.search('刷单', top_k=1)
        assert len(results) > 0
        r = results[0]
        assert 'id' in r
        assert 'description' in r
        assert '_score' in r
        assert '_match_type' in r

    def test_document_count(self, vs_engine):
        """知识库文档数量"""
        assert len(vs_engine.documents) >= 16, \
            f"v3.0应有>=16种诈骗类型，实际{len(vs_engine.documents)}"
