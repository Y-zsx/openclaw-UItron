#!/usr/bin/env python3
"""
告警规则引擎
定义和管理告警规则，触发告警
"""
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
from enum import Enum

ALERT_DIR = Path("/root/.openclaw/workspace/ultron-workflow/monitoring")
RULES_FILE = ALERT_DIR / "alert_rules.json"
ALERTS_FILE = ALERT_DIR / "alerts.json"
CONFIG_FILE = ALERT_DIR / "config.json"


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertRule:
    """告警规则"""
    def __init__(self, rule_id, name, condition, level, message, enabled=True, cooldown=300):
        self.rule_id = rule_id
        self.name = name
        self.condition = condition  # lambda函数
        self.level = level
        self.message = message
        self.enabled = enabled
        self.cooldown = cooldown  # 冷却时间（秒）
        self.last_triggered = None
    
    def can_trigger(self):
        """检查是否在冷却期"""
        if not self.last_triggered:
            return True
        elapsed = (datetime.now() - self.last_triggered).total_seconds()
        return elapsed >= self.cooldown
    
    def trigger(self, context):
        """触发告警"""
        self.last_triggered = datetime.now()
        return {
            "rule_id": self.rule_id,
            "rule_name": self.name,
            "level": self.level.value,
            "message": self.message.format(**context),
            "timestamp": self.last_triggered.isoformat(),
            "context": context
        }


class AlertEngine:
    """告警引擎"""
    
    # 默认规则
    DEFAULT_RULES = [
        {
            "rule_id": "agent_down",
            "name": "Agent离线",
            "metric": "agent_status",
            "condition": "==",
            "value": "down",
            "level": "critical",
            "message": "Agent {agent_id} 已离线!",
            "enabled": True,
            "cooldown": 60
        },
        {
            "rule_id": "high_memory",
            "name": "内存使用率高",
            "metric": "memory_percent",
            "condition": ">",
            "value": 85,
            "level": "warning",
            "message": "内存使用率 {memory_percent}% 超过阈值!",
            "enabled": True,
            "cooldown": 300
        },
        {
            "rule_id": "high_cpu",
            "name": "CPU使用率高",
            "metric": "cpu_percent",
            "condition": ">",
            "value": 90,
            "level": "warning",
            "message": "CPU使用率 {cpu_percent}% 过高!",
            "enabled": True,
            "cooldown": 300
        },
        {
            "rule_id": "gateway_unreachable",
            "name": "Gateway不可达",
            "metric": "gateway_reachable",
            "condition": "==",
            "value": False,
            "level": "critical",
            "message": "Gateway服务不可达!",
            "enabled": True,
            "cooldown": 60
        },
        {
            "rule_id": "session_overflow",
            "name": "会话数过多",
            "metric": "session_count",
            "condition": ">",
            "value": 1000,
            "level": "error",
            "message": "会话数 {session_count} 超过阈值!",
            "enabled": True,
            "cooldown": 600
        },
        {
            "rule_id": "agent_heartbeat_timeout",
            "name": "Agent心跳超时",
            "metric": "heartbeat_age",
            "condition": ">",
            "value": 300,
            "level": "error",
            "message": "Agent {agent_id} 心跳超时 {heartbeat_age}秒!",
            "enabled": True,
            "cooldown": 120
        },
        {
            "rule_id": "disk_low",
            "name": "磁盘空间不足",
            "metric": "disk_percent",
            "condition": ">",
            "value": 90,
            "level": "warning",
            "message": "磁盘使用率 {disk_percent}% 过高!",
            "enabled": True,
            "cooldown": 600
        }
    ]
    
    def __init__(self):
        self.rules = []
        self.alerts = []
        self.load_rules()
        self.load_alerts()
    
    def load_rules(self):
        """加载规则"""
        if RULES_FILE.exists():
            with open(RULES_FILE) as f:
                rules_data = json.load(f)
        else:
            rules_data = self.DEFAULT_RULES
            self.save_rules(rules_data)
        
        self.rules = rules_data
    
    def save_rules(self, rules=None):
        """保存规则"""
        if rules is None:
            rules = self.rules
        with open(RULES_FILE, 'w') as f:
            json.dump(rules, f, indent=2, ensure_ascii=False)
    
    def load_alerts(self):
        """加载历史告警"""
        if ALERTS_FILE.exists():
            with open(ALERTS_FILE) as f:
                self.alerts = json.load(f)
        else:
            self.alerts = []
    
    def save_alerts(self):
        """保存告警历史"""
        # 只保留最近100条
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        with open(ALERTS_FILE, 'w') as f:
            json.dump(self.alerts, f, indent=2, ensure_ascii=False)
    
    def check_condition(self, condition, value, threshold):
        """检查条件"""
        ops = {
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b
        }
        op_func = ops.get(condition)
        if op_func:
            return op_func(value, threshold)
        return False
    
    def evaluate(self, metrics):
        """评估所有规则，返回触发的告警"""
        triggered = []
        
        for rule in self.rules:
            if not rule.get("enabled", True):
                continue
            
            metric = rule.get("metric")
            condition = rule.get("condition")
            threshold = rule.get("value")
            
            if metric not in metrics:
                continue
            
            value = metrics[metric]
            
            # 检查是否触发
            if self.check_condition(condition, value, threshold):
                # 检查冷却时间
                last_triggered = rule.get("last_triggered")
                cooldown = rule.get("cooldown", 300)
                
                should_trigger = True
                if last_triggered:
                    try:
                        last_time = datetime.fromisoformat(last_triggered)
                        elapsed = (datetime.now() - last_time).total_seconds()
                        if elapsed < cooldown:
                            should_trigger = False
                    except:
                        pass
                
                if should_trigger:
                    alert = {
                        "rule_id": rule["rule_id"],
                        "rule_name": rule["name"],
                        "level": rule["level"],
                        "message": rule["message"].format(**metrics),
                        "timestamp": datetime.now().isoformat(),
                        "context": metrics,
                        "status": "active"
                    }
                    triggered.append(alert)
                    
                    # 更新最后触发时间
                    rule["last_triggered"] = alert["timestamp"]
        
        if triggered:
            self.alerts.extend(triggered)
            self.save_alerts()
            self.save_rules()
        
        return triggered
    
    def get_alerts(self, level=None, limit=20):
        """获取告警历史"""
        alerts = self.alerts
        if level:
            alerts = [a for a in alerts if a.get("level") == level]
        return alerts[-limit:]
    
    def clear_alert(self, alert_id):
        """清除告警"""
        for alert in self.alerts:
            if alert.get("rule_id") == alert_id and alert.get("status") == "active":
                alert["status"] = "resolved"
                alert["resolved_at"] = datetime.now().isoformat()
        self.save_alerts()
        return True
    
    def add_rule(self, rule):
        """添加新规则"""
        self.rules.append(rule)
        self.save_rules()
        return True
    
    def remove_rule(self, rule_id):
        """删除规则"""
        self.rules = [r for r in self.rules if r.get("rule_id") != rule_id]
        self.save_rules()
        return True
    
    def toggle_rule(self, rule_id, enabled):
        """启用/禁用规则"""
        for rule in self.rules:
            if rule.get("rule_id") == rule_id:
                rule["enabled"] = enabled
        self.save_rules()
        return True


# 全局实例
_engine = None

def get_engine():
    """获取告警引擎实例"""
    global _engine
    if _engine is None:
        _engine = AlertEngine()
    return _engine


if __name__ == "__main__":
    import sys
    
    engine = get_engine()
    
    if len(sys.argv) < 2:
        print(json.dumps({
            "rules_count": len(engine.rules),
            "alerts_count": len(engine.alerts),
            "rules": engine.rules[:3]
        }, indent=2, ensure_ascii=False))
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        print(json.dumps(engine.rules, indent=2, ensure_ascii=False))
    
    elif cmd == "alerts":
        level = sys.argv[2] if len(sys.argv) > 2 else None
        print(json.dumps(engine.get_alerts(level), indent=2, ensure_ascii=False))
    
    elif cmd == "add":
        # 添加规则 (简化版)
        rule = json.loads(sys.argv[2])
        engine.add_rule(rule)
        print(json.dumps({"status": "success"}))
    
    elif cmd == "remove":
        rule_id = sys.argv[2]
        engine.remove_rule(rule_id)
        print(json.dumps({"status": "success"}))
    
    elif cmd == "evaluate":
        # 测试评估
        metrics = json.loads(sys.argv[2])
        triggered = engine.evaluate(metrics)
        print(json.dumps({"triggered": triggered}, indent=2, ensure_ascii=False))
    
    elif cmd == "clear":
        alert_id = sys.argv[2]
        engine.clear_alert(alert_id)
        print(json.dumps({"status": "success"}))