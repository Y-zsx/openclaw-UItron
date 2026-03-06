#!/usr/bin/env python3
"""
奥创智能告警升级系统 V2
支持多渠道通知 + 告警升级 + 统计分析
"""
import asyncio
import aiohttp
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import sqlite3
import os

class IntelligentAlertSystem:
    def __init__(self, db_path="/root/.openclaw/workspace/ultron/data/alert_upgrade.db"):
        self.db_path = db_path
        self.init_db()
        self.notification_channels = {
            "dingtalk": {"enabled": True, "webhook": None, "priority": 1},
            "webhook": {"enabled": False, "url": None, "priority": 2},
            "console": {"enabled": True, "priority": 99}
        }
        
    def init_db(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_type TEXT,
            severity TEXT,
            message TEXT,
            source TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            acknowledged BOOLEAN DEFAULT 0,
            escalated BOOLEAN DEFAULT 0,
            notification_sent BOOLEAN DEFAULT 0
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS notification_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER,
            channel TEXT,
            status TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(alert_id) REFERENCES alerts(id)
        )''')
        conn.commit()
        conn.close()
    
    async def send_notification(self, channel: str, message: str, alert_id: int = None) -> bool:
        """发送通知到指定渠道"""
        if channel == "console":
            print(f"[ALERT] {message}")
            return True
        
        if channel == "dingtalk":
            webhook = self.notification_channels["dingtalk"]["webhook"]
            if not webhook or "YOUR_TOKEN" in webhook:
                print(f"[WARN] DingTalk webhook未配置")
                return False
            try:
                async with aiohttp.ClientSession() as session:
                    payload = {
                        "msgtype": "text",
                        "text": {"content": f"🤖 奥创告警\n{message}"}
                    }
                    async with session.post(webhook, json=payload) as resp:
                        return resp.status == 200
            except Exception as e:
                print(f"[ERROR] DingTalk发送失败: {e}")
                return False
        
        return False
    
    async def process_alert(self, alert_type: str, severity: str, message: str, source: str = "system"):
        """处理新告警"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT INTO alerts (alert_type, severity, message, source) VALUES (?, ?, ?, ?)",
                  (alert_type, severity, message, source))
        alert_id = c.lastrowid
        conn.commit()
        
        # 根据严重级别决定通知渠道
        if severity == "critical":
            channels = ["dingtalk", "console"]
        elif severity == "warning":
            channels = ["console"]
        else:
            channels = ["console"]
        
        # 发送通知
        for channel in channels:
            success = await self.send_notification(channel, message, alert_id)
            c.execute("INSERT INTO notification_log (alert_id, channel, status) VALUES (?, ?, ?)",
                      (alert_id, channel, "sent" if success else "failed"))
        
        conn.commit()
        conn.close()
        return alert_id
    
    async def check_and_alert(self, service_name: str, is_healthy: bool, response_time: float = None):
        """检查服务状态并生成告警"""
        if not is_healthy:
            await self.process_alert(
                alert_type="service_down",
                severity="critical",
                message=f"服务异常: {service_name}",
                source="health_monitor"
            )
        elif response_time and response_time > 5000:  # >5s
            await self.process_alert(
                alert_type="slow_response",
                severity="warning",
                message=f"响应慢: {service_name} 耗时 {response_time}ms",
                source="health_monitor"
            )
    
    def get_stats(self) -> Dict:
        """获取告警统计"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT severity, COUNT(*) FROM alerts GROUP BY severity")
        by_severity = dict(c.fetchall())
        
        c.execute("SELECT COUNT(*) FROM alerts WHERE acknowledged = 0")
        unacknowledged = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM alerts WHERE escalated = 1")
        escalated = c.fetchone()[0]
        
        conn.close()
        
        return {
            "total": sum(by_severity.values()),
            "by_severity": by_severity,
            "unacknowledged": unacknowledged,
            "escalated": escalated
        }

async def main():
    system = IntelligentAlertSystem()
    
    # 测试告警
    await system.process_alert(
        alert_type="test",
        severity="info",
        message="智能告警升级系统已启动",
        source="system_init"
    )
    
    stats = system.get_stats()
    print(f"智能告警系统已启动 - 统计: {stats}")

if __name__ == "__main__":
    asyncio.run(main())