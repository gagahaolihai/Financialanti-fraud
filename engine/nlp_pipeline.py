"""
NLP 集成管道 v3.0
整合语义编码器、向量检索、意图分类器，提供统一接口
与现有规则引擎并行运行，智能回退
"""
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 全局实例（惰性加载）
_nlp_pipeline = None


class NLPPipeline:
    """
    NLP 集成管道 — 现代语义理解 + 规则引擎兜底
    
    使用方式:
        pipeline = get_nlp_pipeline()
        
        # 语义搜索
        results = pipeline.semantic_search("刷单兼职", top_k=3)
        
        # 意图识别
        intent, confidence = pipeline.classify_intent("我是不是被骗了")
        
        # 诈骗类型匹配
        matches = pipeline.match_fraud_type("有人让我下载APP刷单")
    """

    def __init__(self):
        self._encoder = None
        self._vector_search = None
        self._classifier = None
        self._ready = False
        self._load_attempted = False

    @property
    def ready(self) -> bool:
        """是否所有组件就绪"""
        if not self._load_attempted:
            self._ensure_loaded()
        return self._ready

    def _ensure_loaded(self):
        """惰性加载所有组件"""
        if self._load_attempted:
            return
        self._load_attempted = True

        try:
            from engine.nlp_encoder import get_semantic_encoder
            self._encoder = get_semantic_encoder()
            if not self._encoder.load():
                logger.warning("[NLPPipeline] 编码器未就绪")
                return

            from engine.vector_search import get_vector_search
            self._vector_search = get_vector_search()
            # 加载知识库并构建索引
            docs = self._vector_search.load_knowledge_base()
            if docs:
                self._vector_search.build_index(docs)

            from engine.intent_classifier import get_intent_classifier
            self._classifier = get_intent_classifier()
            if not self._classifier.load():
                logger.warning("[NLPPipeline] 意图分类器未就绪")
                return

            self._ready = True
            logger.info("[NLPPipeline] 全部组件就绪 ✓")

        except Exception as e:
            logger.warning(f"[NLPPipeline] 初始化失败，回退规则模式: {e}")

    # ===== 语义搜索 =====

    def semantic_search(self, query: str, top_k: int = 3) -> List[Dict]:
        """
        语义搜索知识库
        
        Returns:
            [{"id": "刷单返利", "description": "...", "_score": 0.85, "_match_type": "semantic"}, ...]
        """
        if not self.ready:
            return []
        try:
            return self._vector_search.hybrid_search(query, top_k=top_k)
        except Exception as e:
            logger.error(f"[NLPPipeline] 语义搜索失败: {e}")
            return []

    def get_relevant_knowledge(self, query: str, top_k: int = 2) -> str:
        """
        获取相关知识的文本摘要（用于 RAG）
        
        Returns:
            格式化的知识文本
        """
        results = self.semantic_search(query, top_k=top_k)
        if not results:
            return ""

        parts = []
        for r in results:
            # 融合分已归一到 [0,1]，这里再夹一次，杜绝「匹配度 160%」这类
            # 越界百分比被写进提示词误导模型。
            # 注意：这是"本次检索内的相对匹配度"，Top-1 恒为 100%，不代表绝对置信度，
            # 因此提示词里必须写明是相对值，避免模型把它当成确定的概率。
            score = min(max(float(r.get("_score", 0) or 0), 0.0), 1.0)
            match_type = r.get("_match_type", "unknown")
            parts.append(f"【{r['id']}】(相对匹配度: {score:.0%}, 方式: {match_type})")
            parts.append(f"描述: {r.get('description', '')}")
            patterns = r.get("common_patterns", [])[:3]
            if patterns:
                parts.append(f"特征: {'; '.join(patterns)}")
            advice = r.get("prevention_advice", [])[:2]
            if advice:
                parts.append(f"建议: {'; '.join(advice)}")
            parts.append("")

        return "\n".join(parts)

    # ===== 意图识别 =====

    def classify_intent(self, text: str) -> Tuple[str, float]:
        """
        语义意图分类
        
        Returns:
            (intent_name, confidence)
        """
        if not self.ready or not self._classifier:
            return ("unknown", 0.0)
        try:
            return self._classifier.classify_top1(text)
        except Exception as e:
            logger.error(f"[NLPPipeline] 意图分类失败: {e}")
            return ("unknown", 0.0)

    def classify_intent_multi(self, text: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """多意图分类"""
        if not self.ready or not self._classifier:
            return []
        try:
            return self._classifier.classify(text, top_k=top_k)
        except Exception as e:
            logger.error(f"[NLPPipeline] 多意图分类失败: {e}")
            return []

    # ===== 诈骗类型匹配 =====

    def match_fraud_type(self, text: str) -> List[Tuple[str, float]]:
        """匹配最可能的诈骗类型"""
        if not self.ready or not self._classifier:
            return []

        try:
            docs = self._vector_search.load_knowledge_base()
            return self._classifier.get_fraud_type_scores(text, docs)
        except Exception as e:
            logger.error(f"[NLPPipeline] 诈骗类型匹配失败: {e}")
            return []

    # ===== 相似度计算 =====

    def text_similarity(self, text1: str, text2: str) -> float:
        """计算两句文本的语义相似度"""
        if not self.ready or not self._encoder:
            return 0.0
        try:
            return self._encoder.similarity(text1, text2)
        except Exception as e:
            logger.error(f"[NLPPipeline] 相似度计算失败: {e}")
            return 0.0

    # ===== 编码 =====

    def encode(self, text: str):
        """编码文本为向量"""
        if not self.ready or not self._encoder:
            return None
        try:
            return self._encoder.encode(text)
        except Exception as e:
            logger.error(f"[NLPPipeline] 编码失败: {e}")
            return None


def get_nlp_pipeline() -> NLPPipeline:
    """获取全局 NLP 管道单例"""
    global _nlp_pipeline
    if _nlp_pipeline is None:
        _nlp_pipeline = NLPPipeline()
    return _nlp_pipeline
