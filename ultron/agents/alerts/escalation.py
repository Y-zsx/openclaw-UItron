#!/usr/bin/env python3
"""
Agent告警升级管理器 - 自动升级未处理告警
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field


logger = logging.getLogger(__name__)


@dataclass
class EscalationPolicy:
    """升级策略"""
    name: str
    level: str  # CRITICAL, WARNING
    wait_minutes: int  # 等待多少分钟后升级
    escalate_to: str  # 升级给谁
    action: str = "notify"  # notify, email, sms
    repeat_every: int = 0  # 0 = 只升级一次, >0 = 每隔多少分钟重复


@dataclass 
class EscalationRecord:
    """升级记录"""
    alert_id: str
    rule_id: str
    level: str
    policy_name: str
    escalated_at: float
    escalated_to: str
    action: str
    notified: bool = False


class AlertEscalationManager:
    """告警升级管理器"""
    
    def __init__(self, store=None):
        self.store = store
        self.policies: List[EscalationPolicy] = []
        self.escalation_history: List[EscalationRecord] = []
        self.pending_escalations: Dict[str, Dict] = {}  # alert_id -> state
        
        self._init_default_policies()
    
    def _init_default_policies(self):
        """初始化默认升级策略"""
        self.policies = [
            # CRITICAL告警：5分钟未处理则升级
            EscalationPolicy(
                name="critical_5min",
                level="CRITICAL",
                wait_minutes=5,
                escalate_to="admin",
                action="notify",
                repeat_every=15  # 每15分钟提醒一次
            ),
            # WARNING告警：30分钟未处理则升级
            EscalationPolicy(
                name="warning_30min",
                level="WARNING",
                wait_minutes=30,
                escalate_to="admin", 
                action="notify",
                repeat_every=60  # 每小时提醒一次
            ),
        ]
    
    def add_policy(self, policy: EscalationPolicy):
        """添加升级策略"""
        self.policies.append(policy)
    
    def remove_policy(self, name: str) -> bool:
        """移除升级策略"""
        self.policies = [p for p in self.policies if p.name != name]
        return True
    
    def check_escalation(self, alert: Dict[str, Any]) -> Optional[EscalationRecord]:
        """检查是否需要升级"""
        if not self.store:
            return None
        
        alert_id = alert.get("_id")
        rule_id = alert.get("rule_id")
        level = alert.get("level")
        state = alert.get("state")
        
        # 只处理触发中的告警
        if state != "firing":
            return None
        
        # 获取告警创建时间
        created_at = alert.get("_created_at", time.time())
        elapsed_minutes = (time.time() - created_at) / 60
        
        # 获取已确认的告警不升级
        if alert.get("_acknowledged"):
            return None
        
        # 检查升级策略
        for policy in self.policies:
            if policy.level != level:
                continue
            
            if elapsed_minutes < policy.wait_minutes:
                continue
            
            # 检查是否已经升级过
            key = f"{alert_id}_{policy.name}"
            if key in self.pending_escalations:
                last_escalation = self.pending_escalations[key]
                
                # 检查是否需要重复升级
                if policy.repeat_every > 0:
                    last_time = last_escalation.get("last_time", 0)
                    if (time.time() - last_time) < policy.repeat_every * 60:
                        continue
                else:
                    # 不需要重复，已升级过
                    continue
            
            # 创建升级记录
            record = EscalationRecord(
                alert_id=alert_id,
                rule_id=rule_id,
                level=level,
                policy_name=policy.name,
                escalated_at=time.time(),
                escalated_to=policy.escalate_to,
                action=policy.action
            )
            
            # 记录升级状态
            self.pending_escalations[key] = {
                "last_time": time.time(),
                "record": record
            }
            
            self.escalation_history.append(record)
            
            logger.warning(f"⚠️ 告警升级: {alert_id} -> {policy.escalate_to}")
            
            return record
        
        return None
    
    def process_escalations(self, alerts: List[Dict], notifier=None) -> List[Dict]:
        """处理所有告警的升级"""
        results = []
        
        for alert in alerts:
            record = self.check_escalation(alert)
            
            if record and notifier:
                # 构建升级通知
                elapsed = (time.time() - alert.get("_created_at", time.time())) / 60
                escalation_alert = {
                    "rule_id": f"escalation_{record.policy_name}",
                    "rule_name": f"告警升级: {record.policy_name}",
                    "level": "CRITICAL",
                    "message": f"⚠️ 告警升级: {alert.get('message', '告警未处理')}",
                    "metric": "system.escalation",
                    "value": elapsed,
                    "threshold": 0,
                    "condition": "gt",
                    "state": "firing",
                    "timestamp": datetime.now().isoformat(),
                    "tags": {
                        "original_alert_id": record.alert_id,
                        "escalated_to": record.escalated_to,
                        "policy": record.policy_name
                    },
                    "_is_escalation": True
                }
                
                # 发送升级通知
                notifier.send(escalation_alert)
                results.append(escalation_alert)
        
        return results
    
    def get_escalation_stats(self) -> Dict[str, Any]:
        """获取升级统计"""
        total = len(self.escalation_history)
        
        by_level = {}
        by_policy = {}
        
        for record in self.escalation_history:
            level = record.level
            policy = record.policy_name
            
            by_level[level] = by_level.get(level, 0) + 1
            by_policy[policy] = by_policy.get(policy, 0) + 1
        
        return {
            "total_escalations": total,
            "pending_count": len(self.pending_escalations),
            "by_level": by_level,
            "by_policy": by_policy,
            "policies_count": len(self.policies)
        }
    
    def acknowledge_escalation(self, alert_id: str) -> bool:
        """确认升级（标记该告警已处理）"""
        keys_to_remove = [k for k in self.pending_escalations.keys() if k.startswith(alert_id)]
        
        for key in keys_to_remove:
            del self.pending_escalations[key]
        
        return len(keys_to_remove) > 0
    
    def clear_history(self, before_hours: int = 168):
        """清理历史记录"""
        before = time.time() - (before_hours * 3600)
        self.escalation_history = [
            r for r in self.escalation_history
            if r.escalated_at > before
        ]


# 导出
__all__ = ['AlertEscalationManager', 'EscalationPolicy', 'EscalationRecord']