"""
RAG (检索增强生成) 引擎 v3.0
将知识库检索结果注入 LLM 上下文，生成精准、有依据的反诈回复
支持流式输出、多轮对话记忆、智能路由
"""
import json
import logging
from typing import Dict, List, Optional, Generator

logger = logging.getLogger(__name__)

# 反诈 RAG System Prompt
RAG_SYSTEM_PROMPT = """你是一个专业的反电信网络诈骗AI助手"反诈卫士"。你的职责是帮助用户识别诈骗、普及防骗知识、进行紧急劝阻。

## 核心原则
1. **安全第一**：遇到疑似正在被骗的情况，优先劝阻并给出明确行动步骤
2. **有据可依**：你的回答基于提供的知识库内容，不要编造信息
3. **通俗易懂**：用生活化的语言解释，避免过多专业术语
4. **温暖共情**：对受害者和老年人要特别温和耐心，先安抚再给建议
5. **行动导向**：给出具体可操作的建议，不只是泛泛而谈

## 回答格式
- 紧急情况：🚨 优先标记 + 立即行动步骤
- 科普答疑：📚 简洁解释 + 关键识别点 + 防范建议
- 风险提醒：⚠️ 风险等级标注 + 原因分析 + 建议

## 重要提醒（必须遵守）
- 公检法不会通过电话/视频办案，不存在"安全账户"
- 所有刷单都是诈骗
- 不要向任何人透露验证码
- 不要开启屏幕共享给陌生人
- 遇到诈骗请立即拨打 96110 或 110"""


class RAGEngine:
    """
    RAG 引擎 — 检索 + 增强 + 生成
    
    流程:
        用户输入 → NLP语义搜索(知识库) → 构建增强Prompt → LLM生成回复
    """

    def __init__(self, llm_client=None):
        self._llm_client = llm_client
        self._nlp_pipeline = None

    def _get_llm(self):
        """惰性获取 LLM 客户端"""
        if self._llm_client is None:
            try:
                from engine.llm_client import LLMClient
                from config import Config
                self._llm_client = LLMClient(
                    provider=Config.LLM_PROVIDER,
                    api_key=Config.LLM_API_KEY,
                    api_url=Config.LLM_API_URL,
                    model=Config.LLM_MODEL,
                )
            except Exception as e:
                logger.warning(f"[RAG] LLM客户端初始化失败: {e}")
                from engine.llm_client import LLMClient
                self._llm_client = LLMClient(fallback_to_rules=True)
        return self._llm_client

    def set_llm_client(self, client) -> None:
        """
        注入外部 LLM 客户端。

        用于让 RAG 与 Flask 应用共用同一个实例 —— 否则两边各自持有一个
        LLMClient，管理后台热切换配置时只会刷新其中一个，出现「后台显示已启用、
        RAG 却仍走规则」的不一致。
        """
        self._llm_client = client

    def reset_llm_client(self) -> None:
        """丢弃当前客户端，下次调用时按最新 Config 重建"""
        self._llm_client = None

    def _get_nlp(self):
        """惰性获取 NLP 管道"""
        if self._nlp_pipeline is None:
            try:
                from engine.nlp_pipeline import get_nlp_pipeline
                self._nlp_pipeline = get_nlp_pipeline()
            except Exception:
                pass
        return self._nlp_pipeline

    @property
    def is_available(self) -> bool:
        """LLM 是否可用"""
        llm = self._get_llm()
        return llm.enabled if hasattr(llm, 'enabled') else False

    def _retrieve_knowledge(self, query: str, top_k: int = 3) -> str:
        """
        检索相关知识并格式化为 LLM 可用的上下文
        
        Returns:
            格式化的知识文本
        """
        nlp = self._get_nlp()
        if nlp and nlp.ready:
            context = nlp.get_relevant_knowledge(query, top_k=top_k)
            if context:
                return context

        # 回退：从传统知识检索获取
        try:
            from engine.knowledge_retriever import KnowledgeRetriever
            kr = KnowledgeRetriever()
            results = kr.search(query, top_k=top_k)
            if results:
                parts = []
                for r in results:
                    parts.append(f"【{r['fraud_id']}】(匹配度: {r.get('similarity', 0):.0%})")
                    parts.append(f"描述: {r.get('description', '')}")
                    fraud = kr.get_fraud_by_id(r['fraud_id'])
                    if fraud:
                        patterns = fraud.get("common_patterns", [])[:3]
                        if patterns:
                            parts.append(f"特征: {'; '.join(patterns)}")
                        advice = fraud.get("prevention_advice", [])[:3]
                        if advice:
                            parts.append(f"建议: {'; '.join(advice)}")
                    parts.append("")
                return "\n".join(parts)
        except Exception as e:
            logger.debug(f"[RAG] 知识检索回退失败: {e}")

        return ""

    def _build_prompt(self, user_input: str, retrieved_knowledge: str,
                      dialog_history: List[Dict] = None) -> List[Dict]:
        """
        构建增强的提示消息列表
        
        Returns:
            [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
        """
        messages = [{"role": "system", "content": RAG_SYSTEM_PROMPT}]

        # 注入检索到的知识
        if retrieved_knowledge:
            knowledge_msg = (
                f"## 知识库参考信息\n\n"
                f"以下是与你当前问题相关的反诈骗知识，请参考这些信息来回答问题：\n\n"
                f"{retrieved_knowledge}\n\n"
                f"---\n"
                f"注意：请基于以上知识回答用户问题，如果知识库没有直接答案，可以结合你的通用知识给出建议。"
            )
            messages.append({"role": "system", "content": knowledge_msg})

        # 注入历史对话
        if dialog_history:
            for msg in dialog_history[-6:]:  # 最近6轮
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })

        # 当前用户输入
        messages.append({"role": "user", "content": user_input})

        return messages

    def generate(self, user_input: str, dialog_history: List[Dict] = None,
                 temperature: float = 0.7, max_tokens: int = 1024) -> Optional[str]:
        """
        RAG 增强生成（非流式）
        
        Args:
            user_input: 用户输入
            dialog_history: 历史对话 [{"role": "user/assistant", "content": "..."}, ...]
            
        Returns:
            生成的回复文本，如果 LLM 不可用返回 None
        """
        llm = self._get_llm()
        if not llm.enabled:
            return None

        # 检索知识
        knowledge = self._retrieve_knowledge(user_input)

        # 构建提示
        messages = self._build_prompt(user_input, knowledge, dialog_history)

        # 调用 LLM
        try:
            return llm.chat_with_messages(messages, temperature=temperature, max_tokens=max_tokens)
        except Exception as e:
            logger.error(f"[RAG] 生成失败: {e}")
            return None

    def generate_stream(self, user_input: str, dialog_history: List[Dict] = None,
                        temperature: float = 0.7, max_tokens: int = 1024):
        """
        RAG 增强生成（流式）
        
        Yields:
            生成的文本片段
        """
        llm = self._get_llm()
        if not llm.enabled:
            yield None
            return

        knowledge = self._retrieve_knowledge(user_input)
        messages = self._build_prompt(user_input, knowledge, dialog_history)

        try:
            for chunk in llm.chat_stream(messages, temperature=temperature, max_tokens=max_tokens):
                yield chunk
        except Exception as e:
            logger.error(f"[RAG] 流式生成失败: {e}")
            yield None

    def should_use_rag(self, user_input: str, rule_confidence: float) -> bool:
        """
        智能路由：判断是否应该使用 RAG+LLM 而非纯规则引擎
        
        规则:
        - 规则引擎高置信度 (>0.8) → 用规则
        - 开放性问题 / 复杂描述 → 用 RAG
        - 紧急情况 → 先用规则快速响应，后台 RAG
        """
        if rule_confidence > 0.8:
            return False

        # 开放性问题特征
        open_indicators = [
            "为什么", "怎么办", "如何", "怎样", "什么是",
            "解释", "详细", "具体", "能不能", "可以吗",
            "我想了解", "给我讲讲", "介绍一下",
        ]
        if any(ind in user_input for ind in open_indicators):
            return True

        # 长文本通常是复杂场景描述
        if len(user_input) > 30:
            return True

        # 模糊/困惑表达
        fuzzy_indicators = ["不太确定", "好像", "大概", "可能", "感觉"]
        if any(ind in user_input for ind in fuzzy_indicators):
            return True

        return False


# 全局单例
_rag_engine: Optional[RAGEngine] = None


def get_rag_engine() -> RAGEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine
