#!/usr/bin/env python3
"""
Agent告警引擎 - 规则引擎与告警检测
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from enum import Enum


class AlertLevel(Enum):
    """告警级别"""
    CRITICAL = 1  # 严重 - 需要立即处理
    WARNING = 2   # 警告 - 需要关注
    INFO = 3      # 信息 - 提示性


class AlertState(Enum):
    """告警状态"""
    FIRING = "firing"      # 触发中
    RESOLVED = "resolved"  # 已恢复
    ACKNOWLEDGED = "acknowledged"  # 已确认


class AlertRule:
    """告警规则"""
    
    def __init__(
        self,
        id: str,
        name: str,
        metric_path: str,
        condition: str,  # "gt", "lt", "eq", "gte", "lte"
        threshold: float,
        level: AlertLevel,
        message: str = "",
        enabled: bool = True,
        cooldown_seconds: int = 300,
        duration_seconds: int = 0,  # 持续多长时间才触发 (0=立即触发)
        tags: Dict[str, str] = None
    ):
        self.id = id
        self.name = name
        self.metric_path = metric_path
        self.condition = condition
        self.threshold = threshold
        self.level = level
        self.message = message or f"{name} 触发告警"
        self.enabled = enabled
        self.cooldown_seconds = cooldown_seconds
        self.duration_seconds = duration_seconds
        self.tags = tags or {}
        
        # 运行时状态
        self.last_triggered: Optional[float] = None
        self.first_triggered: Optional[float] = None
        self.is_firing = False
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "metric_path": self.metric_path,
            "condition": self.condition,
            "threshold": self.threshold,
            "level": self.level.value,
            "message": self.message,
            "enabled": self.enabled,
            "cooldown_seconds": self.cooldown_seconds,
            "duration_seconds": self.duration_seconds,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AlertRule':
        return cls(
            id=data["id"],
            name=data["name"],
            metric_path=data["metric_path"],
            condition=data["condition"],
            threshold=data["threshold"],
            level=AlertLevel(data.get("level", 2)),
            message=data.get("message", ""),
            enabled=data.get("enabled", True),
            cooldown_seconds=data.get("cooldown_seconds", 300),
            duration_seconds=data.get("duration_seconds", 0),
            tags=data.get("tags", {})
        )
    
    def check(self, metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """检查规则是否触发"""
        if not self.enabled:
            return None
        
        # 解析指标路径
        value = self._get_nested_value(metrics, self.metric_path)
        if value is None:
            return None
        
        # 比较条件
        triggered = self._compare(value)
        
        now = time.time()
        
        if triggered:
            # 首次触发记录时间
            if self.first_triggered is None:
                self.first_triggered = now
            
            # 检查持续时间
            if now - self.first_triggered < self.duration_seconds:
                return None
            
            # 冷却期检查
            if self.last_triggered and (now - self.last_triggered) < self.cooldown_seconds:
                return None
            
            # 检查是否已发送过（避免重复）
            if self.is_firing and self.last_triggered:
                return None
            
            self.last_triggered = now
            self.is_firing = True
            
            return {
                "rule_id": self.id,
                "rule_name": self.name,
                "metric": self.metric_path,
                "value": value,
                "threshold": self.threshold,
                "condition": self.condition,
                "level": self.level.name,
                "message": self.message,
                "timestamp": datetime.now().isoformat(),
                "tags": self.tags,
                "state": AlertState.FIRING.value
            }
        else:
            # 指标恢复正常，检查是否需要发送恢复通知
            if self.is_firing:
                self.is_firing = False
                self.first_triggered = None
                return {
                    "rule_id": self.id,
                    "rule_name": self.name,
                    "metric": self.metric_path,
                    "value": value,
                    "threshold": self.threshold,
                    "condition": self.condition,
                    "level": self.level.name,
                    "message": f"✅ {self.name} 已恢复",
                    "timestamp": datetime.now().isoformat(),
                    "tags": self.tags,
                    "state": AlertState.RESOLVED.value
                }
        
        return None
    
    def _get_nested_value(self, data: Dict, path: str) -> Optional[float]:
        """获取嵌套指标值"""
        keys = path.split('.')
        current = data
        
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        try:
            return float(current)
        except (TypeError, ValueError):
            return None
    
    def _compare(self, value: float) -> bool:
        """比较条件"""
        ops = {
            "gt": lambda v, t: v > t,
            "lt": lambda v, t: v < t,
            "eq": lambda v, t: v == t,
            "gte": lambda v, t: v >= t,
            "lte": lambda v, t: v <= t,
            "ne": lambda v, t: v != t,
        }
        return ops.get(self.condition, lambda v, t: False)(value, self.threshold)


class AlertEngine:
    """Agent告警引擎"""
    
    def __init__(self, config_path: str = None):
        self.rules: Dict[str, AlertRule] = {}
        self.alerts: List[Dict[str, Any]] = []
        self.config_path = config_path
        
        if config_path and os.path.exists(config_path):
            self.load_rules(config_path)
        else:
            self._init_default_rules()
    
    def _init_default_rules(self):
        """初始化默认规则"""
        default_rules = [
            # Agent服务相关告警
            AlertRule(
                id="agent_cpu_high",
                name="Agent服务CPU使用率过高",
                metric_path="agent.cpu.percent",
                condition="gte",
                threshold=80,
                level=AlertLevel.WARNING,
                message="Agent服务CPU使用率超过80%"
            ),
            AlertRule(
                id="agent_memory_high",
                name="Agent服务内存使用率过高",
                metric_path="agent.memory.percent",
                condition="gte",
                threshold=85,
                level=AlertLevel.WARNING,
                message="Agent服务内存使用率超过85%"
            ),
            AlertRule(
                id="agent_task_queue_full",
                name="Agent任务队列积压",
                metric_path="agent.queue.pending",
                condition="gte",
                threshold=100,
                level=AlertLevel.CRITICAL,
                message="Agent任务队列积压超过100个"
            ),
            AlertRule(
                id="agent_task_failed",
                name="Agent任务失败率过高",
                metric_path="agent.tasks.failure_rate",
                condition="gte",
                threshold=0.2,
                level=AlertLevel.WARNING,
                message="Agent任务失败率超过20%"
            ),
            AlertRule(
                id="agent_response_slow",
                name="Agent响应时间过长",
                metric_path="agent.latency.p99",
                condition="gte",
                threshold=5000,
                level=AlertLevel.WARNING,
                message="Agent响应时间P99超过5秒"
            ),
            AlertRule(
                id="agent_unhealthy",
                name="Agent服务不健康",
                metric_path="agent.health",
                condition="eq",
                threshold=0,
                level=AlertLevel.CRITICAL,
                message="Agent服务健康检查失败"
            ),
            # 系统资源告警
            AlertRule(
                id="system_cpu_critical",
                name="系统CPU使用率严重",
                metric_path="system.cpu.usage",
                condition="gte",
                threshold=95,
                level=AlertLevel.CRITICAL,
                message="系统CPU使用率超过95%"
            ),
            AlertRule(
                id="system_memory_critical",
                name="系统内存使用率严重",
                metric_path="system.memory.usage",
                condition="gte",
                threshold=95,
                level=AlertLevel.CRITICAL,
                message="系统内存使用率超过95%"
            ),
            AlertRule(
                id="system_disk_critical",
                name="系统磁盘使用率过高",
                metric_path="system.disk.usage",
                condition="gte",
                threshold=90,
                level=AlertLevel.CRITICAL,
                message="系统磁盘使用率超过90%"
            ),
        ]
        
        for rule in default_rules:
            self.rules[rule.id] = rule
    
    def add_rule(self, rule: AlertRule):
        """添加规则"""
        self.rules[rule.id] = rule
    
    def remove_rule(self, rule_id: str) -> bool:
        """移除规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            return True
        return False
    
    def enable_rule(self, rule_id: str) -> bool:
        """启用规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            return True
        return False
    
    def disable_rule(self, rule_id: str) -> bool:
        """禁用规则"""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            return True
        return False
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """获取规则"""
        return self.rules.get(rule_id)
    
    def list_rules(self) -> List[Dict]:
        """列出所有规则"""
        return [rule.to_dict() for rule in self.rules.values()]
    
    def check(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检查所有规则"""
        triggered = []
        
        for rule in self.rules.values():
            result = rule.check(metrics)
            if result:
                triggered.append(result)
                self.alerts.append(result)
        
        # 按级别排序（CRITICAL优先）
        triggered.sort(key=lambda x: x.get('level', 'INFO'))
        
        return triggered
    
    def get_firing_alerts(self) -> List[Dict[str, Any]]:
        """获取当前触发中的告警"""
        return [
            a for a in self.alerts 
            if a.get('state') == AlertState.FIRING.value
        ]
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """获取告警统计"""
        firing = self.get_firing_alerts()
        return {
            "total_alerts": len(self.alerts),
            "firing_count": len(firing),
            "critical_firing": len([a for a in firing if a.get('level') == 'CRITICAL']),
            "warning_firing": len([a for a in firing if a.get('level') == 'WARNING']),
            "info_firing": len([a for a in firing if a.get('level') == 'INFO']),
            "rules_count": len(self.rules),
            "enabled_rules": len([r for r in self.rules.values() if r.enabled])
        }
    
    def save_rules(self, path: str = None):
        """保存规则到文件"""
        save_path = path or self.config_path
        if not save_path:
            return
        
        rules_data = {
            "version": "1.0",
            "rules": [rule.to_dict() for rule in self.rules.values()]
        }
        
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        with open(save_path, 'w') as f:
            json.dump(rules_data, f, indent=2, ensure_ascii=False)
    
    def load_rules(self, path: str):
        """从文件加载规则"""
        with open(path, 'r') as f:
            data = json.load(f)
        
        self.rules.clear()
        for rule_data in data.get("rules", []):
            rule = AlertRule.from_dict(rule_data)
            self.rules[rule.id] = rule


import os

# 导出
__all__ = ['AlertEngine', 'AlertRule', 'AlertLevel', 'AlertState']