#!/usr/bin/env python3
"""告警自动升级与多人协作处理模块"""
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import importlib.util

BASE_DIR = Path(__file__).parent
STATE_FILE = BASE_DIR / "data" / "alert_escalation_state.json"

# 动态导入告警通知模块
notifier_spec = importlib.util.spec_from_file_location(
    "ops_alert_notifier", 
    BASE_DIR / "ops-alert-notifier.py"
)
notifier_module = importlib.util.module_from_spec(notifier_spec)
notifier_spec.loader.exec_module(notifier_module)
AlertNotifier = notifier_module.AlertNotifier
AlertLevel = notifier_module.AlertLevel


class AlertEscalation:
    """告警自动升级引擎"""
    
    # 升级时间阈值（秒）
    ESCALATION_TIMES = {
        "WARNING": 600,    # 10分钟未响应则升级
        "ERROR": 300,      # 5分钟未响应则升级  
        "CRITICAL": 60,    # 1分钟未响应则升级
    }
    
    # 升级级别映射
    ESCALATION_LEVELS = {
        "WARNING": "ERROR",
        "ERROR": "CRITICAL", 
        "CRITICAL": "EMERGENCY"
    }
    
    def __init__(self):
        self.notifier = AlertNotifier()
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """加载状态"""
        if STATE_FILE.exists():
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return {
            "active_alerts": {},      # 当前活跃告警
            "escalated_alerts": {},   # 已升级告警
            "acknowledged": {},       # 已确认告警
            "assignments": {},        # 告警分配记录
            "team_members": {         # 团队成员配置
                "primary": ["西西弗斯"],
                "secondary": [],
                "emergency": []
            }
        }
    
    def _save_state(self):
        """保存状态"""
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)
    
    def register_alert(self, alert: Dict) -> str:
        """注册新告警"""
        alert_id = f"alert_{int(time.time() * 1000)}"
        
        self.state["active_alerts"][alert_id] = {
            "id": alert_id,
            "rule": alert.get("rule", "unknown"),
            "level": alert.get("level", "WARNING"),
            "message": alert.get("message", ""),
            "timestamp": alert.get("timestamp", datetime.now().isoformat()),
            "last_escalation": None,
            "escalation_count": 0,
            "assigned_to": None,
            "status": "active"  # active, acknowledged, resolved
        }
        
        # 自动分配告警
        self._auto_assign(alert_id)
        self._save_state()
        
        print(f"[Escalation] 注册新告警: {alert_id} - {alert.get('level')} - {alert.get('message', '')[:50]}")
        return alert_id
    
    def _auto_assign(self, alert_id: str):
        """自动分配告警给团队成员"""
        alert = self.state["active_alerts"].get(alert_id)
        if not alert:
            return
        
        level = alert["level"]
        
        # 根据级别分配给不同的人
        if level == "CRITICAL" or level == "EMERGENCY":
            recipients = self.state["team_members"].get("emergency", 
                        self.state["team_members"].get("primary", []))
        elif level == "ERROR":
            recipients = self.state["team_members"].get("secondary",
                        self.state["team_members"].get("primary", []))
        else:
            recipients = self.state["team_members"].get("primary", [])
        
        if recipients:
            assigned = recipients[0]  # 分配给第一人
            self.state["assignments"][alert_id] = {
                "assigned_to": assigned,
                "assigned_at": datetime.now().isoformat(),
                "notified": False
            }
            alert["assigned_to"] = assigned
    
    def check_escalation(self) -> List[Dict]:
        """检查需要升级的告警"""
        now = datetime.now()
        escalations = []
        
        for alert_id, alert in list(self.state["active_alerts"].items()):
            # 跳过已确认和已解决的告警
            if alert["status"] != "active":
                continue
            
            # 检查是否已分配但未确认
            if alert_id in self.state["assignments"]:
                assignment = self.state["assignments"][alert_id]
                if assignment.get("notified", False):
                    continue  # 已通知
            
            # 计算等待时间
            alert_time = datetime.fromisoformat(alert["timestamp"])
            wait_seconds = (now - alert_time).total_seconds()
            
            level = alert["level"]
            threshold = self.ESCALATION_TIMES.get(level, 600)
            
            if wait_seconds >= threshold:
                # 需要升级
                new_level = self.ESCALATION_LEVELS.get(level, level)
                escalation = {
                    "alert_id": alert_id,
                    "original_level": level,
                    "new_level": new_level,
                    "wait_time": int(wait_seconds),
                    "rule": alert["rule"],
                    "message": alert["message"]
                }
                escalations.append(escalation)
                
                # 执行升级
                self._do_escalation(alert_id, new_level, wait_seconds)
        
        return escalations
    
    def _do_escalation(self, alert_id: str, new_level: str, wait_time: int):
        """执行告警升级"""
        alert = self.state["active_alerts"].get(alert_id)
        if not alert:
            return
        
        old_level = alert["level"]
        alert["level"] = new_level
        alert["escalation_count"] = alert.get("escalation_count", 0) + 1
        alert["last_escalation"] = datetime.now().isoformat()
        
        # 记录升级
        self.state["escalated_alerts"][alert_id] = {
            "original_level": old_level,
            "new_level": new_level,
            "escalated_at": datetime.now().isoformat(),
            "wait_time": wait_time
        }
        
        # 发送升级通知
        escalation_alert = {
            "rule": f"升级:{alert['rule']}",
            "level": new_level,
            "message": f"告警升级: {old_level} → {new_level} (等待{wait_time}秒未响应)",
            "timestamp": datetime.now().isoformat(),
            "original_alert_id": alert_id
        }
        
        self.notifier.notify([escalation_alert])
        
        # 重新分配给更高优先级人员
        self._auto_assign(alert_id)
        
        print(f"[Escalation] 告警 {alert_id} 已升级: {old_level} → {new_level}")
        self._save_state()
    
    def acknowledge(self, alert_id: str, user: str) -> bool:
        """确认告警"""
        if alert_id in self.state["active_alerts"]:
            alert = self.state["active_alerts"][alert_id]
            alert["status"] = "acknowledged"
            
            self.state["acknowledged"][alert_id] = {
                "user": user,
                "acknowledged_at": datetime.now().isoformat()
            }
            
            # 更新分配状态
            if alert_id in self.state["assignments"]:
                self.state["assignments"][alert_id]["notified"] = True
            
            self._save_state()
            print(f"[Escalation] 告警 {alert_id} 已由 {user} 确认")
            return True
        return False
    
    def resolve(self, alert_id: str, user: str, resolution: str = "") -> bool:
        """解决告警"""
        if alert_id in self.state["active_alerts"]:
            alert = self.state["active_alerts"][alert_id]
            alert["status"] = "resolved"
            
            # 记录解决信息
            self.state["active_alerts"][alert_id]["resolved_by"] = user
            self.state["active_alerts"][alert_id]["resolved_at"] = datetime.now().isoformat()
            self.state["active_alerts"][alert_id]["resolution"] = resolution
            
            self._save_state()
            print(f"[Escalation] 告警 {alert_id} 已解决: {resolution}")
            return True
        return False
    
    def get_status(self) -> Dict:
        """获取状态摘要"""
        active = [a for a in self.state["active_alerts"].values() if a["status"] == "active"]
        escalated = len(self.state["escalated_alerts"])
        acknowledged = len(self.state["acknowledged"])
        
        # 按级别统计
        level_counts = {}
        for alert in active:
            level = alert["level"]
            level_counts[level] = level_counts.get(level, 0) + 1
        
        return {
            "active_alerts": len(active),
            "escalated": escalated,
            "acknowledged": acknowledged,
            "by_level": level_counts,
            "assignments": len(self.state["assignments"]),
            "timestamp": datetime.now().isoformat()
        }
    
    def get_active_alerts(self) -> List[Dict]:
        """获取所有活跃告警"""
        return [
            {
                "id": alert_id,
                **alert,
                "assigned_to": self.state["assignments"].get(alert_id, {}).get("assigned_to")
            }
            for alert_id, alert in self.state["active_alerts"].items()
            if alert["status"] == "active"
        ]


class TeamCollaboration:
    """团队协作处理"""
    
    def __init__(self):
        self.escalation = AlertEscalation()
    
    def process_new_alert(self, alert: Dict) -> str:
        """处理新告警"""
        return self.escalation.register_alert(alert)
    
    def get_my_alerts(self, user: str) -> List[Dict]:
        """获取分配给某用户的告警"""
        all_alerts = self.escalation.get_active_alerts()
        return [
            alert for alert in all_alerts 
            if alert.get("assigned_to") == user
        ]
    
    def run(self) -> Dict:
        """运行协作处理检查"""
        # 检查需要升级的告警
        escalations = self.escalation.check_escalation()
        
        # 返回状态
        status = self.escalation.get_status()
        status["new_escalations"] = len(escalations)
        
        return status


if __name__ == "__main__":
    collab = TeamCollaboration()
    
    # 测试：注册一个告警
    test_alert = {
        "rule": "test_high_cpu",
        "level": "WARNING",
        "message": "CPU使用率过高",
        "timestamp": datetime.now().isoformat()
    }
    
    alert_id = collab.process_new_alert(test_alert)
    print(f"注册告警ID: {alert_id}")
    
    # 检查状态
    status = collab.run()
    print(json.dumps(status, indent=2, ensure_ascii=False))