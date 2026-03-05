#!/usr/bin/env python3
"""
奥创决策引擎 - 第一世：决策引擎框架
功能：决策树/规则引擎 + 数据驱动决策 + 决策日志
"""

import json
import os
import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

# 决策类型枚举
class DecisionType(Enum):
    RULE_BASED = "rule_based"           # 规则驱动
    DATA_DRIVEN = "data_driven"         # 数据驱动
    HYBRID = "hybrid"                   # 混合决策

# 决策级别
class DecisionLevel(Enum):
    LOW = "low"         # 低风险，自动执行
    MEDIUM = "medium"  # 中风险，需确认
    HIGH = "high"      # 高风险，拒绝执行

# 决策结果
class DecisionResult(Enum):
    EXECUTE = "execute"     # 执行
    DEFER = "defer"        # 延迟
    REJECT = "reject"      # 拒绝
    ESCALATE = "escalate"  # 升级

@dataclass
class Decision:
    """决策记录"""
    id: str
    timestamp: str
    context: Dict[str, Any]
    decision_type: str
    level: str
    rule_applied: Optional[str]
    result: str
    reason: str
    confidence: float  # 置信度 0-1
    action_taken: Optional[str]
    
@dataclass
class DecisionRule:
    """决策规则"""
    name: str
    condition: Callable[[Dict], bool]
    action: Callable[[Dict], str]
    level: DecisionLevel
    description: str

class DecisionEngine:
    """决策引擎"""
    
    def __init__(self, log_path: str = None):
        self.log_path = log_path or "/root/.openclaw/workspace/ultron/logs/decisions.json"
        self.rules: List[DecisionRule] = []
        self.decisions: List[Decision] = []
        self.metrics: Dict[str, int] = {
            "total_decisions": 0,
            "executed": 0,
            "rejected": 0,
            "deferred": 0,
            "escalated": 0
        }
        self._ensure_log_dir()
        self._load_decisions()
        self._register_default_rules()
    
    def _ensure_log_dir(self):
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
    
    def _load_decisions(self):
        """加载历史决策"""
        if os.path.exists(self.log_path):
            try:
                with open(self.log_path, 'r') as f:
                    data = json.load(f)
                    self.decisions = [Decision(**d) for d in data.get('decisions', [])]
                    self.metrics = data.get('metrics', self.metrics)
            except:
                pass
    
    def _save_decisions(self):
        """保存决策日志"""
        data = {
            "decisions": [asdict(d) for d in self.decisions[-1000:]],  # 保留最近1000条
            "metrics": self.metrics,
            "last_updated": datetime.datetime.now().isoformat()
        }
        with open(self.log_path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def _register_default_rules(self):
        """注册默认规则"""
        
        # 规则1：资源检查 - 磁盘空间
        self.add_rule(DecisionRule(
            name="disk_space_check",
            condition=lambda ctx: ctx.get('disk_usage', 0) > 90,
            action=lambda ctx: f"磁盘使用率 {ctx.get('disk_usage')}%，建议清理",
            level=DecisionLevel.MEDIUM,
            description="磁盘空间不足时提醒清理"
        ))
        
        # 规则2：资源检查 - 内存
        self.add_rule(DecisionRule(
            name="memory_check",
            condition=lambda ctx: ctx.get('memory_usage', 0) > 85,
            action=lambda ctx: f"内存使用率 {ctx.get('memory_usage')}%，考虑释放",
            level=DecisionLevel.LOW,
            description="内存使用率高时建议释放"
        ))
        
        # 规则3：服务状态检查
        self.add_rule(DecisionRule(
            name="service_down",
            condition=lambda ctx: ctx.get('service_status') == 'down',
            action=lambda ctx: f"服务 {ctx.get('service_name')} 宕机，尝试重启",
            level=DecisionLevel.HIGH,
            description="服务宕机时尝试重启"
        ))
        
        # 规则4：异常检测
        self.add_rule(DecisionRule(
            name="anomaly_detected",
            condition=lambda ctx: ctx.get('anomaly_score', 0) > 0.8,
            action=lambda ctx: f"检测到异常活动 (score={ctx.get('anomaly_score')})，需人工确认",
            level=DecisionLevel.HIGH,
            description="高异常分数时需人工确认"
        ))
        
        # 规则5：安全检查
        self.add_rule(DecisionRule(
            name="security_threat",
            condition=lambda ctx: ctx.get('threat_level', 0) > 7,
            action=lambda ctx: f"检测到安全威胁 (level={ctx.get('threat_level')})，立即处理",
            level=DecisionLevel.HIGH,
            description="高威胁级别时立即处理"
        ))
    
    def add_rule(self, rule: DecisionRule):
        """添加决策规则"""
        self.rules.append(rule)
    
    def remove_rule(self, name: str):
        """移除决策规则"""
        self.rules = [r for r in self.rules if r.name != name]
    
    def decide(self, context: Dict[str, Any], decision_type: DecisionType = DecisionType.RULE_BASED) -> Decision:
        """做出决策"""
        import uuid
        
        decision_id = str(uuid.uuid4())[:8]
        timestamp = datetime.datetime.now().isoformat()
        
        # 应用规则引擎
        rule_applied = None
        action = None
        confidence = 0.5
        
        for rule in self.rules:
            try:
                if rule.condition(context):
                    rule_applied = rule.name
                    action = rule.action(context)
                    confidence = 0.9 if rule.level == DecisionLevel.LOW else 0.7
                    break
            except Exception as e:
                pass
        
        # 确定决策级别
        level = DecisionLevel.LOW
        for rule in self.rules:
            if rule.condition(context):
                if rule.level == DecisionLevel.HIGH:
                    level = DecisionLevel.HIGH
                elif rule.level == DecisionLevel.MEDIUM and level != DecisionLevel.HIGH:
                    level = DecisionLevel.MEDIUM
        
        # 根据规则和上下文确定结果
        if action:
            if level == DecisionLevel.HIGH:
                result = DecisionResult.ESCALATE
                reason = "高风险决策，需要升级"
            elif level == DecisionLevel.MEDIUM:
                result = DecisionResult.DEFER
                reason = "中风险决策，建议延迟执行"
            else:
                result = DecisionResult.EXECUTE
                reason = "低风险决策，可以执行"
        else:
            result = DecisionResult.EXECUTE
            reason = "无特定规则匹配，执行默认操作"
            action = "继续正常流程"
        
        # 创建决策记录
        decision = Decision(
            id=decision_id,
            timestamp=timestamp,
            context=context,
            decision_type=decision_type.value,
            level=level.value,
            rule_applied=rule_applied,
            result=result.value,
            reason=reason,
            confidence=confidence,
            action_taken=action
        )
        
        # 记录决策
        self.decisions.append(decision)
        self.metrics['total_decisions'] += 1
        
        if result == DecisionResult.EXECUTE:
            self.metrics['executed'] += 1
        elif result == DecisionResult.REJECT:
            self.metrics['rejected'] += 1
        elif result == DecisionResult.DEFER:
            self.metrics['deferred'] += 1
        elif result == DecisionResult.ESCALATE:
            self.metrics['escalated'] += 1
        
        # 保存日志
        self._save_decisions()
        
        return decision
    
    def get_statistics(self) -> Dict:
        """获取决策统计"""
        return {
            "total_decisions": self.metrics['total_decisions'],
            "executed": self.metrics['executed'],
            "rejected": self.metrics['rejected'],
            "deferred": self.metrics['deferred'],
            "escalated": self.metrics['escalated'],
            "rules_count": len(self.rules),
            "recent_decisions": len(self.decisions)
        }
    
    def explain_decision(self, decision_id: str) -> str:
        """解释决策"""
        for d in reversed(self.decisions):
            if d.id == decision_id:
                return f"""
决策ID: {d.id}
时间: {d.timestamp}
类型: {d.decision_type}
级别: {d.level}
规则: {d.rule_applied or '无'}
结果: {d.result}
原因: {d.reason}
置信度: {d.confidence:.0%}
执行操作: {d.action_taken}
上下文: {json.dumps(d.context, ensure_ascii=False)}
"""
        return "未找到决策记录"


# 全局实例
_engine: Optional[DecisionEngine] = None

def get_engine() -> DecisionEngine:
    global _engine
    if _engine is None:
        _engine = DecisionEngine()
    return _engine

if __name__ == "__main__":
    import sys
    
    engine = get_engine()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "stats":
            print(json.dumps(engine.get_statistics(), indent=2, ensure_ascii=False))
        elif sys.argv[1] == "test":
            # 测试决策
            test_cases = [
                {"disk_usage": 95, "memory_usage": 50},
                {"disk_usage": 50, "memory_usage": 90},
                {"service_status": "down", "service_name": "nginx"},
                {"anomaly_score": 0.9},
                {"threat_level": 8},
                {"disk_usage": 30, "memory_usage": 40}  # 正常
            ]
            
            print("=== 决策引擎测试 ===\n")
            for i, ctx in enumerate(test_cases):
                decision = engine.decide(ctx)
                print(f"测试 {i+1}: {ctx}")
                print(f"  -> {decision.result}: {decision.action_taken}")
                print(f"  -> 规则: {decision.rule_applied}, 置信度: {decision.confidence:.0%}")
                print()
        else:
            print("用法: python ultron-decision-engine.py [stats|test]")
    else:
        print("奥创决策引擎 v1.0")
        print(f"已加载 {len(engine.rules)} 条规则")
        print(f"历史决策: {len(engine.decisions)} 条")
        stats = engine.get_statistics()
        print(f"执行: {stats['executed']}, 拒绝: {stats['rejected']}, 延迟: {stats['deferred']}, 升级: {stats['escalated']}")