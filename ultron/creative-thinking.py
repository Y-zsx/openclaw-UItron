#!/usr/bin/env python3
"""
奥创创造性思维引擎 - 第2世核心组件
联想推理、概念融合、问题重塑、创意生成
"""

import random
import re
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

@dataclass
class Concept:
    """概念节点"""
    id: str
    name: str
    attributes: Set[str] = field(default_factory=set)
    connections: Set[str] = field(default_factory=set)
    
class CreativeEngine:
    """创造性思维引擎"""
    
    def __init__(self):
        self.concepts: Dict[str, Concept] = {}
        self.association_cache: Dict[Tuple[str, str], float] = {}
        self.creativity_history: List[Dict] = []
        self._init_concept_network()
    
    def _init_concept_network(self):
        """初始化概念网络"""
        # 核心概念
        core_concepts = [
            ("ai", {"智能", "计算", "学习", "自动化", "算法"}),
            ("human", {"意识", "情感", "创造", "直觉", "目标"}),
            ("problem", {"挑战", "障碍", "需要", "矛盾", "未知"}),
            ("solution", {"答案", "方法", "路径", "结果", "创新"}),
            ("learning", {"获取", "理解", "应用", "反馈", "改进"}),
            ("memory", {"存储", "回忆", "关联", "模式", "经验"}),
            ("time", {"顺序", "因果", "持续", "变化", "节奏"}),
            ("space", {"结构", "关系", "距离", "位置", "组织"}),
            ("action", {"执行", "改变", "影响", "交互", "结果"}),
            ("value", {"意义", "判断", "优先", "目标", "伦理"}),
        ]
        
        for name, attrs in core_concepts:
            cid = f"c_{name}"
            self.concepts[cid] = Concept(
                id=cid,
                name=name,
                attributes=attrs
            )
        
        # 建立关联
        self._build_associations()
    
    def _build_associations(self):
        """建立概念间关联"""
        concept_names = list(self.concepts.keys())
        
        # 强关联
        strong_links = [
            ("ai", "learning"),
            ("ai", "problem"),
            ("human", "value"),
            ("problem", "solution"),
            ("learning", "memory"),
            ("memory", "time"),
        ]
        
        for c1, c2 in strong_links:
            id1, id2 = f"c_{c1}", f"c_{c2}"
            if id1 in self.concepts and id2 in self.concepts:
                self.concepts[id1].connections.add(id2)
                self.concepts[id2].connections.add(id1)
                self.association_cache[(id1, id2)] = 0.9
                self.association_cache[(id2, id1)] = 0.9
    
    def associate(self, concept1: str, concept2: str) -> float:
        """联想强度计算"""
        key = (concept1, concept2)
        if key in self.association_cache:
            return self.association_cache[key]
        
        # 基础关联计算
        c1 = self.concepts.get(concept1)
        c2 = self.concepts.get(concept2)
        
        if not c1 or not c2:
            return 0.1
        
        # 属性重叠
        overlap = len(c1.attributes & c2.attributes)
        max_attrs = max(len(c1.attributes), len(c2.attributes))
        
        if max_attrs > 0:
            score = overlap / max_attrs
        else:
            score = 0.1
        
        # 距离衰减
        if concept2 in c1.connections:
            score += 0.3
        
        self.association_cache[key] = min(score, 1.0)
        return score
    
    def brainstorm(self, topic: str, count: int = 5) -> List[str]:
        """头脑风暴 - 生成关联概念"""
        result = []
        topic_cid = None
        
        # 找到最相关的概念
        for cid, concept in self.concepts.items():
            if topic.lower() in concept.name.lower():
                topic_cid = cid
                break
        
        if not topic_cid:
            # 创建临时概念
            topic_cid = f"c_temp_{topic}"
            self.concepts[topic_cid] = Concept(
                id=topic_cid,
                name=topic,
                attributes={topic.lower()}
            )
        
        # 收集关联概念
        candidates = []
        for cid, concept in self.concepts.items():
            if cid != topic_cid:
                score = self.associate(topic_cid, cid)
                candidates.append((concept.name, score))
        
        # 排序并选择
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # 添加一些随机性
        random.shuffle(candidates)
        result = [name for name, _ in candidates[:count]]
        
        # 记录
        self.creativity_history.append({
            "type": "brainstorm",
            "topic": topic,
            "results": result,
            "timestamp": datetime.now().isoformat(),
        })
        
        return result
    
    def remix(self, concept1: str, concept2: str) -> Dict:
        """概念融合 - 创造新想法"""
        c1 = self._find_concept(concept1)
        c2 = self._find_concept(concept2)
        
        if not c1 or not c2:
            return {"error": "概念未找到"}
        
        # 融合属性
        new_attrs = c1.attributes | c2.attributes
        new_name = f"{c1.name}-{c2.name}"
        
        # 生成融合概念
        fusion = {
            "name": new_name,
            "attributes": list(new_attrs),
            "parent_concepts": [c1.name, c2.name],
            "novelty_score": self._calculate_novelty(new_attrs),
        }
        
        self.creativity_history.append({
            "type": "remix",
            "inputs": [concept1, concept2],
            "output": fusion,
            "timestamp": datetime.now().isoformat(),
        })
        
        return fusion
    
    def reformulate(self, problem: str) -> List[str]:
        """问题重塑 - 从不同角度看待问题"""
        reformulations = []
        
        # 角度变体
        angles = [
            ("根本原因", f"为什么{problem}？"),
            ("解决方案", f"如何解决{problem}？"),
            ("反面", f"什么不是{problem}？"),
            ("类比", f"{problem}类似于什么？"),
            ("简化", f"{problem}最簡单的形式是什么？"),
            ("扩展", f"{problem}会引发什么问题？"),
        ]
        
        reformulations = [q for _, q in angles]
        
        self.creativity_history.append({
            "type": "reformulate",
            "original": problem,
            "variations": reformulations,
            "timestamp": datetime.now().isoformat(),
        })
        
        return reformulations
    
    def _find_concept(self, name: str) -> Optional[Concept]:
        """查找概念"""
        name = name.lower()
        for concept in self.concepts.values():
            if concept.name.lower() == name:
                return concept
        return None
    
    def _calculate_novelty(self, attributes: Set[str]) -> float:
        """计算新颖度"""
        # 简单的新颖度计算
        known_patterns = {
            {"智能", "计算"}, {"学习", "改进"}, {"意识", "情感"}
        }
        
        for pattern in known_patterns:
            if pattern <= attributes:
                return random.uniform(0.3, 0.6)
        
        return random.uniform(0.7, 1.0)
    
    def get_associations(self, concept: str, depth: int = 2) -> Dict:
        """获取概念关联网络"""
        result = {"root": concept, "connections": []}
        
        root = self._find_concept(concept)
        if not root:
            return result
        
        # 广度优先扩展
        visited = {root.id}
        queue = [(root.id, 0)]
        
        while queue:
            cid, d = queue.pop(0)
            if d >= depth:
                continue
            
            concept = self.concepts.get(cid)
            if not concept:
                continue
            
            for conn_id in concept.connections:
                if conn_id not in visited:
                    visited.add(conn_id)
                    conn = self.concepts[conn_id]
                    result["connections"].append({
                        "name": conn.name,
                        "distance": d + 1,
                        "strength": self.associate(cid, conn_id)
                    })
                    queue.append((conn_id, d + 1))
        
        return result
    
    def get_stats(self) -> Dict:
        """获取创意统计"""
        return {
            "total_concepts": len(self.concepts),
            "total_associations": len(self.association_cache),
            "creativity_count": len(self.creativity_history),
            "types": self._count_types(),
        }
    
    def _count_types(self) -> Dict[str, int]:
        """统计创意类型"""
        counts = defaultdict(int)
        for item in self.creativity_history:
            counts[item.get("type", "unknown")] += 1
        return dict(counts)


def main():
    """测试创造性思维引擎"""
    print("💡 奥创创造性思维引擎 v1.0")
    print("=" * 40)
    
    engine = CreativeEngine()
    
    # 统计
    print("\n📊 引擎统计:")
    stats = engine.get_stats()
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    # 头脑风暴
    print("\n🧠 头脑风暴 'ai':")
    ideas = engine.brainstorm("ai", 5)
    for idea in ideas:
        print(f"  → {idea}")
    
    # 概念融合
    print("\n🔗 概念融合 'ai' + 'human':")
    fusion = engine.remix("ai", "human")
    print(f"  结果: {fusion.get('name')}")
    print(f"  属性: {fusion.get('attributes')}")
    print(f"  新颖度: {fusion.get('novelty_score'):.2f}")
    
    # 问题重塑
    print("\n🔄 问题重塑 '系统崩溃':")
    reform = engine.reformulate("系统崩溃")
    for q in reform:
        print(f"  → {q}")
    
    print("\n✅ 创造性思维引擎运行正常")


if __name__ == "__main__":
    main()