"""
诈骗知识图谱 - 构建诈骗类型间的关联网络，支持关联推理和风险传播分析
使用 NetworkX 构建有向图，节点为诈骗类型/手法/群体/场景
"""
import json
import os
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    logger.warning("networkx 未安装，知识图谱功能受限。pip install networkx")


class FraudKnowledgeGraph:
    """诈骗知识图谱 - 实体关系网络"""

    # 关系类型定义
    RELATION_TYPES = {
        "related_to": "关联骗局",
        "leads_to": "升级为",        # 刷单 → 虚假投资
        "shares_tactic": "共享手法",  # 使用相似心理操控
        "targets_same": "相同群体",   # 针对同一人群
        "uses_channel": "利用渠道",   # 使用同一传播渠道
        "evolution_of": "变种自",     # 从某骗局演变而来
        "collateral": "伴随风险",     # 可能同时发生的风险
    }

    # 节点颜色（前端可视化用）
    NODE_COLORS = {
        "fraud_type": "#e74c3c",     # 诈骗类型 - 红色
        "tactic": "#f39c12",         # 手法 - 橙色
        "target": "#3498db",         # 群体 - 蓝色
        "channel": "#2ecc71",        # 渠道 - 绿色
        "risk": "#9b59b6",           # 风险 - 紫色
    }

    def __init__(self, kb_path: str = None):
        self.graph = nx.DiGraph() if HAS_NETWORKX else None
        self.kb_path = kb_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'knowledge_base', 'fraud_types.json'
        )
        self._built = False

    def build(self):
        """从知识库构建知识图谱"""
        if not HAS_NETWORKX:
            logger.warning("networkx 未安装，跳过知识图谱构建")
            return

        try:
            with open(self.kb_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"加载知识库失败: {e}")
            return

        fraud_types = data.get("fraud_types", [])
        if not fraud_types:
            logger.warning("知识库为空，无法构建图谱")
            return

        # 添加节点
        for fraud in fraud_types:
            fid = fraud["id"]
            # 诈骗类型节点
            self.graph.add_node(fid, type="fraud_type",
                                risk_level=fraud.get("risk_level", "medium"),
                                description=fraud.get("description", "")[:50])

            # 手法节点
            for tactic in fraud.get("psychological_tactics", []):
                tactic_id = f"tactic_{hash(tactic) % 10000}"
                self.graph.add_node(tactic_id, type="tactic",
                                    label=tactic[:30])
                self.graph.add_edge(fid, tactic_id, relation="uses_tactic")

            # 受害群体节点
            for group in fraud.get("victim_analysis", {}).get("target_groups", []):
                gid = f"target_{group}"
                self.graph.add_node(gid, type="target", label=group)
                self.graph.add_edge(fid, gid, relation="targets")

            # 场景节点
            for scene in fraud.get("victim_analysis", {}).get("common_scenarios", []):
                sid = f"channel_{scene}"
                self.graph.add_node(sid, type="channel", label=scene)
                self.graph.add_edge(fid, sid, relation="uses_channel")

            # 关联骗局
            for related in fraud.get("related_frauds", []):
                self.graph.add_edge(fid, related, relation="related_to")

        # 跨骗局关联：共享手法
        self._build_shared_tactic_edges(fraud_types)

        # 跨骗局关联：共享场景
        self._build_shared_channel_edges(fraud_types)

        self._built = True
        logger.info(f"✅ 知识图谱构建完成: {self.graph.number_of_nodes()} 节点, "
                    f"{self.graph.number_of_edges()} 条边")

    def _build_shared_tactic_edges(self, fraud_types: list):
        """构建共享心理手法的关联边"""
        tactic_map = {}
        for fraud in fraud_types:
            fid = fraud["id"]
            for tactic in fraud.get("psychological_tactics", []):
                key = tactic[:20]  # 将手法截断作为分组键
                if key not in tactic_map:
                    tactic_map[key] = []
                tactic_map[key].append(fid)

        for key, frauds in tactic_map.items():
            if len(frauds) >= 2:
                for i in range(len(frauds)):
                    for j in range(i + 1, len(frauds)):
                        if not self.graph.has_edge(frauds[i], frauds[j]):
                            self.graph.add_edge(frauds[i], frauds[j],
                                                relation="shares_tactic")

    def _build_shared_channel_edges(self, fraud_types: list):
        """构建共享传播渠道的关联边"""
        channel_map = {}
        for fraud in fraud_types:
            fid = fraud["id"]
            for scene in fraud.get("victim_analysis", {}).get("common_scenarios", []):
                if scene not in channel_map:
                    channel_map[scene] = []
                channel_map[scene].append(fid)

        for channel, frauds in channel_map.items():
            if len(frauds) >= 2:
                for i in range(len(frauds)):
                    for j in range(i + 1, len(frauds)):
                        if not self.graph.has_edge(frauds[i], frauds[j]):
                            self.graph.add_edge(frauds[i], frauds[j],
                                                relation="shares_channel")

    # ========== 查询接口 ==========

    def get_related_frauds_deep(self, fraud_id: str, max_depth: int = 2) -> List[dict]:
        """深度获取关联骗局（支持多跳）"""
        if not HAS_NETWORKX or not self._built:
            return []

        related = {}
        if fraud_id not in self.graph:
            return []

        from collections import deque
        visited = {fraud_id}
        queue = deque([(fraud_id, 0)])
        bfs_order = []

        while queue:
            node, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for neighbor in self.graph.neighbors(node):
                if neighbor not in visited:
                    visited.add(neighbor)
                    edge_data = self.graph.get_edge_data(node, neighbor)
                    rel = edge_data.get("relation", "related") if edge_data else "related"
                    node_data = self.graph.nodes[neighbor]
                    if node_data.get("type") == "fraud_type":
                        related[neighbor] = {
                            "fraud_id": neighbor,
                            "relation": rel,
                            "depth": depth + 1,
                            "risk_level": node_data.get("risk_level", ""),
                        }
                    queue.append((neighbor, depth + 1))

        return list(related.values())

    def find_risk_path(self, from_fraud: str, to_fraud: str) -> List[str]:
        """查找两个骗局之间的最短路径（风险传播链）"""
        if not HAS_NETWORKX or not self._built:
            return []
        try:
            path = nx.shortest_path(self.graph, from_fraud, to_fraud)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def get_hot_channels(self, top_n: int = 5) -> List[dict]:
        """获取最高风险的传播渠道"""
        if not HAS_NETWORKX or not self._built:
            return []
        channels = {}
        for node, data in self.graph.nodes(data=True):
            if data.get("type") == "channel":
                degree = self.graph.degree(node)
                fraud_types = []
                for neighbor in self.graph.neighbors(node):
                    if self.graph.nodes[neighbor].get("type") == "fraud_type":
                        fraud_types.append(neighbor)
                if fraud_types:
                    channels[node] = {
                        "channel": data.get("label", node),
                        "fraud_count": len(fraud_types),
                        "fraud_types": fraud_types,
                        "risk_score": degree
                    }
        return sorted(channels.values(), key=lambda x: x["risk_score"], reverse=True)[:top_n]

    def get_graph_stats(self) -> dict:
        """获取图谱统计信息"""
        if not HAS_NETWORKX or not self._built:
            return {"built": False}
        return {
            "built": True,
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "fraud_types": len([n for n, d in self.graph.nodes(data=True)
                                if d.get("type") == "fraud_type"]),
            "channels": len([n for n, d in self.graph.nodes(data=True)
                             if d.get("type") == "channel"]),
            "targets": len([n for n, d in self.graph.nodes(data=True)
                            if d.get("type") == "target"]),
            "density": round(nx.density(self.graph), 4) if HAS_NETWORKX else 0,
        }

    def to_vis_json(self) -> dict:
        """导出为 Vis.js 可视化格式（前端展示用）"""
        if not HAS_NETWORKX or not self._built:
            return {"nodes": [], "edges": []}

        nodes = []
        for n, data in self.graph.nodes(data=True):
            node_type = data.get("type", "unknown")
            nodes.append({
                "id": n,
                "label": data.get("label", n),
                "group": node_type,
                "color": self.NODE_COLORS.get(node_type, "#95a5a6"),
                "title": data.get("description", ""),
                "risk_level": data.get("risk_level", ""),
            })

        edges = []
        for u, v, data in self.graph.edges(data=True):
            edges.append({
                "from": u,
                "to": v,
                "label": self.RELATION_TYPES.get(data.get("relation", "related"), "关联"),
                "arrows": "to",
            })

        return {"nodes": nodes, "edges": edges}
