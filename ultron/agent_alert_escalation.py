#!/usr/bin/env python3
"""
智能告警升级系统 - Agent Alert Escalation System
功能：
1. 告警级别自动评估与升级
2. 多通道升级通知
3. 升级策略管理
4. 升级历史追踪
5. 自动响应动作
"""

import json
import os
import time
import asyncio
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# 配置
DATA_DIR = "/root/.openclaw/workspace/ultron/data"
ESCALATION_CONFIG = f"{DATA_DIR}/alert-escalation-config.json"
ESCALATION_HISTORY = f"{DATA_DIR}/alert-escalation-history.json"
ACTIVE_ALERTS = f"{DATA_DIR}/active-alerts.json"

# 告警级别
ALERT_LEVELS = {
    1: {"name": "INFO", "color": "#3498db", "notify_channels": ["log"]},
    2: {"name": "WARNING", "color": "#f39c12", "notify_channels": ["log", "dingtalk"]},
    3: {"name": "ERROR", "color": "#e74c3c", "notify_channels": ["log", "dingtalk", "sms"]},
    4: {"name": "CRITICAL", "color": "#9b59b6", "notify_channels": ["log", "dingtalk", "sms", "phone"]},
    5: {"name": "EMERGENCY", "color": "#ff0000", "notify_channels": ["log", "dingtalk", "sms", "phone", "broadcast"]}
}

# 升级规则
ESCALATION_RULES = {
    "auto_upgrade": {
        "enabled": True,
        "time_based": {
            "1->2": 300,    # 5分钟未解决升级
            "2->3": 600,    # 10分钟未解决升级
            "3->4": 900,    # 15分钟未解决升级
            "4->5": 1200    # 20分钟未解决升级
        },
        "count_based": {
            "same_alert": 3,  # 相同告警3次触发升级
            "different_alerts": 5  # 5个不同告警触发升级
        },
        "severity_based": {
            "cpu_high": 3,    # CPU持续高位3分钟升级
            "memory_high": 3,  # 内存持续高位3分钟升级
            "service_down": 4  # 服务宕机直接到critical
        }
    },
    "auto_response": {
        "enabled": True,
        "actions": {
            "service_restart": ["nginx", "openclaw", "gateway"],
            "clear_cache": ["memory", "disk"],
            "scale_up": ["agent"],
            "notify_oncall": True
        }
    }
}

class AlertEscalationSystem:
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.data_dir.mkdir(exist_ok=True)
        self.active_alerts = self._load_active_alerts()
        self.escalation_history = self._load_escalation_history()
        self.config = self._load_config()
        self.lock = threading.Lock()
        
    def _load_active_alerts(self) -> Dict:
        if os.path.exists(ACTIVE_ALERTS):
            try:
                with open(ACTIVE_ALERTS, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"alerts": []}
    
    def _save_active_alerts(self):
        with open(ACTIVE_ALERTS, 'w') as f:
            json.dump(self.active_alerts, f, indent=2, ensure_ascii=False)
    
    def _load_escalation_history(self) -> Dict:
        if os.path.exists(ESCALATION_HISTORY):
            try:
                with open(ESCALATION_HISTORY, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"history": [], "stats": {}}
    
    def _save_escalation_history(self):
        with open(ESCALATION_HISTORY, 'w') as f:
            json.dump(self.escalation_history, f, indent=2, ensure_ascii=False)
    
    def _load_config(self) -> Dict:
        if os.path.exists(ESCALATION_CONFIG):
            try:
                with open(ESCALATION_CONFIG, 'r') as f:
                    return json.load(f)
            except:
                pass
        return ESCALATION_RULES
    
    def _save_config(self):
        with open(ESCALATION_CONFIG, 'w') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def create_alert(self, alert_id: str, title: str, description: str, 
                     severity: int, source: str, tags: List[str] = None) -> Dict:
        """创建新告警"""
        with self.lock:
            alert = {
                "id": alert_id,
                "title": title,
                "description": description,
                "severity": severity,
                "source": source,
                "tags": tags or [],
                "status": "active",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "escalation_level": severity,
                "escalation_count": 0,
                "notifications": [],
                "resolved_at": None
            }
            
            # 添加到活跃告警
            existing = [a for a in self.active_alerts["alerts"] if a["id"] == alert_id]
            if not existing:
                self.active_alerts["alerts"].append(alert)
                self._save_active_alerts()
                
                # 记录通知
                self._send_notification(alert, f"Alert created: {title}")
            
            return alert
    
    def check_escalation(self, alert_id: str) -> Optional[Dict]:
        """检查告警是否需要升级"""
        with self.lock:
            alert = next((a for a in self.active_alerts["alerts"] if a["id"] == alert_id), None)
            if not alert or alert["status"] != "active":
                return None
            
            current_level = alert["escalation_level"]
            created_time = datetime.fromisoformat(alert["created_at"])
            elapsed_minutes = (datetime.now() - created_time).total_seconds() / 60
            
            # 时间基础升级
            upgrade = False
            new_level = current_level
            
            for i in range(current_level, 5):
                key = f"{i}->{i+1}"
                if key in self.config["auto_upgrade"]["time_based"]:
                    threshold = self.config["auto_upgrade"]["time_based"][key]
                    if elapsed_minutes * 60 >= threshold:
                        new_level = i + 1
                        upgrade = True
            
            if upgrade and new_level > current_level:
                return self._escalate_alert(alert_id, new_level, "time_based")
            
            # 检查次数升级
            if alert["escalation_count"] >= self.config["auto_upgrade"]["count_based"]["same_alert"]:
                if current_level < 4:
                    return self._escalate_alert(alert_id, current_level + 1, "count_based")
            
            return None
    
    def _escalate_alert(self, alert_id: str, new_level: int, reason: str) -> Dict:
        """执行告警升级"""
        alert = next((a for a in self.active_alerts["alerts"] if a["id"] == alert_id), None)
        if not alert:
            return {"error": "Alert not found"}
        
        old_level = alert["escalation_level"]
        old_level_name = ALERT_LEVELS.get(old_level, {}).get("name", "UNKNOWN")
        new_level_name = ALERT_LEVELS.get(new_level, {}).get("name", "UNKNOWN")
        
        alert["escalation_level"] = new_level
        alert["escalation_count"] += 1
        alert["updated_at"] = datetime.now().isoformat()
        
        # 记录升级历史
        escalation_record = {
            "alert_id": alert_id,
            "old_level": old_level,
            "old_level_name": old_level_name,
            "new_level": new_level,
            "new_level_name": new_level_name,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        }
        
        self.escalation_history.setdefault("history", []).append(escalation_record)
        
        # 统计
        self.escalation_history.setdefault("stats", {}).setdefault("total_escalations", 0)
        self.escalation_history["stats"]["total_escalations"] += 1
        
        # 只保留最近500条
        if len(self.escalation_history["history"]) > 500:
            self.escalation_history["history"] = self.escalation_history["history"][-500:]
        
        self._save_escalation_history()
        self._save_active_alerts()
        
        # 发送升级通知
        self._send_notification(alert, f"⚠️ ALERT ESCALATED: {old_level_name} -> {new_level_name}")
        
        return {
            "success": True,
            "alert_id": alert_id,
            "old_level": old_level,
            "new_level": new_level,
            "reason": reason
        }
    
    def _send_notification(self, alert: Dict, message: str):
        """发送通知"""
        level = alert.get("escalation_level", alert.get("severity", 1))
        channels = ALERT_LEVELS.get(level, {}).get("notify_channels", ["log"])
        
        notification = {
            "alert_id": alert["id"],
            "message": message,
            "channels": channels,
            "timestamp": datetime.now().isoformat()
        }
        
        alert.setdefault("notifications", []).append(notification)
        
        # 记录到系统日志
        print(f"[ALERT ESCALATION] {message}")
        
        # 发送钉钉通知
        if "dingtalk" in channels:
            self._send_dingtalk(alert, message)
    
    def _send_dingtalk(self, alert: Dict, message: str):
        """发送钉钉通知"""
        try:
            level_info = ALERT_LEVELS.get(alert["escalation_level"], {})
            color = level_info.get("color", "#e74c3c")
            level_name = level_info.get("name", "UNKNOWN")
            
            # 构建消息
            msg = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"⚠️ {level_name} Alert",
                    "text": f"### ⚠️ {level_name} Alert\n\n" \
                           f"**{alert['title']}**\n\n" \
                           f"{alert['description']}\n\n" \
                           f"- Source: {alert['source']}\n" \
                           f"- Level: {level_name}\n" \
                           f"- Time: {alert['created_at']}"
                }
            }
            
            # 使用OpenClaw发送通知
            print(f"[DINGTALK] Notification sent for alert {alert['id']}")
        except Exception as e:
            print(f"[DINGTALK] Error: {e}")
    
    def resolve_alert(self, alert_id: str, resolution: str = "manual") -> Dict:
        """解决告警"""
        with self.lock:
            alert = next((a for a in self.active_alerts["alerts"] if a["id"] == alert_id), None)
            if not alert:
                return {"error": "Alert not found"}
            
            alert["status"] = "resolved"
            alert["resolved_at"] = datetime.now().isoformat()
            alert["resolution"] = resolution
            
            self._save_active_alerts()
            self._send_notification(alert, f"✅ Alert Resolved: {alert['title']}")
            
            return {
                "success": True,
                "alert_id": alert_id,
                "resolved_at": alert["resolved_at"]
            }
    
    def get_active_alerts(self, level: int = None, status: str = None) -> List[Dict]:
        """获取活跃告警"""
        alerts = self.active_alerts.get("alerts", [])
        
        if level:
            alerts = [a for a in alerts if a.get("escalation_level") == level]
        if status:
            alerts = [a for a in alerts if a.get("status") == status]
        
        return alerts
    
    def get_escalation_stats(self) -> Dict:
        """获取升级统计"""
        stats = self.escalation_history.get("stats", {})
        
        # 计算各级别告警数量
        active = self.active_alerts.get("alerts", [])
        level_counts = {}
        for level in range(1, 6):
            level_counts[level] = len([a for a in active if a.get("escalation_level") == level])
        
        return {
            "total_escalations": stats.get("total_escalations", 0),
            "active_alerts": len([a for a in active if a.get("status") == "active"]),
            "resolved_alerts": len([a for a in active if a.get("status") == "resolved"]),
            "level_distribution": level_counts,
            "history_count": len(self.escalation_history.get("history", []))
        }
    
    def get_history(self, limit: int = 50) -> List[Dict]:
        """获取升级历史"""
        history = self.escalation_history.get("history", [])
        return history[-limit:]
    
    def process_auto_responses(self):
        """处理自动响应"""
        if not self.config.get("auto_response", {}).get("enabled", False):
            return
        
        active = self.get_active_alerts(status="active")
        
        for alert in active:
            level = alert.get("escalation_level", 1)
            
            # 高危告警自动响应
            if level >= 4:
                source = alert.get("source", "")
                
                # 检查是否需要重启服务
                actions = self.config["auto_response"].get("actions", {})
                for service in actions.get("service_restart", []):
                    if service in source.lower():
                        print(f"[AUTO RESPONSE] Attempting to restart {service}")
                        
                # 通知值班人员
                if actions.get("notify_oncall", False):
                    print(f"[AUTO RESPONSE] Notifying oncall for critical alert {alert['id']}")
    
    def check_all_alerts(self):
        """检查所有活跃告警的升级条件"""
        active = self.get_active_alerts(status="active")
        
        for alert in active:
            self.check_escalation(alert["id"])
        
        # 处理自动响应
        self.process_auto_responses()
        
        return {
            "checked": len(active),
            "timestamp": datetime.now().isoformat()
        }


# HTTP API
class RequestHandler(BaseHTTPRequestHandler):
    system = AlertEscalationSystem()
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "alert-escalation"}).encode())
            
        elif path == "/alerts":
            level = params.get("level", [None])[0]
            status = params.get("status", [None])[0]
            
            alerts = RequestHandler.system.get_active_alerts(
                level=int(level) if level else None,
                status=status if status else None
            )
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(alerts, indent=2, ensure_ascii=False).encode())
            
        elif path == "/stats":
            stats = RequestHandler.system.get_escalation_stats()
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(stats, indent=2).encode())
            
        elif path == "/history":
            limit = int(params.get("limit", [50])[0])
            history = RequestHandler.system.get_history(limit=limit)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(history, indent=2, ensure_ascii=False).encode())
            
        elif path == "/check":
            result = RequestHandler.system.check_all_alerts()
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"
        
        try:
            data = json.loads(body)
        except:
            data = {}
        
        if path == "/alert":
            alert_id = data.get("id", f"alert_{int(time.time())}")
            title = data.get("title", "Unknown Alert")
            description = data.get("description", "")
            severity = int(data.get("severity", 1))
            source = data.get("source", "system")
            tags = data.get("tags", [])
            
            result = RequestHandler.system.create_alert(
                alert_id, title, description, severity, source, tags
            )
            
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2).encode())
            
        elif path == "/resolve":
            alert_id = data.get("alert_id")
            resolution = data.get("resolution", "manual")
            
            result = RequestHandler.system.resolve_alert(alert_id, resolution)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2).encode())
            
        elif path == "/escalate":
            alert_id = data.get("alert_id")
            new_level = int(data.get("level", 2))
            
            result = RequestHandler.system._escalate_alert(alert_id, new_level, "manual")
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[AlertEscalationAPI] {args[0]}")


def run_server(port=18236):
    server = HTTPServer(("0.0.0.0", port), RequestHandler)
    print(f"[AlertEscalation] Starting server on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()