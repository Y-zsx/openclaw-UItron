#!/usr/bin/env python3
"""
全智能系统协同平台 - 第3世：跨域决策与实时优化
Cross-Domain Decision & Real-Time Optimization System
跨领域决策支持 + 动态性能优化

功能：
1. 跨域决策引擎 - 多域协同决策
2. 实时性能优化 - 动态调整系统参数
3. 智能预测 - 基于历史数据的预测性优化
4. 自适应学习 - 从执行结果中持续优化
"""

import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import threading
import random
import math

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """决策类型"""
    TACTICAL = "tactical"       # 战术决策 - 短期
    OPERATIONAL = "operational" # 运营决策 - 中期
    STRATEGIC = "strategic"    # 战略决策 - 长期


class OptimizationScope(Enum):
    """优化范围"""
    LOCAL = "local"            # 本地优化
    DOMAIN = "domain"          # 域级优化
    SYSTEM = "system"          # 系统级优化
    GLOBAL = "global"          # 全局优化


@dataclass
class Decision:
    """决策"""
    id: str
    type: DecisionType
    scope: OptimizationScope
    description: str
    confidence: float = 0.0
    risk_level: float = 0.0
    expected_impact: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    executed_at: Optional[str] = None
    result: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "scope": self.scope.value,
            "description": self.description,
            "confidence": round(self.confidence, 2),
            "risk_level": round(self.risk_level, 2),
            "expected_impact": round(self.expected_impact, 2),
            "created_at": self.created_at,
            "executed_at": self.executed_at,
            "result": self.result
        }


@dataclass
class PerformanceData:
    """性能数据"""
    timestamp: str
    cpu_usage: float
    memory_usage: float
    throughput: float
    latency: float
    error_rate: float
    resource_utilization: float
    
    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp,
            "cpu_usage": round(self.cpu_usage, 2),
            "memory_usage": round(self.memory_usage, 2),
            "throughput": round(self.throughput, 2),
            "latency": round(self.latency, 2),
            "error_rate": round(self.error_rate, 2),
            "resource_utilization": round(self.resource_utilization, 2)
        }


class CrossDomainDecisionEngine:
    """
    跨域决策引擎
    综合多域信息，做出最优决策
    """
    
    def __init__(self):
        self.domains: Dict[str, Dict] = {}
        self.decisions: Dict[str, Decision] = {}
        self.decision_history: deque = deque(maxlen=500)
        
        # 决策规则
        self.decision_rules: Dict[str, Callable] = {}
        
        # 决策权重
        self.weights = {
            "performance": 0.3,
            "reliability": 0.3,
            "cost": 0.2,
            "speed": 0.2
        }
        
        logger.info("🎯 跨域决策引擎初始化完成")
    
    def register_domain(self, domain_id: str, domain_info: Dict) -> bool:
        """注册决策域"""
        self.domains[domain_id] = {
            "id": domain_id,
            "name": domain_info.get("name", domain_id),
            "type": domain_info.get("type", "general"),
            "capabilities": domain_info.get("capabilities", []),
            "priority": domain_info.get("priority", 1.0),
            "status": "active",
            "metrics": {}
        }
        
        logger.info(f"✅ 决策域注册: {domain_id}")
        return True
    
    def collect_domain_metrics(self, domain_id: str) -> Dict:
        """收集域指标"""
        domain = self.domains.get(domain_id)
        if not domain:
            return {}
        
        # 模拟指标收集
        return {
            "cpu_usage": random.uniform(0.2, 0.8),
            "memory_usage": random.uniform(0.3, 0.7),
            "throughput": random.uniform(50, 200),
            "latency": random.uniform(10, 100),
            "error_rate": random.uniform(0.01, 0.1),
            "success_rate": random.uniform(0.85, 0.99)
        }
    
    def evaluate_domain_health(self, domain_id: str) -> float:
        """评估域健康状态"""
        metrics = self.collect_domain_metrics(domain_id)
        
        if not metrics:
            return 0.0
        
        # 综合健康评分
        health = (
            (1 - metrics["cpu_usage"]) * 0.2 +
            (1 - metrics["memory_usage"]) * 0.2 +
            metrics["success_rate"] * 0.3 +
            (1 - metrics["error_rate"]) * 0.2 +
            (1 - metrics["latency"] / 500) * 0.1  # 归一化延迟
        )
        
        return min(1.0, health)
    
    def make_decision(self, context: Dict) -> Decision:
        """做出决策"""
        decision_id = f"decision_{len(self.decisions)}_{int(time.time())}"
        
        # 分析上下文
        decision_type = self._analyze_decision_type(context)
        scope = self._determine_scope(context)
        
        # 收集各域健康状态
        domain_health = {
            domain_id: self.evaluate_domain_health(domain_id)
            for domain_id in self.domains.keys()
        }
        
        # 计算决策置信度
        confidence = self._calculate_confidence(domain_health, context)
        
        # 评估风险
        risk_level = self._assess_risk(domain_health, context)
        
        # 预测影响
        expected_impact = self._predict_impact(decision_type, scope, domain_health)
        
        # 生成决策描述
        description = self._generate_description(decision_type, scope, domain_health)
        
        decision = Decision(
            id=decision_id,
            type=decision_type,
            scope=scope,
            description=description,
            confidence=confidence,
            risk_level=risk_level,
            expected_impact=expected_impact
        )
        
        self.decisions[decision_id] = decision
        self.decision_history.append(decision)
        
        logger.info(f"🎯 决策生成: {decision_id} ({decision_type.value}) - 置信度: {confidence:.2f}")
        
        return decision
    
    def _analyze_decision_type(self, context: Dict) -> DecisionType:
        """分析决策类型"""
        urgency = context.get("urgency", 0.5)
        complexity = context.get("complexity", 0.5)
        
        if urgency > 0.8:
            return DecisionType.TACTICAL
        elif complexity > 0.7:
            return DecisionType.STRATEGIC
        else:
            return DecisionType.OPERATIONAL
    
    def _determine_scope(self, context: Dict) -> OptimizationScope:
        """确定优化范围"""
        scope_type = context.get("scope", "system")
        
        if scope_type == "local":
            return OptimizationScope.LOCAL
        elif scope_type == "global":
            return OptimizationScope.GLOBAL
        elif scope_type == "domain":
            return OptimizationScope.DOMAIN
        else:
            return OptimizationScope.SYSTEM
    
    def _calculate_confidence(self, domain_health: Dict, context: Dict) -> float:
        """计算置信度"""
        if not domain_health:
            return 0.5
        
        avg_health = sum(domain_health.values()) / len(domain_health)
        
        # 根据健康状态和上下文调整
        confidence = avg_health * 0.7 + context.get("data_quality", 0.5) * 0.3
        
        return min(1.0, max(0.0, confidence))
    
    def _assess_risk(self, domain_health: Dict, context: Dict) -> float:
        """评估风险"""
        if not domain_health:
            return 0.5
        
        # 最低健康状态
        min_health = min(domain_health.values())
        
        # 风险与最低健康状态成反比
        risk = 1 - min_health
        
        # 考虑上下文风险因素
        risk *= (1 + context.get("risk_factor", 0))
        
        return min(1.0, max(0.0, risk))
    
    def _predict_impact(self, decision_type: DecisionType, 
                       scope: OptimizationScope, domain_health: Dict) -> float:
        """预测影响"""
        # 基础影响
        base_impact = {
            DecisionType.TACTICAL: 0.3,
            DecisionType.OPERATIONAL: 0.5,
            DecisionType.STRATEGIC: 0.8
        }.get(decision_type, 0.5)
        
        # 范围加成
        scope_bonus = {
            OptimizationScope.LOCAL: 0.1,
            OptimizationScope.DOMAIN: 0.3,
            OptimizationScope.SYSTEM: 0.5,
            OptimizationScope.GLOBAL: 0.8
        }.get(scope, 0.3)
        
        # 健康状态调整
        health_factor = sum(domain_health.values()) / len(domain_health) if domain_health else 0.5
        
        return (base_impact + scope_bonus) * health_factor
    
    def _generate_description(self, decision_type: DecisionType,
                             scope: OptimizationScope, domain_health: Dict) -> str:
        """生成决策描述"""
        type_name = decision_type.value
        scope_name = scope.value
        
        # 找出最需要优化的域
        if domain_health:
            worst_domain = min(domain_health.items(), key=lambda x: x[1])
            domain_name = worst_domain[0]
        else:
            domain_name = "多个域"
        
        return f"为{domain_name}执行{type_name}级别的{scope_name}优化决策"
    
    def execute_decision(self, decision_id: str) -> Dict:
        """执行决策"""
        decision = self.decisions.get(decision_id)
        if not decision:
            return {"status": "error", "message": "决策不存在"}
        
        # 模拟执行
        time.sleep(0.1)
        
        # 更新决策状态
        decision.executed_at = datetime.now().isoformat()
        decision.result = {
            "status": "success",
            "execution_time": random.uniform(0.5, 2.0),
            "improvement": decision.expected_impact * random.uniform(0.8, 1.2)
        }
        
        logger.info(f"✅ 决策执行: {decision_id} - 改进: {decision.result['improvement']:.2f}")
        
        return decision.result
    
    def get_decision_history(self, limit: int = 10) -> List[Dict]:
        """获取决策历史"""
        decisions = list(self.decision_history)[-limit:]
        return [d.to_dict() for d in decisions]
    
    def get_recommendations(self) -> List[str]:
        """获取优化建议"""
        recommendations = []
        
        # 分析域健康状态
        for domain_id in self.domains.keys():
            health = self.evaluate_domain_health(domain_id)
            
            if health < 0.5:
                recommendations.append(f"⚠️ {domain_id}健康状态不佳({health:.2f})，建议进行优化")
            elif health > 0.8:
                recommendations.append(f"✅ {domain_id}运行良好")
        
        # 分析最近决策
        recent_decisions = list(self.decision_history)[-5:]
        if recent_decisions:
            avg_confidence = sum(d.confidence for d in recent_decisions) / len(recent_decisions)
            if avg_confidence < 0.6:
                recommendations.append("⚠️ 近期决策置信度较低，建议收集更多数据")
        
        return recommendations


class RealTimeOptimizer:
    """
    实时性能优化器
    动态调整系统参数以优化性能
    """
    
    def __init__(self):
        self.performance_history: deque = deque(maxlen=1000)
        self.optimization_rules: Dict[str, Callable] = {}
        self.active_optimizations: Dict[str, Dict] = {}
        
        # 优化参数
        self.thresholds = {
            "cpu_high": 0.8,
            "cpu_low": 0.2,
            "memory_high": 0.85,
            "memory_low": 0.3,
            "latency_high": 100,
            "latency_low": 20,
            "error_rate_high": 0.05
        }
        
        # 优化策略
        self.strategies = {
            "scale_up": self._scale_up,
            "scale_down": self._scale_down,
            "balance": self._balance_load,
            "prioritize": self._prioritize_traffic,
            "cache": self._enable_caching,
            "compress": self._compress_data
        }
        
        logger.info("⚡ 实时性能优化器初始化完成")
    
    def record_performance(self, data: PerformanceData):
        """记录性能数据"""
        self.performance_history.append(data)
        
        # 触发自动优化检查
        self._check_optimization_needed(data)
    
    def _check_optimization_needed(self, data: PerformanceData):
        """检查是否需要优化"""
        optimizations_needed = []
        
        # CPU检查
        if data.cpu_usage > self.thresholds["cpu_high"]:
            optimizations_needed.append("scale_up")
        elif data.cpu_usage < self.thresholds["cpu_low"]:
            optimizations_needed.append("scale_down")
        
        # 内存检查
        if data.memory_usage > self.thresholds["memory_high"]:
            optimizations_needed.append("balance")
        
        # 延迟检查
        if data.latency > self.thresholds["latency_high"]:
            optimizations_needed.append("cache")
        
        # 错误率检查
        if data.error_rate > self.thresholds["error_rate_high"]:
            optimizations_needed.append("prioritize")
        
        # 执行优化
        for opt in optimizations_needed:
            self._execute_optimization(opt, data)
    
    def _execute_optimization(self, strategy: str, data: PerformanceData):
        """执行优化策略"""
        if strategy not in self.strategies:
            return
        
        opt_id = f"opt_{strategy}_{int(time.time())}"
        
        # 执行优化
        result = self.strategies[strategy](data)
        
        self.active_optimizations[opt_id] = {
            "id": opt_id,
            "strategy": strategy,
            "timestamp": datetime.now().isoformat(),
            "data": data.to_dict(),
            "result": result
        }
        
        logger.info(f"⚡ 执行优化: {strategy} - {result}")
    
    def _scale_up(self, data: PerformanceData) -> Dict:
        """扩容优化"""
        return {
            "action": "scale_up",
            "target": "compute_resources",
            "scale_factor": 1.2,
            "expected_improvement": (data.cpu_usage - 0.5) * 0.3
        }
    
    def _scale_down(self, data: PerformanceData) -> Dict:
        """缩容优化"""
        return {
            "action": "scale_down",
            "target": "compute_resources",
            "scale_factor": 0.8,
            "expected_savings": (0.5 - data.cpu_usage) * 0.2
        }
    
    def _balance_load(self, data: PerformanceData) -> Dict:
        """负载均衡"""
        return {
            "action": "load_balance",
            "target": "all_domains",
            "method": "adaptive",
            "expected_improvement": data.memory_usage * 0.15
        }
    
    def _prioritize_traffic(self, data: PerformanceData) -> Dict:
        """流量优先级"""
        return {
            "action": "prioritize",
            "target": "network",
            "qos_level": "high",
            "expected_reduction": data.error_rate * 0.5
        }
    
    def _enable_caching(self, data: PerformanceData) -> Dict:
        """启用缓存"""
        return {
            "action": "enable_cache",
            "target": "storage",
            "cache_size": "large",
            "expected_latency_reduction": data.latency * 0.3
        }
    
    def _compress_data(self, data: PerformanceData) -> Dict:
        """数据压缩"""
        return {
            "action": "compress",
            "target": "network",
            "compression_ratio": 0.6,
            "expected_bandwidth_reduction": 0.4
        }
    
    def analyze_trends(self) -> Dict:
        """分析性能趋势"""
        if len(self.performance_history) < 10:
            return {"status": "insufficient_data"}
        
        # 收集指标
        cpu_values = [d.cpu_usage for d in self.performance_history]
        memory_values = [d.memory_usage for d in self.performance_history]
        throughput_values = [d.throughput for d in self.performance_history]
        latency_values = [d.latency for d in self.performance_history]
        
        # 计算趋势
        def calculate_trend(values: List[float]) -> str:
            if len(values) < 2:
                return "stable"
            
            recent = values[-5:]
            older = values[-10:-5] if len(values) >= 10 else values[:-5]
            
            if not older:
                return "stable"
            
            avg_recent = sum(recent) / len(recent)
            avg_older = sum(older) / len(older)
            
            diff = (avg_recent - avg_older) / (avg_older + 0.01)
            
            if diff > 0.1:
                return "increasing"
            elif diff < -0.1:
                return "decreasing"
            else:
                return "stable"
        
        return {
            "cpu_trend": calculate_trend(cpu_values),
            "memory_trend": calculate_trend(memory_values),
            "throughput_trend": calculate_trend(throughput_values),
            "latency_trend": calculate_trend(latency_values),
            "sample_count": len(self.performance_history)
        }
    
    def get_active_optimizations(self) -> List[Dict]:
        """获取活跃优化"""
        return list(self.active_optimizations.values())[-10:]


class PredictiveOptimizer:
    """
    预测性优化器
    基于历史数据预测未来性能并提前优化
    """
    
    def __init__(self):
        self.prediction_model = SimplePredictor()
        self.predictions: deque = deque(maxlen=100)
        self.optimization_schedule: Dict[str, Dict] = {}
        
        logger.info("🔮 预测性优化器初始化完成")
    
    def predict_performance(self, look_ahead: int = 5) -> Dict:
        """预测未来性能"""
        prediction = self.prediction_model.predict(look_ahead)
        
        self.predictions.append({
            "timestamp": datetime.now().isoformat(),
            "prediction": prediction,
            "look_ahead": look_ahead
        })
        
        return prediction
    
    def schedule_optimization(self, prediction: Dict) -> Optional[str]:
        """安排优化"""
        predicted_issues = []
        
        # 检查预测的问题
        if prediction.get("cpu_predicted", 0) > 0.8:
            predicted_issues.append("cpu_overload")
        if prediction.get("memory_predicted", 0) > 0.85:
            predicted_issues.append("memory_pressure")
        if prediction.get("latency_predicted", 0) > 100:
            predicted_issues.append("high_latency")
        
        if not predicted_issues:
            return None
        
        # 生成优化计划
        schedule_id = f"schedule_{len(self.optimization_schedule)}_{int(time.time())}"
        
        self.optimization_schedule[schedule_id] = {
            "id": schedule_id,
            "predicted_issues": predicted_issues,
            "scheduled_time": datetime.now().isoformat(),
            "optimizations": [
                {"issue": issue, "strategy": self._get_strategy_for_issue(issue)}
                for issue in predicted_issues
            ],
            "status": "scheduled"
        }
        
        logger.info(f"📅 优化计划: {schedule_id} - {predicted_issues}")
        
        return schedule_id
    
    def _get_strategy_for_issue(self, issue: str) -> str:
        """获取问题对应的优化策略"""
        strategies = {
            "cpu_overload": "scale_up",
            "memory_pressure": "balance",
            "high_latency": "cache"
        }
        return strategies.get(issue, "balance")


class SimplePredictor:
    """简单预测器 - 基于移动平均"""
    
    def __init__(self):
        self.history: List[Dict] = []
    
    def predict(self, look_ahead: int) -> Dict:
        """预测"""
        # 简化实现：基于随机预测
        return {
            "cpu_predicted": random.uniform(0.3, 0.7),
            "memory_predicted": random.uniform(0.4, 0.8),
            "throughput_predicted": random.uniform(80, 150),
            "latency_predicted": random.uniform(30, 80),
            "confidence": random.uniform(0.6, 0.9)
        }


class AdaptiveLearningOptimizer:
    """
    自适应学习优化器
    从执行结果中持续学习和优化
    """
    
    def __init__(self):
        self.learning_history: deque = deque(maxlen=500)
        self.optimization_effects: Dict[str, List[float]] = defaultdict(list)
        self.learned_patterns: Dict[str, Dict] = {}
        
        # 学习参数
        self.learning_rate = 0.1
        self.discount_factor = 0.9
        
        logger.info("🧠 自适应学习优化器初始化完成")
    
    def record_optimization_result(self, optimization: Dict, result: Dict):
        """记录优化结果"""
        improvement = result.get("improvement", 0)
        
        # 记录优化效果
        strategy = optimization.get("strategy", "unknown")
        self.optimization_effects[strategy].append(improvement)
        
        # 记录学习历史
        self.learning_history.append({
            "optimization": optimization,
            "result": result,
            "improvement": improvement,
            "timestamp": datetime.now().isoformat()
        })
        
        # 更新学习模式
        self._update_patterns(strategy, improvement)
    
    def _update_patterns(self, strategy: str, improvement: float):
        """更新学习模式"""
        if strategy not in self.learned_patterns:
            self.learned_patterns[strategy] = {
                "count": 0,
                "total_improvement": 0,
                "avg_improvement": 0,
                "best_improvement": float('-inf'),
                "confidence": 0
            }
        
        pattern = self.learned_patterns[strategy]
        
        # 更新统计
        pattern["count"] += 1
        pattern["total_improvement"] += improvement
        pattern["avg_improvement"] = pattern["total_improvement"] / pattern["count"]
        pattern["best_improvement"] = max(pattern["best_improvement"], improvement)
        
        # 更新置信度
        pattern["confidence"] = min(1.0, pattern["count"] / 20)
    
    def get_best_strategy(self, context: Dict) -> str:
        """获取最佳策略"""
        if not self.learned_patterns:
            return "balance"  # 默认策略
        
        # 根据上下文选择最佳策略
        cpu_usage = context.get("cpu_usage", 0.5)
        
        if cpu_usage > 0.8:
            # 高CPU：选择scale_up
            candidates = ["scale_up", "balance"]
        elif cpu_usage < 0.3:
            # 低CPU：选择scale_down
            candidates = ["scale_down", "balance"]
        else:
            candidates = list(self.learned_patterns.keys())
        
        # 选择平均效果最好的
        best_strategy = max(
            candidates,
            key=lambda s: self.learned_patterns.get(s, {}).get("avg_improvement", 0)
        )
        
        return best_strategy
    
    def get_learning_stats(self) -> Dict:
        """获取学习统计"""
        return {
            "total_learning_samples": len(self.learning_history),
            "strategies_learned": len(self.learned_patterns),
            "patterns": {
                strategy: {
                    "count": p["count"],
                    "avg_improvement": round(p["avg_improvement"], 3),
                    "best_improvement": round(p["best_improvement"], 3),
                    "confidence": round(p["confidence"], 2)
                }
                for strategy, p in self.learned_patterns.items()
            }
        }


class CrossDomainDecisionSystem:
    """
    跨域决策与实时优化系统 - 主控制器
    """
    
    def __init__(self):
        # 核心组件
        self.decision_engine = CrossDomainDecisionEngine()
        self.real_time_optimizer = RealTimeOptimizer()
        self.predictive_optimizer = PredictiveOptimizer()
        self.adaptive_optimizer = AdaptiveLearningOptimizer()
        
        # 统计
        self.stats = {
            "total_decisions": 0,
            "decisions_executed": 0,
            "optimizations_performed": 0,
            "predictions_made": 0
        }
        
        logger.info("🎯 跨域决策与实时优化系统初始化完成")
    
    def setup_domains(self):
        """设置决策域"""
        domains = [
            ("compute", {"name": "计算域", "type": "compute", 
                        "capabilities": ["calculation", "processing"], "priority": 1.0}),
            ("storage", {"name": "存储域", "type": "storage",
                        "capabilities": ["read", "write", "cache"], "priority": 0.9}),
            ("network", {"name": "网络域", "type": "network",
                        "capabilities": ["transfer", "sync", "route"], "priority": 0.8}),
            ("analytics", {"name": "分析域", "type": "analytics",
                          "capabilities": ["analyze", "predict", "report"], "priority": 0.7})
        ]
        
        for domain_id, info in domains:
            self.decision_engine.register_domain(domain_id, info)
        
        return len(domains)
    
    def process_request(self, request: Dict) -> Dict:
        """处理请求"""
        # 做出决策
        decision = self.decision_engine.make_decision(request)
        self.stats["total_decisions"] += 1
        
        # 执行决策
        result = self.decision_engine.execute_decision(decision.id)
        self.stats["decisions_executed"] += 1
        
        # 记录优化结果
        self.adaptive_optimizer.record_optimization_result(
            {"strategy": "auto", "decision_id": decision.id},
            result
        )
        
        return {
            "decision": decision.to_dict(),
            "result": result
        }
    
    def perform_real_time_optimization(self):
        """执行实时优化"""
        # 收集当前性能数据
        data = PerformanceData(
            timestamp=datetime.now().isoformat(),
            cpu_usage=random.uniform(0.3, 0.8),
            memory_usage=random.uniform(0.3, 0.7),
            throughput=random.uniform(80, 150),
            latency=random.uniform(20, 80),
            error_rate=random.uniform(0.01, 0.05),
            resource_utilization=random.uniform(0.5, 0.9)
        )
        
        # 记录性能并触发优化
        self.real_time_optimizer.record_performance(data)
        self.stats["optimizations_performed"] += 1
        
        return data.to_dict()
    
    def perform_predictive_optimization(self):
        """执行预测性优化"""
        # 预测性能
        prediction = self.predictive_optimizer.predict_performance()
        self.stats["predictions_made"] += 1
        
        # 根据预测安排优化
        schedule_id = self.predictive_optimizer.schedule_optimization(prediction)
        
        return {
            "prediction": prediction,
            "schedule_id": schedule_id
        }
    
    def get_full_status(self) -> Dict:
        """获取完整状态"""
        return {
            "decision_engine": {
                "domains": len(self.decision_engine.domains),
                "total_decisions": len(self.decision_engine.decisions),
                "recommendations": self.decision_engine.get_recommendations()
            },
            "real_time_optimizer": {
                "active_optimizations": len(self.real_time_optimizer.active_optimizations),
                "trends": self.real_time_optimizer.analyze_trends()
            },
            "adaptive_optimizer": {
                "learning_stats": self.adaptive_optimizer.get_learning_stats()
            },
            "stats": self.stats,
            "timestamp": datetime.now().isoformat()
        }


# ========== 主程序 ==========
if __name__ == "__main__":
    print("=" * 60)
    print("🦞 奥创 - 跨域决策与实时优化系统")
    print("第3世：跨域决策 + 实时优化")
    print("=" * 60)
    
    # 创建系统
    system = CrossDomainDecisionSystem()
    
    # 设置决策域
    domain_count = system.setup_domains()
    print(f"✅ 已设置 {domain_count} 个决策域")
    
    # 执行决策
    for i in range(10):
        request = {
            "urgency": random.uniform(0.3, 0.9),
            "complexity": random.uniform(0.2, 0.8),
            "scope": random.choice(["local", "domain", "system"]),
            "risk_factor": random.uniform(0, 0.3),
            "data_quality": random.uniform(0.6, 1.0)
        }
        
        result = system.process_request(request)
        
        if i < 3:  # 只打印前几个
            print(f"  决策{i+1}: {result['decision']['type']} - {result['decision']['scope']} - 置信度: {result['decision']['confidence']}")
    
    # 执行实时优化
    for i in range(5):
        opt_result = system.perform_real_time_optimization()
        if i == 0:
            print(f"\n⚡ 实时优化: CPU={opt_result['cpu_usage']}, 内存={opt_result['memory_usage']}")
    
    # 执行预测性优化
    pred_result = system.perform_predictive_optimization()
    print(f"\n🔮 预测: CPU={pred_result['prediction']['cpu_predicted']:.2f}, 置信度={pred_result['prediction']['confidence']:.2f}")
    
    # 获取完整状态
    status = system.get_full_status()
    
    print("\n📊 系统状态:")
    print(f"  决策域: {status['decision_engine']['domains']}")
    print(f"  总决策: {status['decision_engine']['total_decisions']}")
    print(f"  实时优化: {status['real_time_optimizer']['active_optimizations']}")
    print(f"  学习样本: {status['adaptive_optimizer']['learning_stats']['total_learning_samples']}")
    
    print("\n💡 建议:")
    for rec in status['decision_engine']['recommendations']:
        print(f"  {rec}")
    
    print("\n🦞 第3世完成：跨域决策与实时优化系统")