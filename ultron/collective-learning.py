#!/usr/bin/env python3
"""
集体学习系统 (Collective Learning)
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


class LearningType(Enum):
    """学习类型"""
    SUPERVISED = "supervised"        # 监督学习
    REINFORCEMENT = "reinforcement"  # 强化学习
    UNSUPERVISED = "unsupervised"    # 无监督学习
    IMITATION = "imitation"          # 模仿学习
    COLLABORATIVE = "collaborative"  # 协作学习
    DISTRIBUTED = "distributed"      # 分布式学习
    FEDERATED = "federated"          # 联邦学习
    TRANSFER = "transfer"             # 迁移学习


class KnowledgeType(Enum):
    """知识类型"""
    PROCEDURAL = "procedural"        # 程序性知识
    DECLARATIVE = "declarative"      # 陈述性知识
    EPISODIC = "episodic"            # 情景记忆
    SEMANTIC = "semantic"            # 语义知识
    SOCIAL = "social"                # 社会知识
    PROCEDURAL_COLLECTIVE = "procedural_collective"
    EMERGENT = "emergent"            # 涌现知识


@dataclass
class Knowledge:
    """知识单元"""
    id: str
    knowledge_type: KnowledgeType
    content: Any
    confidence: float
    source_agents: List[str]
    target_agents: List[str]
    created_at: float
    last_accessed: float
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LearningExperience:
    """学习经验"""
    id: str
    agent_id: str
    state: Any
    action: Any
    reward: float
    next_state: Any
    timestamp: float
    quality: float = 1.0
    success: bool = True


@dataclass
class AgentKnowledge:
    """智能体知识"""
    agent_id: str
    knowledge_items: Dict[str, Knowledge] = field(default_factory=dict)
    expertise: Dict[str, float] = field(default_factory=dict)
    learning_history: List[str] = field(default_factory=list)


@dataclass
class SharedInsight:
    """共享洞察"""
    id: str
    content: str
    contributors: List[str]
    confidence: float
    applications: List[str]
    created_at: float
    validated: bool = False


class CollectiveLearningEngine:
    """集体学习引擎"""
    
    def __init__(self):
        self.agent_knowledge: Dict[str, AgentKnowledge] = {}
        self.shared_knowledge: Dict[str, Knowledge] = {}
        self.experiences: List[LearningExperience] = []
        self.insights: List[SharedInsight] = []
        self.learning_policies: Dict[LearningType, Callable] = {}
        self.knowledge_graph: Dict[str, List[str]] = defaultdict(list)
        self.collaboration_network: Dict[str, List[str]] = defaultdict(list)
        self.performance_metrics = {
            "total_knowledge_shared": 0,
            "successful_transfers": 0,
            "collaborative_solutions": 0,
            "average_knowledge_quality": 0.0
        }
        
        self._init_learning_policies()
    
    def _init_learning_policies(self):
        """初始化学习策略"""
        self.learning_policies = {
            LearningType.SUPERVISED: self._supervised_learning,
            LearningType.REINFORCEMENT: self._reinforcement_learning,
            LearningType.UNSUPERVISED: self._unsupervised_learning,
            LearningType.IMITATION: self._imitation_learning,
            LearningType.COLLABORATIVE: self._collaborative_learning,
            LearningType.DISTRIBUTED: self._distributed_learning,
            LearningType.FEDERATED: self._federated_learning,
            LearningType.TRANSFER: self._transfer_learning
        }
    
    # ==================== 知识管理 ====================
    
    def register_agent(self, agent_id: str):
        """注册智能体"""
        if agent_id not in self.agent_knowledge:
            self.agent_knowledge[agent_id] = AgentKnowledge(agent_id=agent_id)
    
    def add_knowledge(self, agent_id: str, knowledge: Knowledge):
        """添加知识"""
        if agent_id not in self.agent_knowledge:
            self.register_agent(agent_id)
        
        self.agent_knowledge[agent_id].knowledge_items[knowledge.id] = knowledge
        self._update_knowledge_graph(agent_id, knowledge)
    
    def share_knowledge(self, source_id: str, target_id: str, knowledge_id: str) -> bool:
        """分享知识"""
        if source_id not in self.agent_knowledge:
            return False
        
        if knowledge_id not in self.agent_knowledge[source_id].knowledge_items:
            return False
        
        knowledge = self.agent_knowledge[source_id].knowledge_items[knowledge_id]
        
        if target_id not in self.agent_knowledge:
            self.register_agent(target_id)
        
        shared_knowledge = Knowledge(
            id=f"{knowledge_id}_shared_{target_id}",
            knowledge_type=knowledge.knowledge_type,
            content=knowledge.content,
            confidence=knowledge.confidence * 0.9,
            source_agents=knowledge.source_agents + [source_id],
            target_agents=[target_id],
            created_at=time.time(),
            last_accessed=time.time(),
            metadata={**knowledge.metadata, "shared_from": source_id}
        )
        
        self.agent_knowledge[target_id].knowledge_items[shared_knowledge.id] = shared_knowledge
        self.shared_knowledge[shared_knowledge.id] = shared_knowledge
        self.collaboration_network[source_id].append(target_id)
        
        self.performance_metrics["total_knowledge_shared"] += 1
        self.performance_metrics["successful_transfers"] += 1
        
        return True
    
    def broadcast_knowledge(self, source_id: str, knowledge_id: str, radius: int = 3) -> int:
        """广播知识"""
        if source_id not in self.agent_knowledge:
            return 0
        
        knowledge = self.agent_knowledge[source_id].knowledge_items.get(knowledge_id)
        if not knowledge:
            return 0
        
        broadcast_count = 0
        visited = {source_id}
        queue = [(source_id, 0)]
        
        while queue:
            current, depth = queue.pop(0)
            
            if depth >= radius:
                continue
            
            for neighbor in self.collaboration_network.get(current, []):
                if neighbor not in visited:
                    visited.add(neighbor)
                    
                    if self.share_knowledge(source_id, neighbor, knowledge_id):
                        broadcast_count += 1
                    
                    queue.append((neighbor, depth + 1))
        
        return broadcast_count
    
    def _update_knowledge_graph(self, agent_id: str, knowledge: Knowledge):
        """更新知识图谱"""
        self.knowledge_graph[agent_id].append(knowledge.id)
        
        if knowledge.knowledge_type == KnowledgeType.PROCEDURAL:
            for existing in self.agent_knowledge[agent_id].knowledge_items.values():
                if existing.knowledge_type == KnowledgeType.SEMANTIC:
                    self.knowledge_graph[knowledge.id].append(existing.id)
    
    # ==================== 学习算法 ====================
    
    def _supervised_learning(self, agent_id: str, data: List[Tuple[Any, Any]], 
                            labels: List[Any]) -> Dict[str, float]:
        """监督学习"""
        if agent_id not in self.agent_knowledge:
            self.register_agent(agent_id)
        
        correct = 0
        total = len(data)
        
        for i, (features, label) in enumerate(zip(data, labels)):
            predicted = self._predict_label(features)
            if predicted == label:
                correct += 1
        
        accuracy = correct / total if total > 0 else 0.0
        
        knowledge = Knowledge(
            id=f"supervised_{agent_id}_{int(time.time())}",
            knowledge_type=KnowledgeType.PROCEDURAL,
            content={"data_size": total, "accuracy": accuracy},
            confidence=accuracy,
            source_agents=[agent_id],
            target_agents=[agent_id],
            created_at=time.time(),
            last_accessed=time.time()
        )
        
        self.add_knowledge(agent_id, knowledge)
        
        return {"accuracy": accuracy, "samples": total}
    
    def _predict_label(self, features: Any) -> Any:
        """预测标签（简化版）"""
        if isinstance(features, (list, tuple)):
            return features[0] if features else None
        return features
    
    def _reinforcement_learning(self, agent_id: str, experiences: List[LearningExperience],
                               learning_rate: float = 0.1, discount: float = 0.9) -> Dict[str, float]:
        """强化学习"""
        if agent_id not in self.agent_knowledge:
            self.register_agent(agent_id)
        
        self.experiences.extend(experiences)
        
        total_reward = sum(exp.reward for exp in experiences)
        avg_reward = total_reward / len(experiences) if experiences else 0
        
        success_rate = sum(1 for exp in experiences if exp.success) / len(experiences) if experiences else 0
        
        knowledge = Knowledge(
            id=f"rl_{agent_id}_{int(time.time())}",
            knowledge_type=KnowledgeType.PROCEDURAL,
            content={
                "learning_rate": learning_rate,
                "discount": discount,
                "avg_reward": avg_reward,
                "success_rate": success_rate
            },
            confidence=success_rate,
            source_agents=[agent_id],
            target_agents=[agent_id],
            created_at=time.time(),
            last_accessed=time.time()
        )
        
        self.add_knowledge(agent_id, knowledge)
        
        return {"avg_reward": avg_reward, "success_rate": success_rate}
    
    def _unsupervised_learning(self, agent_id: str, data: List[Any], 
                               clusters: int = 3) -> Dict[str, Any]:
        """无监督学习"""
        if agent_id not in self.agent_knowledge:
            self.register_agent(agent_id)
        
        cluster_assignments = []
        for i, item in enumerate(data):
            cluster = i % clusters
            cluster_assignments.append(cluster)
        
        clusters_data = defaultdict(list)
        for item, cluster in zip(data, cluster_assignments):
            clusters_data[cluster].append(item)
        
        knowledge = Knowledge(
            id=f"unsupervised_{agent_id}_{int(time.time())}",
            knowledge_type=KnowledgeType.SEMANTIC,
            content={"clusters": dict(clusters_data), "num_clusters": clusters},
            confidence=0.7,
            source_agents=[agent_id],
            target_agents=[agent_id],
            created_at=time.time(),
            last_accessed=time.time()
        )
        
        self.add_knowledge(agent_id, knowledge)
        
        return {"clusters": clusters, "distribution": {k: len(v) for k, v in clusters_data.items()}}
    
    def _imitation_learning(self, agent_id: str, demonstrations: List[Tuple[Any, Any]]) -> Dict[str, float]:
        """模仿学习"""
        if agent_id not in self.agent_knowledge:
            self.register_agent(agent_id)
        
        success_count = 0
        for state, action in demonstrations:
            if action is not None:
                success_count += 1
        
        accuracy = success_count / len(demonstrations) if demonstrations else 0
        
        knowledge = Knowledge(
            id=f"imitation_{agent_id}_{int(time.time())}",
            knowledge_type=KnowledgeType.PROCEDURAL_COLLECTIVE,
            content={"demonstrations": len(demonstrations), "accuracy": accuracy},
            confidence=accuracy,
            source_agents=[agent_id],
            target_agents=[agent_id],
            created_at=time.time(),
            last_accessed=time.time()
        )
        
        self.add_knowledge(agent_id, knowledge)
        
        return {"accuracy": accuracy, "demonstrations": len(demonstrations)}
    
    def _collaborative_learning(self, agent_ids: List[str], task: Any) -> Dict[str, Any]:
        """协作学习"""
        if not agent_ids:
            return {"success": False}
        
        agent_knowledge_sets = []
        for agent_id in agent_ids:
            if agent_id in self.agent_knowledge:
                agent_knowledge_sets.append(
                    set(self.agent_knowledge[agent_id].knowledge_items.keys())
                )
        
        if not agent_knowledge_sets:
            return {"success": False}
        
        common_knowledge = set.intersection(*agent_knowledge_sets) if agent_knowledge_sets else set()
        
        collaborative_insight = SharedInsight(
            id=f"insight_{int(time.time())}",
            content=f"Collaborative solution for task: {task}",
            contributors=agent_ids,
            confidence=len(common_knowledge) / max(len(agent_knowledge_sets[0]), 1) if agent_knowledge_sets else 0,
            applications=["collaborative_task"],
            created_at=time.time()
        )
        
        self.insights.append(collaborative_insight)
        self.performance_metrics["collaborative_solutions"] += 1
        
        return {
            "success": True,
            "common_knowledge": len(common_knowledge),
            "collaborators": len(agent_ids)
        }
    
    def _distributed_learning(self, agent_ids: List[str], data_partitions: Dict[str, List[Any]]) -> Dict[str, Any]:
        """分布式学习"""
        local_models = {}
        
        for agent_id in agent_ids:
            if agent_id not in data_partitions:
                continue
            
            data = data_partitions[agent_id]
            local_model = self._train_local_model(agent_id, data)
            local_models[agent_id] = local_model
        
        global_model = self._aggregate_models(local_models)
        
        for agent_id in agent_ids:
            if agent_id not in self.agent_knowledge:
                self.register_agent(agent_id)
            
            knowledge = Knowledge(
                id=f"distributed_{agent_id}_{int(time.time())}",
                knowledge_type=KnowledgeType.PROCEDURAL,
                content=global_model,
                confidence=0.8,
                source_agents=agent_ids,
                target_agents=[agent_id],
                created_at=time.time(),
                last_accessed=time.time()
            )
            
            self.add_knowledge(agent_id, knowledge)
        
        return {
            "local_models": len(local_models),
            "global_model_aggregated": True,
            "participants": len(agent_ids)
        }
    
    def _train_local_model(self, agent_id: str, data: List[Any]) -> Dict[str, Any]:
        """训练本地模型"""
        return {
            "agent_id": agent_id,
            "data_size": len(data),
            "parameters": {"weight": random.uniform(0, 1), "bias": random.uniform(0, 1)},
            "iterations": random.randint(10, 100)
        }
    
    def _aggregate_models(self, local_models: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """聚合模型"""
        if not local_models:
            return {}
        
        avg_weight = sum(m["parameters"]["weight"] for m in local_models.values()) / len(local_models)
        avg_bias = sum(m["parameters"]["bias"] for m in local_models.values()) / len(local_models)
        
        return {
            "global_parameters": {"weight": avg_weight, "bias": avg_bias},
            "aggregation_method": "fedavg",
            "model_count": len(local_models)
        }
    
    def _federated_learning(self, agent_ids: List[str], rounds: int = 5) -> Dict[str, Any]:
        """联邦学习"""
        round_results = []
        
        for round_num in range(rounds):
            selected_agents = random.sample(agent_ids, min(3, len(agent_ids)))
            
            local_updates = []
            for agent_id in selected_agents:
                update = self._compute_local_update(agent_id)
                local_updates.append(update)
            
            global_update = self._aggregate_updates(local_updates)
            round_results.append({
                "round": round_num + 1,
                "participants": len(selected_agents),
                "update_magnitude": sum(u["magnitude"] for u in local_updates) / len(local_updates)
            })
        
        return {
            "rounds_completed": rounds,
            "round_results": round_results,
            "final_accuracy": random.uniform(0.7, 0.95)
        }
    
    def _compute_local_update(self, agent_id: str) -> Dict[str, Any]:
        """计算本地更新"""
        return {
            "agent_id": agent_id,
            "magnitude": random.uniform(0.1, 0.5),
            "direction": (random.uniform(-1, 1), random.uniform(-1, 1))
        }
    
    def _aggregate_updates(self, updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """聚合更新"""
        avg_magnitude = sum(u["magnitude"] for u in updates) / len(updates)
        
        return {
            "global_magnitude": avg_magnitude,
            "update_count": len(updates)
        }
    
    def _transfer_learning(self, source_agent: str, target_agent: str, 
                          task: str) -> Dict[str, Any]:
        """迁移学习"""
        if source_agent not in self.agent_knowledge:
            return {"success": False, "reason": "source_not_found"}
        
        source_knowledge = self.agent_knowledge[source_agent].knowledge_items
        
        transferred = 0
        for knowledge_id, knowledge in source_knowledge.items():
            if task in knowledge.metadata.get("tags", []) or not knowledge.metadata.get("tags"):
                if self.share_knowledge(source_agent, target_agent, knowledge_id):
                    transferred += 1
        
        return {
            "success": transferred > 0,
            "transferred_knowledge": transferred,
            "source": source_agent,
            "target": target_agent,
            "task": task
        }
    
    # ==================== 知识传播 ====================
    
    def propagate_knowledge(self, source_id: str, depth: int = 2) -> int:
        """传播知识"""
        if source_id not in self.agent_knowledge:
            return 0
        
        total_shared = 0
        knowledge_items = list(self.agent_knowledge[source_id].knowledge_items.values())
        
        visited = {source_id}
        current_level = {source_id}
        
        for _ in range(depth):
            next_level = set()
            
            for agent_id in current_level:
                neighbors = self.collaboration_network.get(agent_id, [])
                
                for neighbor in neighbors:
                    if neighbor in visited:
                        continue
                    
                    visited.add(neighbor)
                    next_level.add(neighbor)
                    
                    for knowledge in knowledge_items:
                        if self.share_knowledge(source_id, neighbor, knowledge.id):
                            total_shared += 1
            
            current_level = next_level
        
        return total_shared
    
    def find_knowledge_paths(self, source_id: str, target_id: str) -> List[List[str]]:
        """查找知识传播路径"""
        if source_id not in self.collaboration_network:
            return []
        
        paths = []
        queue = [(source_id, [source_id])]
        
        while queue:
            current, path = queue.pop(0)
            
            if current == target_id:
                paths.append(path)
                continue
            
            if len(path) > 5:
                continue
            
            for neighbor in self.collaboration_network.get(current, []):
                if neighbor not in path:
                    queue.append((neighbor, path + [neighbor]))
        
        return paths
    
    def calculate_knowledge_distance(self, agent1_id: str, agent2_id: str) -> float:
        """计算知识距离"""
        if agent1_id not in self.agent_knowledge or agent2_id not in self.agent_knowledge:
            return float('inf')
        
        k1 = set(self.agent_knowledge[agent1_id].knowledge_items.keys())
        k2 = set(self.agent_knowledge[agent2_id].knowledge_items.keys())
        
        if not k1 or not k2:
            return float('inf')
        
        intersection = len(k1 & k2)
        union = len(k1 | k2)
        
        similarity = intersection / union if union > 0 else 0
        
        return 1.0 - similarity
    
    # ==================== 智能知识提取 ====================
    
    def extract_shared_patterns(self) -> List[Dict[str, Any]]:
        """提取共享模式"""
        if len(self.agent_knowledge) < 2:
            return []
        
        all_knowledge = defaultdict(list)
        
        for agent_id, knowledge_set in self.agent_knowledge.items():
            for knowledge in knowledge_set.knowledge_items.values():
                all_knowledge[knowledge.knowledge_type.value].append({
                    "agent": agent_id,
                    "confidence": knowledge.confidence,
                    "id": knowledge.id
                })
        
        patterns = []
        for ktype, items in all_knowledge.items():
            if len(items) >= 2:
                avg_confidence = sum(i["confidence"] for i in items) / len(items)
                patterns.append({
                    "type": ktype,
                    "occurrences": len(items),
                    "average_confidence": avg_confidence,
                    "agents": [i["agent"] for i in items]
                })
        
        return patterns
    
    def generate_insight(self, agent_ids: List[str]) -> Optional[SharedInsight]:
        """生成洞察"""
        if len(agent_ids) < 2:
            return None
        
        knowledge_sets = []
        for agent_id in agent_ids:
            if agent_id in self.agent_knowledge:
                knowledge_sets.append(set(self.agent_knowledge[agent_id].knowledge_items.keys()))
        
        if not knowledge_sets:
            return None
        
        common = set.intersection(*knowledge_sets) if knowledge_sets else set()
        
        if len(common) >= 2:
            insight = SharedInsight(
                id=f"insight_{int(time.time())}",
                content=f"Common knowledge discovered: {len(common)} shared items",
                contributors=agent_ids,
                confidence=len(common) / max(len(knowledge_sets[0]), 1),
                applications=["collaboration", "coordination"],
                created_at=time.time()
            )
            
            self.insights.append(insight)
            return insight
        
        return None
    
    # ==================== 性能优化 ====================
    
    def optimize_knowledge_sharing(self) -> Dict[str, Any]:
        """优化知识分享"""
        low_confidence_knowledge = []
        
        for agent_id, knowledge_set in self.agent_knowledge.items():
            for knowledge in knowledge_set.knowledge_items.values():
                if knowledge.confidence < 0.5:
                    low_confidence_knowledge.append((agent_id, knowledge.id))
        
        for agent_id, knowledge_id in low_confidence_knowledge:
            neighbors = self.collaboration_network.get(agent_id, [])
            for neighbor in neighbors[:2]:
                self.share_knowledge(agent_id, neighbor, knowledge_id)
        
        return {
            "optimized_knowledge": len(low_confidence_knowledge),
            "sharing_opportunities": len(low_confidence_knowledge) * 2
        }
    
    # ==================== 状态查询 ====================
    
    def get_learning_state(self) -> Dict[str, Any]:
        """获取学习状态"""
        total_knowledge = sum(
            len(ks.knowledge_items) 
            for ks in self.agent_knowledge.values()
        )
        
        avg_confidence = 0.0
        if total_knowledge > 0:
            all_confidences = [
                k.confidence 
                for ks in self.agent_knowledge.values() 
                for k in ks.knowledge_items.values()
            ]
            avg_confidence = sum(all_confidences) / len(all_confidences)
        
        return {
            "agent_count": len(self.agent_knowledge),
            "total_knowledge": total_knowledge,
            "shared_knowledge": len(self.shared_knowledge),
            "insights": len(self.insights),
            "average_confidence": avg_confidence,
            "metrics": self.performance_metrics
        }
    
    def get_agent_knowledge_summary(self, agent_id: str) -> Dict[str, Any]:
        """获取智能体知识摘要"""
        if agent_id not in self.agent_knowledge:
            return {"error": "agent_not_found"}
        
        knowledge_set = self.agent_knowledge[agent_id]
        
        by_type = defaultdict(int)
        for knowledge in knowledge_set.knowledge_items.values():
            by_type[knowledge.knowledge_type.value] += 1
        
        return {
            "agent_id": agent_id,
            "knowledge_count": len(knowledge_set.knowledge_items),
            "by_type": dict(by_type),
            "collaborations": len(self.collaboration_network.get(agent_id, []))
        }
    
    def get_knowledge_graph(self) -> Dict[str, List[str]]:
        """获取知识图谱"""
        return dict(self.knowledge_graph)


class AdaptiveLearningRate:
    """自适应学习率"""
    
    def __init__(self, initial_rate: float = 0.1):
        self.initial_rate = initial_rate
        self.current_rate = initial_rate
        self.history: List[float] = []
    
    def update(self, performance: float, direction: str = "increase"):
        """更新学习率"""
        if direction == "increase" and performance > 0.8:
            self.current_rate *= 1.1
        elif direction == "decrease" and performance < 0.5:
            self.current_rate *= 0.9
        
        self.current_rate = max(0.001, min(1.0, self.current_rate))
        self.history.append(self.current_rate)
        
        return self.current_rate


class KnowledgeDistillation:
    """知识蒸馏"""
    
    def __init__(self):
        self.teacher_models: Dict[str, Any] = {}
        self.student_models: Dict[str, Any] = {}
        self.distillation_history: List[Dict[str, Any]] = []
    
    def add_teacher(self, teacher_id: str, model: Dict[str, Any]):
        """添加教师模型"""
        self.teacher_models[teacher_id] = model
    
    def distill(self, student_id: str, teacher_id: str, temperature: float = 2.0) -> Dict[str, Any]:
        """蒸馏知识"""
        if teacher_id not in self.teacher_models:
            return {"success": False}
        
        teacher = self.teacher_models[teacher_id]
        
        distilled = {
            "parameters": {k: v * 0.9 for k, v in teacher.get("parameters", {}).items()},
            "temperature": temperature,
            "distilled_from": teacher_id
        }
        
        self.student_models[student_id] = distilled
        
        self.distillation_history.append({
            "student": student_id,
            "teacher": teacher_id,
            "temperature": temperature,
            "timestamp": time.time()
        })
        
        return {"success": True, "knowledge_transferred": len(teacher.get("parameters", {}))}


class CollaborativeProblemSolver:
    """协作问题求解器"""
    
    def __init__(self):
        self.problems: Dict[str, Dict[str, Any]] = {}
        self.solutions: Dict[str, Any] = {}
        self.collaboration_history: List[Dict[str, Any]] = []
    
    def add_problem(self, problem_id: str, problem: Dict[str, Any]):
        """添加问题"""
        self.problems[problem_id] = {
            "problem": problem,
            "status": "open",
            "contributors": [],
            "attempts": 0
        }
    
    def propose_solution(self, problem_id: str, agent_id: str, solution: Any) -> bool:
        """提出解决方案"""
        if problem_id not in self.problems:
            return False
        
        self.problems[problem_id]["attempts"] += 1
        
        if problem_id not in self.solutions:
            self.solutions[problem_id] = []
        
        self.solutions[problem_id].append({
            "agent": agent_id,
            "solution": solution,
            "timestamp": time.time()
        })
        
        if agent_id not in self.problems[problem_id]["contributors"]:
            self.problem[problem_id]["contributors"].append(agent_id)
        
        return True
    
    def evaluate_solution(self, problem_id: str, solution_idx: int) -> float:
        """评估解决方案"""
        if problem_id not in self.solutions:
            return 0.0
        
        if solution_idx >= len(self.solutions[problem_id]):
            return 0.0
        
        solution = self.solutions[problem_id][solution_idx]["solution"]
        
        score = random.uniform(0.5, 1.0)
        
        return score
    
    def select_best_solution(self, problem_id: str) -> Optional[Dict[str, Any]]:
        """选择最佳解决方案"""
        if problem_id not in self.solutions:
            return None
        
        solutions = self.solutions[problem_id]
        
        best_score = -1
        best_solution = None
        
        for i, sol in enumerate(solutions):
            score = self.evaluate_solution(problem_id, i)
            if score > best_score:
                best_score = score
                best_solution = sol
        
        if best_solution:
            self.problems[problem_id]["status"] = "solved"
        
        return best_solution


if __name__ == "__main__":
    engine = CollectiveLearningEngine()
    
    agent_ids = [f"agent_{i}" for i in range(10)]
    
    for agent_id in agent_ids:
        engine.register_agent(agent_id)
    
    for agent_id in agent_ids[:5]:
        for i in range(3):
            knowledge = Knowledge(
                id=f"knowledge_{agent_id}_{i}",
                knowledge_type=random.choice(list(KnowledgeType)),
                content={"data": f"knowledge_{i}"},
                confidence=random.uniform(0.5, 1.0),
                source_agents=[agent_id],
                target_agents=[agent_id],
                created_at=time.time(),
                last_accessed=time.time()
            )
            engine.add_knowledge(agent_id, knowledge)
    
    for i in range(len(agent_ids) - 1):
        engine.collaboration_network[agent_ids[i]].append(agent_ids[i + 1])
    
    result = engine._collaborative_learning(agent_ids[:5], "test_task")
    print(f"协作学习结果: {result}")
    
    state = engine.get_learning_state()
    print(f"学习状态: {state['total_knowledge']} 知识项, {state['agent_count']} 智能体")