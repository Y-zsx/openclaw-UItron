#!/usr/bin/env python3
"""
涌现机制 (Emergence Mechanism)
奥创智能体生态系统 - 第2世：涌现智能
"""

import asyncio
import random
import math
import json
import time
from typing import List, Dict, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import heapq


class EmergenceType(Enum):
    """涌现类型"""
    SPATIAL = "spatial"              # 空间涌现
    TEMPORAL = "temporal"            # 时间涌现
    BEHAVIORAL = "behavioral"        # 行为涌现
    COGNITIVE = "cognitive"          # 认知涌现
    SOCIAL = "social"                # 社会涌现
    COLLECTIVE = "collective"        # 集体涌现
    EMOTIONAL = "emotional"          # 情感涌现
    CREATIVE = "creative"            # 创造性涌现


class PatternType(Enum):
    """模式类型"""
    CLUSTER = "cluster"              # 聚类
    CHAIN = "chain"                  # 链式
    NETWORK = "network"              # 网络
    WAVE = "wave"                    # 波
    SPIRAL = "spiral"                # 螺旋
    GRID = "grid"                    # 网格
    HIERARCHY = "hierarchy"          # 层级
    CYCLE = "cycle"                  # 循环


@dataclass
class EmergentProperty:
    """涌现属性"""
    name: str
    emergence_type: EmergenceType
    strength: float
    stability: float
    components: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Pattern:
    """模式"""
    pattern_type: PatternType
    confidence: float
    nodes: List[str]
    edges: List[Tuple[str, str]]
    center: Optional[Tuple[float, float]] = None
    radius: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentFeature:
    """智能体特征"""
    agent_id: str
    position: Tuple[float, float]
    velocity: Tuple[float, float]
    acceleration: Tuple[float, float]
    energy: float
    state: str
    neighbors: List[str]
    attributes: Dict[str, Any] = field(default_factory=dict)


class EmergenceDetector:
    """涌现检测器"""
    
    def __init__(self):
        self.patterns: List[Pattern] = []
        self.emergent_properties: List[EmergentProperty] = []
        self.detection_history: List[Dict[str, Any]] = []
        self.threshold_config = {
            "spatial_distance": 30.0,
            "temporal_window": 10,
            "behavior_similarity": 0.7,
            "pattern_confidence": 0.6,
            "stability_window": 5
        }
        self.clustering_cache: Dict[str, List[Set[str]]] = {}
        self.correlation_matrix: Dict[Tuple[str, str], float] = {}
    
    def detect_spatial_patterns(self, agents: List[AgentFeature]) -> List[Pattern]:
        """检测空间模式"""
        patterns = []
        
        clusters = self._detect_clusters(agents)
        for cluster in clusters:
            if len(cluster) >= 3:
                center = self._calculate_center(agents, cluster)
                patterns.append(Pattern(
                    pattern_type=PatternType.CLUSTER,
                    confidence=min(1.0, len(cluster) / 10),
                    nodes=list(cluster),
                    edges=self._create_cluster_edges(cluster),
                    center=center,
                    radius=self._calculate_radius(agents, cluster, center)
                ))
        
        chains = self._detect_chains(agents)
        for chain in chains:
            if len(chain) >= 4:
                patterns.append(Pattern(
                    pattern_type=PatternType.CHAIN,
                    confidence=min(1.0, len(chain) / 8),
                    nodes=chain,
                    edges=self._create_chain_edges(chain)
                ))
        
        waves = self._detect_waves(agents)
        for wave in waves:
            patterns.append(Pattern(
                pattern_type=PatternType.WAVE,
                confidence=0.7,
                nodes=wave["nodes"],
                edges=wave["edges"],
                metadata={"direction": wave.get("direction")}
            ))
        
        spirals = self._detect_spirals(agents)
        for spiral in spirals:
            patterns.append(Pattern(
                pattern_type=PatternType.SPIRAL,
                confidence=0.75,
                nodes=spiral["nodes"],
                edges=spiral["edges"],
                center=spiral.get("center"),
                radius=spiral.get("radius")
            ))
        
        self.patterns = patterns
        return patterns
    
    def _detect_clusters(self, agents: List[AgentFeature]) -> List[Set[str]]:
        """检测聚类"""
        clusters = []
        visited: Set[str] = set()
        
        for agent in agents:
            if agent.agent_id in visited:
                continue
            
            cluster = set()
            queue = [agent.agent_id]
            
            while queue:
                current_id = queue.pop(0)
                if current_id in visited:
                    continue
                
                visited.add(current_id)
                cluster.add(current_id)
                
                current = next((a for a in agents if a.agent_id == current_id), None)
                if not current:
                    continue
                
                for neighbor_id in current.neighbors:
                    if neighbor_id not in visited:
                        neighbor = next((a for a in agents if a.agent_id == neighbor_id), None)
                        if neighbor and self._distance(current.position, neighbor.position) < self.threshold_config["spatial_distance"]:
                            queue.append(neighbor_id)
            
            if len(cluster) >= 2:
                clusters.append(cluster)
        
        return clusters
    
    def _detect_chains(self, agents: List[AgentFeature]) -> List[List[str]]:
        """检测链式结构"""
        chains = []
        
        adjacency = defaultdict(list)
        for agent in agents:
            adjacency[agent.agent_id] = agent.neighbors[:]
        
        for agent in agents:
            if len(adjacency[agent.agent_id]) == 1:
                chain = [agent.agent_id]
                current = agent.agent_id
                visited = {agent.agent_id}
                
                while len(adjacency[current]) == 1:
                    next_agent_id = adjacency[current][0]
                    if next_agent_id in visited:
                        break
                    chain.append(next_agent_id)
                    visited.add(next_agent_id)
                    current = next_agent_id
                
                if len(chain) >= 4:
                    chains.append(chain)
        
        return chains
    
    def _detect_waves(self, agents: List[AgentFeature]) -> List[Dict[str, Any]]:
        """检测波动模式"""
        waves = []
        
        if len(agents) < 5:
            return waves
        
        sorted_by_x = sorted(agents, key=lambda a: a.position[0])
        
        wave_nodes = []
        for i in range(len(sorted_by_x) - 1):
            current = sorted_by_x[i]
            next_agent = sorted_by_x[i + 1]
            
            dist = self._distance(current.position, next_agent.position)
            if dist < 50:
                wave_nodes.append(current.agent_id)
        
        if len(wave_nodes) >= 5:
            edges = [(wave_nodes[i], wave_nodes[i+1]) for i in range(len(wave_nodes)-1)]
            waves.append({
                "nodes": wave_nodes,
                "edges": edges,
                "direction": "horizontal"
            })
        
        return waves
    
    def _detect_spirals(self, agents: List[AgentFeature]) -> List[Dict[str, Any]]:
        """检测螺旋模式"""
        spirals = []
        
        if len(agents) < 6:
            return spirals
        
        positions = [(a.agent_id, a.position) for a in agents]
        
        for i, (id1, pos1) in enumerate(positions):
            for j, (id2, pos2) in enumerate(positions):
                if i >= j:
                    continue
                
                center = ((pos1[0] + pos2[0]) / 2, (pos1[1] + pos2[1]) / 2)
                
                angles = []
                for aid, pos in positions:
                    angle = math.atan2(pos[1] - center[1], pos[0] - center[0])
                    angles.append((aid, angle))
                
                angles.sort(key=lambda x: x[1])
                
                spiral_detected = True
                prev_angle = angles[0][1]
                for k in range(1, len(angles)):
                    diff = angles[k][1] - prev_angle
                    if abs(diff) > math.pi / 2:
                        spiral_detected = False
                        break
                    prev_angle = angles[k][1]
                
                if spiral_detected:
                    node_list = [a[0] for a in angles]
                    edge_list = [(node_list[m], node_list[m+1]) for m in range(len(node_list)-1)]
                    radius = sum(self._distance(p[1], center) for p in positions) / len(positions)
                    
                    spirals.append({
                        "nodes": node_list,
                        "edges": edge_list,
                        "center": center,
                        "radius": radius
                    })
                    break
        
        return spirals
    
    def _calculate_center(self, agents: List[AgentFeature], cluster: Set[str]) -> Tuple[float, float]:
        """计算聚类中心"""
        cluster_agents = [a for a in agents if a.agent_id in cluster]
        if not cluster_agents:
            return (0, 0)
        
        sum_x = sum(a.position[0] for a in cluster_agents)
        sum_y = sum(a.position[1] for a in cluster_agents)
        return (sum_x / len(cluster_agents), sum_y / len(cluster_agents))
    
    def _calculate_radius(self, agents: List[AgentFeature], cluster: Set[str], 
                          center: Tuple[float, float]) -> float:
        """计算聚类半径"""
        cluster_agents = [a for a in agents if a.agent_id in cluster]
        if not cluster_agents:
            return 0
        
        distances = [self._distance(a.position, center) for a in cluster_agents]
        return sum(distances) / len(distances)
    
    def _distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """计算距离"""
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def _create_cluster_edges(self, cluster: Set[str]) -> List[Tuple[str, str]]:
        """创建聚类边"""
        return [(a, b) for i, a in enumerate(cluster) for b in list(cluster)[i+1:i+3]]
    
    def _create_chain_edges(self, chain: List[str]) -> List[Tuple[str, str]]:
        """创建链式边"""
        return [(chain[i], chain[i+1]) for i in range(len(chain) - 1)]
    
    def detect_temporal_patterns(self, history: List[List[AgentFeature]]) -> List[Pattern]:
        """检测时间模式"""
        patterns = []
        
        if len(history) < 3:
            return patterns
        
        cycles = self._detect_cycles(history)
        patterns.extend(cycles)
        
        trends = self._detect_trends(history)
        patterns.extend(trends)
        
        oscillations = self._detect_oscillations(history)
        patterns.extend(oscillations)
        
        return patterns
    
    def _detect_cycles(self, history: List[List[AgentFeature]]) -> List[Pattern]:
        """检测循环模式"""
        cycles = []
        
        metric_values = []
        for snapshot in history:
            total_energy = sum(a.energy for a in snapshot)
            metric_values.append(total_energy)
        
        if len(metric_values) >= 10:
            cycle_length = self._find_cycle_length(metric_values)
            if cycle_length > 0:
                cycles.append(Pattern(
                    pattern_type=PatternType.CYCLE,
                    confidence=0.7,
                    nodes=[f"cycle_{i}" for i in range(cycle_length)],
                    edges=[],
                    metadata={"length": cycle_length, "metric": "energy"}
                ))
        
        return cycles
    
    def _detect_trends(self, history: List[List[AgentFeature]]) -> List[Pattern]:
        """检测趋势"""
        trends = []
        
        if len(history) < 5:
            return trends
        
        velocities = []
        for snapshot in history:
            avg_velocity = sum(math.sqrt(v[0]**2 + v[1]**2) for a in snapshot for v in [a.velocity]) / len(snapshot)
            velocities.append(avg_velocity)
        
        if velocities[-1] > velocities[0] * 1.5:
            trends.append(Pattern(
                pattern_type=PatternType.CHAIN,
                confidence=0.6,
                nodes=["trend_up"],
                edges=[],
                metadata={"type": "increasing"}
            ))
        elif velocities[-1] < velocities[0] * 0.5:
            trends.append(Pattern(
                pattern_type=PatternType.CHAIN,
                confidence=0.6,
                nodes=["trend_down"],
                edges=[],
                metadata={"type": "decreasing"}
            ))
        
        return trends
    
    def _detect_oscillations(self, history: List[List[AgentFeature]]) -> List[Pattern]:
        """检测振荡"""
        oscillations = []
        
        if len(history) < 10:
            return oscillations
        
        positions = []
        for snapshot in history:
            if snapshot:
                avg_x = sum(a.position[0] for a in snapshot) / len(snapshot)
                avg_y = sum(a.position[1] for a in snapshot) / len(snapshot)
                positions.append((avg_x, avg_y))
        
        if len(positions) >= 10:
            x_values = [p[0] for p in positions]
            y_values = [p[1] for p in positions]
            
            x_oscillates = self._has_oscillation(x_values)
            y_oscillates = self._has_oscillation(y_values)
            
            if x_oscillates or y_oscillates:
                oscillations.append(Pattern(
                    pattern_type=PatternType.WAVE,
                    confidence=0.65,
                    nodes=["oscillation"],
                    edges=[],
                    metadata={"x_oscillates": x_oscillates, "y_oscillates": y_oscillates}
                ))
        
        return oscillations
    
    def _find_cycle_length(self, values: List[float]) -> int:
        """查找循环长度"""
        for length in range(2, len(values) // 2):
            pattern = values[:length]
            matches = 0
            for i in range(length, len(values), length):
                segment = values[i:i+length]
                if segment == pattern[:len(segment)]:
                    matches += 1
                else:
                    break
            
            if matches >= 2:
                return length
        return 0
    
    def _has_oscillation(self, values: List[float]) -> bool:
        """检测是否振荡"""
        if len(values) < 4:
            return False
        
        sign_changes = 0
        for i in range(1, len(values)):
            if values[i] > values[i-1] and values[i-1] <= values[i-2]:
                sign_changes += 1
            elif values[i] < values[i-1] and values[i-1] >= values[i-2]:
                sign_changes += 1
        
        return sign_changes >= len(values) // 3
    
    def detect_behavioral_patterns(self, agents: List[AgentFeature]) -> List[Pattern]:
        """检测行为模式"""
        patterns = []
        
        state_groups = defaultdict(list)
        for agent in agents:
            state_groups[agent.state].append(agent.agent_id)
        
        for state, agent_ids in state_groups.items():
            if len(agent_ids) >= 3:
                patterns.append(Pattern(
                    pattern_type=PatternType.CLUSTER,
                    confidence=0.7,
                    nodes=agent_ids,
                    edges=self._create_cluster_edges(set(agent_ids)),
                    metadata={"state": state}
                ))
        
        return patterns
    
    def create_emergent_property(self, name: str, emergence_type: EmergenceType,
                                  components: List[str], metadata: Dict[str, Any] = None) -> EmergentProperty:
        """创建涌现属性"""
        property = EmergentProperty(
            name=name,
            emergence_type=emergence_type,
            strength=0.0,
            stability=0.0,
            components=components,
            metadata=metadata or {}
        )
        
        self.emergent_properties.append(property)
        return property
    
    def analyze_property_strength(self, property: EmergentProperty, 
                                   agents: List[AgentFeature]) -> float:
        """分析涌现属性强度"""
        if not property.components:
            return 0.0
        
        component_agents = [a for a in agents if a.agent_id in property.components]
        if len(component_agents) < 2:
            return 0.0
        
        coordination_score = self._calculate_coordination(component_agents)
        interaction_score = self._calculate_interaction(component_agents)
        synchronization_score = self._calculate_synchronization(component_agents)
        
        property.strength = (coordination_score + interaction_score + synchronization_score) / 3
        
        return property.strength
    
    def _calculate_coordination(self, agents: List[AgentFeature]) -> float:
        """计算协调度"""
        if len(agents) < 2:
            return 0.0
        
        velocities = [math.sqrt(v[0]**2 + v[1]**2) for a in agents for v in [a.velocity]]
        if not velocities:
            return 0.0
        
        avg_velocity = sum(velocities) / len(velocities)
        velocity_variance = sum((v - avg_velocity)**2 for v in velocities) / len(velocities)
        
        coordination = 1.0 / (1.0 + velocity_variance)
        return min(1.0, coordination)
    
    def _calculate_interaction(self, agents: List[AgentFeature]) -> float:
        """计算交互度"""
        total_interactions = 0
        max_interactions = 0
        
        for agent in agents:
            total_interactions += len(agent.neighbors)
            max_interactions += len(agents) - 1
        
        if max_interactions == 0:
            return 0.0
        
        return min(1.0, total_interactions / max_interactions)
    
    def _calculate_synchronization(self, agents: List[AgentFeature]) -> float:
        """计算同步度"""
        if len(agents) < 2:
            return 0.0
        
        states = [a.state for a in agents]
        state_counts = defaultdict(int)
        for state in states:
            state_counts[state] += 1
        
        most_common_count = max(state_counts.values()) if state_counts else 0
        synchronization = most_common_count / len(agents)
        
        return synchronization
    
    def get_pattern_statistics(self) -> Dict[str, Any]:
        """获取模式统计"""
        pattern_counts = defaultdict(int)
        for pattern in self.patterns:
            pattern_counts[pattern.pattern_type.value] += 1
        
        total_confidence = sum(p.confidence for p in self.patterns)
        avg_confidence = total_confidence / len(self.patterns) if self.patterns else 0
        
        return {
            "pattern_counts": dict(pattern_counts),
            "total_patterns": len(self.patterns),
            "average_confidence": avg_confidence,
            "emergent_properties": len(self.emergent_properties),
            "property_strengths": [p.strength for p in self.emergent_properties]
        }


class EmergenceSystem:
    """涌现系统"""
    
    def __init__(self):
        self.detector = EmergenceDetector()
        self.agents: Dict[str, AgentFeature] = {}
        self.evolution_history: List[Dict[str, Any]] = []
        self.active_emergences: Dict[str, EmergentProperty] = {}
        self.emergence_rules: List[Callable] = []
        self.feedback_loops: List[Tuple[str, str, float]] = []
        
        self._init_emergence_rules()
    
    def _init_emergence_rules(self):
        """初始化涌现规则"""
        self.emergence_rules = [
            self._rule_cluster_formation,
            self._rule_synchronization,
            self._rule_collective_intelligence,
            self._rule_adaptive_complexity,
            self._rule_emergent_memory
        ]
    
    def _rule_cluster_formation(self, agents: List[AgentFeature]) -> Optional[EmergentProperty]:
        """聚类形成规则"""
        clusters = self.detector._detect_clusters(agents)
        
        large_clusters = [c for c in clusters if len(c) >= 5]
        if large_clusters:
            return self.detector.create_emergent_property(
                "cluster_formation",
                EmergenceType.SPATIAL,
                list(large_clusters[0]),
                {"cluster_size": len(large_clusters[0])}
            )
        return None
    
    def _rule_synchronization(self, agents: List[AgentFeature]) -> Optional[EmergentProperty]:
        """同步规则"""
        states = [a.state for a in agents]
        state_counts = defaultdict(int)
        for state in states:
            state_counts[state] += 1
        
        most_common = max(state_counts.values()) if state_counts else 0
        if most_common >= len(agents) * 0.7:
            return self.detector.create_emergent_property(
                "state_synchronization",
                EmergenceType.TEMPORAL,
                [a.agent_id for a in agents if a.state == max(state_counts, key=state_counts.get)],
                {"synchronized_state": max(state_counts, key=state_counts.get)}
            )
        return None
    
    def _rule_collective_intelligence(self, agents: List[AgentFeature]) -> Optional[EmergentProperty]:
        """集体智慧规则"""
        total_energy = sum(a.energy for a in agents)
        avg_connections = sum(len(a.neighbors) for a in agents) / len(agents) if agents else 0
        
        if total_energy > 500 and avg_connections > 2:
            return self.detector.create_emergent_property(
                "collective_intelligence",
                EmergenceType.COGNITIVE,
                [a.agent_id for a in agents],
                {"total_energy": total_energy, "avg_connections": avg_connections}
            )
        return None
    
    def _rule_adaptive_complexity(self, agents: List[AgentFeature]) -> Optional[EmergentProperty]:
        """自适应复杂性规则"""
        unique_states = len(set(a.state for a in agents))
        total_agents = len(agents)
        
        if unique_states >= 3 and total_agents >= 5:
            return self.detector.create_emergent_property(
                "adaptive_complexity",
                EmergenceType.BEHAVIORAL,
                [a.agent_id for a in agents],
                {"unique_states": unique_states}
            )
        return None
    
    def _rule_emergent_memory(self, agents: List[AgentFeature]) -> Optional[EmergentProperty]:
        """涌现记忆规则"""
        patterns = self.detector.patterns
        
        if len(patterns) >= 2:
            all_nodes = set()
            for pattern in patterns:
                all_nodes.update(pattern.nodes)
            
            return self.detector.create_emergent_property(
                "emergent_memory",
                EmergenceType.COLLECTIVE,
                list(all_nodes),
                {"pattern_count": len(patterns)}
            )
        return None
    
    def add_agent(self, agent: AgentFeature):
        """添加智能体"""
        self.agents[agent.agent_id] = agent
    
    def remove_agent(self, agent_id: str):
        """移除智能体"""
        if agent_id in self.agents:
            del self.agents[agent_id]
    
    def update(self) -> Dict[str, Any]:
        """更新涌现系统"""
        agents_list = list(self.agents.values())
        
        spatial_patterns = self.detector.detect_spatial_patterns(agents_list)
        
        self.detector.detect_behavioral_patterns(agents_list)
        
        new_emergences = []
        for rule in self.emergence_rules:
            emergence = rule(agents_list)
            if emergence:
                self.active_emergences[emergence.name] = emergence
                self.detector.analyze_property_strength(emergence, agents_list)
                new_emergences.append(emergence)
        
        self.evolution_history.append({
            "timestamp": time.time(),
            "pattern_count": len(spatial_patterns),
            "emergence_count": len(self.active_emergences),
            "agent_count": len(self.agents)
        })
        
        if len(self.evolution_history) > 1000:
            self.evolution_history = self.evolution_history[-1000:]
        
        return {
            "patterns": len(spatial_patterns),
            "emergences": len(self.active_emergences),
            "new_emergences": len(new_emergences),
            "agents": len(self.agents)
        }
    
    def get_system_state(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            "agent_count": len(self.agents),
            "active_emergences": len(self.active_emergences),
            "pattern_statistics": self.detector.get_pattern_statistics(),
            "evolution_trend": self._analyze_evolution_trend()
        }
    
    def _analyze_emergence_trend(self) -> str:
        """分析涌现趋势"""
        if len(self.evolution_history) < 5:
            return "insufficient_data"
        
        recent = self.evolution_history[-5:]
        emergence_counts = [h["emergence_count"] for h in recent]
        
        if all(emergence_counts[i] <= emergence_counts[i+1] for i in range(len(emergence_counts)-1)):
            return "increasing"
        elif all(emergence_counts[i] >= emergence_counts[i+1] for i in range(len(emergence_counts)-1)):
            return "decreasing"
        else:
            return "stable"
    
    def analyze_evolution_trend(self) -> str:
        """分析进化趋势"""
        return self._analyze_emergence_trend()
    
    def get_emergent_properties(self) -> List[Dict[str, Any]]:
        """获取涌现属性"""
        return [
            {
                "name": p.name,
                "type": p.emergence_type.value,
                "strength": p.strength,
                "stability": p.stability,
                "components": p.components,
                "metadata": p.metadata
            }
            for p in self.active_emergences.values()
        ]


class EmergenceNetwork:
    """涌现网络"""
    
    def __init__(self):
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[Tuple[str, str], float] = {}
        self.emergence_layers: List[Dict[str, EmergentProperty]] = []
    
    def add_node(self, node_id: str, node_type: str, attributes: Dict[str, Any]):
        """添加节点"""
        self.nodes[node_id] = {
            "type": node_type,
            "attributes": attributes,
            "connections": 0,
            "strength": 0.0
        }
    
    def add_edge(self, node1_id: str, node2_id: str, weight: float = 1.0):
        """添加边"""
        if node1_id in self.nodes and node2_id in self.nodes:
            self.edges[(node1_id, node2_id)] = weight
            self.nodes[node1_id]["connections"] += 1
            self.nodes[node2_id]["connections"] += 1
    
    def calculate_centrality(self, node_id: str) -> float:
        """计算中心性"""
        if node_id not in self.nodes:
            return 0.0
        
        connections = sum(1 for e in self.edges if node_id in e)
        total_nodes = len(self.nodes) - 1
        
        return connections / total_nodes if total_nodes > 0 else 0.0
    
    def find_hubs(self, top_k: int = 5) -> List[Tuple[str, float]]:
        """查找中心节点"""
        centralities = [(node_id, self.calculate_centrality(node_id)) 
                       for node_id in self.nodes]
        return sorted(centralities, key=lambda x: x[1], reverse=True)[:top_k]
    
    def detect_communities(self) -> List[Set[str]]:
        """检测社区"""
        visited = set()
        communities = []
        
        for node_id in self.nodes:
            if node_id in visited:
                continue
            
            community = set()
            queue = [node_id]
            
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                
                visited.add(current)
                community.add(current)
                
                for (n1, n2), weight in self.edges.items():
                    neighbor = n2 if n1 == current else n1 if n2 == current else None
                    if neighbor and neighbor not in visited and weight > 0.5:
                        queue.append(neighbor)
            
            if community:
                communities.append(community)
        
        return communities
    
    def get_network_metrics(self) -> Dict[str, Any]:
        """获取网络指标"""
        if not self.nodes:
            return {}
        
        total_connections = len(self.edges)
        avg_connections = sum(n["connections"] for n in self.nodes.values()) / len(self.nodes)
        
        return {
            "node_count": len(self.nodes),
            "edge_count": total_connections,
            "average_connections": avg_connections,
            "density": total_connections / (len(self.nodes) * (len(self.nodes) - 1)) if len(self.nodes) > 1 else 0,
            "communities": len(self.detect_communities())
        }


if __name__ == "__main__":
    system = EmergenceSystem()
    
    for i in range(20):
        agent = AgentFeature(
            agent_id=f"agent_{i}",
            position=(random.uniform(0, 500), random.uniform(0, 500)),
            velocity=(random.uniform(-2, 2), random.uniform(-2, 2)),
            acceleration=(0, 0),
            energy=random.uniform(50, 100),
            state=random.choice(["idle", "exploring", "foraging", "resting"]),
            neighbors=[f"agent_{random.randint(0, 19)}" for _ in range(random.randint(1, 4))]
        )
        system.add_agent(agent)
    
    print(f"涌现系统初始化完成")
    print(f"智能体数量: {len(system.agents)}")
    
    for step in range(20):
        for agent in system.agents.values():
            agent.position = (
                agent.position[0] + agent.velocity[0],
                agent.position[1] + agent.velocity[1]
            )
            agent.position = (
                max(0, min(500, agent.position[0])),
                max(0, min(500, agent.position[1]))
            )
        
        result = system.update()
        
        if step % 5 == 0:
            print(f"步骤 {step}: 模式={result['patterns']}, 涌现={result['emergences']}")