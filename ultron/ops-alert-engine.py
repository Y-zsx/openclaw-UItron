#!/usr/bin/env python3
"""
智能运维助手 - 告警规则引擎
第28世: 实现告警规则引擎
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


class AlertRule:
    """告警规则"""
    
    def __init__(
        self,
        name: str,
        metric_path: str,
        condition: str,  # "gt", "lt", "eq", "gte", "lte"
        threshold: float,
        level: AlertLevel,
        message: str = ""
    ):
        self.name = name
        self.metric_path = metric_path  # e.g., "memory.percent"
        self.condition = condition
        self.threshold = threshold
        self.level = level
        self.message = message or f"{name} 触发告警"
        self.last_triggered: Optional[float] = None
        self.cooldown_seconds = 300  # 5分钟冷却期
    
    def check(self, metrics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """检查规则是否触发"""
        # 解析指标路径
        value = self._get_nested_value(metrics, self.metric_path)
        if value is None:
            return None
        
        # 比较条件
        triggered = self._compare(value)
        
        if triggered:
            # 冷却期检查
            now = time.time()
            if self.last_triggered and (now - self.last_triggered) < self.cooldown_seconds:
                return None
            
            self.last_triggered = now
            return {
                "rule": self.name,
                "metric": self.metric_path,
                "value": value,
                "threshold": self.threshold,
                "condition": self.condition,
                "level": self.level.name,
                "message": self.message,
                "timestamp": datetime.now().isoformat()
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
        }
        return ops.get(self.condition, lambda v, t: False)(value, self.threshold)


class AlertEngine:
    """告警引擎"""
    
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.alerts: List[Dict[str, Any]] = []
        self._init_default_rules()
    
    def _init_default_rules(self):
        """初始化默认规则"""
        # CPU告警
        self.add_rule(AlertRule(
            name="CPU使用率过高",
            metric_path="cpu.usage_percent",
            condition="gte",
            threshold=90,
            level=AlertLevel.WARNING,
            message="CPU使用率超过90%"
        ))
        
        self.add_rule(AlertRule(
            name="CPU使用率严重",
            metric_path="cpu.usage_percent",
            condition="gte",
            threshold=95,
            level=AlertLevel.CRITICAL,
            message="CPU使用率超过95%"
        ))
        
        # 内存告警
        self.add_rule(AlertRule(
            name="内存使用率过高",
            metric_path="memory.percent",
            condition="gte",
            threshold=85,
            level=AlertLevel.WARNING,
            message="内存使用率超过85%"
        ))
        
        self.add_rule(AlertRule(
            name="内存使用率严重",
            metric_path="memory.percent",
            condition="gte",
            threshold=95,
            level=AlertLevel.CRITICAL,
            message="内存使用率超过95%"
        ))
        
        # 磁盘告警
        self.add_rule(AlertRule(
            name="磁盘使用率过高",
            metric_path="disk.disks.0.percent",
            condition="gte",
            threshold=90,
            level=AlertLevel.WARNING,
            message="根分区使用率超过90%"
        ))
        
        # 负载告警
        self.add_rule(AlertRule(
            name="系统负载过高",
            metric_path="cpu.load_avg.0",
            condition="gte",
            threshold=4,
            level=AlertLevel.WARNING,
            message="系统负载超过4"
        ))
        
        # 网络丢包告警
        self.add_rule(AlertRule(
            name="网络丢包",
            metric_path="network.dropin",
            condition="gt",
            threshold=100,
            level=AlertLevel.WARNING,
            message="网络入口丢包"
        ))
    
    def add_rule(self, rule: AlertRule):
        """添加规则"""
        self.rules.append(rule)
    
    def check(self, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        """检查所有规则"""
        triggered = []
        
        for rule in self.rules:
            result = rule.check(metrics)
            if result:
                triggered.append(result)
                self.alerts.append(result)
        
        # 按级别排序
        triggered.sort(key=lambda x: x.get('level', 'INFO'))
        
        return triggered
    
    def get_active_alerts(self, minutes: int = 30) -> List[Dict[str, Any]]:
        """获取活跃告警"""
        cutoff = time.time() - (minutes * 60)
        return [
            a for a in self.alerts 
            if a.get('_created_at', 0) > cutoff
        ]
    
    def get_alert_summary(self) -> Dict[str, Any]:
        """获取告警统计"""
        return {
            "total": len(self.alerts),
            "critical": len([a for a in self.alerts if a.get('level') == 'CRITICAL']),
            "warning": len([a for a in self.alerts if a.get('level') == 'WARNING']),
            "info": len([a for a in self.alerts if a.get('level') == 'INFO']),
            "recent": len(self.get_active_alerts(30))
        }
    
    def deduplicate_alerts(self, alerts: List[Dict], window_seconds: int = 300) -> List[Dict]:
        """告警去重 - 同一规则在时间窗口内只保留一条"""
        if not alerts:
            return []
        
        seen = {}  # rule_name -> earliest alert in window
        now = time.time()
        
        for alert in sorted(alerts, key=lambda x: x.get('timestamp', '')):
            rule_name = alert.get('rule', '')
            alert_time = alert.get('timestamp', '')
            
            # 解析时间戳
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(alert_time.replace('Z', '+00:00'))
                alert_ts = dt.timestamp()
            except:
                alert_ts = now
            
            if rule_name not in seen:
                if now - alert_ts < window_seconds:
                    seen[rule_name] = alert
        
        return list(seen.values())
    
    def group_alerts_by_level(self, alerts: List[Dict]) -> Dict[str, List[Dict]]:
        """按级别分组告警"""
        grouped = {"CRITICAL": [], "WARNING": [], "INFO": []}
        for alert in alerts:
            level = alert.get('level', 'INFO')
            if level in grouped:
                grouped[level].append(alert)
        return grouped
    
    def group_alerts_by_metric(self, alerts: List[Dict]) -> Dict[str, List[Dict]]:
        """按指标分组告警"""
        grouped = {}
        for alert in alerts:
            metric = alert.get('metric', 'unknown')
            if metric not in grouped:
                grouped[metric] = []
            grouped[metric].append(alert)
        return grouped


def main():
    """测试告警引擎"""
    # 模拟指标数据
    test_metrics = {
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "usage_percent": 92,
            "load_avg": [5.2, 4.1, 3.5]
        },
        "memory": {
            "percent": 88
        },
        "disk": {
            "disks": [{"percent": 75}]
        },
        "network": {
            "dropin": 50
        }
    }
    
    engine = AlertEngine()
    
    print("=" * 50)
    print("智能运维助手 - 告警规则引擎")
    print("=" * 50)
    print(f"\n📊 加载规则数: {len(engine.rules)}")
    
    # 检查告警
    alerts = engine.check(test_metrics)
    
    print(f"\n🚨 触发告警数: {len(alerts)}")
    
    for alert in alerts:
        level_emoji = {
            "CRITICAL": "🔴",
            "WARNING": "🟡",
            "INFO": "🔵"
        }.get(alert['level'], "⚪")
        
        print(f"\n{level_emoji} [{alert['level']}] {alert['message']}")
        print(f"   指标: {alert['metric']} = {alert['value']:.1f}")
        print(f"   阈值: {alert['condition']} {alert['threshold']}")
        print(f"   时间: {alert['timestamp']}")
    
    # 统计
    summary = engine.get_alert_summary()
    print(f"\n📈 告警统计: {summary}")
    print("\n✅ 告警引擎运行正常")


if __name__ == "__main__":
    main()