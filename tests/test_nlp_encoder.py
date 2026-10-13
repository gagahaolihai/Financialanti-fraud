"""v3.0 语义编码器单元测试"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import numpy as np

@pytest.fixture(scope="module")
def encoder():
    """模块级 fixture，只加载一次模型"""
    from engine.nlp_encoder import SemanticEncoder
    enc = SemanticEncoder()
    assert enc.load(), "模型加载失败（检查 models/ 目录是否存在）"
    return enc


class TestSemanticEncoder:
    """语义编码器测试"""

    def test_model_loaded(self, encoder):
        """模型成功加载，维度正确"""
        assert encoder.ready
        assert encoder.vector_dim == 384

    def test_encode_single(self, encoder):
        """单条文本编码"""
        vec = encoder.encode('刷单返利诈骗')
        assert vec is not None
        assert len(vec) == 384
        assert abs(np.linalg.norm(vec) - 1.0) < 0.01  # 归一化

    def test_encode_batch(self, encoder):
        """批量编码"""
        texts = ['刷单诈骗', '冒充公检法', '虚假投资']
        vecs = encoder.encode_batch(texts)
        assert vecs is not None
        assert vecs.shape == (3, 384)
        # 批量编码结果应归一化
        norms = np.linalg.norm(vecs, axis=1)
        assert np.allclose(norms, 1.0, atol=0.01)

    def test_similarity_related(self, encoder):
        """相关文本相似度高"""
        sim = encoder.similarity(
            '刷单返利诈骗，足不出户日赚数百',
            '兼职刷单，动动手指月入过万'
        )
        assert sim > 0.3, f"相关文本相似度应>0.3, 实际={sim:.4f}"

    def test_similarity_unrelated(self, encoder):
        """无关文本相似度低"""
        sim = encoder.similarity(
            '刷单诈骗需要警惕',
            '今天天气很好适合出游'
        )
        assert sim < 0.5, f"无关文本相似度应<0.5, 实际={sim:.4f}"

    def test_similarity_symmetric(self, encoder):
        """相似度对称"""
        a, b = '刷单诈骗', '兼职刷单返利'
        assert abs(encoder.similarity(a, b) - encoder.similarity(b, a)) < 0.001

    def test_most_similar(self, encoder):
        """从候选列表找最相似"""
        candidates = [
            '刷单返利是常见诈骗',
            '游戏交易要注意安全',
            '冒充公检法很可怕',
            '今天天气不错',
        ]
        ranked = encoder.most_similar('兼职刷单赚钱靠谱吗', candidates)
        assert len(ranked) == len(candidates)
        # 第一名应该和刷单相关
        assert '刷单' in candidates[ranked[0][0]]

    def test_empty_text(self, encoder):
        """空文本不崩溃"""
        vec = encoder.encode('')
        assert vec is not None

    def test_global_singleton(self):
        """全局单例"""
        from engine.nlp_encoder import get_semantic_encoder
        e1 = get_semantic_encoder()
        e2 = get_semantic_encoder()
        assert e1 is e2
