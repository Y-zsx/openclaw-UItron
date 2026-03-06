#!/usr/bin/env python3
"""
Agent任务队列管理增强版API服务
端口: 18183
功能:
  - 队列状态监控
  - 任务统计与分析
  - 健康检查
  - 调度优化建议
"""

import http.server
import socketserver
import json
import os
import time
import uuid
from pathlib import Path
from datetime import datetime, timedelta
import urllib.parse

AGENT_DIR = Path(__file__).parent
QUEUE_STATE_FILE = AGENT_DIR / "queue-manager-state.json"
QUEUE_DATA_FILE = AGENT_DIR / "queue-data.json"
PRIORITY_CONFIG_FILE = AGENT_DIR / "priority-config.json"
PORT = 18183

class QueueAPIHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        
        # 队列监控API
        if path == '/api/monitor':
            self.send_json(self.get_monitor())
        elif path == '/api/health':
            self.send_json(self.get_health())
        elif path == '/api/analysis':
            self.send_json(self.get_analysis())
        elif path == '/api/recommendations':
            self.send_json(self.get_recommendations())
        elif path == '/api/performance':
            self.send_json(self.get_performance())
        elif path == '/api/queue/depth':
            self.send_json(self.get_queue_depth())
        elif path == '/api/tasks/summary':
            self.send_json(self.get_tasks_summary())
        # 原有API兼容
        elif path == '/api/status':
            self.send_json(self.get_status())
        elif path == '/api/stats':
            self.send_json(self.get_stats())
        elif path == '/':
            self.send_json({"service": "queue-api-server", "version": "2.0", "port": PORT})
        else:
            self.send_error(404)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
    
    def get_monitor(self):
        """获取队列监控数据"""
        queue_data = self._load_queue_data()
        queue_state = self._load_queue_state()
        
        waiting = len(queue_data.get('waiting', []))
        ready = len(queue_data.get('ready', []))
        running = len(queue_data.get('running', []))
        completed = len(queue_data.get('completed', []))
        failed = len(queue_data.get('failed', []))
        total = len(queue_data.get('tasks', {}))
        
        return {
            "timestamp": datetime.now().isoformat(),
            "queues": {
                "waiting": waiting,
                "ready": ready,
                "running": running,
                "completed": completed,
                "failed": failed
            },
            "total_tasks": total,
            "active_tasks": running,
            "queue_health": self._calculate_health(waiting, ready, running, failed),
            "backpressure": self._check_backpressure(waiting, ready, running)
        }
    
    def get_health(self):
        """健康检查"""
        queue_data = self._load_queue_data()
        queue_state = self._load_queue_state()
        
        # 检查各项指标
        waiting = len(queue_data.get('waiting', []))
        ready = len(queue_data.get('ready', []))
        running = len(queue_data.get('running', []))
        failed = len(queue_data.get('failed', []))
        
        health_score = 100
        issues = []
        
        # 检查待处理任务积压
        if waiting + ready > 100:
            health_score -= 30
            issues.append(f"队列积压严重: {waiting + ready} 个任务等待处理")
        
        # 检查失败任务
        if failed > 10:
            health_score -= 20
            issues.append(f"失败任务过多: {failed} 个任务失败")
        
        # 检查长时间运行的任务
        running_tasks = queue_data.get('running', [])
        stale_tasks = []
        for task_id in running_tasks:
            task = queue_data.get('tasks', {}).get(task_id, {})
            started = task.get('started_at')
            if started:
                try:
                    start_time = datetime.fromisoformat(started)
                    if (datetime.now() - start_time).total_seconds() > 600:  # 10分钟
                        stale_tasks.append(task_id)
                except:
                    pass
        
        if stale_tasks:
            health_score -= 15
            issues.append(f"存在{stale_tasks.__len__()}个超时任务")
        
        # 检查心跳
        last_heartbeat = queue_state.get('last_heartbeat')
        if last_heartbeat:
            try:
                hb_time = datetime.fromisoformat(last_heartbeat)
                if (datetime.now() - hb_time).total_seconds() > 60:
                    health_score -= 20
                    issues.append("队列管理器心跳超时")
            except:
                pass
        
        status = "healthy" if health_score >= 80 else "degraded" if health_score >= 50 else "unhealthy"
        
        return {
            "status": status,
            "health_score": health_score,
            "issues": issues,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_analysis(self):
        """任务分析"""
        queue_data = self._load_queue_data()
        
        tasks = queue_data.get('tasks', {})
        
        # 按优先级统计
        priority_stats = {}
        for task_id, task in tasks.items():
            priority = task.get('priority', 3)
            priority_stats[priority] = priority_stats.get(priority, 0) + 1
        
        # 按状态统计
        status_stats = {}
        for status in ['pending', 'running', 'completed', 'failed', 'cancelled']:
            status_stats[status] = len(queue_data.get(status, []))
        
        # 计算平均执行时间（如果有完成的任务）
        durations = []
        for task_id, task in tasks.items():
            if task.get('status') == 'completed':
                created = task.get('created_at')
                completed = task.get('completed_at')
                if created and completed:
                    try:
                        c = datetime.fromisoformat(created)
                        cpl = datetime.fromisoformat(completed)
                        durations.append((cpl - c).total_seconds())
                    except:
                        pass
        
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        return {
            "priority_distribution": priority_stats,
            "status_distribution": status_stats,
            "avg_execution_time_seconds": round(avg_duration, 2),
            "total_tasks": len(tasks)
        }
    
    def get_recommendations(self):
        """调度优化建议"""
        queue_data = self._load_queue_data()
        recommendations = []
        
        waiting = len(queue_data.get('waiting', []))
        ready = len(queue_data.get('ready', []))
        running = len(queue_data.get('running', []))
        failed = len(queue_data.get('failed', []))
        
        # 队列积压建议
        if waiting + ready > 50:
            recommendations.append({
                "type": "scale",
                "priority": "high",
                "message": f"队列积压{(waiting + ready)}个任务，建议增加并发数"
            })
        
        # 失败任务建议
        if failed > 5:
            recommendations.append({
                "type": "investigate",
                "priority": "medium",
                "message": f"存在{failed}个失败任务，建议检查错误原因"
            })
        
        # 空闲检测
        if waiting + ready == 0 and running == 0:
            recommendations.append({
                "type": "idle",
                "priority": "low",
                "message": "队列空闲，可以调度更多任务"
            })
        
        # 检查优先级分布
        tasks = queue_data.get('tasks', {})
        high_priority = sum(1 for t in tasks.values() if t.get('priority', 3) <= 2)
        if high_priority > 20:
            recommendations.append({
                "type": "priority",
                "priority": "medium",
                "message": f"有{high_priority}个高优先级任务等待处理"
            })
        
        if not recommendations:
            recommendations.append({
                "type": "ok",
                "priority": "info",
                "message": "队列运行正常"
            })
        
        return {
            "recommendations": recommendations,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_performance(self):
        """性能指标"""
        queue_data = self._load_queue_data()
        tasks = queue_data.get('tasks', {})
        
        # 计算吞吐量（最近1小时）
        one_hour_ago = datetime.now() - timedelta(hours=1)
        completed_last_hour = 0
        failed_last_hour = 0
        
        for task_id, task in tasks.items():
            completed = task.get('completed_at')
            if completed:
                try:
                    cpl_time = datetime.fromisoformat(completed)
                    if cpl_time > one_hour_ago:
                        if task.get('status') == 'completed':
                            completed_last_hour += 1
                        elif task.get('status') == 'failed':
                            failed_last_hour += 1
                except:
                    pass
        
        return {
            "throughput_per_hour": completed_last_hour,
            "failure_rate_per_hour": failed_last_hour,
            "success_rate": round(completed_last_hour / (completed_last_hour + failed_last_hour) * 100, 1) if (completed_last_hour + failed_last_hour) > 0 else 100,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_queue_depth(self):
        """队列深度监控"""
        queue_data = self._load_queue_data()
        
        return {
            "waiting": len(queue_data.get('waiting', [])),
            "ready": len(queue_data.get('ready', [])),
            "running": len(queue_data.get('running', [])),
            "timestamp": datetime.now().isoformat()
        }
    
    def get_tasks_summary(self):
        """任务摘要"""
        queue_data = self._load_queue_data()
        tasks = queue_data.get('tasks', {})
        
        pending_tasks = []
        for task_id in queue_data.get('ready', []) + queue_data.get('waiting', []):
            task = tasks.get(task_id, {})
            if task:
                pending_tasks.append({
                    "id": task_id,
                    "name": task.get('name', 'unknown'),
                    "priority": task.get('priority', 3),
                    "created": task.get('created_at', '')
                })
        
        return {
            "pending_count": len(pending_tasks),
            "pending_tasks": pending_tasks[:10],  # 只返回前10个
            "timestamp": datetime.now().isoformat()
        }
    
    def get_status(self):
        """兼容旧API"""
        return self.get_monitor()
    
    def get_stats(self):
        """兼容旧API"""
        return self.get_analysis()
    
    def _load_queue_data(self):
        if QUEUE_DATA_FILE.exists():
            try:
                with open(QUEUE_DATA_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {"tasks": {}, "waiting": [], "ready": [], "running": [], "completed": [], "failed": []}
    
    def _load_queue_state(self):
        if QUEUE_STATE_FILE.exists():
            try:
                with open(QUEUE_STATE_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def _calculate_health(self, waiting, ready, running, failed):
        score = 100
        if waiting + ready > 50:
            score -= 20
        if failed > 10:
            score -= 30
        if running == 0 and waiting + ready > 0:
            score -= 10
        return "healthy" if score >= 80 else "degraded" if score >= 50 else "unhealthy"
    
    def _check_backpressure(self, waiting, ready, running):
        if waiting + ready > 100:
            return "high"
        elif waiting + ready > 50:
            return "medium"
        return "normal"
    
    def log_message(self, format, *args):
        pass

def main():
    with socketserver.TCPServer(("", PORT), QueueAPIHandler) as httpd:
        print(f"Queue API Server running on http://localhost:{PORT}")
        httpd.serve_forever()

if __name__ == "__main__":
    main()