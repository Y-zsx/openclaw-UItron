#!/usr/bin/env python3
"""
协作历史分析与统计模块
Collaboration Analytics Module
为多智能体协作网络提供历史数据分析与统计功能
"""

import json
import sqlite3
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
import threading

class CollaborationAnalytics:
    """协作历史分析器"""
    
    def __init__(self, db_path: str = "/root/.openclaw/workspace/ultron/agents/data/collaboration_analytics.db"):
        self.db_path = db_path
        self._ensure_db()
        self._lock = threading.Lock()
    
    def _ensure_db(self):
        """确保数据库和表结构存在"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 协作事件表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collaboration_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                agent_id TEXT,
                task_id TEXT,
                metadata TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 任务统计表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT UNIQUE,
                task_type TEXT,
                priority INTEGER,
                status TEXT,
                agent_id TEXT,
                duration_ms INTEGER,
                created_at DATETIME,
                completed_at DATETIME,
                error_count INTEGER DEFAULT 0
            )
        ''')
        
        # Agent性能表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS agent_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                metric_name TEXT NOT NULL,
                metric_value REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 协作会话表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS collaboration_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE,
                status TEXT,
                agent_count INTEGER,
                task_count INTEGER,
                started_at DATETIME,
                ended_at DATETIME,
                metadata TEXT
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_session ON collaboration_events(session_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_events_timestamp ON collaboration_events(timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_task_stats_agent ON task_stats(agent_id)')
        
        conn.commit()
        conn.close()
    
    def record_event(self, session_id: str, event_type: str, agent_id: str = None, 
                     task_id: str = None, metadata: Dict = None):
        """记录协作事件"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO collaboration_events (session_id, event_type, agent_id, task_id, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (session_id, event_type, agent_id, task_id, json.dumps(metadata) if metadata else None))
            conn.commit()
            conn.close()
    
    def record_task(self, task_id: str, task_type: str, priority: int, agent_id: str = None):
        """记录任务开始"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO task_stats 
                (task_id, task_type, priority, status, agent_id, created_at)
                VALUES (?, ?, ?, 'running', ?, datetime('now'))
            ''', (task_id, task_type, priority, agent_id))
            conn.commit()
            conn.close()
    
    def complete_task(self, task_id: str, status: str = 'completed', duration_ms: int = 0, 
                      error_count: int = 0):
        """记录任务完成"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE task_stats 
                SET status = ?, duration_ms = ?, error_count = ?, completed_at = datetime('now')
                WHERE task_id = ?
            ''', (status, duration_ms, error_count, task_id))
            conn.commit()
            conn.close()
    
    def record_agent_metric(self, agent_id: str, metric_name: str, metric_value: float):
        """记录Agent性能指标"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO agent_performance (agent_id, metric_name, metric_value)
                VALUES (?, ?, ?)
            ''', (agent_id, metric_name, metric_value))
            conn.commit()
            conn.close()
    
    def get_task_statistics(self, days: int = 7) -> Dict[str, Any]:
        """获取任务统计信息"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_tasks,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                AVG(duration_ms) as avg_duration,
                SUM(duration_ms) as total_duration,
                task_type,
                priority
            FROM task_stats
            WHERE created_at >= datetime('now', '-' || ? || ' days')
            GROUP BY task_type, priority
        ''', (days,))
        
        results = cursor.fetchall()
        conn.close()
        
        stats = {
            "period_days": days,
            "by_type": [],
            "by_priority": defaultdict(lambda: {"total": 0, "completed": 0, "failed": 0}),
            "summary": {"total": 0, "completed": 0, "failed": 0, "avg_duration_ms": 0}
        }
        
        total_duration = 0
        for row in results:
            type_stat = {
                "task_type": row["task_type"],
                "total": row["total_tasks"],
                "completed": row["completed"],
                "failed": row["failed"],
                "avg_duration_ms": row["avg_duration"] or 0
            }
            stats["by_type"].append(type_stat)
            
            priority_key = f"priority_{row['priority']}"
            stats["by_priority"][priority_key]["total"] += row["total_tasks"]
            stats["by_priority"][priority_key]["completed"] += row["completed"]
            stats["by_priority"][priority_key]["failed"] += row["failed"]
            
            stats["summary"]["total"] += row["total_tasks"]
            stats["summary"]["completed"] += row["completed"]
            stats["summary"]["failed"] += row["failed"]
            total_duration += row["total_duration"] or 0
        
        if stats["summary"]["total"] > 0:
            stats["summary"]["avg_duration_ms"] = total_duration / stats["summary"]["total"]
        
        return stats
    
    def get_agent_performance(self, days: int = 7) -> List[Dict]:
        """获取Agent性能统计"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                agent_id,
                metric_name,
                AVG(metric_value) as avg_value,
                MIN(metric_value) as min_value,
                MAX(metric_value) as max_value,
                COUNT(*) as samples
            FROM agent_performance
            WHERE timestamp >= datetime('now', '-' || ? || ' days')
            GROUP BY agent_id, metric_name
            ORDER BY agent_id, metric_name
        ''', (days,))
        
        results = cursor.fetchall()
        conn.close()
        
        performance = defaultdict(dict)
        for row in results:
            agent_id = row["agent_id"]
            performance[agent_id][row["metric_name"]] = {
                "avg": row["avg_value"],
                "min": row["min_value"],
                "max": row["max_value"],
                "samples": row["samples"]
            }
        
        return dict(performance)
    
    def get_collaboration_timeline(self, days: int = 7, limit: int = 100) -> List[Dict]:
        """获取协作时间线"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT session_id, event_type, agent_id, task_id, metadata, timestamp
            FROM collaboration_events
            WHERE timestamp >= datetime('now', '-' || ? || ' days')
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (days, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        timeline = []
        for row in results:
            timeline.append({
                "session_id": row["session_id"],
                "event_type": row["event_type"],
                "agent_id": row["agent_id"],
                "task_id": row["task_id"],
                "metadata": json.loads(row["metadata"]) if row["metadata"] else {},
                "timestamp": row["timestamp"]
            })
        
        return timeline
    
    def get_session_summary(self, session_id: str) -> Dict:
        """获取会话摘要"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 会话信息
        cursor.execute('SELECT * FROM collaboration_sessions WHERE session_id = ?', (session_id,))
        session = cursor.fetchone()
        
        # 事件统计
        cursor.execute('''
            SELECT event_type, COUNT(*) as count
            FROM collaboration_events
            WHERE session_id = ?
            GROUP BY event_type
        ''', (session_id,))
        event_counts = cursor.fetchall()
        
        # 任务统计
        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM task_stats
            WHERE task_id LIKE ?
            GROUP BY status
        ''', (f"{session_id}%",))
        task_counts = cursor.fetchall()
        
        conn.close()
        
        return {
            "session_id": session_id,
            "session_info": dict(session) if session else None,
            "event_counts": {row["event_type"]: row["count"] for row in event_counts},
            "task_counts": {row["status"]: row["count"] for row in task_counts}
        }
    
    def generate_report(self, days: int = 7) -> Dict:
        """生成综合分析报告"""
        task_stats = self.get_task_statistics(days)
        agent_perf = self.get_agent_performance(days)
        timeline = self.get_collaboration_timeline(days, limit=50)
        
        # 计算协作效率
        total_events = sum(s["total"] for s in task_stats["by_type"])
        success_rate = (task_stats["summary"]["completed"] / task_stats["summary"]["total"] * 100 
                       if task_stats["summary"]["total"] > 0 else 0)
        
        return {
            "report_period_days": days,
            "generated_at": datetime.now().isoformat(),
            "task_statistics": task_stats,
            "agent_performance": agent_perf,
            "efficiency": {
                "success_rate": round(success_rate, 2),
                "total_events": total_events,
                "active_agents": len(agent_perf)
            },
            "recent_events": timeline[:10]
        }


# API服务
from flask import Flask, jsonify, request

app = Flask(__name__)
analytics = CollaborationAnalytics()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})

@app.route('/api/stats', methods=['GET'])
def get_stats():
    days = request.args.get('days', 7, type=int)
    return jsonify(analytics.get_task_statistics(days))

@app.route('/api/agents/performance', methods=['GET'])
def get_agent_performance():
    days = request.args.get('days', 7, type=int)
    return jsonify(analytics.get_agent_performance(days))

@app.route('/api/timeline', methods=['GET'])
def get_timeline():
    days = request.args.get('days', 7, type=int)
    limit = request.args.get('limit', 100, type=int)
    return jsonify(analytics.get_collaboration_timeline(days, limit))

@app.route('/api/report', methods=['GET'])
def get_report():
    days = request.args.get('days', 7, type=int)
    return jsonify(analytics.generate_report(days))

@app.route('/api/session/<session_id>', methods=['GET'])
def get_session(session_id):
    return jsonify(analytics.get_session_summary(session_id))

@app.route('/api/event', methods=['POST'])
def record_event():
    data = request.json
    analytics.record_event(
        session_id=data.get('session_id'),
        event_type=data.get('event_type'),
        agent_id=data.get('agent_id'),
        task_id=data.get('task_id'),
        metadata=data.get('metadata')
    )
    return jsonify({"status": "recorded"})

@app.route('/api/task', methods=['POST'])
def record_task():
    data = request.json
    analytics.record_task(
        task_id=data.get('task_id'),
        task_type=data.get('task_type'),
        priority=data.get('priority', 2),
        agent_id=data.get('agent_id')
    )
    return jsonify({"status": "recorded"})

@app.route('/api/task/complete', methods=['POST'])
def complete_task():
    data = request.json
    analytics.complete_task(
        task_id=data.get('task_id'),
        status=data.get('status', 'completed'),
        duration_ms=data.get('duration_ms', 0),
        error_count=data.get('error_count', 0)
    )
    return jsonify({"status": "recorded"})

def main():
    port = 18270
    print(f"启动协作分析服务: http://0.0.0.0:{port}")
    print(f"API端点:")
    print(f"  - GET  /api/stats          任务统计")
    print(f"  - GET  /api/agents/performance  Agent性能")
    print(f"  - GET  /api/timeline       协作时间线")
    print(f"  - GET  /api/report         综合报告")
    print(f"  - GET  /api/session/<id>   会话摘要")
    print(f"  - POST /api/event          记录事件")
    print(f"  - POST /api/task           记录任务")
    print(f"  - POST /api/task/complete  完成任务")
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    main()