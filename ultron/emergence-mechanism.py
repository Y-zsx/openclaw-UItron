#!/usr/bin/env python3
"""
 emergence-mechanism.py - 涌现机制
 夙愿二十六第2世：涌现智能
 功能：复杂系统中的涌现现象、层级涌现、自组织临界性
"""

import asyncio
import random
import math
import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Set, Tuple, Callable
from enum import Enum
from collections import defaultdict, deque
import time
import heapq


class EmergenceType(Enum):
    """涌现类型"""
    SPATIAL = "spatial"           # 空间涌现
    TEMPORAL = "temporal"         # 时间涌现
    BEHAVIORAL = "behavioral"     # 行为涌现
    COGNITIVE = "cognitive"       # 认知涌现
    SOCIAL = "social"             # 社会涌现
    COLLECTIVE = "collective"     # 集体涌现
    EMERGENT_MEMORY = "emergent_memory"  # 记忆涌现
    ADAPTIVE = "adaptive"         # 适应性涌现


@dataclass
class SystemState:
    """系统状态"""
    timestamp: float
    entities: Dict[str, 'Entity']
    interactions: List['Interaction']
    properties: Dict[str, float] = field(default_factory=dict)


@dataclass
class Entity:
    """实体"""
    id: str
    state: Dict = field(default_factory=dict)
    properties: Dict[str, float] = field(default_factory=dict)
    neighbors: Set[str] = field(default_factory=set)
    history: List[Dict] = field(default_factory=list)
    
    def add_property(self, key: str, value: float) -> None:
        self.properties[key] = value
    
    def get_property(self, key: str, default: float = 0.0) -> float:
        return self.properties.get(key, default)


@dataclass
class Interaction:
    """交互"""
    entity_a: str
    entity_b: str
    type: str
    strength: float
    timestamp: float


class EmergenceDetector:
    """涌现检测器"""
    
    def __init__(self):
        self.baseline_properties: Dict[str, float] = {}
        self.emergence_threshold = 0.3
        self.learning_rate = 0.1
    
    def calculate_entropy(self, values: List[float]) -> float:
        if not values:
            return 0.0
        
        # 离散化
        bins = 10
        min_val, max_val = min(values), max(values)
        if min_val == max_val:
            return 0.0
        
        hist = [0] * bins
        for v in values:
            bin_idx = min(bins - 1, int((v - min_val) / (max_val - min_val) * bins))
            hist[bin_idx] += 1
        
        # 计算香农熵
        entropy = 0.0
        total = len(values)
        for count in hist:
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)
        
        return entropy
    
    def calculate_complexity(self, system: SystemState) -> float:
        if not system.entities:
            return 0.0
        
        # 基于实体间差异计算复杂度
        states = [list(e.state.values()) for e in system.entities.values()]
        if not states:
            return 0.0
        
        flat_states = [v for s in states for v in s if isinstance(v, (int, float))]
        
        if len(flat_states) < 2:
            return 0.0
        
        entropy = self.calculate_entropy(flat_states)
        
        # 系统大小
        n = len(system.entities)
        
        # 复杂度 = 熵 * log(系统大小)
        complexity = entropy * math.log2(n + 1)
        
        return complexity
    
    def detect_emergence(self, before: SystemState, after: SystemState) -> Dict[str, float]:
        """检测涌现现象"""
        before_complexity = self.calculate_complexity(before)
        after_complexity = self.calculate_complexity(after)
        
        emergence_strength = max(0, after_complexity - before_complexity)
        
        # 检测不同类型的涌现
        emergence_types = {}
        
        # 空间涌现：检查位置模式
        spatial_score = self._detect_spatial_emergence(before, after)
        emergence_types[EmergenceType.SPATIAL.value] = spatial_score
        
        # 行为涌现：检查行为模式变化
        behavioral_score = self._detect_behavioral_emergence(before, after)
        emergence_types[EmergenceType.BEHAVIORAL.value] = behavioral_score
        
        # 社交涌现：检查交互模式
        social_score = self._detect_social_emergence(before, after)
        emergence_types[EmergenceType.SOCIAL.value] = social_score
        
        # 适应性涌现：检查系统适应性
        adaptive_score = self._detect_adaptive_emergence(before, after)
        emergence_types[EmergenceType.ADAPTIVE.value] = adaptive_score
        
        return {
            "strength": emergence_strength,
            "complexity_change": after_complexity - before_complexity,
            "types": emergence_types,
            "is_emergent": emergence_strength > self.emergence_threshold,
        }
    
    def _detect_spatial_emergence(self, before: SystemState, after: SystemState) -> float:
        """空间涌现检测"""
        if not before.entities or not after.entities:
            return 0.0
        
        # 计算位置熵的变化
        before_x = [e.state.get("x", 0) for e in before.entities.values()]
        after_x = [e.state.get("x", 0) for e in after.entities.values()]
        
        before_entropy = self.calculate_entropy(before_x)
        after_entropy = self.calculate_entropy(after_x)
        
        return max(0, after_entropy - before_entropy)
    
    def _detect_behavioral_emergence(self, before: SystemState, after: SystemState) -> float:
        """行为涌现检测"""
        before_behaviors = set()
        for e in before.entities.values():
            if "behavior" in e.state:
                before_behaviors.add(e.state["behavior"])
        
        after_behaviors = set()
        for e in after.entities.values():
            if "behavior" in e.state:
                after_behaviors.add(e.state["behavior"])
        
        new_behaviors = after_behaviors - before_behaviors
        
        return min(1.0, len(new_behaviors) / 3)
    
    def _detect_social_emergence(self, before: SystemState, after: SystemState) -> float:
        """社交涌现检测"""
        before_connections = sum(len(e.neighbors) for e in before.entities.values())
        after_connections = sum(len(e.neighbors) for e in after.entities.values())
        
        if before_connections == 0:
            return 0.0
        
        connection_change = (after_connections - before_connections) / before_connections
        
        return max(0, connection_change)
    
    def _detect_adaptive_emergence(self, before: SystemState, after: SystemState) -> float:
        """适应性涌现检测"""
        # 检查系统响应环境变化的能力
        before_props = list(before.properties.values())
        after_props = list(after.properties.values())
        
        if not before_props or not after_props:
            return 0.0
        
        # 适应性 = 系统调整能力的度量
        adaptation = sum(abs(a - b) for a, b in zip(before_props, after_props)) / len(before_props)
        
        return min(1.0, adaptation)


class SelfOrganizedCriticality:
    """自组织临界性"""
    
    def __init__(self, threshold: float = 0.8):
        self.threshold = threshold
        self.sandpile_state: Dict[Tuple[int, int], int] = {}
        self.avalanche_history: List[Dict] = []
        self.grid_size = 50
    
    def add_grain(self, x: int, y: int) -> None:
        key = (x % self.grid_size, y % self.grid_size)
        self.sandpile_state[key] = self.sandpile_state.get(key, 0) + 1
    
    def topple(self) -> List[Tuple[int, int]]:
        """雪崩过程"""
        unstable = []
        
        for (x, y), height in self.sandpile_state.items():
            if height >= 4:
                unstable.append((x, y))
        
        if not unstable:
            return []
        
        avalanche_sites = []
        
        for x, y in unstable:
            current_height = self.sandpile_state.get((x, y), 0)
            if current_height >= 4:
                self.sandpile_state[(x, y)] -= 4
                avalanche_sites.append((x, y))
                
                # 分配到邻居
                neighbors = [(x+1, y), (x-1, y), (x, y+1), (x, y-1)]
                for nx, ny in neighbors:
                    nkey = (nx % self.grid_size, ny % self.grid_size)
                    self.sandpile_state[nkey] = self.sandpile_state.get(nkey, 0) + 1
        
        if avalanche_sites:
            self.avalanche_history.append({
                "size": len(avalanche_sites),
                "timestamp": time.time(),
            })
        
        return avalanche_sites
    
    def run_to_stability(self) -> int:
        steps = 0
        max_steps = 1000
        
        while steps < max_steps:
            avalanche = self.topple()
            if not avalanche:
                break
            steps += 1
        
        return steps
    
    def get_power_law_exponent(self) -> float:
        """计算幂律指数"""
        if len(self.avalanche_history) < 10:
            return 0.0
        
        sizes = [a["size"] for a in self.avalanche_history]
        max_size = max(sizes)
        
        if max_size == 0:
            return 0.0
        
        # 简化计算：基于大小分布
        buckets = defaultdict(int)
        for s in sizes:
            bucket = int(math.log2(s + 1))
            buckets[bucket] += 1
        
        # 线性回归计算斜率
        log_sizes = []
        log_counts = []
        
        for bucket, count in sorted(buckets.items()):
            if count > 0:
                log_sizes.append(bucket)
                log_counts.append(math.log2(count))
        
        if len(log_sizes) < 2:
            return 0.0
        
        n = len(log_sizes)
        sum_x = sum(log_sizes)
        sum_y = sum(log_counts)
        sum_xy = sum(x * y for x, y in zip(log_sizes, log_counts))
        sum_x2 = sum(x ** 2 for x in log_sizes)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2)
        
        return abs(slope)


class PhaseTransition:
    """相变检测"""
    
    def __init__(self):
        self.order_parameter_history: List[float] = []
        self.critical_threshold = 0.7
    
    def calculate_order_parameter(self, system: SystemState) -> float:
        """计算序参量"""
        if not system.entities:
            return 0.0
        
        # 使用平均场近似
        properties = []
        for e in system.entities.values():
            for v in e.properties.values():
                properties.append(v)
        
        if not properties:
            return 0.0
        
        mean = sum(properties) / len(properties)
        variance = sum((p - mean) ** 2 for p in properties) / len(properties)
        
        # 序参量 = 1 - (归一化方差)
        normalized_variance = math.sqrt(variance) / (abs(mean) + 1)
        
        return 1.0 - min(1.0, normalized_variance)
    
    def detect_phase_transition(self, system: SystemState) -> Dict:
        """检测相变"""
        order_param = self.calculate_order_parameter(system)
        self.order_parameter_history.append(order_param)
        
        if len(self.order_parameter_history) < 10:
            return {"transition": False, "order_parameter": order_param}
        
        # 计算序参量变化率
        recent = self.order_parameter_history[-10:]
        changes = [abs(recent[i] - recent[i-1]) for i in range(1, len(recent))]
        
        avg_change = sum(changes) / len(changes)
        
        is_transition = avg_change > (1 - self.critical_threshold) * 0.1
        
        return {
            "transition": is_transition,
            "order_parameter": order_param,
            "change_rate": avg_change,
            "phase": "ordered" if order_param > self.critical_threshold else "disordered",
        }


class NetworkEmergence:
    """网络涌现"""
    
    def __init__(self):
        self.nodes: Set[str] = set()
        self.edges: Dict[str, Set[str]] = defaultdict(set)
        self.centrality: Dict[str, float] = {}
        self.community_detected = False
        self.communities: Dict[int, Set[str]] = {}
    
    def add_node(self, node_id: str) -> None:
        self.nodes.add(node_id)
        if node_id not in self.edges:
            self.edges[node_id] = set()
    
    def add_edge(self, node_a: str, node_b: str) -> None:
        self.add_node(node_a)
        self.add_node(node_b)
        self.edges[node_a].add(node_b)
        self.edges[node_b].add(node_a)
    
    def calculate_centrality(self) -> Dict[str, float]:
        """计算度中心性"""
        if not self.nodes:
            return {}
        
        max_degree = max(len(neighbors) for neighbors in self.edges.values()) or 1
        
        self.centrality = {
            node: len(neighbors) / max_degree
            for node, neighbors in self.edges.items()
        }
        
        return self.centrality
    
    def detect_communities(self) -> Dict[int, Set[str]]:
        """社区检测（简化版Label Propagation）"""
        if not self.nodes:
            return {}
        
        labels = {node: i for i, node in enumerate(self.nodes)}
        
        for _ in range(10):  # 迭代次数
            nodes_list = list(self.nodes)
            random.shuffle(nodes_list)
            
            for node in nodes_list:
                neighbor_labels = [labels[n] for n in self.edges[node] if n in labels]
                if neighbor_labels:
                    labels[node] = max(set(neighbor_labels), key=neighbor_labels.count)
        
        self.communities = defaultdict(set)
        for node, label in labels.items():
            self.communities[label].add(node)
        
        self.community_detected = True
        return dict(self.communities)
    
    def calculate_modularity(self) -> float:
        """计算模块度"""
        if not self.community_detected or not self.edges:
            return 0.0
        
        m = sum(len(neighbors) for neighbors in self.edges.values()) / 2
        
        if m == 0:
            return 0.0
        
        Q = 0.0
        
        for community in self.communities.values():
            for node_a in community:
                for node_b in community:
                    if node_b in self.edges[node_a]:
                        ki = len(self.edges[node_a])
                        kj = len(self.edges[node_b])
                        Q += 1 - (ki * kj) / (2 * m)
        
        Q /= (2 * m)
        
        return Q
    
    def get_network_properties(self) -> Dict:
        """获取网络属性"""
        if not self.nodes:
            return {}
        
        degrees = [len(self.edges[n]) for n in self.nodes]
        
        return {
            "node_count": len(self.nodes),
            "edge_count": sum(len(neighbors) for neighbors in self.edges.values()) / 2,
            "avg_degree": sum(degrees) / len(degrees),
            "max_degree": max(degrees),
            "clustering_coefficient": self._calculate_clustering(),
            "communities": len(self.communities),
        }
    
    def _calculate_clustering(self) -> float:
        """计算聚类系数"""
        if not self.nodes:
            return 0.0
        
        clustering_sum = 0.0
        
        for node in self.nodes:
            neighbors = list(self.edges[node])
            k = len(neighbors)
            
            if k < 2:
                continue
            
            edges_between = 0
            for i in range(k):
                for j in range(i + 1, k):
                    if neighbors[j] in self.edges[neighbors[i]]:
                        edges_between += 1
            
            max_edges = k * (k - 1) / 2
            clustering_sum += edges_between / max_edges
        
        return clustering_sum / len(self.nodes) if self.nodes else 0.0


class HierarchyEmergence:
    """层级涌现"""
    
    def __init__(self):
        self.layers: Dict[int, Set[str]] = defaultdict(set)
        self.layer_properties: Dict[int, Dict[str, float]] = {}
    
    def add_entity(self, entity_id: str, layer: int) -> None:
        self.layers[layer].add(entity_id)
    
    def compute_layer_properties(self, layer: int, entities: Dict[str, Entity]) -> Dict[str, float]:
        """计算层属性"""
        layer_entities = [entities[eid] for eid in self.layers[layer] if eid in entities]
        
        if not layer_entities:
            return {}
        
        properties = {}
        
        # 聚合属性
        numeric_props = defaultdict(list)
        for e in layer_entities:
            for k, v in e.properties.items():
                if isinstance(v, (int, float)):
                    numeric_props[k].append(v)
        
        for k, values in numeric_props.items():
            properties[f"{k}_mean"] = sum(values) / len(values)
            properties[f"{k}_sum"] = sum(values)
            properties[f"{k}_std"] = math.sqrt(sum((v - sum(values)/len(values))**2 for v in values) / len(values))
        
        return properties
    
    def detect_emergent_layer(self, system: SystemState) -> Optional[int]:
        """检测新涌现的层级"""
        if len(self.layers) < 2:
            return None
        
        # 比较相邻层的复杂度
        for layer in range(1, max(self.layers.keys()) + 1):
            if layer not in self.layers:
                continue
            
            entities_in_layer = [system.entities[eid] for eid in self.layers[layer] if eid in system.entities]
            
            if not entities_in_layer:
                continue
            
            # 计算层复杂度
            complexity = 0.0
            for e in entities_in_layer:
                complexity += len(e.state) + len(e.properties)
            
            # 如果复杂度显著高于下层，可能有涌现
            if layer > 1 and layer - 1 in self.layers:
                prev_entities = [system.entities[eid] for eid in self.layers[layer - 1] if eid in system.entities]
                if prev_entities:
                    prev_complexity = sum(len(e.state) + len(e.properties) for e in prev_entities)
                    if complexity > prev_complexity * 1.5:
                        return layer
        
        return None


class FeedbackLoop:
    """反馈循环"""
    
    def __init__(self):
        self.positive_loops: List[str] = []
        self.negative_loops: List[str] = []
        self.loop_strength: Dict[str, float] = {}
    
    def add_feedback(self, loop_id: str, is_positive: bool, strength: float = 1.0) -> None:
        if is_positive:
            if loop_id not in self.positive_loops:
                self.positive_loops.append(loop_id)
        else:
            if loop_id not in self.negative_loops:
                self.negative_loops.append(loop_id)
        
        self.loop_strength[loop_id] = strength
    
    def analyze_stability(self) -> Dict:
        """分析系统稳定性"""
        total_positive = sum(self.loop_strength.get(loop, 0) for loop in self.positive_loops)
        total_negative = sum(self.loop_strength.get(loop, 0) for loop in self.negative_loops)
        
        # 如果正反馈大于负反馈，系统可能不稳定（涌现的前兆）
        stability_score = total_negative / (total_positive + 0.1)
        
        return {
            "positive_feedback_count": len(self.positive_loops),
            "negative_feedback_count": len(self.negative_loops),
            "total_positive_strength": total_positive,
            "total_negative_strength": total_negative,
            "stability_score": stability_score,
            "is_stable": stability_score > 1.0,
            "likely_emergence": total_positive > total_negative * 1.5,
        }


class EmergentMemory:
    """涌现记忆系统"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.memory: deque = deque(maxlen=max_size)
        self.patterns: Dict[str, List[Dict]] = defaultdict(list)
        self.association_weights: Dict[Tuple[str, str], float] = {}
    
    def add_experience(self, experience: Dict) -> None:
        self.memory.append({**experience, "timestamp": time.time()})
        
        # 提取特征模式
        features = self._extract_features(experience)
        pattern_key = self._hash_features(features)
        
        self.patterns[pattern_key].append(experience)
    
    def _extract_features(self, experience: Dict) -> Tuple:
        """提取特征"""
        features = []
        for key in sorted(experience.keys()):
            if key == "timestamp":
                continue
            val = experience[key]
            if isinstance(val, (int, float)):
                features.append(int(val))
            elif isinstance(val, str):
                features.append(val[:10])
        return tuple(features)
    
    def _hash_features(self, features: Tuple) -> str:
        return str(hash(features))
    
    def find_similar(self, experience: Dict, threshold: float = 0.7) -> List[Dict]:
        """查找相似经历"""
        features = self._extract_features(experience)
        pattern_key = self._hash_features(features)
        
        similar = self.patterns.get(pattern_key, [])
        
        if similar:
            return similar[:5]
        
        # 模糊匹配
        results = []
        for exp in self.memory:
            similarity = self._calculate_similarity(experience, exp)
            if similarity >= threshold:
                results.append(exp)
        
        return sorted(results, key=lambda x: self._calculate_similarity(experience, x), reverse=True)[:5]
    
    def _calculate_similarity(self, a: Dict, b: Dict) -> float:
        """计算相似度"""
        common_keys = set(a.keys()) & set(b.keys())
        if not common_keys:
            return 0.0
        
        matches = 0
        for key in common_keys:
            if key == "timestamp":
                continue
            if a[key] == b[key]:
                matches += 1
        
        return matches / len(common_keys)
    
    def get_emergent_insights(self) -> List[str]:
        """从记忆中提取涌现洞察"""
        insights = []
        
        if len(self.memory) < 10:
            return insights
        
        # 统计频繁模式
        pattern_counts = defaultdict(int)
        for exp in self.memory:
            pattern_key = self._hash_features(self._extract_features(exp))
            pattern_counts[pattern_key] += 1
        
        # 找出频繁模式
        frequent = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        for pattern, count in frequent:
            if count >= 5:
                insights.append(f"频繁模式出现{count}次")
        
        return insights


class EmergenceSystem:
    """涌现系统 - 主入口"""
    
    def __init__(self):
        self.entities: Dict[str, Entity] = {}
        self.system_state = SystemState(
            timestamp=time.time(),
            entities={},
            interactions=[],
        )
        self.detector = EmergenceDetector()
        self.sandpile = SelfOrganizedCriticality()
        self.phase_transition = PhaseTransition()
        self.network = NetworkEmergence()
        self.hierarchy = HierarchyEmergence()
        self.feedback = FeedbackLoop()
        self.memory = EmergentMemory()
        self.state_history: List[SystemState] = []
    
    def add_entity(self, entity_id: str, properties: Optional[Dict] = None) -> Entity:
        entity = Entity(
            id=entity_id,
            properties=properties or {},
        )
        self.entities[entity_id] = entity
        return entity
    
    def add_interaction(self, entity_a: str, entity_b: str, interaction_type: str, strength: float = 1.0) -> None:
        interaction = Interaction(
            entity_a=entity_a,
            entity_b=entity_b,
            type=interaction_type,
            strength=strength,
            timestamp=time.time(),
        )
        self.system_state.interactions.append(interaction)
        
        # 更新网络
        self.network.add_edge(entity_a, entity_b)
        
        # 更新实体的邻居
        if entity_a in self.entities:
            self.entities[entity_a].neighbors.add(entity_b)
        if entity_b in self.entities:
            self.entities[entity_b].neighbors.add(entity_a)
    
    def update(self) -> Dict:
        """更新系统状态"""
        # 保存之前的状态
        before_state = SystemState(
            timestamp=self.system_state.timestamp,
            entities={k: Entity(id=v.id, state=dict(v.state), properties=dict(v.properties), 
                              neighbors=set(v.neighbors), history=list(v.history))
                     for k, v in self.entities.items()},
            interactions=list(self.system_state.interactions[-100:]),
        )
        
        # 更新系统时间
        self.system_state.timestamp = time.time()
        self.system_state.entities = self.entities
        
        # 运行自组织临界性模型
        if random.random() < 0.1:
            x, y = random.randint(0, 49), random.randint(0, 49)
            self.sandpile.add_grain(x, y)
            self.sandpile.run_to_stability()
        
        # 检测相变
        phase_info = self.phase_transition.detect_phase_transition(self.system_state)
        
        # 计算网络属性
        if self.network.nodes:
            self.network.calculate_centrality()
            self.network.detect_communities()
        
        # 检测涌现
        emergence_info = self.detector.detect_emergence(before_state, self.system_state)
        
        # 分析反馈循环
        feedback_info = self.feedback.analyze_stability()
        
        # 保存状态历史
        self.state_history.append(self.system_state)
        if len(self.state_history) > 100:
            self.state_history = self.state_history[-100:]
        
        return {
            "emergence": emergence_info,
            "phase_transition": phase_info,
            "network_properties": self.network.get_network_properties(),
            "feedback": feedback_info,
            "sandpile_exponent": self.sandpile.get_power_law_exponent(),
            "entity_count": len(self.entities),
            "interaction_count": len(self.system_state.interactions),
        }
    
    def learn_from_interaction(self, entity_a: str, entity_b: str, outcome: Dict) -> None:
        """从交互中学习"""
        # 记录经验
        self.memory.add_experience({
            "entity_a": entity_a,
            "entity_b": entity_b,
            "outcome": outcome,
        })
        
        # 更新实体属性
        if entity_a in self.entities:
            for k, v in outcome.items():
                if isinstance(v, (int, float)):
                    self.entities[entity_a].add_property(k, v)
        
        # 更新网络权重
        key = (min(entity_a, entity_b), max(entity_a, entity_b))
        self.network.association_weights[key] = self.network.association_weights.get(key, 0) + 0.1


def main():
    print("=== 涌现机制测试 ===")
    
    system = EmergenceSystem()
    
    # 创建100个实体
    for i in range(100):
        system.add_entity(f"entity_{i}", {
            "energy": random.uniform(0, 100),
            "coherence": random.uniform(0, 1),
            "activity": random.uniform(0, 1),
        })
    
    print(f"创建了 {len(system.entities)} 个实体")
    
    # 创建随机交互
    for _ in range(500):
        a = random.choice(list(system.entities.keys()))
        b = random.choice(list(system.entities.keys()))
        if a != b:
            system.add_interaction(a, b, "interaction", random.uniform(0.5, 1.0))
    
    print(f"创建了 {len(system.system_state.interactions)} 个交互")
    
    # 模拟系统演化
    for step in range(20):
        result = system.update()
        
        if step % 5 == 0:
            print(f"\n步骤 {step}:")
            print(f"  实体数: {result['entity_count']}")
            print(f"  涌现强度: {result['emergence']['strength']:.3f}")
            print(f"  相变状态: {result['phase_transition']['phase']}")
            print(f"  网络节点: {result['network_properties'].get('node_count', 0)}")
            print(f"  稳定性: {result['feedback']['is_stable']}")
    
    # 测试涌现洞察
    print("\n=== 涌现洞察 ===")
    system.learn_from_interaction("entity_0", "entity_1", {"learning": 0.8, "adaptation": 0.6})
    system.learn_from_interaction("entity_0", "entity_2", {"learning": 0.7, "adaptation": 0.5})
    
    insights = system.memory.get_emergent_insights()
    for insight in insights:
        print(f"  - {insight}")


if __name__ == "__main__":
    main()