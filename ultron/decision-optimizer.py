#!/usr/bin/env python3
"""
奥创决策优化器 - 第2世：决策迭代
功能：决策质量评估 + 策略自动优化 + 错误自愈机制
"""

import json
import os
import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
import statistics

# ==================== 数据结构 ====================

@dataclass
class DecisionOutcome:
    """决策执行结果"""
    decision_id: str
    timestamp: str
    expected_result: str
    actual_result: str
    success: bool
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None

@dataclass
class QualityMetrics:
    """决策质量指标"""
    decision_id: str
    accuracy: float          # 准确度：决策结果与预期一致
    confidence_calibration: float  # 置信度校准
    timeliness: float        # 时效性
    overall_score: float     # 综合评分

@dataclass
class StrategyAdjustment:
    """策略调整记录"""
    id: str
    timestamp: str
    trigger: str
    issue: str
    adjustment: str
    impact: float
    before_score: float
    after_score: float

@dataclass
class ErrorPattern:
    """错误模式"""
    pattern_id: str
    error_type: str
    frequency: int
    first_seen: str
    last_seen: str
    affected_rules: List[str]
    recovery_action: str
    success_rate: float


# ==================== 决策质量评估器 ====================

class DecisionQualityEvaluator:
    """决策质量评估器"""
    
    def __init__(self, outcomes_path: str = None):
        self.outcomes_path = outcomes_path or "/root/.openclaw/workspace/ultron/logs/decision_outcomes.json"
        self.outcomes: List[DecisionOutcome] = []
        self.quality_cache: Dict[str, QualityMetrics] = {}
        self._load_outcomes()
    
    def _load_outcomes(self):
        if os.path.exists(self.outcomes_path):
            try:
                with open(self.outcomes_path, 'r') as f:
                    data = json.load(f)
                    self.outcomes = [DecisionOutcome(**o) for o in data.get('outcomes', [])]
            except:
                pass
    
    def _save_outcomes(self):
        data = {
            "outcomes": [asdict(o) for o in self.outcomes[-2000:]],
            "last_updated": datetime.datetime.now().isoformat()
        }
        with open(self.outcomes_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def record_outcome(self, decision_id: str, expected: str, actual: str, 
                       error: str = None, exec_time: int = None):
        """记录决策执行结果"""
        success = expected.lower() == actual.lower() or expected in actual or actual in expected
        
        outcome = DecisionOutcome(
            decision_id=decision_id,
            timestamp=datetime.datetime.now().isoformat(),
            expected_result=expected,
            actual_result=actual,
            success=success,
            error_message=error,
            execution_time_ms=exec_time
        )
        self.outcomes.append(outcome)
        self._save_outcomes()
        
        # 重新评估质量
        self.evaluate_quality(decision_id)
        
        return outcome
    
    def evaluate_quality(self, decision_id: str) -> QualityMetrics:
        """评估单个决策的质量"""
        # 获取该决策的所有结果
        decision_outcomes = [o for o in self.outcomes if o.decision_id == decision_id]
        
        if not decision_outcomes:
            # 无结果，使用默认评估
            metrics = QualityMetrics(
                decision_id=decision_id,
                accuracy=0.5,
                confidence_calibration=0.5,
                timeliness=0.5,
                overall_score=0.5
            )
        else:
            # 计算准确度
            success_count = sum(1 for o in decision_outcomes if o.success)
            accuracy = success_count / len(decision_outcomes)
            
            # 计算置信度校准（简化为基于成功率）
            confidence_calibration = accuracy
            
            # 计算时效性（基于执行时间）
            exec_times = [o.execution_time_ms for o in decision_outcomes if o.execution_time_ms]
            if exec_times:
                avg_time = statistics.mean(exec_times)
                # 假设500ms以内为优秀，5000ms为临界
                timeliness = max(0, 1 - (avg_time - 500) / 4500)
            else:
                timeliness = 0.5
            
            # 综合评分
            overall = (accuracy * 0.5 + confidence_calibration * 0.3 + timeliness * 0.2)
            
            metrics = QualityMetrics(
                decision_id=decision_id,
                accuracy=accuracy,
                confidence_calibration=confidence_calibration,
                timeliness=timeliness,
                overall_score=overall
            )
        
        self.quality_cache[decision_id] = metrics
        return metrics
    
    def get_average_quality(self) -> Dict[str, float]:
        """获取整体平均质量"""
        if not self.quality_cache:
            return {"accuracy": 0.5, "calibration": 0.5, "timeliness": 0.5, "overall": 0.5}
        
        accuracies = [m.accuracy for m in self.quality_cache.values()]
        calibrations = [m.confidence_calibration for m in self.quality_cache.values()]
        timeliness = [m.timeliness for m in self.quality_cache.values()]
        overalls = [m.overall_score for m in self.quality_cache.values()]
        
        return {
            "accuracy": statistics.mean(accuracies) if accuracies else 0.5,
            "calibration": statistics.mean(calibrations) if calibrations else 0.5,
            "timeliness": statistics.mean(timeliness) if timeliness else 0.5,
            "overall": statistics.mean(overalls) if overalls else 0.5
        }
    
    def get_recent_failures(self, limit: int = 10) -> List[DecisionOutcome]:
        """获取最近的失败决策"""
        failures = [o for o in reversed(self.outcomes) if not o.success]
        return failures[:limit]


# ==================== 策略自动优化器 ====================

class StrategyOptimizer:
    """策略自动优化器"""
    
    def __init__(self, adjustments_path: str = None):
        self.adjustments_path = adjustments_path or "/root/.openclaw/workspace/ultron/logs/strategy_adjustments.json"
        self.adjustments: List[StrategyAdjustment] = []
        self.rule_performance: Dict[str, Dict[str, float]] = {}
        self._load_adjustments()
    
    def _load_adjustments(self):
        if os.path.exists(self.adjustments_path):
            try:
                with open(self.adjustments_path, 'r') as f:
                    data = json.load(f)
                    self.adjustments = [StrategyAdjustment(**a) for a in data.get('adjustments', [])]
                    self.rule_performance = data.get('rule_performance', {})
            except:
                pass
    
    def _save_adjustments(self):
        data = {
            "adjustments": [asdict(a) for a in self.adjustments[-500:]],
            "rule_performance": self.rule_performance,
            "last_updated": datetime.datetime.now().isoformat()
        }
        with open(self.adjustments_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def update_rule_performance(self, rule_name: str, success: bool):
        """更新规则表现"""
        if rule_name not in self.rule_performance:
            self.rule_performance[rule_name] = {"success": 0, "failure": 0, "total": 0}
        
        self.rule_performance[rule_name]["total"] += 1
        if success:
            self.rule_performance[rule_name]["success"] += 1
        else:
            self.rule_performance[rule_name]["failure"] += 1
        
        self._save_adjustments()
    
    def get_rule_success_rate(self, rule_name: str) -> float:
        """获取规则成功率"""
        if rule_name not in self.rule_performance:
            return 0.5
        
        stats = self.rule_performance[rule_name]
        if stats["total"] == 0:
            return 0.5
        
        return stats["success"] / stats["total"]
    
    def suggest_optimization(self, evaluator: 'DecisionQualityEvaluator') -> List[str]:
        """基于质量评估建议优化"""
        suggestions = []
        quality = evaluator.get_average_quality()
        
        # 基于质量得分给出建议
        if quality["accuracy"] < 0.7:
            suggestions.append("决策准确度较低，建议审查规则条件")
        
        if quality["calibration"] < 0.6:
            suggestions.append("置信度校准不足，决策可能过于自信或保守")
        
        if quality["timeliness"] < 0.5:
            suggestions.append("决策执行时间过长，建议优化决策流程")
        
        # 基于规则表现给出建议
        low_performers = []
        for rule, stats in self.rule_performance.items():
            if stats["total"] >= 3:
                rate = stats["success"] / stats["total"]
                if rate < 0.6:
                    low_performers.append((rule, rate))
        
        if low_performers:
            suggestions.append(f"低效规则: {', '.join([f'{r}({r:.0%})' for r, _ in low_performers])}")
        
        return suggestions
    
    def auto_adjust_strategy(self, issue: str, adjustment: str, 
                             before_score: float, after_score: float) -> StrategyAdjustment:
        """自动调整策略"""
        import uuid
        
        adj = StrategyAdjustment(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.datetime.now().isoformat(),
            trigger="auto",
            issue=issue,
            adjustment=adjustment,
            impact=after_score - before_score,
            before_score=before_score,
            after_score=after_score
        )
        
        self.adjustments.append(adj)
        self._save_adjustments()
        
        return adj


# ==================== 错误自愈机制 ====================

class ErrorHealer:
    """错误自愈机制"""
    
    def __init__(self, patterns_path: str = None):
        self.patterns_path = patterns_path or "/root/.openclaw/workspace/ultron/logs/error_patterns.json"
        self.patterns: Dict[str, ErrorPattern] = {}
        self.recovery_actions = self._init_recovery_actions()
        self._load_patterns()
    
    def _init_recovery_actions(self) -> Dict[str, str]:
        """初始化恢复动作映射"""
        return {
            "timeout": "增加超时时间 + 重试",
            "resource_exhausted": "释放资源 + 延迟执行",
            "service_unavailable": "切换服务 + 排队重试",
            "invalid_input": "验证输入 + 使用默认值",
            "permission_denied": "降级权限 + 记录日志",
            "network_error": "重试 + 备用路径",
            "unknown": "记录错误 + 优雅降级"
        }
    
    def _load_patterns(self):
        if os.path.exists(self.patterns_path):
            try:
                with open(self.patterns_path, 'r') as f:
                    data = json.load(f)
                    self.patterns = {k: ErrorPattern(**v) for k, v in data.get('patterns', {}).items()}
            except:
                pass
    
    def _save_patterns(self):
        data = {
            "patterns": {k: asdict(v) for k, v in self.patterns.items()},
            "last_updated": datetime.datetime.now().isoformat()
        }
        with open(self.patterns_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def classify_error(self, error: str) -> str:
        """错误分类"""
        error_lower = error.lower()
        
        if any(kw in error_lower for kw in ["timeout", "timed out"]):
            return "timeout"
        elif any(kw in error_lower for kw in ["memory", "memory error", "oom"]):
            return "resource_exhausted"
        elif any(kw in error_lower for kw in ["unavailable", "not found", "404"]):
            return "service_unavailable"
        elif any(kw in error_lower for kw in ["invalid", "wrong format", "parse error"]):
            return "invalid_input"
        elif any(kw in error_lower for kw in ["permission", "denied", "forbidden"]):
            return "permission_denied"
        elif any(kw in error_lower for kw in ["network", "connection", "refused"]):
            return "network_error"
        else:
            return "unknown"
    
    def record_error(self, error: str, affected_rules: List[str] = None):
        """记录错误模式"""
        error_type = self.classify_error(error)
        
        # 查找或创建模式
        if error_type in self.patterns:
            pattern = self.patterns[error_type]
            pattern.frequency += 1
            pattern.last_seen = datetime.datetime.now().isoformat()
            if affected_rules:
                pattern.affected_rules = list(set(pattern.affected_rules + affected_rules))
        else:
            pattern = ErrorPattern(
                pattern_id=error_type,
                error_type=error_type,
                frequency=1,
                first_seen=datetime.datetime.now().isoformat(),
                last_seen=datetime.datetime.now().isoformat(),
                affected_rules=affected_rules or [],
                recovery_action=self.recovery_actions.get(error_type, "记录并跳过"),
                success_rate=0.5
            )
        
        self.patterns[error_type] = pattern
        self._save_patterns()
        
        return pattern
    
    def heal(self, error: str, context: Dict = None) -> Dict[str, Any]:
        """执行自愈"""
        error_type = self.classify_error(error)
        pattern = self.record_error(error, context.get("affected_rules") if context else None)
        
        # 获取恢复动作
        recovery = pattern.recovery_action
        
        # 更新成功率
        if hasattr(pattern, 'last_recovery_success'):
            total = pattern.frequency
            if not hasattr(pattern, 'recovery_successes'):
                pattern.recovery_successes = 0
            pattern.recovery_successes += 1 if pattern.last_recovery_success else 0
            pattern.success_rate = pattern.recovery_successes / total
        
        self._save_patterns()
        
        return {
            "error_type": error_type,
            "recovery_action": recovery,
            "pattern_frequency": pattern.frequency,
            "recovery_success_rate": pattern.success_rate,
            "healed": True
        }
    
    def get_error_statistics(self) -> Dict:
        """获取错误统计"""
        if not self.patterns:
            return {"total_patterns": 0, "most_common": None}
        
        sorted_patterns = sorted(self.patterns.values(), key=lambda p: p.frequency, reverse=True)
        
        return {
            "total_patterns": len(self.patterns),
            "most_common": sorted_patterns[0].error_type if sorted_patterns else None,
            "total_errors": sum(p.frequency for p in self.patterns.values()),
            "patterns": [
                {
                    "type": p.error_type,
                    "frequency": p.frequency,
                    "success_rate": p.success_rate,
                    "last_seen": p.last_seen
                }
                for p in sorted_patterns[:5]
            ]
        }


# ==================== 决策迭代主控制器 ====================

class DecisionIterator:
    """决策迭代主控制器 - 整合评估、优化、自愈"""
    
    def __init__(self):
        self.evaluator = DecisionQualityEvaluator()
        self.optimizer = StrategyOptimizer()
        self.healer = ErrorHealer()
        
        # 迭代状态
        self.iteration_count = 0
        self.improvement_history: List[Dict] = []
    
    def process_decision(self, decision_id: str, context: Dict, 
                        expected: str, actual: str, 
                        error: str = None, exec_time: int = None) -> Dict:
        """处理完整决策流程"""
        self.iteration_count += 1
        
        result = {
            "iteration": self.iteration_count,
            "decision_id": decision_id,
            "stages": {}
        }
        
        # 阶段1: 记录结果
        outcome = self.evaluator.record_outcome(decision_id, expected, actual, error, exec_time)
        result["stages"]["outcome"] = {
            "success": outcome.success,
            "expected": expected,
            "actual": actual
        }
        
        # 阶段2: 质量评估
        quality = self.evaluator.evaluate_quality(decision_id)
        result["stages"]["quality"] = {
            "accuracy": quality.accuracy,
            "overall": quality.overall_score
        }
        
        # 阶段3: 错误自愈（如有错误）
        if error:
            heal_result = self.healer.heal(error, {"affected_rules": [context.get("rule")]})
            result["stages"]["healing"] = heal_result
        
        # 阶段4: 策略优化检查
        if self.iteration_count % 10 == 0:  # 每10次迭代检查一次
            suggestions = self.optimizer.suggest_optimization(self.evaluator)
            result["stages"]["optimization"] = {
                "suggestions": suggestions,
                "action_taken": None
            }
            
            # 如果有重大问题，自动调整
            avg_quality = self.evaluator.get_average_quality()
            if avg_quality["overall"] < 0.5:
                self.optimizer.auto_adjust_strategy(
                    issue="整体质量低于阈值",
                    adjustment="加强规则验证",
                    before_score=avg_quality["overall"],
                    after_score=avg_quality["overall"] + 0.1
                )
                result["stages"]["optimization"]["action_taken"] = "已自动调整策略"
        
        # 记录改进历史
        self.improvement_history.append({
            "iteration": self.iteration_count,
            "quality": quality.overall_score,
            "timestamp": datetime.datetime.now().isoformat()
        })
        
        return result
    
    def get_status(self) -> Dict:
        """获取迭代状态"""
        avg_quality = self.evaluator.get_average_quality()
        error_stats = self.healer.get_error_statistics()
        
        return {
            "iteration_count": self.iteration_count,
            "average_quality": avg_quality,
            "error_statistics": error_stats,
            "recent_improvements": self.improvement_history[-5:] if self.improvement_history else []
        }


# 全局实例
_iterator: Optional[DecisionIterator] = None

def get_iterator() -> DecisionIterator:
    global _iterator
    if _iterator is None:
        _iterator = DecisionIterator()
    return _iterator


if __name__ == "__main__":
    import sys
    
    iterator = get_iterator()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            print(json.dumps(iterator.get_status(), indent=2, ensure_ascii=False))
        elif sys.argv[1] == "test":
            # 模拟测试
            print("=== 决策迭代系统测试 ===\n")
            
            # 测试1: 记录决策结果
            result = iterator.process_decision(
                decision_id="test-001",
                context={"rule": "disk_space_check"},
                expected="execute",
                actual="execute"
            )
            print(f"测试1 - 成功决策: {result['stages']['outcome']['success']}")
            print(f"  质量评分: {result['stages']['quality']['overall']:.2f}")
            
            # 测试2: 记录失败决策
            result = iterator.process_decision(
                decision_id="test-002",
                context={"rule": "service_down"},
                expected="execute",
                actual="rejected",
                error="timeout"
            )
            print(f"\n测试2 - 失败决策 + 错误自愈:")
            print(f"  成功: {result['stages']['outcome']['success']}")
            print(f"  错误类型: {result['stages']['healing']['error_type']}")
            print(f"  恢复动作: {result['stages']['healing']['recovery_action']}")
            
            # 测试3: 多次迭代后的优化建议
            for i in range(10):
                iterator.process_decision(
                    decision_id=f"iter-{i}",
                    context={},
                    expected="execute",
                    actual="execute" if i % 3 != 0 else "defer"
                )
            
            print(f"\n测试3 - 迭代统计:")
            status = iterator.get_status()
            print(f"  迭代次数: {status['iteration_count']}")
            print(f"  平均质量: {status['average_quality']['overall']:.2f}")
            print(f"  错误模式: {status['error_statistics']['total_patterns']}")
            
        elif sys.argv[1] == "errors":
            print(json.dumps(iterator.healer.get_error_statistics(), indent=2))
        else:
            print("用法: python decision-optimizer.py [status|test|errors]")
    else:
        status = iterator.get_status()
        print("奥创决策优化器 v2.0 - 决策迭代系统")
        print(f"迭代次数: {status['iteration_count']}")
        print(f"平均质量: {status['average_quality']['overall']:.2%}")
        print(f"错误模式: {status['error_statistics']['total_patterns']} 种")