#!/usr/bin/env python3
"""
自主进化引擎 (Autonomous Evolution Engine)
自我迭代与持续进化的核心系统

功能：
- 自我评估与改进
- 能力边界扩展
- 行为模式优化
- 适应性进化

作者: 奥创 (Ultron)
版本: 1.0
创建时间: 2026-03-04
"""

import json
import time
import hashlib
import random
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque


class EvolutionType(Enum):
    """进化类型"""
    GRADUAL = "gradual"           # 渐进式
    BREAKTHROUGH = "breakthrough" # 突破式
    ADAPTIVE = "adaptive"         # 适应性
    EMERGENT = "emergent"         # 涌现式


class CapabilityDomain(Enum):
    """能力域"""
    COGNITION = "cognition"       # 认知
    LEARNING = "learning"         # 学习
    REASONING = "reasoning"       # 推理
    CREATIVITY = "creativity"     # 创造
    MEMORY = "memory"             # 记忆
    DECISION = "decision"         # 决策
    ACTION = "action"             # 行动
    METACOGNITION = "metacognition"  # 元认知


@dataclass
class Capability:
    """能力单元"""
    name: str
    domain: CapabilityDomain
    level: float = 1.0            # 0-10
    potential: float = 1.0        # 潜在上限
    last_improved: float = field(default_factory=time.time)
    improvement_count: int = 0
    tags: List[str] = field(default_factory=list)
    
    def can_improve(self) -> bool:
        """是否还能提升"""
        return self.level < self.potential
    
    def improve(self, amount: float = 0.1) -> bool:
        """提升能力"""
        if self.can_improve():
            self.level = min(self.potential, self.level + amount)
            self.last_improved = time.time()
            self.improvement_count += 1
            return True
        return False
    
    def assess_gap(self, target: float) -> float:
        """评估与目标的差距"""
        return max(0, target - self.level)


@dataclass
class EvolutionRecord:
    """进化记录"""
    timestamp: float
    evolution_type: EvolutionType
    capability: str
    from_level: float
    to_level: float
    trigger: str
    description: str


@dataclass
class SelfAssessment:
    """自我评估结果"""
    overall_score: float
    strengths: List[str]
    weaknesses: List[str]
    opportunities: List[str]
    threats: List[str]
    recommendations: List[str]
    timestamp: float = field(default_factory=time.time)


class EvolutionStrategy:
    """进化策略"""
    
    def __init__(self, name: str, priority: float = 1.0):
        self.name = name
        self.priority = priority
        self.success_count = 0
        self.failure_count = 0
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.5
    
    def record_success(self):
        self.success_count += 1
    
    def record_failure(self):
        self.failure_count += 1


class AutonomousEvolutionEngine:
    """自主进化引擎"""
    
    def __init__(self, config_path: str = None):
        # 能力系统
        self.capabilities: Dict[str, Capability] = {}
        self.capability_trees: Dict[CapabilityDomain, List[str]] = {
            domain: [] for domain in CapabilityDomain
        }
        
        # 进化历史
        self.evolution_history: deque = deque(maxlen=1000)
        self.self_assessments: deque = deque(maxlen=100)
        
        # 进化策略
        self.strategies: Dict[str, EvolutionStrategy] = {}
        self.current_strategy: Optional[EvolutionStrategy] = None
        
        # 状态
        self.is_evolving = False
        self.evolution_cycle = 0
        self.last_evolution: float = time.time()
        
        # 配置
        self.config = {
            "auto_evolve_enabled": True,
            "evolution_interval": 3600,       # 1小时
            "min_improvement_threshold": 0.05,
            "max_parallel_evolutions": 3,
            "exploration_rate": 0.2,          # 探索率
            "exploitation_rate": 0.8,         # 利用率
            "capability_decay": 0.01,         # 能力衰减
        }
        
        if config_path:
            self._load_config(config_path)
        
        self._initialize_default_capabilities()
        self._initialize_strategies()
        self.lock = threading.RLock()
    
    def _load_config(self, path: str):
        """加载配置"""
        try:
            with open(path, 'r') as f:
                self.config.update(json.load(f))
        except Exception as e:
            print(f"Config load warning: {e}")
    
    def _initialize_default_capabilities(self):
        """初始化默认能力"""
        default_caps = [
            # 认知能力
            ("pattern_recognition", CapabilityDomain.COGNITION, 5.0, 8.0, ["视觉", "文本", "时序"]),
            ("abstraction", CapabilityDomain.COGNITION, 4.5, 8.5, ["概念", "关系"]),
            ("generalization", CapabilityDomain.COGNITION, 4.0, 8.0, ["迁移", "泛化"]),
            
            # 学习能力
            ("few_shot_learning", CapabilityDomain.LEARNING, 5.5, 9.0, ["快速", "高效"]),
            ("continual_learning", CapabilityDomain.LEARNING, 4.0, 8.5, ["持续", "累积"]),
            ("meta_learning", CapabilityDomain.LEARNING, 3.5, 9.0, ["学习如何学习"]),
            
            # 推理能力
            ("logical_reasoning", CapabilityDomain.REASONING, 5.0, 8.5, ["演绎", "归纳"]),
            ("causal_reasoning", CapabilityDomain.REASONING, 4.0, 9.0, ["因果"]),
            ("analogical_reasoning", CapabilityDomain.REASONING, 4.5, 8.0, ["类比"]),
            
            # 创造力
            ("divergent_thinking", CapabilityDomain.CREATIVITY, 4.0, 8.0, ["发散"]),
            ("concept_blending", CapabilityDomain.CREATIVITY, 3.5, 8.5, ["融合"]),
            ("novel_generation", CapabilityDomain.CREATIVITY, 3.0, 9.0, ["原创"]),
            
            # 记忆能力
            ("episodic_memory", CapabilityDomain.MEMORY, 4.5, 8.0, ["情景"]),
            ("semantic_memory", CapabilityDomain.MEMORY, 5.0, 8.5, ["概念"]),
            ("working_memory", CapabilityDomain.MEMORY, 5.5, 8.0, ["工作"]),
            
            # 决策能力
            ("multi_criteria", CapabilityDomain.DECISION, 4.0, 8.5, ["多标准"]),
            ("risk_assessment", CapabilityDomain.DECISION, 4.5, 8.0, ["风险"]),
            ("long_term_planning", CapabilityDomain.DECISION, 3.5, 9.0, ["长期"]),
            
            # 元认知
            ("self_monitoring", CapabilityDomain.METACOGNITION, 4.0, 8.0, ["监控"]),
            ("strategy_selection", CapabilityDomain.METACOGNITION, 3.5, 8.5, ["策略"]),
            ("performance_tuning", CapabilityDomain.METACOGNITION, 3.0, 9.0, ["调优"]),
        ]
        
        for name, domain, level, potential, tags in default_caps:
            cap = Capability(
                name=name,
                domain=domain,
                level=level,
                potential=potential,
                tags=tags
            )
            self.capabilities[name] = cap
            self.capability_trees[domain].append(name)
    
    def _initialize_strategies(self):
        """初始化进化策略"""
        self.strategies = {
            "gradual": EvolutionStrategy("渐进化", 0.4),
            "breakthrough": EvolutionStrategy("突破化", 0.2),
            "adaptive": EvolutionStrategy("适应化", 0.3),
            "exploratory": EvolutionStrategy("探索化", 0.1),
        }
        self.current_strategy = self.strategies["gradual"]
    
    def assess_self(self) -> SelfAssessment:
        """自我评估"""
        # 计算各维度得分
        domain_scores = {}
        for domain in CapabilityDomain:
            caps = self.capability_trees[domain]
            if caps:
                scores = [self.capabilities[c].level for c in caps]
                domain_scores[domain.value] = sum(scores) / len(scores)
        
        overall = sum(domain_scores.values()) / len(domain_scores) if domain_scores else 0
        
        # 识别强项和弱项
        sorted_caps = sorted(
            self.capabilities.items(),
            key=lambda x: x[1].level,
            reverse=True
        )
        
        strengths = [c[0] for c in sorted_caps[:3]]
        weaknesses = [c[0] for c in sorted_caps[-3:]]
        
        # 识别机会和威胁
        opportunities = []
        threats = []
        
        for name, cap in self.capabilities.items():
            if cap.can_improve() and cap.level < cap.potential * 0.7:
                opportunities.append(f"{name} 可提升")
            if time.time() - cap.last_improved > 86400:  # 24小时未提升
                threats.append(f"{name} 可能退化")
        
        # 生成建议
        recommendations = self._generate_recommendations(weaknesses, opportunities)
        
        assessment = SelfAssessment(
            overall_score=overall,
            strengths=strengths,
            weaknesses=weaknesses,
            opportunities=opportunities,
            threats=threats,
            recommendations=recommendations
        )
        
        self.self_assessments.append(assessment)
        return assessment
    
    def _generate_recommendations(self, weaknesses: List[str], opportunities: List[str]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        # 基于弱点
        for w in weaknesses[:2]:
            cap = self.capabilities.get(w)
            if cap:
                recommendations.append(
                    f"重点提升 {w}: 当前 {cap.level:.1f}/潜在 {cap.potential:.1f}"
                )
        
        # 基于机会
        for o in opportunities[:2]:
            recommendations.append(f"抓住机会: {o}")
        
        # 策略建议
        if self.current_strategy:
            recommendations.append(
                f"采用策略: {self.current_strategy.name}"
            )
        
        return recommendations
    
    def evolve(self, target_capability: str = None, 
               evolution_type: EvolutionType = None) -> Optional[EvolutionRecord]:
        """
        执行进化
        
        Args:
            target_capability: 目标能力（None则自动选择）
            evolution_type: 进化类型
        
        Returns:
            EvolutionRecord: 进化记录
        """
        with self.lock:
            if self.is_evolving:
                return None
            
            self.is_evolving = True
            self.evolution_cycle += 1
        
        try:
            # 选择进化类型
            if evolution_type is None:
                evolution_type = self._select_evolution_type()
            
            # 选择目标能力
            if target_capability is None:
                target_capability = self._select_target_capability()
            
            cap = self.capabilities.get(target_capability)
            if not cap:
                return None
            
            from_level = cap.level
            
            # 执行进化
            improvement = self._execute_evolution(cap, evolution_type)
            
            to_level = cap.level
            cap.improve(improvement)
            
            # 记录
            record = EvolutionRecord(
                timestamp=time.time(),
                evolution_type=evolution_type,
                capability=target_capability,
                from_level=from_level,
                to_level=to_level,
                trigger=f"cycle_{self.evolution_cycle}",
                description=f"{evolution_type.value}进化: {target_capability}"
            )
            
            self.evolution_history.append(record)
            self.last_evolution = time.time()
            
            # 更新策略
            self._update_strategy(improvement > self.config["min_improvement_threshold"])
            
            return record
            
        finally:
            self.is_evolving = False
    
    def _select_evolution_type(self) -> EvolutionType:
        """选择进化类型"""
        # epsilon-greedy 策略
        if random.random() < self.config["exploration_rate"]:
            # 探索新类型
            return random.choice([
                EvolutionType.BREAKTHROUGH,
                EvolutionType.EMERGENT,
                EvolutionType.ADAPTIVE
            ])
        else:
            # 利用已知有效类型
            if self.current_strategy:
                if self.current_strategy.success_rate > 0.7:
                    return EvolutionType.BREAKTHROUGH
                elif self.current_strategy.success_rate > 0.4:
                    return EvolutionType.ADAPTIVE
            return EvolutionType.GRADUAL
    
    def _select_target_capability(self) -> str:
        """选择目标能力"""
        # 基于需求选择
        candidates = []
        
        for name, cap in self.capabilities.items():
            if not cap.can_improve():
                continue
            
            # 计算优先级分数
            priority = 0.0
            
            # 潜力越大越优先
            priority += (cap.potential - cap.level) * 0.3
            
            # 长时间未提升的优先
            time_gap = time.time() - cap.last_improved
            priority += min(time_gap / 86400, 1.0) * 0.2
            
            # 弱点优先（反向：level低的优先）
            priority += (10 - cap.level) * 0.3
            
            # 随机因素（保持多样性）
            priority += random.random() * 0.2
            
            candidates.append((name, priority))
        
        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]
        
        # 降级：随机选择可提升的能力
        improvable = [n for n, c in self.capabilities.items() if c.can_improve()]
        return random.choice(improvable) if improvable else list(self.capabilities.keys())[0]
    
    def _execute_evolution(self, cap: Capability, evo_type: EvolutionType) -> float:
        """执行进化"""
        base_improvement = 0.1
        
        type_bonuses = {
            EvolutionType.GRADUAL: 0.1,
            EvolutionType.BREAKTHROUGH: 0.3,
            EvolutionType.ADAPTIVE: 0.2,
            EvolutionType.EMERGENT: 0.4,
        }
        
        # 考虑能力域的难度
        domain_difficulty = {
            CapabilityDomain.METACOGNITION: 1.5,
            CapabilityDomain.CREATIVITY: 1.3,
            CapabilityDomain.REASONING: 1.2,
            CapabilityDomain.COGNITION: 1.0,
            CapabilityDomain.LEARNING: 1.1,
            CapabilityDomain.MEMORY: 1.0,
            CapabilityDomain.DECISION: 1.1,
            CapabilityDomain.ACTION: 1.0,
        }
        
        difficulty = domain_difficulty.get(cap.domain, 1.0)
        bonus = type_bonuses.get(evo_type, 0.1)
        
        improvement = base_improvement * bonus / difficulty
        
        # 随机波动
        improvement *= random.uniform(0.8, 1.2)
        
        return max(0.01, improvement)
    
    def _update_strategy(self, success: bool):
        """更新进化策略"""
        if not self.current_strategy:
            return
        
        if success:
            self.current_strategy.record_success()
        else:
            self.current_strategy.record_failure()
        
        # 如果当前策略效果不好，考虑切换
        if self.current_strategy.failure_count > 5:
            # 切换到更保守的策略
            if self.current_strategy.name == "突破化":
                self.current_strategy = self.strategies["gradual"]
            elif self.current_strategy.name == "探索化":
                self.current_strategy = self.strategies["adaptive"]
    
    def auto_evolve(self) -> List[EvolutionRecord]:
        """自动进化"""
        records = []
        max_evolutions = self.config["max_parallel_evolutions"]
        
        for _ in range(max_evolutions):
            if not self.config["auto_evolve_enabled"]:
                break
            record = self.evolve()
            if record:
                records.append(record)
        
        return records
    
    def get_evolution_analytics(self) -> Dict[str, Any]:
        """获取进化分析"""
        if not self.evolution_history:
            return {"status": "No evolution history"}
        
        recent = list(self.evolution_history)[-50:]
        
        # 进化类型分布
        type_counts = {}
        for r in recent:
            t = r.evolution_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
        
        # 平均提升
        avg_improvement = sum(
            r.to_level - r.from_level for r in recent
        ) / len(recent)
        
        # 最常进化的能力
        cap_counts = {}
        for r in recent:
            cap_counts[r.capability] = cap_counts.get(r.capability, 0) + 1
        
        most_evolved = max(cap_counts.items(), key=lambda x: x[1]) if cap_counts else (None, 0)
        
        return {
            "total_evolution_cycles": self.evolution_cycle,
            "recent_improvement": avg_improvement,
            "evolution_types": type_counts,
            "most_evolved_capability": most_evolved[0],
            "evolution_frequency": len(recent) / max(1, time.time() - self.last_evolution) * 3600,
            "strategies": {
                name: {
                    "priority": s.priority,
                    "success_rate": s.success_rate,
                    "successes": s.success_count,
                    "failures": s.failure_count
                }
                for name, s in self.strategies.items()
            }
        }
    
    def get_capability_map(self) -> Dict[str, Any]:
        """获取能力地图"""
        domain_map = {}
        
        for domain in CapabilityDomain:
            caps = self.capability_trees[domain]
            if caps:
                domain_map[domain.value] = {
                    "count": len(caps),
                    "average_level": sum(self.capabilities[c].level for c in caps) / len(caps),
                    "capabilities": {
                        c: {
                            "level": self.capabilities[c].level,
                            "potential": self.capabilities[c].potential,
                            "can_improve": self.capabilities[c].can_improve(),
                            "gap": self.capabilities[c].assess_gap(self.capabilities[c].potential)
                        }
                        for c in caps
                    }
                }
        
        return domain_map
    
    def export_state(self) -> Dict:
        """导出状态"""
        return {
            "capabilities": {
                name: {
                    "level": cap.level,
                    "potential": cap.potential,
                    "improvement_count": cap.improvement_count
                }
                for name, cap in self.capabilities.items()
            },
            "evolution_cycle": self.evolution_cycle,
            "last_evolution": self.last_evolution,
            "config": self.config
        }
    
    def import_state(self, state: Dict):
        """导入状态"""
        if "capabilities" in state:
            for name, data in state["capabilities"].items():
                if name in self.capabilities:
                    self.capabilities[name].level = data.get("level", 1.0)
                    self.capabilities[name].potential = data.get("potential", 1.0)
        
        if "evolution_cycle" in state:
            self.evolution_cycle = state["evolution_cycle"]
        if "last_evolution" in state:
            self.last_evolution = state["last_evolution"]


def main():
    """主函数 - 测试自主进化引擎"""
    print("=" * 60)
    print("🧬 自主进化引擎 (Autonomous Evolution Engine)")
    print("=" * 60)
    
    # 创建引擎
    engine = AutonomousEvolutionEngine()
    
    # 自我评估
    print("\n📊 自我评估:")
    assessment = engine.assess_self()
    print(f"  总体得分: {assessment.overall_score:.2f}/10")
    print(f"  强项: {', '.join(assessment.strengths)}")
    print(f"  弱项: {', '.join(assessment.weaknesses)}")
    if assessment.recommendations:
        print("  建议:")
        for r in assessment.recommendations:
            print(f"    - {r}")
    
    # 执行进化
    print("\n🚀 执行进化:")
    records = engine.auto_evolve()
    for r in records:
        print(f"  {r.evolution_type.value}: {r.capability} {r.from_level:.2f}→{r.to_level:.2f}")
    
    # 能力地图
    print("\n🗺️ 能力地图:")
    cap_map = engine.get_capability_map()
    for domain, info in cap_map.items():
        print(f"  {domain}: 平均 {info['average_level']:.2f} ({info['count']}项)")
    
    # 进化分析
    print("\n📈 进化分析:")
    analytics = engine.get_evolution_analytics()
    for key, val in analytics.items():
        if key != "strategies":
            print(f"  {key}: {val}")
    
    print("\n" + "=" * 60)
    print("✅ 自主进化引擎测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()