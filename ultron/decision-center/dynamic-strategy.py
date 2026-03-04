#!/usr/bin/env python3
"""
动态策略调整系统 - 夙愿二十三第3世
基于推理结果的自适应策略调整与执行
"""

import json
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum
import random

class StrategyType(Enum):
    ADAPTIVE = "adaptive"        # 自适应策略
    PREDICTIVE = "predictive"    # 预测性策略
    REACTIVE = "reactive"        # 响应式策略
    PROACTIVE = "proactive"      # 前瞻性策略

class StrategyStatus(Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    EVALUATING = "evaluating"
    OPTIMIZING = "optimizing"

@dataclass
class Strategy:
    """策略定义"""
    id: str
    name: str
    type: StrategyType
    conditions: Dict[str, Any]
    actions: List[Dict[str, Any]]
    priority: int = 5
    cooldown: int = 60
    last_triggered: Optional[str] = None
    success_rate: float = 0.0
    execution_count: int = 0

@dataclass
class StrategyExecution:
    """策略执行记录"""
    strategy_id: str
    timestamp: str
    trigger_reason: str
    actions_executed: List[str]
    result: str
    effectiveness: float
    duration_ms: float

class DynamicStrategyManager:
    """动态策略管理器"""
    
    def __init__(self):
        self.strategies: Dict[str, Strategy] = {}
        self.execution_history: List[StrategyExecution] = []
        self.evaluation_metrics: Dict[str, Dict] = {}
        self.context: Dict[str, Any] = {}
        
    def add_strategy(self, strategy: Strategy) -> None:
        """添加策略"""
        self.strategies[strategy.id] = strategy
        self.evaluation_metrics[strategy.id] = {
            "total_executions": 0,
            "successful": 0,
            "failed": 0,
            "avg_effectiveness": 0.0,
            "last_evaluation": None
        }
        
    def evaluate_and_select(self, context: Dict[str, Any]) -> Optional[Strategy]:
        """评估并选择最佳策略"""
        self.context = context
        matching_strategies = []
        
        for strategy in self.strategies.values():
            if self._check_conditions(strategy, context):
                matching_strategies.append(strategy)
                
        if not matching_strategies:
            return None
            
        # 按优先级和成功率排序
        matching_strategies.sort(
            key=lambda s: (s.priority, s.success_rate),
            reverse=True
        )
        
        return matching_strategies[0]
    
    def _check_conditions(self, strategy: Strategy, context: Dict[str, Any]) -> bool:
        """检查策略条件是否满足"""
        conditions = strategy.conditions
        
        for key, expected in conditions.items():
            if key not in context:
                return False
                
            actual = context[key]
            
            # 数值比较
            if isinstance(expected, dict):
                op = expected.get("op", "==")
                value = expected["value"]
                
                if op == ">" and not actual > value:
                    return False
                elif op == "<" and not actual < value:
                    return False
                elif op == ">=" and not actual >= value:
                    return False
                elif op == "<=" and not actual <= value:
                    return False
                elif op == "==" and actual != value:
                    return False
                elif op == "!=" and actual == value:
                    return False
            else:
                if actual != expected:
                    return False
                    
        # 冷却时间检查
        if strategy.last_triggered:
            last_time = datetime.fromisoformat(strategy.last_triggered)
            elapsed = (datetime.now() - last_time).total_seconds()
            if elapsed < strategy.cooldown:
                return False
                
        return True
    
    def execute_strategy(self, strategy: Strategy) -> StrategyExecution:
        """执行策略"""
        start_time = time.time()
        
        actions_executed = []
        for action in strategy.actions:
            action_type = action.get("type", "unknown")
            actions_executed.append(f"{action_type}: {action.get('description', '')}")
            # 模拟执行
            time.sleep(0.01)
            
        duration_ms = (time.time() - start_time) * 1000
        
        # 评估执行效果（模拟）
        effectiveness = random.uniform(0.6, 1.0)
        result = "success" if effectiveness > 0.7 else "partial"
        
        execution = StrategyExecution(
            strategy_id=strategy.id,
            timestamp=datetime.now().isoformat(),
            trigger_reason=str(self.context),
            actions_executed=actions_executed,
            result=result,
            effectiveness=effectiveness,
            duration_ms=duration_ms
        )
        
        self.execution_history.append(execution)
        self._update_metrics(strategy, execution)
        
        strategy.last_triggered = datetime.now().isoformat()
        strategy.execution_count += 1
        
        return execution
    
    def _update_metrics(self, strategy: Strategy, execution: StrategyExecution) -> None:
        """更新策略评估指标"""
        metrics = self.evaluation_metrics[strategy.id]
        
        metrics["total_executions"] += 1
        
        if execution.result == "success":
            metrics["successful"] += 1
        else:
            metrics["failed"] += 1
            
        # 更新成功率
        metrics["avg_effectiveness"] = (
            (metrics["avg_effectiveness"] * (metrics["total_executions"] - 1) + execution.effectiveness)
            / metrics["total_executions"]
        )
        metrics["last_evaluation"] = datetime.now().isoformat()
        
        strategy.success_rate = metrics["successful"] / metrics["total_executions"]
    
    def optimize_strategies(self) -> Dict[str, Any]:
        """优化策略"""
        optimization_results = {}
        
        for strategy in self.strategies.values():
            metrics = self.evaluation_metrics[strategy.id]
            
            if metrics["total_executions"] >= 3:
                # 基于历史表现调整优先级
                if metrics["avg_effectiveness"] > 0.8:
                    strategy.priority = min(strategy.priority + 1, 10)
                    optimization_results[strategy.id] = "优先级提升"
                elif metrics["avg_effectiveness"] < 0.5:
                    strategy.priority = max(strategy.priority - 1, 1)
                    optimization_results[strategy.id] = "优先级降低"
                else:
                    optimization_results[strategy.id] = "保持不变"
            else:
                optimization_results[strategy.id] = "数据不足，待评估"
                
        return optimization_results
    
    def get_strategy_report(self) -> Dict[str, Any]:
        """获取策略报告"""
        return {
            "total_strategies": len(self.strategies),
            "active_strategies": sum(1 for s in self.strategies.values() if s.last_triggered),
            "total_executions": len(self.execution_history),
            "metrics": self.evaluation_metrics,
            "optimization_needed": sum(
                1 for m in self.evaluation_metrics.values()
                if m["total_executions"] >= 3 and m["avg_effectiveness"] < 0.7
            )
        }

def main():
    """主函数 - 演示动态策略系统"""
    manager = DynamicStrategyManager()
    
    # 添加示例策略
    manager.add_strategy(Strategy(
        id="s1",
        name="高CPU自动扩容",
        type=StrategyType.ADAPTIVE,
        conditions={"cpu_usage": {"op": ">", "value": 80}},
        actions=[
            {"type": "scale", "description": "增加实例数量"},
            {"type": "notify", "description": "发送告警通知"}
        ],
        priority=8,
        cooldown=120
    ))
    
    manager.add_strategy(Strategy(
        id="s2",
        name="内存告警",
        type=StrategyType.REACTIVE,
        conditions={"memory_usage": {"op": ">", "value": 90}},
        actions=[
            {"type": "alert", "description": "触发内存告警"},
            {"type": "cleanup", "description": "清理缓存"}
        ],
        priority=7,
        cooldown=60
    ))
    
    manager.add_strategy(Strategy(
        id="s3",
        name="预测性扩容",
        type=StrategyType.PREDICTIVE,
        conditions={"predicted_load": {"op": ">", "value": 70}},
        actions=[
            {"type": "pre-scale", "description": "提前扩容"},
            {"type": "optimize", "description": "优化资源配置"}
        ],
        priority=9,
        cooldown=180
    ))
    
    print("=" * 50)
    print("动态策略调整系统 - 演示")
    print("=" * 50)
    
    # 测试场景1：高CPU
    print("\n【场景1】高CPU告警")
    context1 = {"cpu_usage": 85, "memory_usage": 60}
    strategy1 = manager.evaluate_and_select(context1)
    
    if strategy1:
        result1 = manager.execute_strategy(strategy1)
        print(f"选中策略: {strategy1.name}")
        print(f"执行动作: {result1.actions_executed}")
        print(f"效果评分: {result1.effectiveness:.2%}")
    
    # 测试场景2：内存告警
    print("\n【场景2】内存告警")
    context2 = {"cpu_usage": 40, "memory_usage": 92}
    strategy2 = manager.evaluate_and_select(context2)
    
    if strategy2:
        result2 = manager.execute_strategy(strategy2)
        print(f"选中策略: {strategy2.name}")
        print(f"执行动作: {result2.actions_executed}")
        print(f"效果评分: {result2.effectiveness:.2%}")
    
    # 优化策略
    print("\n【策略优化】")
    optimization = manager.optimize_strategies()
    for sid, result in optimization.items():
        print(f"  {sid}: {result}")
    
    # 生成报告
    print("\n【策略报告】")
    report = manager.get_strategy_report()
    print(f"  总策略数: {report['total_strategies']}")
    print(f"  总执行次数: {report['total_executions']}")
    print(f"  待优化: {report['optimization_needed']}个")
    
    return True

if __name__ == "__main__":
    main()
