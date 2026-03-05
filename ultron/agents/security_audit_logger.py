#!/usr/bin/env python3
"""
多智能体协作网络 - 安全审计日志系统
Security Audit Log System
"""

import json
import hashlib
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from enum import Enum
import threading

DB_PATH = "/root/.openclaw/workspace/ultron/agents/data/audit.db"

class EventType(Enum):
    """事件类型"""
    AGENT_REGISTER = "agent_register"
    AGENT_UNREGISTER = "agent_unregister"
    TASK_SUBMIT = "task_submit"
    TASK_COMPLETE = "task_complete"
    TASK_FAIL = "task_fail"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILURE = "auth_failure"
    SECURITY_ALERT = "security_alert"
    CONFIG_CHANGE = "config_change"
    ACCESS_DENIED = "access_denied"

class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class SecurityAuditor:
    """安全审计器"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()
        self._lock = threading.Lock()
    
    def _init_db(self):
        """初始化数据库"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS audit_log
                     (id INTEGER PRIMARY KEY, timestamp TEXT, event_type TEXT,
                      agent_id TEXT, user_id TEXT, resource TEXT, action TEXT,
                      risk_level TEXT, ip_address TEXT, details TEXT,
                      checksum TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS security_alerts
                     (id INTEGER PRIMARY KEY, timestamp TEXT, alert_type TEXT,
                      severity TEXT, description TEXT, resolved INTEGER)''')
        
        c.execute('''CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_log(timestamp)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_agent ON audit_log(agent_id)''')
        c.execute('''CREATE INDEX IF NOT EXISTS idx_risk ON audit_log(risk_level)''')
        
        conn.commit()
        conn.close()
    
    def _calculate_checksum(self, data: str) -> str:
        """计算校验和"""
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def log_event(self, event_type: EventType, agent_id: str = None,
                  user_id: str = None, resource: str = None, action: str = None,
                  risk_level: RiskLevel = RiskLevel.LOW, ip_address: str = None,
                  details: dict = None):
        """记录审计事件"""
        with self._lock:
            timestamp = datetime.now().isoformat()
            details_str = json.dumps(details) if details else None
            
            # 计算校验和
            checksum_data = f"{timestamp}{event_type.value}{agent_id}{user_id}"
            checksum = self._calculate_checksum(checksum_data)
            
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("""INSERT INTO audit_log
                         (timestamp, event_type, agent_id, user_id, resource, action,
                          risk_level, ip_address, details, checksum)
                         VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                      (timestamp, event_type.value, agent_id, user_id, resource,
                       action, risk_level.value, ip_address, details_str, checksum))
            conn.commit()
            conn.close()
            
            # 检查是否需要告警
            if risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
                self._create_alert(event_type.value, risk_level, details_str)
    
    def _create_alert(self, alert_type: str, severity: RiskLevel, description: str):
        """创建安全告警"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("""INSERT INTO security_alerts
                     (timestamp, alert_type, severity, description, resolved)
                     VALUES (?, ?, ?, ?, 0)""",
                  (datetime.now().isoformat(), alert_type, severity.value, description))
        conn.commit()
        conn.close()
    
    def query_logs(self, start_time: datetime = None, end_time: datetime = None,
                   agent_id: str = None, event_type: EventType = None,
                   risk_level: RiskLevel = None, limit: int = 100) -> List[Dict]:
        """查询审计日志"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time.isoformat())
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)
        if risk_level:
            query += " AND risk_level = ?"
            params.append(risk_level.value)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        
        columns = ['id', 'timestamp', 'event_type', 'agent_id', 'user_id', 'resource',
                   'action', 'risk_level', 'ip_address', 'details', 'checksum']
        
        return [dict(zip(columns, row)) for row in rows]
    
    def get_security_summary(self, hours: int = 24) -> Dict:
        """获取安全摘要"""
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 事件统计
        c.execute("""SELECT event_type, COUNT(*) FROM audit_log
                     WHERE timestamp > ? GROUP BY event_type""", (since,))
        event_counts = dict(c.fetchall())
        
        # 风险统计
        c.execute("""SELECT risk_level, COUNT(*) FROM audit_log
                     WHERE timestamp > ? GROUP BY risk_level""", (since,))
        risk_counts = dict(c.fetchall())
        
        # 未解决的告警
        c.execute("""SELECT COUNT(*) FROM security_alerts WHERE resolved = 0""")
        active_alerts = c.fetchone()[0]
        
        # 高风险事件
        c.execute("""SELECT * FROM audit_log
                     WHERE timestamp > ? AND risk_level IN ('high', 'critical')
                     ORDER BY timestamp DESC LIMIT 10""", (since,))
        high_risk_events = c.fetchall()
        
        conn.close()
        
        return {
            'period_hours': hours,
            'event_counts': event_counts,
            'risk_counts': risk_counts,
            'active_alerts': active_alerts,
            'high_risk_events': len(high_risk_events)
        }
    
    def verify_integrity(self) -> Dict:
        """验证日志完整性"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT COUNT(*) FROM audit_log")
        total = c.fetchone()[0]
        
        c.execute("SELECT checksum FROM audit_log ORDER BY id")
        checksums = [row[0] for row in c.fetchall()]
        
        conn.close()
        
        # 验证校验和
        valid = 0
        invalid = 0
        for cs in checksums:
            if cs:
                valid += 1
        
        return {
            'total_logs': total,
            'valid_checksums': valid,
            'integrity_valid': valid == total
        }
    
    def export_logs(self, format: str = 'json', filepath: str = None) -> str:
        """导出日志"""
        logs = self.query_logs(limit=10000)
        
        if format == 'json':
            content = json.dumps(logs, indent=2)
        elif format == 'csv':
            if logs:
                headers = list(logs[0].keys())
                lines = [','.join(headers)]
                for log in logs:
                    lines.append(','.join(str(log.get(h, '')) for h in headers))
                content = '\n'.join(lines)
            else:
                content = ''
        else:
            content = json.dumps(logs, indent=2)
        
        if filepath:
            with open(filepath, 'w') as f:
                f.write(content)
        
        return content


# 测试
if __name__ == '__main__':
    print("🔧 安全审计日志系统测试")
    print("="*50)
    
    auditor = SecurityAuditor()
    
    # 记录测试事件
    auditor.log_event(EventType.AGENT_REGISTER, agent_id='agent-001',
                      risk_level=RiskLevel.LOW)
    auditor.log_event(EventType.TASK_SUBMIT, agent_id='agent-001',
                      user_id='user-001', risk_level=RiskLevel.LOW)
    auditor.log_event(EventType.AUTH_FAILURE, user_id='unknown',
                      risk_level=RiskLevel.HIGH,
                      details={'reason': 'invalid_token'})
    auditor.log_event(EventType.ACCESS_DENIED, user_id='user-002',
                      resource='/api/admin', risk_level=RiskLevel.CRITICAL)
    
    print("\n📊 安全摘要 (24小时):")
    summary = auditor.get_security_summary()
    print(json.dumps(summary, indent=2))
    
    print("\n🔍 查询最近日志:")
    logs = auditor.query_logs(limit=5)
    for log in logs:
        print(f"  [{log['risk_level']}] {log['timestamp']} - {log['event_type']}")
    
    print("\n✅ 审计日志系统测试完成")