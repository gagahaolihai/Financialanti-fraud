"""知识检索引擎 - 支持TF-IDF语义搜索、热加载、交叉引用"""
import json
import os
import re
import math
import time
from collections import Counter
from typing import Optional


class KnowledgeRetriever:
    """知识检索引擎，支持TF-IDF语义搜索、知识关联、快速接入新骗局"""

    def __init__(self, kb_path: str = None):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.kb_path = kb_path or os.path.join(self.base_dir, 'knowledge_base', 'fraud_types.json')
        self.laws_path = os.path.join(self.base_dir, 'knowledge_base', 'laws.json')
        self._knowledge = None
        self._laws = None
        self._tfidf_index = {}
        self._last_load_time = 0
        self._refresh_interval = 60  # 60秒热加载检查
        self._loaded_types = set()
        self.load_knowledge_base()

    def load_knowledge_base(self):
        """加载/热加载知识库"""
        self._knowledge = self._load_json(self.kb_path, {"fraud_types": []})
        self._laws = self._load_json(self.laws_path, {"laws": []})
        self._build_index()
        self._last_load_time = time.time()
        self._loaded_types = {f["id"] for f in self._knowledge.get("fraud_types", [])}

    def _load_json(self, path: str, default: dict) -> dict:
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return default

    def refresh_if_needed(self):
        """热加载检查 - 支持运行时新增骗局快速接入"""
        if time.time() - self._last_load_time > self._refresh_interval:
            current_types = set()
            try:
                with open(self.kb_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                current_types = {f["id"] for f in data.get("fraud_types", [])}
            except Exception:
                pass

            if current_types != self._loaded_types:
                self.load_knowledge_base()
                return True
            self._last_load_time = time.time()
        return False

    def _build_index(self):
        """构建TF-IDF检索索引"""
        self._tfidf_index = {}
        fraud_types = self._knowledge.get("fraud_types", [])

        # 文档集：每个骗局的所有文本建成一个文档
        docs = []
        doc_ids = []
        for fraud in fraud_types:
            text = self._get_fraud_text(fraud)
            docs.append(text)
            doc_ids.append(fraud["id"])

        if not docs:
            return

        # 计算TF-IDF
        self._doc_count = len(docs)
        self._doc_freq = Counter()
        self._term_docs = {}  # term -> set of doc ids
        self._doc_terms = {}  # doc_id -> Counter of terms

        for i, doc in enumerate(docs):
            terms = self._tokenize(doc)
            term_counter = Counter(terms)
            self._doc_terms[doc_ids[i]] = term_counter
            for term in term_counter:
                if term not in self._term_docs:
                    self._term_docs[term] = set()
                self._term_docs[term].add(doc_ids[i])

        for term, doc_set in self._term_docs.items():
            self._doc_freq[term] = len(doc_set)

        # 计算每篇文档的TF-IDF向量
        self._doc_vectors = {}
        for doc_id, term_counter in self._doc_terms.items():
            vector = {}
            doc_len = sum(term_counter.values())
            if doc_len == 0:
                continue
            for term, count in term_counter.items():
                tf = count / doc_len
                idf = math.log((self._doc_count + 1) / (self._doc_freq[term] + 1)) + 1
                vector[term] = tf * idf
            self._doc_vectors[doc_id] = vector

    def _tokenize(self, text: str) -> list:
        """中文分词（基于字符n-gram和关键词）"""
        text = text.lower()
        # 提取中文字符和英文单词
        tokens = []
        # 英文/数字token
        for token in re.findall(r'[a-zA-Z0-9]+', text):
            if len(token) > 1:
                tokens.append(token.lower())
        # 中文2-gram
        chinese_chars = re.findall(r'[一-鿿]', text)
        for i in range(len(chinese_chars) - 1):
            bigram = chinese_chars[i] + chinese_chars[i+1]
            tokens.append(bigram)
        return tokens

    def _get_fraud_text(self, fraud: dict) -> str:
        """将骗局所有文本合并为检索文档"""
        parts = [
            fraud.get("description", ""),
            fraud.get("id", ""),
            " ".join(fraud.get("aliases", [])),
            " ".join(fraud.get("keywords", [])),
            " ".join(fraud.get("common_patterns", [])),
            " ".join(fraud.get("typical_dialogs", [])),
            " ".join(fraud.get("prevention_advice", [])),
            " ".join(fraud.get("victim_analysis", {}).get("target_groups", [])),
        ]
        # 典型案例
        for case in fraud.get("case_studies", []):
            parts.append(case.get("title", ""))
            parts.append(case.get("process", ""))
            parts.append(case.get("lesson", ""))
        return " ".join(parts)

    def search(self, query: str, top_k: int = 3) -> list:
        """语义搜索 - 返回最相关的骗局类型"""
        self.refresh_if_needed()
        if not query or not self._doc_vectors:
            return []

        query_terms = self._tokenize(query)
        if not query_terms:
            return []

        # 计算查询向量
        query_counter = Counter(query_terms)
        query_len = len(query_terms)
        query_vector = {}
        for term, count in query_counter.items():
            tf = count / query_len
            idf = math.log((self._doc_count + 1) / (self._doc_freq.get(term, 0) + 1)) + 1
            query_vector[term] = tf * idf

        # 计算余弦相似度
        scores = []
        for doc_id, doc_vector in self._doc_vectors.items():
            dot_product = sum(query_vector.get(t, 0) * doc_vector.get(t, 0) for t in set(query_vector) & set(doc_vector))
            query_norm = math.sqrt(sum(v*v for v in query_vector.values()))
            doc_norm = math.sqrt(sum(v*v for v in doc_vector.values()))
            if query_norm * doc_norm == 0:
                continue
            similarity = dot_product / (query_norm * doc_norm)
            scores.append((doc_id, similarity))

        scores.sort(key=lambda x: x[1], reverse=True)

        # 返回结果
        results = []
        for doc_id, score in scores[:top_k]:
            fraud = self.get_fraud_by_id(doc_id)
            if fraud:
                results.append({
                    "fraud_id": doc_id,
                    "fraud_name": fraud.get("id", ""),
                    "similarity": round(score, 4),
                    "description": fraud.get("description", ""),
                    "risk_level": fraud.get("risk_level", ""),
                    "matched_keywords": [t for t in query_terms if t in self._doc_terms.get(doc_id, {})]
                })
        return results

    def get_fraud_by_id(self, fraud_id: str) -> Optional[dict]:
        """按ID获取骗局完整信息"""
        self.refresh_if_needed()
        for fraud in self._knowledge.get("fraud_types", []):
            if fraud["id"] == fraud_id or fraud_id in fraud.get("aliases", []):
                return fraud
        return None

    def get_law_by_id(self, law_id: str) -> Optional[dict]:
        """按ID获取法律条文"""
        for law in self._laws.get("laws", []):
            if law["id"] == law_id or law_id in law.get("title", ""):
                return law
        return None

    def get_emergency_contacts(self) -> list:
        """获取紧急联系方式"""
        return self._knowledge.get("general_prevention", {}).get("emergency_contacts",
               self._laws.get("emergency_contacts", []))

    def get_fraud_list(self) -> list:
        """获取所有骗局列表（摘要）"""
        self.refresh_if_needed()
        return [{
            "id": f["id"],
            "name": f["id"],
            "risk_level": f.get("risk_level", ""),
            "description": f.get("description", "")[:100],
            "aliases": f.get("aliases", [])[:5],
            "keywords": f.get("keywords", [])[:10],
            "total_cases": len(f.get("case_studies", [])),
            "total_patterns": len(f.get("common_patterns", []))
        } for f in self._knowledge.get("fraud_types", [])]

    def get_reasoning(self, fraud_id: str) -> dict:
        """获取骗局的推理分析（用于劝阻话术生成）"""
        fraud = self.get_fraud_by_id(fraud_id)
        if not fraud:
            return {}

        return {
            "fraud_id": fraud_id,
            "tactics_analysis": fraud.get("psychological_tactics", []),
            "intervention_templates": fraud.get("intervention_templates", {}),
            "reporting_guidance": fraud.get("reporting_guidance", {}),
            "legal_references": fraud.get("legal_references", []),
            "related_frauds": fraud.get("related_frauds", []),
            "statistics": fraud.get("statistics", {})
        }

    def generate_intervention(self, fraud_id: str, risk_level: str = "high") -> str:
        """根据骗局类型和风险等级生成劝阻话术"""
        fraud = self.get_fraud_by_id(fraud_id)
        if not fraud:
            return ""

        templates = fraud.get("intervention_templates", {})
        template = templates.get(risk_level) or templates.get("high", "")

        if not template:
            # 默认劝阻话术
            template = (
                f"⚠️ **{fraud_id}诈骗风险提醒！**\n\n"
                f"**{fraud.get('description', '')}**\n\n"
                "**防范建议：**\n"
                + "\n".join(f"{i+1}. {a}" for i, a in enumerate(fraud.get("prevention_advice", [])[:3]))
                + "\n\n如有疑问请拨打96110反诈专线咨询。"
            )

        return template

    def get_common_qa(self, question: str = "") -> list:
        """获取常见问题解答"""
        qa_list = self._knowledge.get("general_prevention", {}).get("common_questions", [])
        if not question:
            return qa_list

        results = []
        for qa in qa_list:
            if any(kw in question for kw in qa.get("tags", [])):
                results.append(qa)
            elif any(kw in qa.get("question", "") for kw in self._tokenize(question)):
                results.append(qa)

        return results[:3] if results else qa_list[:2]

    def get_related_frauds(self, fraud_id: str) -> list:
        """获取关联骗局"""
        fraud = self.get_fraud_by_id(fraud_id)
        if not fraud:
            return []
        related_ids = fraud.get("related_frauds", [])
        return [self.get_fraud_by_id(rid) for rid in related_ids if self.get_fraud_by_id(rid)]

    def check_fraud_indicators(self, text: str) -> list:
        """检查文本中包含哪些骗局的典型特征"""
        self.refresh_if_needed()
        matches = []
        for fraud in self._knowledge.get("fraud_types", []):
            match_count = 0
            matched_keywords = []
            for kw in fraud.get("keywords", []):
                if kw in text:
                    match_count += 1
                    matched_keywords.append(kw)
            for pattern in fraud.get("common_patterns", []):
                if any(kw in text for kw in pattern.split()):
                    match_count += 1

            if match_count > 0:
                matches.append({
                    "fraud_id": fraud["id"],
                    "risk_level": fraud.get("risk_level", ""),
                    "match_count": match_count,
                    "confidence": min(match_count / 3, 1.0),
                    "matched_keywords": matched_keywords[:5]
                })

        matches.sort(key=lambda x: x["match_count"], reverse=True)
        return matches

    def get_quick_reply_suggestions(self, context: str = "") -> list:
        """根据上下文生成快捷回复建议"""
        suggestions = [
            "什么是刷单诈骗？",
            "我是不是被骗了？",
            "举报一个链接",
            "我想做情景模拟"
        ]

        if "转账" in context or "汇款" in context:
            suggestions = ["停止转账", "这是诈骗吗", "拨打110", "联系银行止付"] + suggestions
        elif "链接" in context or "网址" in context:
            suggestions = ["分析这个链接", "举报这个网址"] + suggestions

        return suggestions[:6]

    # ========== v3.0 NLP 增强方法 ==========

    def semantic_search(self, query: str, top_k: int = 3) -> list:
        """
        v3.0 语义向量搜索 — 基于 sentence-transformers + FAISS
        自动回退到 TF-IDF
        
        Returns:
            [{"fraud_id": "刷单返利", "similarity": 0.85, "match_type": "semantic", ...}, ...]
        """
        try:
            from engine.nlp_pipeline import get_nlp_pipeline
            pipeline = get_nlp_pipeline()
            if pipeline.ready:
                results = pipeline.semantic_search(query, top_k=top_k)
                if results:
                    return [{
                        "fraud_id": r.get("id", ""),
                        "fraud_name": r.get("id", ""),
                        "similarity": round(r.get("_score", 0), 4),
                        "description": r.get("description", ""),
                        "risk_level": r.get("risk_level", ""),
                        "match_type": r.get("_match_type", "semantic"),
                    } for r in results]
        except Exception as e:
            logger = __import__('logging').getLogger(__name__)
            logger.debug(f"[KnowledgeRetriever] NLP增强搜索失败，回退TF-IDF: {e}")

        # 回退到传统 TF-IDF
        return self.search(query, top_k=top_k)

    def semantic_check_fraud(self, text: str) -> list:
        """
        v3.0 语义诈骗类型检测 — 结合关键词 + 语义相似度
        
        Returns:
            [{"fraud_id": "...", "confidence": 0.85, "match_type": "semantic+keyword"}, ...]
        """
        # 先用传统方法快速筛选
        keyword_matches = self.check_fraud_indicators(text)

        try:
            from engine.nlp_pipeline import get_nlp_pipeline
            pipeline = get_nlp_pipeline()
            if pipeline.ready:
                semantic_matches = pipeline.match_fraud_type(text)
                if semantic_matches:
                    # 合并关键词和语义结果
                    merged = {}
                    for km in keyword_matches:
                        merged[km["fraud_id"]] = {
                            "fraud_id": km["fraud_id"],
                            "risk_level": km.get("risk_level", ""),
                            "confidence": km.get("confidence", 0),
                            "match_type": "keyword",
                            "matched_keywords": km.get("matched_keywords", []),
                        }
                    for fid, score in semantic_matches[:3]:
                        if score > 0.3:
                            if fid in merged:
                                merged[fid]["confidence"] = max(
                                    merged[fid]["confidence"], score
                                )
                                merged[fid]["match_type"] = "semantic+keyword"
                            else:
                                fraud = self.get_fraud_by_id(fid)
                                merged[fid] = {
                                    "fraud_id": fid,
                                    "risk_level": fraud.get("risk_level", "") if fraud else "",
                                    "confidence": score,
                                    "match_type": "semantic",
                                    "matched_keywords": [],
                                }

                    result = sorted(merged.values(), key=lambda x: x["confidence"], reverse=True)
                    return result
        except Exception:
            pass

        return keyword_matches
