#!/usr/bin/env python3
"""
Agent告警存储 - 告警数据持久化
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict


class AlertStore:
    """告警数据存储"""
    
    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or "/root/.openclaw/workspace/ultron/agents/alerts/data"
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.alerts_file = os.path.join(self.data_dir, "alerts.json")
        self.state_file = os.path.join(self.data_dir, "state.json")
        
        self.alerts: List[Dict] = []
        self.state: Dict[str, Any] = {}
        
        self._load()
    
    def _load(self):
        """加载数据"""
        # 加载告警
        if os.path.exists(self.alerts_file):
            try:
                with open(self.alerts_file, 'r') as f:
                    data = json.load(f)
                    self.alerts = data.get("alerts", [])
            except:
                self.alerts = []
        
        # 加载状态
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
            except:
                self.state = {}
    
    def _save(self):
        """保存数据"""
        # 保存告警
        data = {
            "version": "1.0",
            "alerts": self.alerts[-5000:],  # 保留最近5000条
            "updated_at": datetime.now().isoformat()
        }
        
        with open(self.alerts_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        # 保存状态
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def add_alert(self, alert: Dict[str, Any]) -> str:
        """添加告警"""
        alert_id = f"alert_{int(time.time() * 1000)}_{len(self.alerts)}"
        alert["_id"] = alert_id
        alert["_created_at"] = time.time()
        
        self.alerts.append(alert)
        self._save()
        
        # 更新告警状态
        self._update_state(alert)
        
        return alert_id
    
    def _update_state(self, alert: Dict):
        """更新告警状态"""
        rule_id = alert.get("rule_id")
        if not rule_id:
            return
        
        state = alert.get("state", "firing")
        
        if rule_id not in self.state:
            self.state[rule_id] = {}
        
        self.state[rule_id]["last_alert"] = alert.get("timestamp")
        self.state[rule_id]["last_state"] = state
        
        if state == "firing":
            self.state[rule_id]["firing_since"] = alert.get("timestamp")
            self.state[rule_id]["last_resolved"] = None
        elif state == "resolved":
            self.state[rule_id]["firing_since"] = None
            self.state[rule_id]["last_resolved"] = alert.get("timestamp")
        
        # 统计
        self.state[rule_id]["total_count"] = self.state[rule_id].get("total_count", 0) + 1
    
    def get_alert(self, alert_id: str) -> Optional[Dict]:
        """获取单个告警"""
        for alert in reversed(self.alerts):
            if alert.get("_id") == alert_id:
                return alert
        return None
    
    def get_alerts(
        self,
        state: str = None,
        level: str = None,
        rule_id: str = None,
        since: float = None,
        limit: int = 100
    ) -> List[Dict]:
        """查询告警"""
        results = self.alerts
        
        if state:
            results = [a for a in results if a.get("state") == state]
        
        if level:
            results = [a for a in results if a.get("level") == level]
        
        if rule_id:
            results = [a for a in results if a.get("rule_id") == rule_id]
        
        if since:
            results = [a for a in results if a.get("_created_at", 0) > since]
        
        return results[-limit:]
    
    def get_firing_alerts(self) -> List[Dict]:
        """获取当前触发中的告警"""
        return self.get_alerts(state="firing", limit=1000)
    
    def get_alert_stats(self, hours: int = 24) -> Dict[str, Any]:
        """获取告警统计"""
        since = time.time() - (hours * 3600)
        recent_alerts = self.get_alerts(since=since, limit=10000)
        
        total = len(recent_alerts)
        firing = len([a for a in recent_alerts if a.get("state") == "firing"])
        resolved = len([a for a in recent_alerts if a.get("state") == "resolved"])
        
        by_level = defaultdict(int)
        by_rule = defaultdict(int)
        
        for alert in recent_alerts:
            by_level[alert.get("level", "UNKNOWN")] += 1
            by_rule[alert.get("rule_id", "unknown")] += 1
        
        # 按小时统计
        by_hour = defaultdict(int)
        for alert in recent_alerts:
            created = alert.get("_created_at", 0)
            if created:
                hour = datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:00")
                by_hour[hour] += 1
        
        return {
            "period_hours": hours,
            "total": total,
            "firing": firing,
            "resolved": resolved,
            "by_level": dict(by_level),
            "by_rule": dict(by_rule),
            "by_hour": dict(sorted(by_hour.items()))
        }
    
    def get_rule_states(self) -> Dict[str, Dict]:
        """获取所有规则的状态"""
        return self.state
    
    def acknowledge_alert(self, alert_id: str, ack_by: str = "system") -> bool:
        """确认告警"""
        alert = self.get_alert(alert_id)
        if alert:
            alert["_acknowledged"] = True
            alert["_acknowledged_by"] = ack_by
            alert["_acknowledged_at"] = time.time()
            self._save()
            return True
        return False
    
    def clear_resolved(self, before_hours: int = 24) -> int:
        """清理已恢复的旧告警"""
        before = time.time() - (before_hours * 3600)
        
        original_count = len(self.alerts)
        self.alerts = [
            a for a in self.alerts
            if a.get("state") != "resolved" or a.get("_created_at", 0) > before
        ]
        
        cleared = original_count - len(self.alerts)
        self._save()
        return cleared


# 导出
__all__ = ['AlertStore']