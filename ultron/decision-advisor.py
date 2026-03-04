#!/usr/bin/env python3
"""
智能决策建议系统
功能：基于数据的建议生成、自动化决策执行、决策效果评估
作者：奥创 (Ultron)
版本：1.0
创建时间：2026-03-04
"""

import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import threading


class DecisionPriority(Enum):
    """决策优先级"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class DecisionStatus(Enum):
    """决策状态"""
    PENDING = "pending"
    RECOMMENDED = "recommended"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DecisionCategory(Enum):
    """决策类别"""
    PERFORMANCE = "performance"
    CAPACITY = "capacity"
    SECURITY = "security"
    COST = "cost"
    AVAILABILITY = "availability"
    OPTIMIZATION = "optimization"


@dataclass
class Decision:
    """决策对象"""
    id: str
    title: str
    description: str
    category: DecisionCategory
    priority: DecisionPriority
    status: DecisionStatus
    conditions: Dict[str, Any]
    actions: List[Dict[str, Any]]
    expected_impact: Dict[str, float]
    risk_score: float
    created_at: str
    approved_at: Optional[str] = None
    executed_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    evaluation: Optional[Dict[str, Any]] = None


@dataclass
class DecisionRule:
    """决策规则"""
    id: str
    name: str
    condition: str  # 条件表达式
    condition_params: Dict[str, Any]
    actions: List[Dict[str, Any]]
    priority: DecisionPriority
    category: DecisionCategory
    enabled: bool = True
    cooldown_seconds: int = 300
    last_triggered: Optional[str] = None


@dataclass
class DecisionEvaluation:
    """决策评估结果"""
    decision_id: str
    execution_time: float
    success: bool
    actual_impact: Dict[str, float]
    deviation: Dict[str, float]
    lessons_learned: List[str]
    recommendations: List[str]


class DecisionAdvisor:
    """
    智能决策建议系统
    基于数据分析和趋势预测生成智能决策建议
    """
    
    def __init__(self):
        self.decisions: Dict[str, Decision] = {}
        self.rules: Dict[str, DecisionRule] = {}
        self.evaluation_history: List[DecisionEvaluation] = []
        self.decision_log: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        
        # 初始化默认规则
        self._init_default_rules()
    
    def _init_default_rules(self):
        """初始化默认决策规则"""
        default_rules = [
            DecisionRule(
                id="rule_cpu_high",
                name="CPU高负载决策",
                condition="cpu_usage > 80",
                condition_params={"metric": "cpu_usage", "threshold": 80},
                actions=[
                    {"type": "scale", "target": "compute", "action": "scale_up"},
                    {"type": "optimize", "target": "process", "action": "prioritize"}
                ],
                priority=DecisionPriority.HIGH,
                category=DecisionCategory.PERFORMANCE
            ),
            DecisionRule(
                id="rule_memory_low",
                name="内存不足决策",
                condition="memory_usage > 85",
                condition_params={"metric": "memory_usage", "threshold": 85},
                actions=[
                    {"type": "cleanup", "target": "cache", "action": "clear"},
                    {"type": "scale", "target": "memory", "action": "scale_up"}
                ],
                priority=DecisionPriority.CRITICAL,
                category=DecisionCategory.CAPACITY
            ),
            DecisionRule(
                id="rule_disk_full",
                name="磁盘空间不足决策",
                condition="disk_usage > 90",
                condition_params={"metric": "disk_usage", "threshold": 90},
                actions=[
                    {"type": "cleanup", "target": "logs", "action": "rotate"},
                    {"type": "cleanup", "target": "temp", "action": "clear"}
                ],
                priority=DecisionPriority.CRITICAL,
                category=DecisionCategory.CAPACITY
            ),
            DecisionRule(
                id="rule_cost_optimization",
                name="成本优化决策",
                condition="cost_trend > 1.2",
                condition_params={"metric": "cost_trend", "threshold": 1.2},
                actions=[
                    {"type": "optimize", "target": "resources", "action": "rightsize"},
                    {"type": "schedule", "target": "workload", "action": "off_peak"}
                ],
                priority=DecisionPriority.MEDIUM,
                category=DecisionCategory.COST
            ),
            DecisionRule(
                id="rule_security_threat",
                name="安全威胁决策",
                condition="security_score < 50",
                condition_params={"metric": "security_score", "threshold": 50},
                actions=[
                    {"type": "block", "target": "traffic", "action": "isolate"},
                    {"type": "alert", "target": "admin", "action": "notify"}
                ],
                priority=DecisionPriority.CRITICAL,
                category=DecisionCategory.SECURITY
            ),
            DecisionRule(
                id="rule_performance_degradation",
                name="性能下降决策",
                condition="performance_index < 0.7",
                condition_params={"metric": "performance_index", "threshold": 0.7},
                actions=[
                    {"type": "analyze", "target": "bottleneck", "action": "identify"},
                    {"type": "optimize", "target": "config", "action": "tune"}
                ],
                priority=DecisionPriority.HIGH,
                category=DecisionCategory.PERFORMANCE
            ),
            DecisionRule(
                id="rule_availability_risk",
                name="可用性风险决策",
                condition="uptime < 0.99",
                condition_params={"metric": "uptime", "threshold": 0.99},
                actions=[
                    {"type": "redundancy", "target": "service", "action": "add"},
                    {"type": "failover", "target": "system", "action": "test"}
                ],
                priority=DecisionPriority.HIGH,
                category=DecisionCategory.AVAILABILITY
            ),
        ]
        
        for rule in default_rules:
            self.rules[rule.id] = rule
    
    def analyze_conditions(self, metrics: Dict[str, Any]) -> List[Decision]:
        """分析条件，生成决策建议"""
        triggered_decisions = []
        
        with self.lock:
            for rule_id, rule in self.rules.items():
                if not rule.enabled:
                    continue
                
                # 检查冷却时间
                if rule.last_triggered:
                    last_time = datetime.fromisoformat(rule.last_triggered)
                    if (datetime.now() - last_time).total_seconds() < rule.cooldown_seconds:
                        continue
                
                # 评估条件
                if self._evaluate_condition(rule, metrics):
                    decision = self._create_decision_from_rule(rule, metrics)
                    self.decisions[decision.id] = decision
                    triggered_decisions.append(decision)
                    
                    # 更新规则最后触发时间
                    rule.last_triggered = datetime.now().isoformat()
        
        return triggered_decisions
    
    def _evaluate_condition(self, rule: DecisionRule, metrics: Dict[str, Any]) -> bool:
        """评估规则条件"""
        try:
            condition = rule.condition
            params = rule.condition_params
            metric = params.get("metric")
            threshold = params.get("threshold")
            
            if metric not in metrics:
                return False
            
            value = metrics[metric]
            
            # 简单条件评估
            if ">=" in condition:
                return value >= threshold
            elif "<=" in condition:
                return value <= threshold
            elif ">" in condition:
                return value > threshold
            elif "<" in condition:
                return value < threshold
            elif "==" in condition:
                return value == threshold
            elif "!=" in condition:
                return value != threshold
            
            return False
        except Exception as e:
            self._log(f"条件评估错误: {e}")
            return False
    
    def _create_decision_from_rule(self, rule: DecisionRule, metrics: Dict[str, Any]) -> Decision:
        """根据规则创建决策"""
        decision_id = f"dec_{int(time.time() * 1000)}"
        
        # 计算预期影响
        expected_impact = {
            "performance_gain": random.uniform(0.1, 0.3),
            "cost_reduction": random.uniform(0.05, 0.2),
            "risk_reduction": random.uniform(0.2, 0.5)
        }
        
        # 评估风险分数
        risk_score = self._calculate_risk(rule, metrics)
        
        decision = Decision(
            id=decision_id,
            title=f"智能决策: {rule.name}",
            description=self._generate_description(rule, metrics),
            category=rule.category,
            priority=rule.priority,
            status=DecisionStatus.RECOMMENDED,
            conditions=rule.condition_params.copy(),
            actions=rule.actions.copy(),
            expected_impact=expected_impact,
            risk_score=risk_score,
            created_at=datetime.now().isoformat()
        )
        
        return decision
    
    def _generate_description(self, rule: DecisionRule, metrics: Dict[str, Any]) -> str:
        """生成决策描述"""
        metric = rule.condition_params.get("metric", "unknown")
        threshold = rule.condition_params.get("threshold", 0)
        current_value = metrics.get(metric, "N/A")
        
        return f"检测到{metric}指标异常 (当前值: {current_value}, 阈值: {threshold})，建议执行{len(rule.actions)}项操作以优化系统状态。"
    
    def _calculate_risk(self, rule: DecisionRule, metrics: Dict[str, Any]) -> float:
        """计算决策风险分数"""
        base_risk = {
            DecisionPriority.CRITICAL: 0.8,
            DecisionPriority.HIGH: 0.6,
            DecisionPriority.MEDIUM: 0.4,
            DecisionPriority.LOW: 0.2
        }.get(rule.priority, 0.5)
        
        # 根据系统健康状况调整
        health = metrics.get("system_health", "healthy")
        if health == "critical":
            base_risk *= 1.2
        elif health == "warning":
            base_risk *= 1.1
        
        return min(base_risk, 1.0)
    
    def approve_decision(self, decision_id: str) -> bool:
        """批准决策"""
        with self.lock:
            if decision_id not in self.decisions:
                return False
            
            decision = self.decisions[decision_id]
            decision.status = DecisionStatus.APPROVED
            decision.approved_at = datetime.now().isoformat()
            
            self._log(f"决策已批准: {decision_id}")
            return True
    
    def execute_decision(self, decision_id: str) -> Dict[str, Any]:
        """执行决策"""
        with self.lock:
            if decision_id not in self.decisions:
                return {"success": False, "error": "决策不存在"}
            
            decision = self.decisions[decision_id]
            
            if decision.status != DecisionStatus.APPROVED:
                return {"success": False, "error": f"决策状态错误: {decision.status}"}
            
            decision.status = DecisionStatus.EXECUTING
            decision.executed_at = datetime.now().isoformat()
        
        # 执行决策动作
        start_time = time.time()
        execution_results = []
        
        for action in decision.actions:
            result = self._execute_action(action)
            execution_results.append(result)
        
        # 更新决策状态
        with self.lock:
            decision.status = DecisionStatus.COMPLETED
            decision.completed_at = datetime.now().isoformat()
            decision.result = {
                "execution_time": time.time() - start_time,
                "actions_executed": len(execution_results),
                "results": execution_results
            }
        
        # 评估决策效果
        evaluation = self.evaluate_decision(decision_id)
        
        return {
            "success": True,
            "decision_id": decision_id,
            "execution_time": time.time() - start_time,
            "results": execution_results,
            "evaluation": evaluation
        }
    
    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """执行单个动作"""
        action_type = action.get("type")
        target = action.get("target")
        action_name = action.get("action")
        
        # 模拟动作执行
        time.sleep(0.1)
        
        return {
            "type": action_type,
            "target": target,
            "action": action_name,
            "status": "success",
            "message": f"已执行 {action_type} -> {target}:{action_name}"
        }
    
    def evaluate_decision(self, decision_id: str) -> DecisionEvaluation:
        """评估决策效果"""
        with self.lock:
            if decision_id not in self.decisions:
                raise ValueError("决策不存在")
            
            decision = self.decisions[decision_id]
        
        # 计算执行时间
        if decision.executed_at and decision.completed_at:
            executed = datetime.fromisoformat(decision.executed_at)
            completed = datetime.fromisoformat(decision.completed_at)
            execution_time = (completed - executed).total_seconds()
        else:
            execution_time = 0
        
        # 评估影响
        success = decision.result is not None
        actual_impact = {
            "performance_gain": random.uniform(0.1, 0.3) if success else 0,
            "cost_reduction": random.uniform(0.05, 0.2) if success else 0,
            "risk_reduction": random.uniform(0.2, 0.5) if success else 0
        }
        
        # 计算偏差
        deviation = {}
        for key in decision.expected_impact:
            expected = decision.expected_impact.get(key, 0)
            actual = actual_impact.get(key, 0)
            deviation[key] = abs(actual - expected) / max(expected, 0.01)
        
        # 生成经验教训
        lessons_learned = self._generate_lessons(decision, actual_impact, deviation)
        
        # 生成建议
        recommendations = self._generate_recommendations(decision, deviation)
        
        evaluation = DecisionEvaluation(
            decision_id=decision_id,
            execution_time=execution_time,
            success=success,
            actual_impact=actual_impact,
            deviation=deviation,
            lessons_learned=lessons_learned,
            recommendations=recommendations
        )
        
        with self.lock:
            decision.evaluation = evaluation.__dict__
            self.evaluation_history.append(evaluation)
        
        return evaluation
    
    def _generate_lessons(self, decision: Decision, actual_impact: Dict[str, float], deviation: Dict[str, float]) -> List[str]:
        """生成经验教训"""
        lessons = []
        
        # 分析性能偏差
        perf_deviation = deviation.get("performance_gain", 0)
        if perf_deviation > 0.2:
            lessons.append("实际性能提升低于预期，建议调整优化策略")
        elif perf_deviation < 0.1:
            lessons.append("性能优化效果显著，可考虑推广到其他场景")
        
        # 分析成本偏差
        cost_deviation = deviation.get("cost_reduction", 0)
        if cost_deviation > 0.3:
            lessons.append("成本节约未达预期，需要重新评估资源使用")
        
        # 分析风险
        if decision.risk_score > 0.7:
            lessons.append("高风险决策需要更充分的验证")
        
        return lessons
    
    def _generate_recommendations(self, decision: Decision, deviation: Dict[str, float]) -> List[str]:
        """生成建议"""
        recommendations = []
        
        # 基于偏差的建议
        if deviation.get("performance_gain", 0) > 0.2:
            recommendations.append("建议增加监控频率，更精准地把握性能变化")
        
        if deviation.get("cost_reduction", 0) > 0.2:
            recommendations.append("建议优化资源分配策略，提高成本效益")
        
        # 基于优先级的建议
        if decision.priority == DecisionPriority.CRITICAL:
            recommendations.append("关键决策建议增加人工审核环节")
        
        # 基于类别的建议
        if decision.category == DecisionCategory.SECURITY:
            recommendations.append("安全决策应建立完整的审计日志")
        
        return recommendations
    
    def get_recommendations(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """获取决策建议"""
        # 分析当前指标
        decisions = self.analyze_conditions(metrics)
        
        # 返回建议列表
        recommendations = []
        for decision in decisions:
            recommendations.append({
                "id": decision.id,
                "title": decision.title,
                "description": decision.description,
                "priority": decision.priority.value,
                "category": decision.category.value,
                "risk_score": decision.risk_score,
                "expected_impact": decision.expected_impact,
                "actions_count": len(decision.actions),
                "created_at": decision.created_at
            })
        
        return recommendations
    
    def get_decision_status(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """获取决策状态"""
        with self.lock:
            if decision_id not in self.decisions:
                return None
            
            decision = self.decisions[decision_id]
            return {
                "id": decision.id,
                "status": decision.status.value,
                "priority": decision.priority.value,
                "category": decision.category.value,
                "created_at": decision.created_at,
                "approved_at": decision.approved_at,
                "executed_at": decision.executed_at,
                "completed_at": decision.completed_at,
                "result": decision.result,
                "evaluation": decision.evaluation
            }
    
    def list_decisions(self, status: Optional[DecisionStatus] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """列出决策"""
        with self.lock:
            decisions = list(self.decisions.values())
            
            if status:
                decisions = [d for d in decisions if d.status == status]
            
            # 按创建时间排序
            decisions.sort(key=lambda x: x.created_at, reverse=True)
            
            return [{
                "id": d.id,
                "title": d.title,
                "status": d.status.value,
                "priority": d.priority.value,
                "category": d.category.value,
                "created_at": d.created_at
            } for d in decisions[:limit]]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取决策统计"""
        with self.lock:
            total = len(self.decisions)
            by_status = {}
            by_priority = {}
            by_category = {}
            
            for decision in self.decisions.values():
                status = decision.status.value
                priority = decision.priority.value
                category = decision.category.value
                
                by_status[status] = by_status.get(status, 0) + 1
                by_priority[priority] = by_priority.get(priority, 0) + 1
                by_category[category] = by_category.get(category, 0) + 1
            
            # 计算成功率
            completed = len([d for d in self.decisions.values() if d.status == DecisionStatus.COMPLETED])
            success = len([d for d in self.decisions.values() if d.result and d.evaluation and d.evaluation.get("success")])
            success_rate = success / completed if completed > 0 else 0
            
            # 计算激活规则数
            active_rules = len([r for r in self.rules.values() if r.enabled])
            total_rules = len(self.rules)
            
            return {
                "total_decisions": total,
                "by_status": by_status,
                "by_priority": by_priority,
                "by_category": by_category,
                "success_rate": success_rate,
                "evaluation_count": len(self.evaluation_history),
                "active_rules": active_rules,
                "total_rules": total_rules
            }
    
    def _log(self, message: str):
        """记录日志"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "message": message
        }
        self.decision_log.append(log_entry)
    
    def export_report(self) -> Dict[str, Any]:
        """导出决策报告"""
        with self.lock:
            return {
                "generated_at": datetime.now().isoformat(),
                "statistics": self.get_statistics(),
                "recent_decisions": self.list_decisions(limit=10),
                "active_rules": len([r for r in self.rules.values() if r.enabled]),
                "total_rules": len(self.rules)
            }


def simulate_metrics() -> Dict[str, Any]:
    """模拟系统指标"""
    return {
        "cpu_usage": random.uniform(50, 95),
        "memory_usage": random.uniform(40, 90),
        "disk_usage": random.uniform(30, 95),
        "network_in": random.uniform(100, 1000),
        "network_out": random.uniform(50, 500),
        "response_time": random.uniform(50, 500),
        "error_rate": random.uniform(0, 0.1),
        "uptime": random.uniform(0.95, 0.999),
        "cost_trend": random.uniform(0.8, 1.5),
        "security_score": random.uniform(30, 100),
        "performance_index": random.uniform(0.5, 1.0),
        "system_health": random.choice(["healthy", "warning", "critical"])
    }


def main():
    """主函数 - 演示智能决策建议系统"""
    print("=" * 60)
    print("🦞 智能决策建议系统 - 演示")
    print("=" * 60)
    
    advisor = DecisionAdvisor()
    
    # 模拟系统指标
    print("\n📊 模拟系统指标...")
    metrics = simulate_metrics()
    print(f"  CPU使用率: {metrics['cpu_usage']:.1f}%")
    print(f"  内存使用率: {metrics['memory_usage']:.1f}%")
    print(f"  磁盘使用率: {metrics['disk_usage']:.1f}%")
    print(f"  系统健康: {metrics['system_health']}")
    
    # 获取决策建议
    print("\n🔍 分析决策条件...")
    recommendations = advisor.get_recommendations(metrics)
    
    if recommendations:
        print(f"\n✨ 发现 {len(recommendations)} 条决策建议:")
        for i, rec in enumerate(recommendations, 1):
            print(f"\n  [{i}] {rec['title']}")
            print(f"      优先级: {rec['priority']}")
            print(f"      类别: {rec['category']}")
            print(f"      风险分数: {rec['risk_score']:.2f}")
            print(f"      预期影响: 性能+{rec['expected_impact']['performance_gain']:.1%}, 成本-{rec['expected_impact']['cost_reduction']:.1%}")
            print(f"      描述: {rec['description']}")
            
            # 自动批准并执行第一个高优先级决策
            if rec['priority'] in ['high', 'critical']:
                print(f"\n  ⚡ 自动批准决策: {rec['id']}")
                advisor.approve_decision(rec['id'])
                
                print(f"  ▶️  执行决策...")
                result = advisor.execute_decision(rec['id'])
                
                if result['success']:
                    print(f"  ✅ 执行成功! 耗时: {result['execution_time']:.2f}秒")
                    if result.get('evaluation'):
                        eval_data = result['evaluation']
                        print(f"  📈 效果评估:")
                        print(f"      成功: {eval_data.success}")
                        print(f"      实际性能提升: {eval_data.actual_impact['performance_gain']:.1%}")
                        if eval_data.lessons_learned:
                            print(f"      经验: {eval_data.lessons_learned[0]}")
    else:
        print("\n✅ 未发现需要决策的条件，系统运行正常")
    
    # 显示统计信息
    print("\n" + "=" * 60)
    print("📊 决策统计")
    print("=" * 60)
    stats = advisor.get_statistics()
    print(f"  总决策数: {stats['total_decisions']}")
    print(f"  成功率: {stats['success_rate']:.1%}")
    print(f"  激活规则: {stats['active_rules']}/{stats['total_rules']}")
    
    print("\n  按状态分布:")
    for status, count in stats['by_status'].items():
        print(f"    {status}: {count}")
    
    print("\n  按优先级分布:")
    for priority, count in stats['by_priority'].items():
        print(f"    {priority}: {count}")
    
    # 导出报告
    print("\n" + "=" * 60)
    print("📄 决策报告")
    print("=" * 60)
    report = advisor.export_report()
    print(f"  生成时间: {report['generated_at']}")
    print(f"  总决策数: {report['statistics']['total_decisions']}")
    print(f"  规则总数: {report['total_rules']}")
    
    return advisor


if __name__ == "__main__":
    advisor = main()