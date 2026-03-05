#!/usr/bin/env python3
"""
Agent审计日志系统
记录所有Agent操作、认证、任务执行、通信等
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any
import hashlib

class AuditLogger:
    """审计日志记录器"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = "/root/.openclaw/workspace/ultron/collab-audit/audit.db"
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                agent_id TEXT,
                action TEXT NOT NULL,
                resource TEXT,
                status TEXT NOT NULL,
                details TEXT,
                ip_address TEXT,
                user_agent TEXT,
                checksum TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp ON audit_logs(timestamp)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_event_type ON audit_logs(event_type)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_agent_id ON audit_logs(agent_id)
        ''')
        
        conn.commit()
        conn.close()
    
    def _generate_checksum(self, data: str) -> str:
        """生成校验和"""
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def log(self, event_type: str, action: str, status: str,
            agent_id: str = None, resource: str = None, 
            details: Dict = None, ip_address: str = None,
            user_agent: str = None) -> int:
        """记录审计日志"""
        timestamp = datetime.now().isoformat()
        details_json = json.dumps(details) if details else None
        
        # 生成校验和
        checksum_data = f"{timestamp}:{event_type}:{action}:{status}"
        checksum = self._generate_checksum(checksum_data)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO audit_logs 
            (timestamp, event_type, agent_id, action, resource, status, 
             details, ip_address, user_agent, checksum)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, event_type, agent_id, action, resource, status,
              details_json, ip_address, user_agent, checksum))
        
        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return log_id
    
    # 便捷方法
    def log_auth(self, agent_id: str, action: str, status: str, details: Dict = None):
        """记录认证事件"""
        return self.log("AUTH", action, status, agent_id=agent_id, details=details)
    
    def log_task(self, agent_id: str, task_id: str, action: str, status: str, details: Dict = None):
        """记录任务事件"""
        return self.log("TASK", action, status, agent_id=agent_id, resource=task_id, details=details)
    
    def log_communication(self, from_agent: str, to_agent: str, action: str, status: str, details: Dict = None):
        """记录通信事件"""
        return self.log("COMMUNICATION", action, status, agent_id=from_agent, 
                       resource=to_agent, details=details)
    
    def log_api(self, agent_id: str, endpoint: str, method: str, status: str, details: Dict = None):
        """记录API调用"""
        return self.log("API", f"{method} {endpoint}", status, agent_id=agent_id, details=details)
    
    def log_security(self, event: str, severity: str, details: Dict = None):
        """记录安全事件"""
        return self.log("SECURITY", event, severity, details=details)
    
    def query(self, event_type: str = None, agent_id: str = None,
              start_time: str = None, end_time: str = None,
              status: str = None, limit: int = 100) -> List[Dict]:
        """查询审计日志"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params = []
        
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_stats(self) -> Dict:
        """获取审计统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总数
        cursor.execute("SELECT COUNT(*) FROM audit_logs")
        total = cursor.fetchone()[0]
        
        # 按事件类型统计
        cursor.execute("""
            SELECT event_type, COUNT(*) as count 
            FROM audit_logs 
            GROUP BY event_type
        """)
        by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 按状态统计
        cursor.execute("""
            SELECT status, COUNT(*) as count 
            FROM audit_logs 
            GROUP BY status
        """)
        by_status = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 最近24小时
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute("SELECT COUNT(*) FROM audit_logs WHERE timestamp >= ?", (yesterday,))
        last_24h = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total": total,
            "by_type": by_type,
            "by_status": by_status,
            "last_24h": last_24h
        }


# 全局实例
_logger = None

def get_logger() -> AuditLogger:
    global _logger
    if _logger is None:
        _logger = AuditLogger()
    return _logger


if __name__ == "__main__":
    # 测试
    logger = get_logger()
    
    # 测试记录
    logger.log_auth("agent-001", "LOGIN", "SUCCESS", {"method": "API_KEY"})
    logger.log_task("agent-001", "task-123", "CREATE", "SUCCESS", {"priority": "high"})
    logger.log_communication("agent-001", "agent-002", "SEND_MESSAGE", "SUCCESS", {"msg_type": "text"})
    logger.log_api("agent-001", "/api/tasks", "POST", "SUCCESS", {"duration_ms": 150})
    logger.log_security("UNAUTHORIZED_ACCESS", "WARNING", {"ip": "192.168.1.100"})
    
    print("✅ 审计日志测试完成")
    print(f"统计: {logger.get_stats()}")