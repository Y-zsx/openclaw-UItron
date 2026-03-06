#!/usr/bin/env python3
"""
任务失败告警模块
监控任务执行状态，检测失败并发送告警通知
"""

import json
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict
import threading
import uuid

WORKSPACE = "/root/.openclaw/workspace"
DATA_DIR = Path(WORKSPACE) / "ultron" / "data"


class TaskFailureAlert:
    """任务失败告警器"""
    
    def __init__(
        self,
        workspace: str = WORKSPACE,
        check_interval: int = 30,
        alert_threshold: int = 3,
        cooldown_minutes: int = 15
    ):
        self.workspace = workspace
        self.data_dir = Path(workspace) / "ultron" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.check_interval = check_interval
        self.alert_threshold = alert_threshold  # 连续失败次数触发告警
        self.cooldown_minutes = cooldown_minutes  # 告警冷却期
        
        self.db_path = self.data_dir / "task_alerts.db"
        self._init_db()
        
        self.alert_history: List[Dict] = []
        self.last_alert_time: Dict[str, datetime] = {}
        
        # 告警回调
        self.alert_callbacks: List[callable] = []
        
        # 加载告警历史
        self._load_alert_history()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_history (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                agent_id TEXT,
                alert_type TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                created_at TEXT NOT NULL,
                acknowledged INTEGER DEFAULT 0,
                resolved_at TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                task_pattern TEXT,
                agent_id TEXT,
                failure_count INTEGER DEFAULT 3,
                time_window_minutes INTEGER DEFAULT 30,
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_cooldowns (
                task_id TEXT PRIMARY KEY,
                last_alert_time TEXT NOT NULL,
                alert_count INTEGER DEFAULT 1
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_alert_history(self):
        """加载告警历史"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, task_id, agent_id, alert_type, message, details, created_at, acknowledged, resolved_at
            FROM alert_history
            ORDER BY created_at DESC
            LIMIT 100
        """)
        
        self.alert_history = []
        for row in cursor.fetchall():
            self.alert_history.append({
                "id": row[0],
                "task_id": row[1],
                "agent_id": row[2],
                "alert_type": row[3],
                "message": row[4],
                "details": json.loads(row[5]) if row[5] else {},
                "created_at": row[6],
                "acknowledged": bool(row[7]),
                "resolved_at": row[8]
            })
        
        conn.close()
    
    def register_callback(self, callback: callable):
        """注册告警回调"""
        self.alert_callbacks.append(callback)
    
    def _send_alert(self, task_id: str, agent_id: str, alert_type: str, message: str, details: Dict = None):
        """发送告警"""
        # 检查冷却期
        if task_id in self.last_alert_time:
            elapsed = (datetime.now() - self.last_alert_time[task_id]).total_seconds()
            if elapsed < self.cooldown_minutes * 60:
                return None
        
        alert_id = str(uuid.uuid4())
        alert = {
            "id": alert_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "alert_type": alert_type,
            "message": message,
            "details": details or {},
            "created_at": datetime.now().isoformat(),
            "acknowledged": False,
            "resolved_at": None
        }
        
        # 保存到数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO alert_history (id, task_id, agent_id, alert_type, message, details, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            alert_id,
            task_id,
            agent_id,
            alert_type,
            message,
            json.dumps(details or {}),
            alert["created_at"]
        ))
        
        cursor.execute("""
            INSERT OR REPLACE INTO alert_cooldowns (task_id, last_alert_time, alert_count)
            VALUES (?, ?, COALESCE((SELECT alert_count FROM alert_cooldowns WHERE task_id = ?), 0) + 1)
        """, (task_id, alert["created_at"], task_id))
        
        conn.commit()
        conn.close()
        
        # 更新内存
        self.alert_history.insert(0, alert)
        self.last_alert_time[task_id] = datetime.now()
        
        # 触发回调
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"[TaskFailureAlert] Callback error: {e}")
        
        return alert
    
    def check_failure(
        self,
        task_id: str,
        agent_id: str,
        error: str,
        retry_count: int = 0,
        execution_history: List[Dict] = None
    ) -> Optional[Dict]:
        """检查是否需要告警"""
        
        # 根据重试次数判断告警级别
        if retry_count >= self.alert_threshold:
            alert_type = "critical"
            message = f"任务 {task_id} 连续失败 {retry_count + 1} 次"
        elif retry_count >= 2:
            alert_type = "warning"
            message = f"任务 {task_id} 失败 {retry_count + 1} 次，请关注"
        else:
            # 首次失败不告警，等待自动重试
            return None
        
        details = {
            "error": error,
            "retry_count": retry_count,
            "agent_id": agent_id,
            "execution_history": execution_history[-5:] if execution_history else []
        }
        
        return self._send_alert(task_id, agent_id, alert_type, message, details)
    
    def check_success(self, task_id: str):
        """任务成功后清除告警状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 标记已解决
        cursor.execute("""
            UPDATE alert_history
            SET resolved_at = ?
            WHERE task_id = ? AND resolved_at IS NULL
        """, (datetime.now().isoformat(), task_id))
        
        # 清除冷却
        cursor.execute("DELETE FROM alert_cooldowns WHERE task_id = ?", (task_id,))
        
        conn.commit()
        conn.close()
        
        # 清除内存中的冷却记录
        if task_id in self.last_alert_time:
            del self.last_alert_time[task_id]
    
    def get_active_alerts(self) -> List[Dict]:
        """获取活跃告警"""
        return [a for a in self.alert_history if not a.get("resolved_at")]
    
    def get_alert_history(self, hours: int = 24, limit: int = 50) -> List[Dict]:
        """获取告警历史"""
        cutoff = datetime.now() - timedelta(hours=hours)
        result = []
        
        for alert in self.alert_history:
            try:
                created = datetime.fromisoformat(alert["created_at"])
                if created >= cutoff:
                    result.append(alert)
            except:
                result.append(alert)
        
        return result[:limit]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("UPDATE alert_history SET acknowledged = 1 WHERE id = ?", (alert_id,))
        affected = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        if affected > 0:
            for alert in self.alert_history:
                if alert["id"] == alert_id:
                    alert["acknowledged"] = True
                    break
        
        return affected > 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取告警统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总告警数
        cursor.execute("SELECT COUNT(*) FROM alert_history")
        total = cursor.fetchone()[0]
        
        # 活跃告警
        cursor.execute("SELECT COUNT(*) FROM alert_history WHERE resolved_at IS NULL")
        active = cursor.fetchone()[0]
        
        # 按类型统计
        cursor.execute("""
            SELECT alert_type, COUNT(*) 
            FROM alert_history 
            GROUP BY alert_type
        """)
        by_type = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 今日告警
        today = datetime.now().date().isoformat()
        cursor.execute("SELECT COUNT(*) FROM alert_history WHERE created_at LIKE ?", (f"{today}%",))
        today_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total": total,
            "active": active,
            "by_type": by_type,
            "today": today_count,
            "cooldown_tasks": len(self.last_alert_time)
        }


def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="任务失败告警")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # 检查失败
    check_parser = subparsers.add_parser("check", help="检查失败并发送告警")
    check_parser.add_argument("--task-id", required=True)
    check_parser.add_argument("--agent-id", required=True)
    check_parser.add_argument("--error", required=True)
    check_parser.add_argument("--retry-count", type=int, default=0)
    
    # 查看活跃告警
    subparsers.add_parser("active", help="查看活跃告警")
    
    # 查看告警历史
    history_parser = subparsers.add_parser("history", help="查看告警历史")
    history_parser.add_argument("--hours", type=int, default=24)
    history_parser.add_argument("--limit", type=int, default=50)
    
    # 确认告警
    ack_parser = subparsers.add_parser("ack", help="确认告警")
    ack_parser.add_argument("--alert-id", required=True)
    
    # 任务成功后清除告警
    success_parser = subparsers.add_parser("success", help="任务成功后清除告警")
    success_parser.add_argument("--task-id", required=True)
    
    # 统计
    subparsers.add_parser("stats", help="查看告警统计")
    
    args = parser.parse_args()
    
    alert_system = TaskFailureAlert()
    
    if args.command == "check":
        result = alert_system.check_failure(
            task_id=args.task_id,
            agent_id=args.agent_id,
            error=args.error,
            retry_count=args.retry_count
        )
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("No alert sent (within cooldown)")
    
    elif args.command == "active":
        alerts = alert_system.get_active_alerts()
        print(json.dumps(alerts, indent=2, ensure_ascii=False))
    
    elif args.command == "history":
        history = alert_system.get_alert_history(args.hours, args.limit)
        print(json.dumps(history, indent=2, ensure_ascii=False))
    
    elif args.command == "ack":
        if alert_system.acknowledge_alert(args.alert_id):
            print("Alert acknowledged")
        else:
            print("Alert not found")
    
    elif args.command == "success":
        alert_system.check_success(args.task_id)
        print("Alert cleared")
    
    elif args.command == "stats":
        stats = alert_system.get_statistics()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()