#!/usr/bin/env python3
"""
Agent任务结果聚合分析系统
第198世 - 收集并分析Agent任务执行结果
"""

import json
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, jsonify, request
import threading
import time

app = Flask(__name__)

# 存储聚合数据
class ResultAggregator:
    def __init__(self, db_path="/root/.openclaw/workspace/ultron/data/task_results.db"):
        self.db_path = db_path
        self._init_db()
        self.lock = threading.Lock()
        
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                agent_id TEXT,
                agent_name TEXT,
                task_type TEXT,
                status TEXT,
                start_time TEXT,
                end_time TEXT,
                duration_ms INTEGER,
                payload TEXT,
                result TEXT,
                error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS aggregation_cache (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    def record_result(self, task_id, agent_id, agent_name, task_type, status, 
                      start_time, end_time, duration_ms, payload="", result="", error=""):
        """记录任务结果"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO task_results 
                (task_id, agent_id, agent_name, task_type, status, start_time, end_time, duration_ms, payload, result, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (task_id, agent_id, agent_name, task_type, status, start_time, end_time, 
                  duration_ms, payload, result, error))
            conn.commit()
            conn.close()
    
    def get_summary(self, hours=24):
        """获取聚合摘要"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # 总任务数
        cursor.execute('''
            SELECT COUNT(*) FROM task_results 
            WHERE start_time >= ?
        ''', (since,))
        total = cursor.fetchone()[0]
        
        # 按状态统计
        cursor.execute('''
            SELECT status, COUNT(*) FROM task_results 
            WHERE start_time >= ?
            GROUP BY status
        ''', (since,))
        by_status = dict(cursor.fetchall())
        
        # 按Agent统计
        cursor.execute('''
            SELECT agent_name, COUNT(*), AVG(duration_ms) FROM task_results 
            WHERE start_time >= ?
            GROUP BY agent_name
        ''', (since,))
        by_agent = [{"agent": r[0], "tasks": r[1], "avg_duration_ms": r[2]} for r in cursor.fetchall()]
        
        # 按任务类型统计
        cursor.execute('''
            SELECT task_type, COUNT(*), AVG(duration_ms) FROM task_results 
            WHERE start_time >= ?
            GROUP BY task_type
        ''', (since,))
        by_type = [{"type": r[0], "tasks": r[1], "avg_duration_ms": r[2]} for r in cursor.fetchall()]
        
        # 成功率
        success_rate = (by_status.get('completed', 0) / total * 100) if total > 0 else 0
        
        # 平均执行时间
        cursor.execute('''
            SELECT AVG(duration_ms) FROM task_results 
            WHERE start_time >= ? AND status = 'completed'
        ''', (since,))
        avg_duration = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "period_hours": hours,
            "total_tasks": total,
            "by_status": by_status,
            "success_rate": round(success_rate, 2),
            "avg_duration_ms": round(avg_duration, 2),
            "by_agent": by_agent,
            "by_type": by_type,
            "generated_at": datetime.now().isoformat()
        }
    
    def get_trends(self, hours=24, bucket_minutes=30):
        """获取趋势数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute('''
            SELECT 
                datetime((strftime('%s', start_time) / ?) * ?, 'unixepoch') as bucket,
                COUNT(*) as tasks,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                AVG(duration_ms) as avg_duration
            FROM task_results
            WHERE start_time >= ?
            GROUP BY bucket
            ORDER BY bucket
        ''', (bucket_minutes * 60, bucket_minutes * 60, since))
        
        trends = []
        for row in cursor.fetchall():
            trends.append({
                "bucket": row[0],
                "total_tasks": row[1],
                "completed": row[2],
                "avg_duration_ms": round(row[3], 2) if row[3] else 0
            })
        
        conn.close()
        return trends
    
    def get_agent_performance(self):
        """获取Agent性能详情"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                agent_id, agent_name,
                COUNT(*) as total_tasks,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                AVG(duration_ms) as avg_duration,
                MIN(duration_ms) as min_duration,
                MAX(duration_ms) as max_duration
            FROM task_results
            GROUP BY agent_id
        ''')
        
        performance = []
        for row in cursor.fetchall():
            total = row[2]
            completed = row[3]
            performance.append({
                "agent_id": row[0],
                "agent_name": row[1],
                "total_tasks": total,
                "completed": completed,
                "failed": total - completed,
                "success_rate": round(completed / total * 100, 2) if total > 0 else 0,
                "avg_duration_ms": round(row[4], 2) if row[4] else 0,
                "min_duration_ms": row[5] or 0,
                "max_duration_ms": row[6] or 0
            })
        
        conn.close()
        return performance
    
    def add_sample_results(self):
        """添加示例结果数据"""
        import random
        
        agents = [("worker-1", "Worker One"), ("worker-2", "Worker Two"), ("worker-3", "Worker Three")]
        task_types = ["health_check", "data_sync", "computation", "report_generation"]
        
        for i in range(15):
            agent_id, agent_name = random.choice(agents)
            task_type = random.choice(task_types)
            status = random.choices(["completed", "failed", "timeout"], weights=[80, 15, 5])[0]
            
            start = datetime.now() - timedelta(minutes=random.randint(1, 120))
            duration = random.randint(50, 5000) if status == "completed" else random.randint(100, 2000)
            end = start + timedelta(milliseconds=duration)
            
            self.record_result(
                task_id=f"task-{i+1:04d}",
                agent_id=agent_id,
                agent_name=agent_name,
                task_type=task_type,
                status=status,
                start_time=start.isoformat(),
                end_time=end.isoformat(),
                duration_ms=duration,
                payload=json.dumps({"iteration": i}),
                result=json.dumps({"output": f"Result for task {i}"}) if status == "completed" else "",
                error="Timeout" if status == "timeout" else ("Error occurred" if status == "failed" else "")
            )

# 全局实例
aggregator = ResultAggregator()

# 添加示例数据
aggregator.add_sample_results()

# API 路由
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"service": "agent-result-aggregator", "status": "ok"})

@app.route('/summary', methods=['GET'])
def summary():
    hours = int(request.args.get('hours', 24))
    return jsonify(aggregator.get_summary(hours))

@app.route('/trends', methods=['GET'])
def trends():
    hours = int(request.args.get('hours', 24))
    bucket = int(request.args.get('bucket', 30))
    return jsonify(aggregator.get_trends(hours, bucket))

@app.route('/performance', methods=['GET'])
def performance():
    return jsonify(aggregator.get_agent_performance())

@app.route('/record', methods=['POST'])
def record():
    data = request.json
    aggregator.record_result(
        task_id=data.get('task_id'),
        agent_id=data.get('agent_id'),
        agent_name=data.get('agent_name'),
        task_type=data.get('task_type', 'default'),
        status=data.get('status', 'completed'),
        start_time=data.get('start_time'),
        end_time=data.get('end_time'),
        duration_ms=data.get('duration_ms', 0),
        payload=json.dumps(data.get('payload', {})),
        result=json.dumps(data.get('result', {})),
        error=data.get('error', '')
    )
    return jsonify({"status": "recorded"})

if __name__ == '__main__':
    print(f"🤖 Agent结果聚合分析系统启动 - 端口18298")
    app.run(host='0.0.0.0', port=18298, debug=False)