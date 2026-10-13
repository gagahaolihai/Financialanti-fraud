"""
现代NLP语义向量编码器 v3.0
基于 sentence-transformers 的语义向量编码，替代 TF-IDF
支持中英文混合语义理解
"""
import os
import logging
import numpy as np
from typing import List, Optional, Union

# 国内用户自动使用 HuggingFace 镜像
if "HF_ENDPOINT" not in os.environ:
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

# 离线模式：设置此环境变量后，不尝试从网络下载任何模型
_OFFLINE_MODE = os.environ.get("NLP_OFFLINE_MODE", "").lower() in ("1", "true", "yes")
if _OFFLINE_MODE:
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

logger = logging.getLogger(__name__)

# 惰性导入，避免启动时间过长
_encoder_model = None
_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
_VECTOR_DIM = 384  # MiniLM 的输出维度

# 本地模型路径（打包到项目中，零网络依赖）
_LOCAL_MODEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "models", "paraphrase-multilingual-MiniLM-L12-v2"
)


class SemanticEncoder:
    """语义向量编码器 — 将文本转换为高维语义向量"""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or _MODEL_NAME
        self._model = None
        self.vector_dim = _VECTOR_DIM
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready

    def load(self) -> bool:
        """加载模型（本地优先，零网络支持）"""
        if self._ready:
            return True
        try:
            from sentence_transformers import SentenceTransformer

            # 策略1: 本地打包模型（零网络，比赛环境推荐）
            if os.path.isdir(_LOCAL_MODEL_PATH) and os.path.exists(
                os.path.join(_LOCAL_MODEL_PATH, "model.safetensors")
            ):
                logger.info(f"[NLP] 加载本地模型: {_LOCAL_MODEL_PATH}")
                self._model = SentenceTransformer(
                    _LOCAL_MODEL_PATH,
                    local_files_only=True
                )
            # 策略2: HuggingFace 缓存（已下载过）
            elif not _OFFLINE_MODE:
                logger.info(f"[NLP] 尝试下载/缓存模型: {self.model_name}")
                self._model = SentenceTransformer(self.model_name)
            else:
                logger.warning("[NLP] 离线模式但本地模型不存在")
                return False

            try:
                self.vector_dim = self._model.get_embedding_dimension()
            except AttributeError:
                self.vector_dim = self._model.get_sentence_embedding_dimension()
            self._ready = True
            logger.info(f"[NLP] 语义模型就绪 (dim={self.vector_dim})")
            return True
        except Exception as e:
            logger.warning(f"[NLP] 语义模型加载失败，回退到规则模式: {e}")
            return False

    def encode(self, text: str) -> Optional[np.ndarray]:
        """编码单条文本为语义向量"""
        if not self.load():
            return None
        try:
            return self._model.encode(text, normalize_embeddings=True)
        except Exception as e:
            logger.error(f"[NLP] 编码失败: {e}")
            return None

    def encode_batch(self, texts: List[str], batch_size: int = 32) -> Optional[np.ndarray]:
        """批量编码文本"""
        if not self.load():
            return None
        try:
            return self._model.encode(
                texts,
                normalize_embeddings=True,
                batch_size=batch_size,
                show_progress_bar=False,
            )
        except Exception as e:
            logger.error(f"[NLP] 批量编码失败: {e}")
            return None

    def similarity(self, text1: str, text2: str) -> float:
        """计算两句文本的语义相似度 [0, 1]"""
        v1 = self.encode(text1)
        v2 = self.encode(text2)
        if v1 is None or v2 is None:
            return 0.0
        return float(np.dot(v1, v2))

    def most_similar(self, query: str, candidates: List[str]) -> List[tuple]:
        """从候选列表中找出最相似的文本，返回 (index, score) 排序"""
        if not candidates:
            return []
        query_vec = self.encode(query)
        if query_vec is None:
            return []
        candidate_vecs = self.encode_batch(candidates)
        if candidate_vecs is None:
            return []
        similarities = np.dot(candidate_vecs, query_vec)
        ranked = sorted(
            enumerate(similarities),
            key=lambda x: x[1],
            reverse=True
        )
        return [(idx, float(score)) for idx, score in ranked]


# 全局单例
_global_encoder: Optional[SemanticEncoder] = None


def get_semantic_encoder() -> SemanticEncoder:
    """获取全局语义编码器单例"""
    global _global_encoder
    if _global_encoder is None:
        _global_encoder = SemanticEncoder()
    return _global_encoder
