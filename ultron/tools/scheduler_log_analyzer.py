#!/usr/bin/env python3
"""
调度任务执行日志分析器
功能：记录任务执行历史、分析执行结果、趋势预测、异常检测
"""
import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
import threading

WORKSPACE = "/root/.openclaw/workspace"
DB_PATH = f"{WORKSPACE}/ultron/scheduler_logs.db"
LOG_FILE = f"{WORKSPACE}/ultron/logs/scheduler_execution.log"

class SchedulerLogAnalyzer:
    def __init__(self):
        self.db_path = DB_PATH
        self._ensure_db()
    
    def _ensure_db(self):
        """确保数据库和表存在"""
        os.makedirs(os.path.dirname(self.db_path.replace(".db", "")), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                task_name TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT,
                duration_ms INTEGER,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT,
                metadata TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS task_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT NOT NULL,
                date TEXT NOT NULL,
                total_runs INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                timeout_count INTEGER DEFAULT 0,
                avg_duration_ms INTEGER DEFAULT 0,
                min_duration_ms INTEGER DEFAULT 0,
                max_duration_ms INTEGER DEFAULT 0,
                UNIQUE(task_id, date)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_executions_task_time 
            ON task_executions(task_id, start_time)
        ''')
        
        conn.commit()
        conn.close()
    
    def log_execution(self, task_id, task_name, start_time, end_time, 
                     status, result=None, error=None, metadata=None):
        """记录任务执行"""
        duration_ms = int((end_time - start_time) * 1000) if isinstance(start_time, datetime) else 0
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO task_executions 
            (task_id, task_name, start_time, end_time, duration_ms, status, result, error, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (task_id, task_name, start_time.isoformat() if isinstance(start_time, datetime) else start_time,
              end_time.isoformat() if isinstance(end_time, datetime) else end_time,
              duration_ms, status, json.dumps(result) if result else None,
              error, json.dumps(metadata) if metadata else None))
        
        conn.commit()
        conn.close()
        
        # 同时更新每日统计
        self._update_daily_stat(task_id, status, duration_ms)
    
    def _update_daily_stat(self, task_id, status, duration_ms):
        """更新每日统计"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 尝试更新现有记录
        if status == "success":
            cursor.execute('''
                INSERT INTO task_statistics (task_id, date, total_runs, success_count, avg_duration_ms)
                VALUES (?, ?, 1, 1, ?)
                ON CONFLICT(task_id, date) DO UPDATE SET
                    total_runs = total_runs + 1,
                    success_count = success_count + 1,
                    avg_duration_ms = (avg_duration_ms * total_runs + ?) / (total_runs + 1)
            ''', (task_id, today, duration_ms, duration_ms))
        elif status == "failure":
            cursor.execute('''
                INSERT INTO task_statistics (task_id, date, total_runs, failure_count)
                VALUES (?, ?, 1, 1)
                ON CONFLICT(task_id, date) DO UPDATE SET
                    total_runs = total_runs + 1,
                    failure_count = failure_count + 1
            ''', (task_id, today))
        elif status == "timeout":
            cursor.execute('''
                INSERT INTO task_statistics (task_id, date, total_runs, timeout_count)
                VALUES (?, ?, 1, 1)
                ON CONFLICT(task_id, date) DO UPDATE SET
                    total_runs = total_runs + 1,
                    timeout_count = timeout_count + 1
            ''', (task_id, today))
        
        conn.commit()
        conn.close()
    
    def get_task_history(self, task_id, hours=24, limit=100):
        """获取任务执行历史"""
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM task_executions 
            WHERE task_id = ? AND start_time >= ?
            ORDER BY start_time DESC
            LIMIT ?
        ''', (task_id, since, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def get_statistics(self, task_id=None, days=7):
        """获取统计信息"""
        since = (datetime.now() - timedelta(days=days)).isoformat()[:10]
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if task_id:
            cursor.execute('''
                SELECT * FROM task_statistics
                WHERE task_id = ? AND date >= ?
                ORDER BY date DESC
            ''', (task_id, since))
        else:
            cursor.execute('''
                SELECT * FROM task_statistics
                WHERE date >= ?
                ORDER BY date DESC
            ''', (since,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def analyze_trends(self, task_id, hours=24):
        """分析任务执行趋势"""
        history = self.get_task_history(task_id, hours=hours)
        
        if not history:
            return {"status": "no_data", "message": "无执行历史"}
        
        # 计算统计数据
        total = len(history)
        success = sum(1 for h in history if h["status"] == "success")
        failure = sum(1 for h in history if h["status"] == "failure")
        timeout = sum(1 for h in history if h["status"] == "timeout")
        
        durations = [h["duration_ms"] for h in history if h.get("duration_ms")]
        avg_duration = sum(durations) / len(durations) if durations else 0
        max_duration = max(durations) if durations else 0
        min_duration = min(durations) if durations else 0
        
        # 计算趋势（最近10次 vs 前10次）
        recent = history[:10] if len(history) >= 10 else history
        older = history[10:20] if len(history) >= 20 else []
        
        recent_success_rate = sum(1 for h in recent if h["status"] == "success") / len(recent) if recent else 0
        
        if older:
            older_success_rate = sum(1 for h in older if h["status"] == "success") / len(older)
            if recent_success_rate > older_success_rate + 0.1:
                trend = "improving"
            elif recent_success_rate < older_success_rate - 0.1:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        # 预测下一个执行结果
        predicted_status = "success" if recent_success_rate >= 0.9 else ("uncertain" if recent_success_rate >= 0.7 else "likely_failure")
        
        return {
            "task_id": task_id,
            "total_runs": total,
            "success_count": success,
            "failure_count": failure,
            "timeout_count": timeout,
            "success_rate": round(success / total, 3) if total > 0 else 0,
            "avg_duration_ms": round(avg_duration),
            "min_duration_ms": min_duration,
            "max_duration_ms": max_duration,
            "trend": trend,
            "recent_success_rate": round(recent_success_rate, 3),
            "predicted_next_status": predicted_status,
            "health_score": round(recent_success_rate * 100)
        }
    
    def detect_anomalies(self, task_id, hours=24):
        """检测异常"""
        history = self.get_task_history(task_id, hours=hours)
        
        if len(history) < 5:
            return {"status": "insufficient_data", "anomalies": []}
        
        anomalies = []
        
        # 检测失败率异常
        failures = [h for h in history if h["status"] == "failure"]
        if len(failures) / len(history) > 0.3:
            anomalies.append({
                "type": "high_failure_rate",
                "message": f"失败率过高: {len(failures)}/{len(history)}",
                "severity": "critical"
            })
        
        # 检测执行时长异常
        durations = [h["duration_ms"] for h in history if h.get("duration_ms")]
        if durations:
            avg = sum(durations) / len(durations)
            recent_durations = durations[:5]
            if sum(1 for d in recent_durations if d > avg * 2) > 0:
                anomalies.append({
                    "type": "duration_spike",
                    "message": f"执行时间突然增长: {recent_durations[-1]}ms > 平均{avg}ms",
                    "severity": "warning"
                })
        
        # 检测连续失败
        consecutive_failures = 0
        for h in history:
            if h["status"] == "failure":
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    anomalies.append({
                        "type": "consecutive_failures",
                        "message": f"连续 {consecutive_failures} 次失败",
                        "severity": "critical"
                    })
                    break
            else:
                consecutive_failures = 0
        
        return {
            "task_id": task_id,
            "anomalies": anomalies,
            "anomaly_count": len(anomalies),
            "checked_at": datetime.now().isoformat()
        }
    
    def get_all_tasks_summary(self, hours=24):
        """获取所有任务摘要"""
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT task_id, COUNT(*) as total,
                   SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as success,
                   SUM(CASE WHEN status = 'failure' THEN 1 ELSE 0 END) as failure,
                   AVG(duration_ms) as avg_duration
            FROM task_executions
            WHERE start_time >= ?
            GROUP BY task_id
        ''', (since,))
        
        rows = cursor.fetchall()
        conn.close()
        
        summaries = []
        for row in rows:
            task_id = row["task_id"]
            total = row["total"]
            success = row["success"] or 0
            failure = row["failure"] or 0
            
            summaries.append({
                "task_id": task_id,
                "total_runs": total,
                "success_count": success,
                "failure_count": failure,
                "success_rate": round(success / total, 3) if total > 0 else 0,
                "avg_duration_ms": round(row["avg_duration"] or 0),
                "health_score": round(success / total * 100) if total > 0 else 0
            })
        
        return sorted(summaries, key=lambda x: x["health_score"])
    
    def clear_old_records(self, days=30):
        """清理旧记录"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM task_executions WHERE start_time < ?', (cutoff,))
        cursor.execute('DELETE FROM task_statistics WHERE date < ?', (cutoff[:10],))
        
        deleted_exec = cursor.rowcount
        conn.commit()
        conn.close()
        
        return {"deleted_executions": deleted_exec}


class SchedulerLogAPI:
    """调度日志分析API服务"""
    
    def __init__(self, port=18170):
        self.port = port
        self.analyzer = SchedulerLogAnalyzer()
        self.server = None
    
    def handle_request(self, environ, start_response):
        """处理HTTP请求"""
        path = environ.get("PATH_INFO", "/")
        method = environ.get("REQUEST_METHOD", "GET")
        
        headers = [("Content-Type", "application/json; charset=utf-8")]
        
        try:
            if path == "/health":
                response = {"status": "ok", "service": "scheduler-log-analyzer"}
            
            elif path == "/api/stats" or path == "/api/stats/":
                task_id = environ.get("QUERY_STRING", "").split("=")[1] if "=" in environ.get("QUERY_STRING", "") else None
                hours = int(environ.get("QUERY_STRING", "24h").split("=")[1].split("h")[0]) if "h" in environ.get("QUERY_STRING", "") and "=" in environ.get("QUERY_STRING", "") else 24
                
                if task_id:
                    response = self.analyzer.get_statistics(task_id=task_id, days=hours//24+1)
                else:
                    response = self.analyzer.get_all_tasks_summary(hours=hours)
            
            elif path.startswith("/api/trends/"):
                task_id = path.split("/api/trends/")[1]
                response = self.analyzer.analyze_trends(task_id)
            
            elif path.startswith("/api/anomalies/"):
                task_id = path.split("/api/anomalies/")[1]
                response = self.analyzer.detect_anomalies(task_id)
            
            elif path.startswith("/api/history/"):
                task_id = path.split("/api/history/")[1]
                response = self.analyzer.get_task_history(task_id)
            
            elif path == "/api/cleanup":
                result = self.analyzer.clear_old_records()
                response = {"status": "ok", "result": result}
            
            else:
                response = {"error": "Not found", "paths": [
                    "/health", "/api/stats", "/api/stats?task_id=xxx",
                    "/api/trends/<task_id>", "/api/anomalies/<task_id>",
                    "/api/history/<task_id>", "/api/cleanup"
                ]}
            
            status = "200 OK"
            body = json.dumps(response, ensure_ascii=False, indent=2)
            
        except Exception as e:
            status = "500 Internal Server Error"
            body = json.dumps({"error": str(e)})
        
        start_response(status, headers)
        return [body.encode("utf-8")]
    
    def start(self):
        """启动API服务"""
        try:
            from wsgiref.simple_server import make_server
            print(f"🚀 调度日志分析API服务启动: 端口 {self.port}")
            print(f"   健康检查: http://localhost:{self.port}/health")
            print(f"   统计API:  http://localhost:{self.port}/api/stats")
            print(f"   趋势API:  http://localhost:{self.port}/api/trends/<task_id>")
            print(f"   异常检测: http://localhost:{self.port}/api/anomalies/<task_id>")
            
            self.server = make_server("0.0.0.0", self.port, self.handle_request)
            self.server.serve_forever()
        except ImportError:
            print("❌ 需要安装wsgiref (内置模块)")
        except Exception as e:
            print(f"❌ 启动失败: {e}")


def main():
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "api":
            # 启动API服务
            api = SchedulerLogAPI()
            api.start()
        elif sys.argv[1] == "stats":
            # 打印统计
            analyzer = SchedulerLogAnalyzer()
            summary = analyzer.get_all_tasks_summary(hours=24)
            print("📊 调度任务24小时统计:")
            for s in summary:
                print(f"   {s['task_id']}: 成功率 {s['success_rate']*100:.1f}%, "
                      f"执行{s['total_runs']}次, 平均{s['avg_duration_ms']}ms")
        elif sys.argv[1] == "trends" and len(sys.argv) > 2:
            analyzer = SchedulerLogAnalyzer()
            result = analyzer.analyze_trends(sys.argv[2])
            print(f"📈 {sys.argv[2]} 趋势分析:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("用法:")
            print("  python scheduler_log_analyzer.py api     # 启动API服务")
            print("  python scheduler_log_analyzer.py stats   # 显示统计")
            print("  python scheduler_log_analyzer.py trends <task_id>  # 分析趋势")
    else:
        analyzer = SchedulerLogAnalyzer()
        summary = analyzer.get_all_tasks_summary(hours=24)
        print("📊 调度任务执行日志分析")
        print(f"   监控任务数: {len(summary)}")
        
        # 显示健康度低于100的任务
        unhealthy = [s for s in summary if s['health_score'] < 100]
        if unhealthy:
            print(f"\n⚠️  异常任务 ({len(unhealthy)}个):")
            for s in unhealthy:
                print(f"   {s['task_id']}: 健康度 {s['health_score']}%, "
                      f"失败{s['failure_count']}次")


if __name__ == "__main__":
    main()