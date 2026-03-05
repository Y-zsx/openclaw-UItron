#!/usr/bin/env python3
"""
告警规则引擎集成模块
Alert Rule Engine Integration
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    """告警状态"""
    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"


@dataclass
class AlertRule:
    """告警规则"""
    id: str
    name: str
    condition: str  # 条件表达式
    severity: str = "warning"
    enabled: bool = True
    cooldown_seconds: int = 300  # 冷却时间
    action: str = "notify"  # 触发动作
    metadata: Dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_triggered: Optional[str] = None
    trigger_count: int = 0


@dataclass
class Alert:
    """告警实例"""
    id: str
    rule_id: str
    rule_name: str
    severity: str
    message: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    status: str = "firing"
    fired_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: Optional[str] = None
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None


class AlertRuleEngine:
    """告警规则引擎"""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.alerts: Dict[str, Alert] = {}
        self.alert_history: List[Alert] = []
        self._load_default_rules()
        logger.info("告警规则引擎初始化完成")
    
    def _load_default_rules(self):
        """加载默认告警规则"""
        default_rules = [
            AlertRule(
                id="cpu_high",
                name="CPU使用率过高",
                condition="cpu > 80",
                severity="warning",
                action="scale_up",
                metadata={"threshold": 80, "metric": "cpu"}
            ),
            AlertRule(
                id="memory_high",
                name="内存使用率过高",
                condition="memory > 85",
                severity="warning",
                action="scale_up",
                metadata={"threshold": 85, "metric": "memory"}
            ),
            AlertRule(
                id="disk_full",
                name="磁盘空间不足",
                condition="disk > 90",
                severity="error",
                action="cleanup",
                metadata={"threshold": 90, "metric": "disk"}
            ),
            AlertRule(
                id="service_down",
                name="服务宕机",
                condition="service_status == 'down'",
                severity="critical",
                action="restart_service",
                metadata={"metric": "service_status"}
            ),
            AlertRule(
                id="error_rate_high",
                name="错误率过高",
                condition="error_rate > 5",
                severity="error",
                action="investigate",
                metadata={"threshold": 5, "metric": "error_rate"}
            ),
            AlertRule(
                id="response_slow",
                name="响应时间过长",
                condition="response_time > 1000",
                severity="warning",
                action="optimize",
                metadata={"threshold": 1000, "metric": "response_time"}
            ),
        ]
        
        for rule in default_rules:
            self.rules[rule.id] = rule
        
        logger.info(f"加载了 {len(default_rules)} 条默认告警规则")
    
    def evaluate_condition(self, condition: str, metrics: Dict[str, Any]) -> bool:
        """评估条件表达式"""
        try:
            # 安全评估：只支持基本的比较运算
            # 替换变量名为实际值
            expr = condition
            for key, value in metrics.items():
                if isinstance(value, (int, float)):
                    expr = expr.replace(key, str(value))
                elif isinstance(value, str):
                    expr = expr.replace(f"'{key}'", f"'{value}'").replace(f'"{key}"', f'"{value}"')
            
            # 安全：只允许特定的运算符
            allowed_chars = set("0123456789+-*/%<>=!()._ ")
            if not all(c in allowed_chars or c.isalnum() for c in expr):
                logger.warning(f"条件表达式包含不安全字符: {condition}")
                return False
            
            result = eval(expr, {"__builtins__": {}}, {})
            return bool(result)
        except Exception as e:
            logger.error(f"条件评估失败: {condition}, error: {e}")
            return False
    
    def check_alerts(self, metrics: Dict[str, Any]) -> List[Alert]:
        """检查所有规则，返回触发的告警"""
        triggered_alerts = []
        now = datetime.now()
        
        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue
            
            # 检查冷却时间
            if rule.last_triggered:
                last_time = datetime.fromisoformat(rule.last_triggered)
                if (now - last_time).total_seconds() < rule.cooldown_seconds:
                    continue
            
            # 评估条件
            if self.evaluate_condition(rule.condition, metrics):
                # 创建告警
                alert = Alert(
                    id=f"alert_{rule_id}_{int(now.timestamp())}",
                    rule_id=rule_id,
                    rule_name=rule.name,
                    severity=rule.severity,
                    message=f"{rule.name}: {rule.condition} 触发",
                    metrics=metrics
                )
                
                # 更新规则状态
                rule.last_triggered = now.isoformat()
                rule.trigger_count += 1
                
                # 存储告警
                self.alerts[alert.id] = alert
                triggered_alerts.append(alert)
                
                logger.info(f"告警触发: {rule.name} (severity: {rule.severity})")
        
        return triggered_alerts
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        return self.rules.get(rule_id)
    
    def add_rule(self, rule: AlertRule) -> bool:
        if rule.id in self.rules:
            return False
        self.rules[rule.id] = rule
        return True
    
    def update_rule(self, rule_id: str, **kwargs) -> bool:
        if rule_id not in self.rules:
            return False
        rule = self.rules[rule_id]
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        return True
    
    def delete_rule(self, rule_id: str) -> bool:
        if rule_id in self.rules:
            del self.rules[rule_id]
            return True
        return False
    
    def get_rules(self, enabled_only: bool = False) -> List[AlertRule]:
        rules = list(self.rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules
    
    def get_alerts(self, status: Optional[str] = None, limit: int = 100) -> List[Alert]:
        alerts = list(self.alerts.values())
        if status:
            alerts = [a for a in alerts if a.status == status]
        return sorted(alerts, key=lambda x: x.fired_at, reverse=True)[:limit]
    
    def acknowledge_alert(self, alert_id: str, acknowledged_by: str = "system") -> bool:
        if alert_id not in self.alerts:
            return False
        alert = self.alerts[alert_id]
        alert.acknowledged = True
        alert.acknowledged_by = acknowledged_by
        alert.acknowledged_at = datetime.now().isoformat()
        return True
    
    def resolve_alert(self, alert_id: str) -> bool:
        if alert_id not in self.alerts:
            return False
        alert = self.alerts[alert_id]
        alert.status = "resolved"
        alert.resolved_at = datetime.now().isoformat()
        # 移动到历史
        self.alert_history.append(alert)
        del self.alerts[alert_id]
        return True
    
    def get_stats(self) -> Dict:
        return {
            "total_rules": len(self.rules),
            "enabled_rules": len([r for r in self.rules.values() if r.enabled]),
            "active_alerts": len([a for a in self.alerts.values() if a.status == "firing"]),
            "pending_alerts": len([a for a in self.alerts.values() if a.status == "pending"]),
            "resolved_today": len([a for a in self.alert_history if a.resolved_at and a.resolved_at.startswith(datetime.now().strftime("%Y-%m-%d"))])
        }


# 全局实例
alert_engine = AlertRuleEngine()