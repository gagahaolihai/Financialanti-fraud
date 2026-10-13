"""
FAISS 向量检索引擎 v3.0
基于语义向量的高效知识检索，替代 TF-IDF
支持增量索引、热更新、混合检索（语义+关键词）
"""
import json
import os
import time
import logging
import numpy as np
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False
    logger.warning("[VectorSearch] faiss 未安装，回退到线性搜索")


class VectorSearchEngine:
    """FAISS 向量检索引擎 — 语义相似度搜索"""

    def __init__(self, kb_path: str = None):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.kb_path = kb_path or os.path.join(self.base_dir, 'knowledge_base', 'fraud_types.json')
        self.index: Optional[faiss.IndexFlatIP] = None  # 内积索引(归一化后=余弦相似度)
        self.documents: List[Dict] = []       # 文档列表
        self.doc_vectors: Optional[np.ndarray] = None  # 文档向量缓存
        self._last_load_time = 0
        self._encoder = None  # 惰性加载

    def _get_encoder(self):
        if self._encoder is None:
            from engine.nlp_encoder import get_semantic_encoder
            self._encoder = get_semantic_encoder()
        return self._encoder

    @property
    def is_ready(self) -> bool:
        return HAS_FAISS and self.index is not None

    def build_index(self, documents: List[Dict] = None) -> bool:
        """构建/重建 FAISS 索引"""
        if documents is not None:
            self.documents = documents

        if not self.documents:
            logger.warning("[VectorSearch] 无文档可索引")
            return False

        encoder = self._get_encoder()
        if not encoder.load():
            logger.warning("[VectorSearch] 编码器未就绪，跳过索引构建")
            return False

        # 为每个文档构建搜索文本
        texts = [self._doc_to_text(doc) for doc in self.documents]

        logger.info(f"[VectorSearch] 正在编码 {len(texts)} 篇文档...")
        vectors = encoder.encode_batch(texts)
        if vectors is None:
            return False

        self.doc_vectors = vectors.astype(np.float32)

        if HAS_FAISS:
            dim = vectors.shape[1]
            self.index = faiss.IndexFlatIP(dim)  # 内积 = 余弦相似度(已归一化)
            self.index.add(self.doc_vectors)
            logger.info(f"[VectorSearch] FAISS 索引构建完成 ({len(self.documents)} 文档, dim={dim})")

        self._last_load_time = time.time()
        return True

    def _doc_to_text(self, doc: Dict) -> str:
        """将知识库文档转为可检索文本"""
        parts = []
        parts.append(doc.get("id", ""))
        parts.append(doc.get("description", ""))
        for kw in doc.get("keywords", [])[:20]:
            parts.append(kw)
        for alias in doc.get("aliases", []):
            parts.append(alias)
        for pattern in doc.get("common_patterns", []):
            parts.append(pattern)
        return " ".join(parts)

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        """语义搜索 — 返回最相关的文档"""
        if not query.strip():
            return []

        encoder = self._get_encoder()
        if not encoder.load():
            return self._keyword_fallback(query, top_k)

        query_vec = encoder.encode(query)
        if query_vec is None:
            return self._keyword_fallback(query, top_k)

        query_vec = query_vec.reshape(1, -1).astype(np.float32)

        # FAISS 检索
        if HAS_FAISS and self.index is not None:
            scores, indices = self.index.search(query_vec, min(top_k, len(self.documents)))
            results = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and idx < len(self.documents):
                    results.append({
                        **self.documents[idx],
                        "_score": float(score),
                        "_match_type": "semantic"
                    })
            return results

        # 回退：线性搜索
        return self._linear_search(query_vec[0], top_k)

    def _linear_search(self, query_vec: np.ndarray, top_k: int) -> List[Dict]:
        """线性搜索（FAISS不可用时的回退）"""
        if self.doc_vectors is None:
            return []
        similarities = np.dot(self.doc_vectors, query_vec)
        indices = np.argsort(similarities)[::-1][:top_k]
        results = []
        for idx in indices:
            if idx < len(self.documents):
                results.append({
                    **self.documents[idx],
                    "_score": float(similarities[idx]),
                    "_match_type": "linear"
                })
        return results

    def _keyword_fallback(self, query: str, top_k: int) -> List[Dict]:
        """关键词回退检索（基本字符串匹配）"""
        query_lower = query.lower()
        results = []
        for doc in self.documents:
            score = 0
            text = self._doc_to_text(doc).lower()
            # 关键词命中得分
            for kw in doc.get("keywords", []):
                if kw.lower() in query_lower:
                    score += 2
            for alias in doc.get("aliases", []):
                if alias.lower() in query_lower:
                    score += 1
            # 模式匹配
            for pattern in doc.get("common_patterns", []):
                if any(word in query_lower for word in pattern.split()[:3]):
                    score += 0.5
            if score > 0:
                results.append({**doc, "_score": score, "_match_type": "keyword"})

        results.sort(key=lambda x: x["_score"], reverse=True)
        return results[:top_k]

    @staticmethod
    def _normalize(scores: List[float]) -> List[float]:
        """
        把一路检索的原始分线性压到 [0,1]（除以该路最高分）。

        两路的原始分**量纲不同**：语义路是 FAISS 内积 / 余弦（0~1），
        关键词路是累加命中分（每命中关键词 +2、别名 +1、模式 +0.5，上不封顶）。
        不归一化就直接加权合并，会让关键词路凭量纲碾压语义路 —— 实测出现过
        「匹配度 160%」这类外行数字被当成百分比写进 RAG 提示词。
        """
        if not scores:
            return []
        top = max(scores)
        if top <= 0:
            return [0.0] * len(scores)
        return [s / top for s in scores]

    def hybrid_search(self, query: str, top_k: int = 3) -> List[Dict]:
        """混合检索：语义 + 关键词，各自归一化后加权融合重排"""
        semantic_results = self.search(query, top_k=top_k * 2)
        keyword_results = self._keyword_fallback(query, top_k=top_k)

        # 各路先归一化，再乘权重，使两路可直接比较
        norm_sem = self._normalize([r.get("_score", 0) for r in semantic_results])
        norm_kw = self._normalize([r.get("_score", 0) for r in keyword_results])

        # 合并去重：语义优先入选，避免同一类型被两路重复计入
        seen_ids = set()
        merged = []
        for r, s in zip(semantic_results, norm_sem):
            if r["id"] not in seen_ids:
                r["_raw_score"] = r.get("_score", 0)
                # _score 对外只表示"该路归一化匹配度"，恒在 [0,1]，可直接当百分比展示；
                # 权重只进 _rank_score 参与排序，不污染对外数值（否则会出现 120%）
                r["_score"] = round(s, 4)
                r["_rank_score"] = s * 1.2  # 语义权重略高
                merged.append(r)
                seen_ids.add(r["id"])
        for r, s in zip(keyword_results, norm_kw):
            if r["id"] not in seen_ids:
                r["_raw_score"] = r.get("_score", 0)
                r["_score"] = round(s, 4)
                r["_rank_score"] = s * 0.8
                merged.append(r)
                seen_ids.add(r["id"])

        merged.sort(key=lambda x: x["_rank_score"], reverse=True)
        return merged[:top_k]

    def load_knowledge_base(self) -> List[Dict]:
        """加载知识库并返回文档列表"""
        try:
            with open(self.kb_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("fraud_types", [])
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"[VectorSearch] 知识库加载失败: {e}")
            return []

    def refresh(self) -> bool:
        """热更新索引"""
        docs = self.load_knowledge_base()
        if not docs:
            return False
        if docs == self.documents:
            self._last_load_time = time.time()
            return False  # 无变化
        return self.build_index(docs)


# 全局单例
_global_vs: Optional[VectorSearchEngine] = None


def get_vector_search() -> VectorSearchEngine:
    global _global_vs
    if _global_vs is None:
        _global_vs = VectorSearchEngine()
    return _global_vs
