"""
语义意图分类器 v3.0
基于语义向量相似度的意图分类，替代纯正则匹配
支持零样本分类 + 规则兜底
"""
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 意图分类的语义锚点描述（零样本分类用）
INTENT_ANCHORS = {
    "greetings": [
        "你好，我想打个招呼",
        "初次见面，问候一下",
        "在吗，我想开始对话",
    ],
    "help_requests": [
        "我遇到了困难需要帮助",
        "紧急求助，我可能被骗了",
        "怎么办，我需要援助",
        "帮帮我，我不知道该怎么办",
    ],
    "report_intents": [
        "我要举报一个诈骗电话",
        "我发现可疑链接想举报",
        "我要投诉一个骗子",
        "举报诈骗网站",
    ],
    "knowledge_queries": [
        "什么是刷单诈骗",
        "请解释一下冒充公检法诈骗",
        "给我讲讲杀猪盘的套路",
        "我想了解防骗知识",
    ],
    "scenario_requests": [
        "我想做情景模拟训练",
        "给我一个防骗闯关",
        "我要练习识别骗局",
        "来一个诈骗场景测试",
    ],
    "self_check": [
        "帮我看看这是不是诈骗",
        "我是不是被骗了",
        "这个链接安全吗",
        "帮我分析一下这件事",
    ],
    "fraud_inquiry": [
        "刷单返利是怎么回事",
        "冒充公检法是怎么骗人的",
        "虚假投资的套路是什么",
        "游戏交易诈骗是什么",
    ],
    "legal_queries": [
        "诈骗罪怎么判刑",
        "帮信罪是什么",
        "相关法律条文",
        "报警立案标准",
    ],
    "emergency": [
        "我正在给骗子转账，已经转出去了",
        "紧急！我刚把钱转到安全账户了",
        "我已经把钱转出去了，怎么办",
        "我已经按对方说的操作完了",
    ],
    "describe_situation": [
        "有人加我说可以兼职赚钱",
        "我接到一个公安局的电话",
        "有人在微信群里发了个链接",
        "对方让我下载一个APP",
    ],
    "provide_info": [
        "我的手机号是13812345678",
        "我的身份证号是320101199001011234",
        "这是我的银行卡号",
        "这是我的验证码",
        "我提供一下我的个人信息",
        "我的联系方式是13812345678",
    ],
    "confusion": [
        "我听不懂你在说什么",
        "能不能简单点说",
        "太复杂了我不理解",
        "说人话",
    ],
    "fear_anxiety": [
        "我很害怕被骗",
        "好担心我的钱没了",
        "我现在很紧张",
        "吓死我了",
    ],
    "elderly_identity": [
        "我年纪大了不太懂",
        "我是老年人",
        "我退休了",
        "我今年六十多了",
    ],
    "thanks": [
        "谢谢你帮了我",
        "非常感谢",
        "太感谢了",
    ],
}


class SemanticIntentClassifier:
    """语义意图分类器 — 基于向量相似度的零样本分类"""

    def __init__(self):
        self._encoder = None
        self._anchor_vectors: Dict[str, np.ndarray] = {}
        self._ready = False
        self._intent_list = list(INTENT_ANCHORS.keys())

    def _get_encoder(self):
        if self._encoder is None:
            from engine.nlp_encoder import get_semantic_encoder
            self._encoder = get_semantic_encoder()
        return self._encoder

    @property
    def ready(self) -> bool:
        return self._ready

    def load(self) -> bool:
        """预计算意图锚点向量"""
        if self._ready:
            return True

        encoder = self._get_encoder()
        if not encoder.load():
            logger.warning("[IntentClassifier] 编码器未就绪，意图分类回退规则模式")
            return False

        logger.info("[IntentClassifier] 正在构建意图锚点向量...")
        for intent, anchors in INTENT_ANCHORS.items():
            vecs = encoder.encode_batch(anchors)
            if vecs is not None:
                # 使用平均向量作为意图锚点
                self._anchor_vectors[intent] = vecs.mean(axis=0)

        self._ready = True
        logger.info(f"[IntentClassifier] 意图锚点构建完成 ({len(self._anchor_vectors)} 类)")
        return True

    def classify(self, text: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """
        分类意图，返回 [(intent, confidence), ...] 按置信度降序
        
        置信度 > 0.7: 高置信度
        置信度 0.4-0.7: 中等置信度
        置信度 < 0.4: 低置信度
        """
        if not text.strip():
            return [("greetings", 1.0)]

        if not self.load():
            return []  # 回退到规则模式

        encoder = self._get_encoder()
        query_vec = encoder.encode(text)
        if query_vec is None:
            return []

        scores = []
        for intent, anchor_vec in self._anchor_vectors.items():
            sim = float(np.dot(query_vec, anchor_vec))
            scores.append((intent, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def classify_top1(self, text: str, min_confidence: float = 0.35) -> Tuple[str, float]:
        """返回最高置信度意图"""
        results = self.classify(text, top_k=1)
        if not results:
            return ("unknown", 0.0)
        intent, score = results[0]
        if score < min_confidence:
            return ("unknown", score)
        return (intent, score)

    def get_fraud_type_scores(self, text: str, fraud_types: List[Dict]) -> List[Tuple[str, float]]:
        """计算文本与各诈骗类型的相似度"""
        if not self.load():
            return []

        encoder = self._get_encoder()
        query_vec = encoder.encode(text)
        if query_vec is None:
            return []

        # 构建诈骗类型描述文本
        type_descs = []
        type_ids = []
        for ft in fraud_types:
            desc = f"{ft.get('id', '')} {ft.get('description', '')} " + \
                   " ".join(ft.get("keywords", [])[:10])
            type_descs.append(desc)
            type_ids.append(ft.get("id", ""))

        type_vecs = encoder.encode_batch(type_descs)
        if type_vecs is None:
            return []

        similarities = np.dot(type_vecs, query_vec)
        ranked = sorted(
            zip(type_ids, similarities),
            key=lambda x: x[1],
            reverse=True
        )
        return [(tid, float(score)) for tid, score in ranked]


# 全局单例
_global_classifier: Optional[SemanticIntentClassifier] = None


def get_intent_classifier() -> SemanticIntentClassifier:
    global _global_classifier
    if _global_classifier is None:
        _global_classifier = SemanticIntentClassifier()
    return _global_classifier
