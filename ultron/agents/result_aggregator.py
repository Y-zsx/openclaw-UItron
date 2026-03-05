#!/usr/bin/env python3
"""
Agent任务结果聚合器
Agent Task Result Aggregator
收集、聚合和分析多Agent任务结果
"""

import json
import sqlite3
import os
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, asdict
import hashlib

@dataclass
class TaskResult:
    """任务结果数据模型"""
    task_id: str
    agent_id: str
    status: str  # success, failed, partial, timeout
    result: Dict[str, Any]
    error: Optional[str]
    execution_time: float
    timestamp: str
    metadata: Dict[str, Any]

class ResultAggregator:
    """任务结果聚合器 - 收集和分析多Agent任务结果"""
    
    def __init__(self, db_path: str = "/root/.openclaw/workspace/ultron/agents/data/result_aggregator.db"):
        self.db_path = db_path
        self._ensure_db()
        self._lock = threading.Lock()
        self._callbacks = []
    
    def _ensure_db(self):
        """确保数据库和表结构存在"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 任务结果表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                session_id TEXT,
                agent_id TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT,
                execution_time REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        ''')
        
        # 聚合任务表 - 跟踪多Agent聚合任务
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS aggregate_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                aggregate_id TEXT UNIQUE NOT NULL,
                task_ids TEXT,
                status TEXT DEFAULT 'pending',
                result_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                final_result TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                completed_at DATETIME
            )
        ''')
        
        # 结果统计表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS result_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                agent_id TEXT NOT NULL,
                total_tasks INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                avg_execution_time REAL DEFAULT 0,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def submit_result(self, result: TaskResult) -> bool:
        """提交单个任务结果"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            try:
                cursor.execute('''
                    INSERT INTO task_results 
                    (task_id, agent_id, status, result, error, execution_time, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    result.task_id,
                    result.agent_id,
                    result.status,
                    json.dumps(result.result),
                    result.error,
                    result.execution_time,
                    result.timestamp,
                    json.dumps(result.metadata)
                ))
                
                # 更新统计
                self._update_stats(cursor, result.agent_id, result.status, result.execution_time)
                
                conn.commit()
                return True
            except Exception as e:
                print(f"Error submitting result: {e}")
                return False
            finally:
                conn.close()
    
    def _update_stats(self, cursor, agent_id: str, status: str, exec_time: float):
        """更新Agent统计信息"""
        cursor.execute('SELECT * FROM result_stats WHERE agent_id = ?', (agent_id,))
        row = cursor.fetchone()
        
        if row:
            total = row[2] + 1
            success = row[3] + (1 if status == 'success' else 0)
            failed = row[4] + (1 if status in ('failed', 'timeout') else 0)
            avg_time = ((row[5] * (total - 1)) + exec_time) / total
            
            cursor.execute('''
                UPDATE result_stats 
                SET total_tasks=?, success_count=?, failed_count=?, avg_execution_time=?, last_updated=CURRENT_TIMESTAMP
                WHERE agent_id=?
            ''', (total, success, failed, avg_time, agent_id))
        else:
            cursor.execute('''
                INSERT INTO result_stats (agent_id, total_tasks, success_count, failed_count, avg_execution_time)
                VALUES (?, 1, ?, ?, ?)
            ''', (agent_id, 1 if status == 'success' else 0, 
                  1 if status in ('failed', 'timeout') else 0, exec_time))
    
    def create_aggregate_task(self, task_ids: List[str]) -> str:
        """创建聚合任务 - 跟踪多个子任务的结果"""
        aggregate_id = hashlib.md5(
            f"{':'.join(task_ids)}:{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO aggregate_tasks (aggregate_id, task_ids, status)
            VALUES (?, ?, 'pending')
        ''', (aggregate_id, json.dumps(task_ids)))
        
        conn.commit()
        conn.close()
        
        return aggregate_id
    
    def get_aggregate_result(self, aggregate_id: str) -> Dict[str, Any]:
        """获取聚合任务结果"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT task_ids, status FROM aggregate_tasks WHERE aggregate_id = ?', 
                      (aggregate_id,))
        row = cursor.fetchone()
        
        if not row:
            return {"error": "Aggregate task not found"}
        
        task_ids = json.loads(row[0])
        status = row[1]
        
        # 获取所有子任务结果
        placeholders = ','.join(['?'] * len(task_ids))
        cursor.execute(f'''
            SELECT task_id, agent_id, status, result, error, execution_time, timestamp
            FROM task_results 
            WHERE task_id IN ({placeholders})
        ''', task_ids)
        
        results = []
        success_count = 0
        failed_count = 0
        total_exec_time = 0
        
        for r in cursor.fetchall():
            result_data = json.loads(r[3]) if r[3] else {}
            results.append({
                "task_id": r[0],
                "agent_id": r[1],
                "status": r[2],
                "result": result_data,
                "error": r[4],
                "execution_time": r[5],
                "timestamp": r[6]
            })
            if r[2] == 'success':
                success_count += 1
            else:
                failed_count += 1
            total_exec_time += r[5]
        
        conn.close()
        
        return {
            "aggregate_id": aggregate_id,
            "status": "completed" if len(results) == len(task_ids) else "partial",
            "total_tasks": len(task_ids),
            "completed_tasks": len(results),
            "success_count": success_count,
            "failed_count": failed_count,
            "results": results,
            "avg_execution_time": total_exec_time / len(results) if results else 0
        }
    
    def get_agent_stats(self, agent_id: Optional[str] = None) -> Dict[str, Any]:
        """获取Agent统计信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if agent_id:
            cursor.execute('''
                SELECT agent_id, total_tasks, success_count, failed_count, avg_execution_time, last_updated
                FROM result_stats WHERE agent_id = ?
            ''', (agent_id,))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return {"error": "Agent not found"}
            
            return {
                "agent_id": row[0],
                "total_tasks": row[1],
                "success_count": row[2],
                "failed_count": row[3],
                "success_rate": row[2] / row[1] if row[1] > 0 else 0,
                "avg_execution_time": row[4],
                "last_updated": row[5]
            }
        else:
            cursor.execute('''
                SELECT agent_id, total_tasks, success_count, failed_count, avg_execution_time
                FROM result_stats ORDER BY total_tasks DESC
            ''')
            rows = cursor.fetchall()
            conn.close()
            
            return {
                "agents": [{
                    "agent_id": r[0],
                    "total_tasks": r[1],
                    "success_count": r[2],
                    "failed_count": r[3],
                    "success_rate": r[2] / r[1] if r[1] > 0 else 0,
                    "avg_execution_time": r[4]
                } for r in rows]
            }
    
    def get_task_results(self, limit: int = 100, status: Optional[str] = None) -> List[Dict]:
        """获取任务结果列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT task_id, agent_id, status, result, error, execution_time, timestamp
                FROM task_results WHERE status = ? ORDER BY timestamp DESC LIMIT ?
            ''', (status, limit))
        else:
            cursor.execute('''
                SELECT task_id, agent_id, status, result, error, execution_time, timestamp
                FROM task_results ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
        
        results = []
        for r in cursor.fetchall():
            results.append({
                "task_id": r[0],
                "agent_id": r[1],
                "status": r[2],
                "result": json.loads(r[3]) if r[3] else {},
                "error": r[4],
                "execution_time": r[5],
                "timestamp": r[6]
            })
        
        conn.close()
        return results
    
    def get_analytics_summary(self, hours: int = 24) -> Dict[str, Any]:
        """获取分析摘要 - 指定小时内的统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*), 
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END),
                   SUM(CASE WHEN status IN ('failed', 'timeout') THEN 1 ELSE 0 END),
                   AVG(execution_time)
            FROM task_results
            WHERE timestamp >= datetime('now', '-' || ? || ' hours')
        ''', (hours,))
        
        row = cursor.fetchone()
        
        cursor.execute('''
            SELECT agent_id, COUNT(*) as cnt
            FROM task_results
            WHERE timestamp >= datetime('now', '-' || ? || ' hours')
            GROUP BY agent_id ORDER BY cnt DESC LIMIT 5
        ''', (hours,))
        
        top_agents = [{"agent_id": r[0], "task_count": r[1]} for r in cursor.fetchall()]
        
        conn.close()
        
        return {
            "period_hours": hours,
            "total_tasks": row[0] or 0,
            "success_count": row[1] or 0,
            "failed_count": row[2] or 0,
            "success_rate": row[1] / row[0] if row[0] and row[1] else 0,
            "avg_execution_time": row[3] or 0,
            "top_agents": top_agents
        }


# API服务器
from flask import Flask, jsonify, request

app = Flask(__name__)
aggregator = ResultAggregator()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "result-aggregator"})

@app.route('/result/submit', methods=['POST'])
def submit_result():
    """提交任务结果"""
    data = request.json
    result = TaskResult(
        task_id=data['task_id'],
        agent_id=data['agent_id'],
        status=data['status'],
        result=data.get('result', {}),
        error=data.get('error'),
        execution_time=data.get('execution_time', 0),
        timestamp=data.get('timestamp', datetime.now().isoformat()),
        metadata=data.get('metadata', {})
    )
    
    success = aggregator.submit_result(result)
    return jsonify({"success": success, "task_id": result.task_id})

@app.route('/result/<task_id>', methods=['GET'])
def get_result(task_id):
    """获取单个任务结果"""
    results = aggregator.get_task_results(limit=1000)
    for r in results:
        if r['task_id'] == task_id:
            return jsonify(r)
    return jsonify({"error": "Task not found"}), 404

@app.route('/aggregate/create', methods=['POST'])
def create_aggregate():
    """创建聚合任务"""
    data = request.json
    task_ids = data.get('task_ids', [])
    
    if not task_ids:
        return jsonify({"error": "task_ids required"}), 400
    
    aggregate_id = aggregator.create_aggregate_task(task_ids)
    return jsonify({"aggregate_id": aggregate_id, "task_ids": task_ids})

@app.route('/aggregate/<aggregate_id>', methods=['GET'])
def get_aggregate(aggregate_id):
    """获取聚合结果"""
    result = aggregator.get_aggregate_result(aggregate_id)
    return jsonify(result)

@app.route('/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    agent_id = request.args.get('agent_id')
    return jsonify(aggregator.get_agent_stats(agent_id))

@app.route('/analytics/summary', methods=['GET'])
def analytics_summary():
    """获取分析摘要"""
    hours = int(request.args.get('hours', 24))
    return jsonify(aggregator.get_analytics_summary(hours))

@app.route('/results', methods=['GET'])
def list_results():
    """列出任务结果"""
    limit = int(request.args.get('limit', 100))
    status = request.args.get('status')
    return jsonify(aggregator.get_task_results(limit, status))


if __name__ == '__main__':
    print("=" * 50)
    print("Agent Result Aggregator API")
    print("Port: 18171")
    print("=" * 50)
    app.run(host='0.0.0.0', port=18171, debug=False)