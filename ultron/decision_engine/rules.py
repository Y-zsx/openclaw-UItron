"""
规则引擎模块
Rule Engine - 基于规则的决策系统
"""
import re
import logging
from typing import Dict, List, Any, Callable, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class RuleType(Enum):
    CONDITION = "condition"       # 条件规则
    THRESHOLD = "threshold"       # 阈值规则
    PATTERN = "pattern"          # 模式匹配规则
    TEMPORAL = "temporal"        # 时间规则
    COMPOSITE = "composite"      # 复合规则


class RuleAction(Enum):
    NOTIFY = "notify"
    ALERT = "alert"
    EXECUTE = "execute"
    ESCALATE = "escalate"
    LOG = "log"
    BLOCK = "block"


@dataclass
class Rule:
    """
    决策规则
    """
    name: str
    rule_type: RuleType
    condition: Callable[[Dict], bool] = None
    action: str = "log"
    action_params: Dict = field(default_factory=dict)
    priority: int = 5
    enabled: bool = True
    description: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    
    # 阈值规则专用
    threshold: float = None
    metric: str = None
    operator: str = ">"  # >, <, >=, <=, ==, !=
    
    # 模式匹配专用
    pattern: str = None
    
    # 统计
    triggered_count: int = 0
    last_triggered: datetime = None
    
    def matches(self, context: 'DecisionContext') -> bool:
        """检查规则是否匹配上下文"""
        if not self.enabled:
            return False
            
        try:
            if self.rule_type == RuleType.CONDITION and self.condition:
                return self.condition(context.data)
            elif self.rule_type == RuleType.THRESHOLD:
                return self._match_threshold(context)
            elif self.rule_type == RuleType.PATTERN:
                return self._match_pattern(context)
            elif self.rule_type == RuleType.TEMPORAL:
                return self._match_temporal(context)
            return False
        except Exception as e:
            logger.warning(f"规则匹配失败 {self.name}: {e}")
            return False
    
    def _match_threshold(self, context: 'DecisionContext') -> bool:
        """阈值匹配"""
        if not self.metric or self.threshold is None:
            return False
            
        value = context.get(self.metric)
        if value is None:
            return False
            
        try:
            value = float(value)
            threshold = float(self.threshold)
            
            if self.operator == ">":
                return value > threshold
            elif self.operator == "<":
                return value < threshold
            elif self.operator == ">=":
                return value >= threshold
            elif self.operator == "<=":
                return value <= threshold
            elif self.operator == "==":
                return value == threshold
            elif self.operator == "!=":
                return value != threshold
            return False
        except (ValueError, TypeError):
            return False
    
    def _match_pattern(self, context: 'DecisionContext') -> bool:
        """模式匹配"""
        if not self.pattern:
            return False
            
        # 匹配所有数据字段
        for key, value in context.data.items():
            if isinstance(value, str):
                if re.search(self.pattern, value):
                    return True
        return False
    
    def _match_temporal(self, context: 'DecisionContext') -> bool:
        """时间匹配 - 检查是否在特定时间范围内"""
        # 简化实现: 检查小时
        hour = datetime.now().hour
        temporal_range = self.metadata.get("hour_range")
        if temporal_range:
            start, end = temporal_range
            return start <= hour < end
        return True
    
    def create_decision(self, context: 'DecisionContext') -> 'Decision':
        """根据规则创建决策"""
        from .core import Decision, DecisionPriority
        
        # 映射优先级
        priority_map = {
            1: DecisionPriority.LOW,
            2: DecisionPriority.LOW,
            3: DecisionPriority.NORMAL,
            4: DecisionPriority.NORMAL,
            5: DecisionPriority.HIGH,
            6: DecisionPriority.HIGH,
            7: DecisionPriority.CRITICAL,
            8: DecisionPriority.CRITICAL,
            9: DecisionPriority.CRITICAL,
            10: DecisionPriority.CRITICAL
        }
        
        decision = Decision(
            context=context,
            action=self.action,
            params=self.action_params.copy()
        )
        decision.priority = priority_map.get(self.priority, DecisionPriority.NORMAL)
        
        # 更新统计
        self.triggered_count += 1
        self.last_triggered = datetime.now()
        
        return decision
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "type": self.rule_type.value,
            "action": self.action,
            "priority": self.priority,
            "enabled": self.enabled,
            "description": self.description,
            "tags": self.tags,
            "triggered_count": self.triggered_count,
            "last_triggered": self.last_triggered.isoformat() if self.last_triggered else None
        }


class RuleEngine:
    """
    规则引擎
    管理规则的注册、匹配和执行
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.rules: List[Rule] = []
        self.rule_index: Dict[str, List[Rule]] = {}  # 按标签索引
        
        # 加载预定义规则
        self._load_builtin_rules()
        
        logger.info(f"规则引擎初始化完成, {len(self.rules)} 条规则")
        
    def _load_builtin_rules(self):
        """加载内置规则"""
        # 高CPU告警规则
        self.add_rule(Rule(
            name="high_cpu_alert",
            rule_type=RuleType.THRESHOLD,
            metric="cpu_percent",
            threshold=80,
            operator=">=",
            action="alert",
            action_params={"level": "high", "message": "CPU使用率过高"},
            priority=8,
            description="CPU使用率超过80%时告警",
            tags=["cpu", "alert", "performance"]
        ))
        
        # 内存告警规则
        self.add_rule(Rule(
            name="memory_alert",
            rule_type=RuleType.THRESHOLD,
            metric="memory_percent",
            threshold=90,
            operator=">=",
            action="alert",
            action_params={"level": "critical", "message": "内存使用率过高"},
            priority=9,
            description="内存使用率超过90%时告警",
            tags=["memory", "alert", "performance"]
        ))
        
        # 磁盘告警规则
        self.add_rule(Rule(
            name="disk_alert",
            rule_type=RuleType.THRESHOLD,
            metric="disk_percent",
            threshold=85,
            operator=">=",
            action="notify",
            action_params={"level": "warning", "message": "磁盘空间不足"},
            priority=7,
            description="磁盘使用率超过85%时通知",
            tags=["disk", "alert", "storage"]
        ))
        
        # 服务down规则
        self.add_rule(Rule(
            name="service_down",
            rule_type=RuleType.CONDITION,
            condition=lambda d: d.get("service_status") == "down",
            action="escalate",
            action_params={"level": "critical", "message": "服务宕机"},
            priority=10,
            description="服务宕机时升级告警",
            tags=["service", "alert", "critical"]
        ))
        
        # 错误率规则
        self.add_rule(Rule(
            name="high_error_rate",
            rule_type=RuleType.THRESHOLD,
            metric="error_rate",
            threshold=5,
            operator=">",
            action="alert",
            action_params={"level": "high", "message": "错误率过高"},
            priority=8,
            description="错误率超过5%时告警",
            tags=["error", "alert", "quality"]
        ))
        
        # 日志错误模式
        self.add_rule(Rule(
            name="error_pattern",
            rule_type=RuleType.PATTERN,
            pattern=r"(ERROR|FATAL|CRITICAL|Exception)",
            action="log",
            action_params={"level": "warning"},
            priority=5,
            description="日志中出现错误关键词时记录",
            tags=["log", "error", "pattern"]
        ))
        
    def add_rule(self, rule: Rule):
        """添加规则"""
        self.rules.append(rule)
        
        # 更新索引
        for tag in rule.tags:
            if tag not in self.rule_index:
                self.rule_index[tag] = []
            self.rule_index[tag].append(rule)
            
        logger.info(f"添加规则: {rule.name}")
        
    def remove_rule(self, name: str) -> bool:
        """移除规则"""
        for i, rule in enumerate(self.rules):
            if rule.name == name:
                self.rules.pop(i)
                # 清理索引
                for tag in rule.tags:
                    if tag in self.rule_index:
                        self.rule_index[tag] = [r for r in self.rule_index[tag] if r.name != name]
                logger.info(f"移除规则: {name}")
                return True
        return False
    
    def enable_rule(self, name: str) -> bool:
        """启用规则"""
        for rule in self.rules:
            if rule.name == name:
                rule.enabled = True
                logger.info(f"启用规则: {name}")
                return True
        return False
    
    def disable_rule(self, name: str) -> bool:
        """禁用规则"""
        for rule in self.rules:
            if rule.name == name:
                rule.enabled = False
                logger.info(f"禁用规则: {name}")
                return True
        return False
    
    def get_rules(self, tag: str = None, enabled_only: bool = False) -> List[Rule]:
        """获取规则列表"""
        rules = self.rules
        
        if tag:
            rules = self.rule_index.get(tag, [])
            
        if enabled_only:
            rules = [r for r in rules if r.enabled]
            
        return rules
    
    def match(self, context: 'DecisionContext') -> List[Rule]:
        """匹配所有适用的规则"""
        matched = []
        for rule in self.rules:
            if rule.matches(context):
                matched.append(rule)
        return matched
    
    def get_stats(self) -> Dict:
        """获取规则统计"""
        return {
            "total": len(self.rules),
            "enabled": len([r for r in self.rules if r.enabled]),
            "by_tag": {tag: len(rules) for tag, rules in self.rule_index.items()},
            "triggered_total": sum(r.triggered_count for r in self.rules)
        }
    
    def create_condition_rule(
        self,
        name: str,
        condition_fn: Callable[[Dict], bool],
        action: str = "log",
        priority: int = 5,
        **kwargs
    ) -> Rule:
        """创建条件规则 (便捷方法)"""
        return Rule(
            name=name,
            rule_type=RuleType.CONDITION,
            condition=condition_fn,
            action=action,
            priority=priority,
            **kwargs
        )
    
    def create_threshold_rule(
        self,
        name: str,
        metric: str,
        threshold: float,
        operator: str = ">",
        action: str = "alert",
        priority: int = 5,
        **kwargs
    ) -> Rule:
        """创建阈值规则 (便捷方法)"""
        return Rule(
            name=name,
            rule_type=RuleType.THRESHOLD,
            metric=metric,
            threshold=threshold,
            operator=operator,
            action=action,
            priority=priority,
            **kwargs
        )
    
    def create_pattern_rule(
        self,
        name: str,
        pattern: str,
        action: str = "log",
        priority: int = 5,
        **kwargs
    ) -> Rule:
        """创建模式匹配规则 (便捷方法)"""
        return Rule(
            name=name,
            rule_type=RuleType.PATTERN,
            pattern=pattern,
            action=action,
            priority=priority,
            **kwargs
        )