#!/usr/bin/env python3
"""
能力矩阵 (Capability Matrix)
全智能体生态系统 - 第1世核心组件
"""

import json
import time
import uuid
import math
from enum import Enum
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


class CapabilityDomain(Enum):
    """能力领域"""
    COGNITIVE = "cognitive"           # 认知能力
    PERCEPTUAL = "perceptual"         # 感知能力
    EXECUTIVE = "executive"           # 执行能力
    SOCIAL = "social"                 # 社交能力
    CREATIVE = "creative"             # 创造能力
    ANALYTICAL = "analytical"         # 分析能力
    ADAPTIVE = "adaptive"             # 适应能力
    META = "meta"                     # 元能力


class CapabilityLevel(Enum):
    """能力等级"""
    NONE = 0      # 无能力
    BASIC = 1     # 基础
    DEVELOPING = 2  # 发展中
    COMPETENT = 3  # 胜任
    ADVANCED = 4   # 高级
    EXPERT = 5     # 专家
    MASTER = 6     # 大师
    TRANSCENDENT = 7  # 超越


@dataclass
class CapabilityDimension:
    """能力维度"""
    domain: CapabilityDomain
    name: str
    description: str
    base_level: float = 0.0
    growth_rate: float = 0.1
    max_level: float = 1.0
    decay_rate: float = 0.01
    dependencies: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)


@dataclass
class CapabilityScore:
    """能力评分"""
    current: float = 0.0
    potential: float = 1.0
    experience: float = 0.0  # 经验值
    mastery: float = 0.0     # 掌握度
    last_updated: float = field(default_factory=time.time)
    
    def level(self) -> CapabilityLevel:
        """获取能力等级"""
        if self.current >= 0.95:
            return CapabilityLevel.TRANSCENDENT
        elif self.current >= 0.85:
            return CapabilityLevel.MASTER
        elif self.current >= 0.70:
            return CapabilityLevel.EXPERT
        elif self.current >= 0.55:
            return CapabilityLevel.ADVANCED
        elif self.current >= 0.40:
            return CapabilityLevel.COMPETENT
        elif self.current >= 0.25:
            return CapabilityLevel.DEVELOPING
        elif self.current >= 0.10:
            return CapabilityLevel.BASIC
        else:
            return CapabilityLevel.NONE


@dataclass
class CapabilityUpdate:
    """能力更新记录"""
    capability_id: str
    old_value: float
    new_value: float
    delta: float
    reason: str
    timestamp: float


class CapabilityMatrix:
    """
    能力矩阵
    管理智能体的所有能力维度和成长
    """
    
    # 预定义能力维度
    DEFAULT_DIMENSIONS = {
        # 认知能力
        "memory": CapabilityDimension(
            CapabilityDomain.COGNITIVE, "memory", "记忆能力",
            base_level=0.5, growth_rate=0.15, max_level=1.0
        ),
        "attention": CapabilityDimension(
            CapabilityDomain.COGNITIVE, "attention", "注意力",
            base_level=0.6, growth_rate=0.1, max_level=1.0
        ),
        "comprehension": CapabilityDimension(
            CapabilityDomain.COGNITIVE, "comprehension", "理解力",
            base_level=0.4, growth_rate=0.12, max_level=1.0
        ),
        
        # 感知能力
        "visual_perception": CapabilityDimension(
            CapabilityDomain.PERCEPTUAL, "visual_perception", "视觉感知",
            base_level=0.3, growth_rate=0.08, max_level=1.0,
            tags=["perception", "vision"]
        ),
        "auditory_perception": CapabilityDimension(
            CapabilityDomain.PERCEPTUAL, "auditory_perception", "听觉感知",
            base_level=0.3, growth_rate=0.08, max_level=1.0,
            tags=["perception", "audio"]
        ),
        "text_understanding": CapabilityDimension(
            CapabilityDomain.PERCEPTUAL, "text_understanding", "文本理解",
            base_level=0.6, growth_rate=0.15, max_level=1.0,
            tags=["perception", "text"]
        ),
        
        # 执行能力
        "action_planning": CapabilityDimension(
            CapabilityDomain.EXECUTIVE, "action_planning", "行动规划",
            base_level=0.4, growth_rate=0.1, max_level=1.0
        ),
        "execution": CapabilityDimension(
            CapabilityDomain.EXECUTIVE, "execution", "执行能力",
            base_level=0.5, growth_rate=0.12, max_level=1.0
        ),
        "coordination": CapabilityDimension(
            CapabilityDomain.EXECUTIVE, "coordination", "协调能力",
            base_level=0.4, growth_rate=0.08, max_level=1.0
        ),
        
        # 社交能力
        "communication": CapabilityDimension(
            CapabilityDomain.SOCIAL, "communication", "沟通能力",
            base_level=0.5, growth_rate=0.1, max_level=1.0
        ),
        "collaboration": CapabilityDimension(
            CapabilityDomain.SOCIAL, "collaboration", "协作能力",
            base_level=0.4, growth_rate=0.08, max_level=1.0
        ),
        "empathy": CapabilityDimension(
            CapabilityDomain.SOCIAL, "empathy", "共情能力",
            base_level=0.3, growth_rate=0.05, max_level=1.0
        ),
        
        # 创造能力
        "creative_thinking": CapabilityDimension(
            CapabilityDomain.CREATIVE, "creative_thinking", "创造性思维",
            base_level=0.3, growth_rate=0.06, max_level=1.0
        ),
        "innovation": CapabilityDimension(
            CapabilityDomain.CREATIVE, "innovation", "创新能力",
            base_level=0.2, growth_rate=0.05, max_level=1.0
        ),
        "imagination": CapabilityDimension(
            CapabilityDomain.CREATIVE, "imagination", "想象力",
            base_level=0.3, growth_rate=0.07, max_level=1.0
        ),
        
        # 分析能力
        "pattern_recognition": CapabilityDimension(
            CapabilityDomain.ANALYTICAL, "pattern_recognition", "模式识别",
            base_level=0.5, growth_rate=0.12, max_level=1.0
        ),
        "logical_reasoning": CapabilityDimension(
            CapabilityDomain.ANALYTICAL, "logical_reasoning", "逻辑推理",
            base_level=0.5, growth_rate=0.1, max_level=1.0
        ),
        "data_analysis": CapabilityDimension(
            CapabilityDomain.ANALYTICAL, "data_analysis", "数据分析",
            base_level=0.4, growth_rate=0.11, max_level=1.0
        ),
        
        # 适应能力
        "learning": CapabilityDimension(
            CapabilityDomain.ADAPTIVE, "learning", "学习能力",
            base_level=0.4, growth_rate=0.15, max_level=1.0
        ),
        "adaptation": CapabilityDimension(
            CapabilityDomain.ADAPTIVE, "adaptation", "适应能力",
            base_level=0.4, growth_rate=0.1, max_level=1.0
        ),
        "self_improvement": CapabilityDimension(
            CapabilityDomain.ADAPTIVE, "self_improvement", "自我改进",
            base_level=0.3, growth_rate=0.08, max_level=1.0
        ),
        
        # 元能力
        "metacognition": CapabilityDimension(
            CapabilityDomain.META, "metacognition", "元认知",
            base_level=0.2, growth_rate=0.05, max_level=1.0
        ),
        "self_awareness": CapabilityDimension(
            CapabilityDomain.META, "self_awareness", "自我意识",
            base_level=0.3, growth_rate=0.06, max_level=1.0
        ),
        "abstract_reasoning": CapabilityDimension(
            CapabilityDomain.META, "abstract_reasoning", "抽象推理",
            base_level=0.3, growth_rate=0.08, max_level=1.0
        ),
    }
    
    def __init__(self, agent_id: str, custom_dimensions: Optional[Dict[str, CapabilityDimension]] = None):
        self.agent_id = agent_id
        
        # 初始化能力维度
        self.dimensions: Dict[str, CapabilityDimension] = dict(self.DEFAULT_DIMENSIONS)
        if custom_dimensions:
            self.dimensions.update(custom_dimensions)
        
        # 能力评分
        self.scores: Dict[str, CapabilityScore] = {}
        
        # 初始化评分
        for dim_id, dim in self.dimensions.items():
            self.scores[dim_id] = CapabilityScore(
                current=dim.base_level,
                potential=dim.max_level,
                experience=0.0,
                mastery=0.0
            )
        
        # 更新历史
        self.update_history: List[CapabilityUpdate] = []
        
        # 能力组合缓存
        self._composite_cache: Dict[str, float] = {}
        self._cache_valid = False
        
        # 统计
        self.total_growth = 0.0
        self.total_decay = 0.0
    
    def get(self, capability_id: str) -> float:
        """获取能力值"""
        if capability_id in self.scores:
            return self.scores[capability_id].current
        return 0.0
    
    def set(self, capability_id: str, value: float, reason: str = "manual_set"):
        """设置能力值"""
        if capability_id not in self.scores:
            return
        
        dim = self.dimensions[capability_id]
        old_value = self.scores[capability_id].current
        
        # 限制在有效范围内
        new_value = max(0.0, min(dim.max_level, value))
        
        # 计算变化
        delta = new_value - old_value
        
        # 更新评分
        self.scores[capability_id].current = new_value
        self.scores[capability_id].last_updated = time.time()
        
        # 记录更新
        update = CapabilityUpdate(
            capability_id=capability_id,
            old_value=old_value,
            new_value=new_value,
            delta=delta,
            reason=reason,
            timestamp=time.time()
        )
        self.update_history.append(update)
        
        # 更新统计
        if delta > 0:
            self.total_growth += delta
        else:
            self.total_decay += abs(delta)
        
        # 使缓存失效
        self._invalidate_cache()
    
    def improve(self, capability_id: str, amount: float, reason: str = "improvement") -> bool:
        """提升能力"""
        if capability_id not in self.scores:
            return False
        
        current = self.scores[capability_id].current
        dim = self.dimensions[capability_id]
        
        # 计算提升量（考虑边际效益递减）
        effective_amount = amount * dim.growth_rate * (1.0 - current / dim.max_level)
        
        # 应用提升
        new_value = current + effective_amount
        self.set(capability_id, new_value, reason)
        
        return True
    
    def decay(self, capability_id: str, amount: Optional[float] = None):
        """能力衰减"""
        if capability_id not in self.scores:
            return
        
        dim = self.dimensions[capability_id]
        
        if amount is None:
            amount = dim.decay_rate
        
        current = self.scores[capability_id].current
        new_value = max(dim.base_level, current - amount)
        
        self.set(capability_id, new_value, "decay")
    
    def learn_from_task(self, task_result: Dict):
        """从任务中学习"""
        # 提取相关能力
        relevant_capabilities = task_result.get("capabilities_used", [])
        
        # 提取性能评分
        performance = task_result.get("performance", 0.5)
        
        # 计算学习量
        learning_multiplier = performance  # 高性能 = 更多学习
        
        for cap_id in relevant_capabilities:
            if cap_id in self.dimensions:
                # 基于性能提升能力
                improvement = 0.1 * learning_multiplier
                self.improve(cap_id, improvement, f"task_learning: {task_result.get('task_id', 'unknown')}")
                
                # 增加经验
                self.scores[cap_id].experience += 1
    
    # ==================== 能力组合 ====================
    
    def get_composite(self, capability_group: List[str]) -> float:
        """获取组合能力值"""
        if not capability_group:
            return 0.0
        
        # 生成缓存键
        cache_key = ",".join(sorted(capability_group))
        
        if cache_key in self._composite_cache:
            return self._composite_cache[cache_key]
        
        # 计算组合（几何平均）
        values = [self.get(cap) for cap in capability_group if cap in self.scores]
        
        if not values:
            return 0.0
        
        # 几何平均
        composite = math.exp(sum(math.log(max(v, 0.001)) for v in values) / len(values))
        
        self._composite_cache[cache_key] = composite
        return composite
    
    def get_domain_score(self, domain: CapabilityDomain) -> float:
        """获取领域分数"""
        domain_caps = [
            cap_id for cap_id, dim in self.dimensions.items()
            if dim.domain == domain
        ]
        
        return self.get_composite(domain_caps)
    
    def get_overall_score(self) -> float:
        """获取总体能力分数"""
        all_caps = list(self.dimensions.keys())
        return self.get_composite(all_caps)
    
    def _invalidate_cache(self):
        """使缓存失效"""
        self._composite_cache.clear()
        self._cache_valid = False
    
    # ==================== 依赖管理 ====================
    
    def get_dependencies(self, capability_id: str) -> List[str]:
        """获取能力依赖"""
        if capability_id in self.dimensions:
            return self.dimensions[capability_id].dependencies
        return []
    
    def can_improve(self, capability_id: str, amount: float = 0.1) -> Tuple[bool, List[str]]:
        """
        检查是否可以提升能力
        返回: (是否可行, 缺失的依赖)
        """
        if capability_id not in self.dimensions:
            return False, []
        
        deps = self.get_dependencies(capability_id)
        missing = []
        
        for dep in deps:
            dep_score = self.get(dep)
            if dep_score < amount:
                missing.append(dep)
        
        return len(missing) == 0, missing
    
    def meet_dependencies(self, capability_id: str) -> bool:
        """满足依赖条件"""
        can_do, missing = self.can_improve(capability_id)
        
        if not can_do:
            # 先提升依赖
            for dep in missing:
                self.improve(dep, 0.1, f"dependency_for_{capability_id}")
        
        return True
    
    # ==================== 能力探索 ====================
    
    def suggest_improvements(self, context: str = "", max_suggestions: int = 3) -> List[Dict]:
        """建议能力提升"""
        suggestions = []
        
        for cap_id, score in self.scores.items():
            dim = self.dimensions[cap_id]
            
            # 计算提升潜力
            potential = dim.max_level - score.current
            
            if potential > 0.1:  # 有提升空间
                # 计算提升优先级
                priority = potential * dim.growth_rate
                
                # 检查依赖
                deps_met, _ = self.can_improve(cap_id, 0.1)
                
                suggestions.append({
                    "capability_id": cap_id,
                    "current": score.current,
                    "potential": potential,
                    "priority": priority,
                    "dependencies_met": deps_met,
                    "domain": dim.domain.value,
                    "description": dim.description
                })
        
        # 按优先级排序
        suggestions.sort(key=lambda x: x["priority"], reverse=True)
        
        return suggestions[:max_suggestions]
    
    def get_learning_path(self, target_capability: str, min_level: float = 0.7) -> List[str]:
        """获取学习路径"""
        if target_capability not in self.dimensions:
            return []
        
        path = []
        visited = set()
        
        def build_path(cap_id: str):
            if cap_id in visited:
                return
            
            visited.add(cap_id)
            
            # 检查当前水平
            current = self.get(cap_id)
            if current >= min_level:
                return
            
            # 获取依赖
            deps = self.get_dependencies(cap_id)
            for dep in deps:
                build_path(dep)
            
            path.append(cap_id)
        
        build_path(target_capability)
        return path
    
    # ==================== 状态查询 ====================
    
    def get_capability_list(self) -> List[Dict]:
        """获取能力列表"""
        result = []
        
        for cap_id, score in self.scores.items():
            dim = self.dimensions[cap_id]
            
            result.append({
                "id": cap_id,
                "name": dim.name,
                "domain": dim.domain.value,
                "current": score.current,
                "potential": score.potential,
                "level": score.level().name,
                "experience": score.experience,
                "description": dim.description,
                "tags": dim.tags
            })
        
        return result
    
    def get_status(self) -> Dict:
        """获取能力矩阵状态"""
        # 按领域分组
        domains = defaultdict(list)
        
        for cap_id, score in self.scores.items():
            dim = self.dimensions[cap_id]
            domains[dim.domain.value].append({
                "id": cap_id,
                "current": score.current,
                "level": score.level().name
            })
        
        # 计算领域分数
        domain_scores = {}
        for domain in CapabilityDomain:
            domain_scores[domain.value] = self.get_domain_score(domain)
        
        return {
            "agent_id": self.agent_id,
            "overall_score": self.get_overall_score(),
            "domain_scores": domain_scores,
            "total_capabilities": len(self.scores),
            "total_growth": self.total_growth,
            "total_decay": self.total_decay,
            "domains": dict(domains),
            "suggestions": self.suggest_improvements()
        }
    
    # ==================== 串行化 ====================
    
    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "agent_id": self.agent_id,
            "scores": {
                cap_id: {
                    "current": score.current,
                    "potential": score.potential,
                    "experience": score.experience,
                    "mastery": score.mastery,
                    "last_updated": score.last_updated
                }
                for cap_id, score in self.scores.items()
            },
            "total_growth": self.total_growth,
            "total_decay": self.total_decay
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CapabilityMatrix':
        """从字典反序列化"""
        matrix = cls(data["agent_id"])
        
        for cap_id, score_data in data.get("scores", {}).items():
            if cap_id in matrix.scores:
                matrix.scores[cap_id].current = score_data.get("current", 0)
                matrix.scores[cap_id].potential = score_data.get("potential", 1)
                matrix.scores[cap_id].experience = score_data.get("experience", 0)
                matrix.scores[cap_id].mastery = score_data.get("mastery", 0)
                matrix.scores[cap_id].last_updated = score_data.get("last_updated", time.time())
        
        matrix.total_growth = data.get("total_growth", 0)
        matrix.total_decay = data.get("total_decay", 0)
        
        return matrix


class CapabilityMatrixManager:
    """
    能力矩阵管理器
    管理多个智能体的能力矩阵
    """
    
    def __init__(self):
        self.matrices: Dict[str, CapabilityMatrix] = {}
    
    def create_matrix(self, agent_id: str, custom_dimensions: Optional[Dict[str, CapabilityDimension]] = None) -> CapabilityMatrix:
        """创建能力矩阵"""
        matrix = CapabilityMatrix(agent_id, custom_dimensions)
        self.matrices[agent_id] = matrix
        return matrix
    
    def get_matrix(self, agent_id: str) -> Optional[CapabilityMatrix]:
        """获取能力矩阵"""
        return self.matrices.get(agent_id)
    
    def remove_matrix(self, agent_id: str):
        """移除能力矩阵"""
        if agent_id in self.matrices:
            del self.matrices[agent_id]
    
    def compare_agents(self, agent_id1: str, agent_id2: str) -> Dict:
        """比较两个智能体的能力"""
        matrix1 = self.get_matrix(agent_id1)
        matrix2 = self.get_matrix(agent_id2)
        
        if not matrix1 or not matrix2:
            return {"error": "Agent not found"}
        
        comparison = {
            "agent1": agent_id1,
            "agent2": agent_id2,
            "overall": {
                "agent1": matrix1.get_overall_score(),
                "agent2": matrix2.get_overall_score(),
                "difference": matrix1.get_overall_score() - matrix2.get_overall_score()
            },
            "domains": {}
        }
        
        for domain in CapabilityDomain:
            score1 = matrix1.get_domain_score(domain)
            score2 = matrix2.get_domain_score(domain)
            
            comparison["domains"][domain.value] = {
                "agent1": score1,
                "agent2": score2,
                "difference": score1 - score2
            }
        
        return comparison
    
    def find_complementary_pairs(self, min_score_diff: float = 0.2) -> List[Tuple[str, str]]:
        """寻找互补的智能体对"""
        pairs = []
        agent_ids = list(self.matrices.keys())
        
        for i, id1 in enumerate(agent_ids):
            for id2 in agent_ids[i+1:]:
                m1 = self.matrices[id1]
                m2 = self.matrices[id2]
                
                # 计算整体差异
                diff = abs(m1.get_overall_score() - m2.get_overall_score())
                
                if diff >= min_score_diff:
                    pairs.append((id1, id2))
        
        return pairs
    
    def get_all_status(self) -> Dict:
        """获取所有矩阵状态"""
        return {
            agent_id: matrix.get_status()
            for agent_id, matrix in self.matrices.items()
        }


# 全局管理器
_capability_manager = CapabilityMatrixManager()


def get_capability_manager() -> CapabilityMatrixManager:
    """获取全局能力矩阵管理器"""
    return _capability_manager


# 示例使用
if __name__ == "__main__":
    # 创建能力矩阵
    matrix = CapabilityMatrix("test-agent-001")
    
    # 获取能力
    print(f"Memory: {matrix.get('memory')}")
    print(f"Learning: {matrix.get('learning')}")
    
    # 提升能力
    matrix.improve("memory", 0.2, "practice")
    print(f"Memory after improvement: {matrix.get('memory')}")
    
    # 从任务学习
    task_result = {
        "task_id": "task-001",
        "capabilities_used": ["memory", "comprehension", "logical_reasoning"],
        "performance": 0.8
    }
    matrix.learn_from_task(task_result)
    
    # 获取状态
    status = matrix.get_status()
    print(f"Overall score: {status['overall_score']}")
    print(f"Domain scores: {status['domain_scores']}")
    
    # 建议
    print(f"Suggestions: {status['suggestions']}")