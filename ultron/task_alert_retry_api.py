#!/usr/bin/env python3
"""
任务失败告警与自动重试集成API服务
统一管理任务失败告警和自动重试
端口: 18197
"""

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from pathlib import Path
import threading
import time
import sqlite3

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from task_failure_alert import TaskFailureAlert
from task_auto_retry import TaskAutoRetry
from task_monitor import TaskMonitor

PORT = 18197
WORKSPACE = "/root/.openclaw/workspace"


def execute_task_callback(task_id: str, agent_id: str, task_data: dict, retry_count: int) -> dict:
    """任务执行回调 - 实际执行任务的逻辑"""
    # 这里应该调用实际的任务执行器
    # 暂时返回一个模拟结果
    print(f"[TaskAlertRetryAPI] Executing task {task_id} (attempt {retry_count + 1})")
    return {"success": True, "message": "Task executed via callback"}


class TaskAlertRetryHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器"""
    
    # 共享实例
    alert_system = TaskFailureAlert(WORKSPACE)
    retry_system = TaskAutoRetry(WORKSPACE)
    monitor = TaskMonitor(WORKSPACE)
    
    # 集成：任务失败时自动重试 + 告警
    retry_system.set_execute_callback(execute_task_callback)
    
    def log_message(self, format, *args):
        print(f"[TaskAlertRetryAPI] {args[0]}")
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def get_param(self, name, default=None):
        query = self.path.split('?')[1] if '?' in self.path else ''
        params = dict(p.split('=') for p in query.split('&') if '=' in p)
        return params.get(name, default)
    
    def do_GET(self):
        path = self.path.split('?')[0]
        
        # 根路径
        if path == '/' or path == '':
            self.send_json({
                "service": "Task Alert & Retry API",
                "version": "1.0",
                "port": PORT,
                "endpoints": [
                    "/api/status - 系统状态",
                    "/api/alert/stats - 告警统计",
                    "/api/alert/active - 活跃告警",
                    "/api/alert/history - 告警历史",
                    "/api/retry/stats - 重试统计",
                    "/api/retry/pending - 待重试任务",
                    "/api/retry/status/<task_id> - 重试状态",
                    "/api/integrated/status - 集成状态概览",
                    "POST /api/task/fail - 报告任务失败（自动重试+告警）",
                    "POST /api/task/success - 报告任务成功（清除告警）"
                ]
            })
        
        # 告警统计
        elif path == '/api/alert/stats':
            stats = self.alert_system.get_statistics()
            self.send_json(stats)
        
        # 活跃告警
        elif path == '/api/alert/active':
            alerts = self.alert_system.get_active_alerts()
            self.send_json({"alerts": alerts, "count": len(alerts)})
        
        # 告警历史
        elif path == '/api/alert/history':
            hours = int(self.get_param('hours', 24))
            limit = int(self.get_param('limit', 50))
            history = self.alert_system.get_alert_history(hours, limit)
            self.send_json({"history": history, "count": len(history)})
        
        # 确认告警
        elif path == '/api/alert/ack':
            alert_id = self.get_param('alert_id')
            if alert_id:
                success = self.alert_system.acknowledge_alert(alert_id)
                self.send_json({"success": success})
            else:
                self.send_json({"error": "alert_id required"}, 400)
        
        # 重试统计
        elif path == '/api/retry/stats':
            stats = self.retry_system.get_statistics()
            self.send_json(stats)
        
        # 待重试任务
        elif path == '/api/retry/pending':
            pending = self.retry_system.get_pending_retries()
            self.send_json({"pending": pending, "count": len(pending)})
        
        # 重试状态
        elif path.startswith('/api/retry/status/'):
            task_id = path.split('/')[-1]
            status = self.retry_system.get_retry_status(task_id)
            if status:
                self.send_json(status)
            else:
                self.send_json({"error": "Not found"}, 404)
        
        # 取消重试
        elif path == '/api/retry/cancel':
            task_id = self.get_param('task_id')
            if task_id:
                success = self.retry_system.cancel_retry(task_id)
                self.send_json({"success": success})
            else:
                self.send_json({"error": "task_id required"}, 400)
        
        # 集成状态
        elif path == '/api/integrated/status':
            alert_stats = self.alert_system.get_statistics()
            retry_stats = self.retry_system.get_statistics()
            success_rate = self.monitor.get_success_rate(24)
            
            self.send_json({
                "status": "running",
                "timestamp": datetime.now().isoformat(),
                "alerts": alert_stats,
                "retries": retry_stats,
                "task_success_rate": success_rate
            })
        
        # 任务监控摘要
        elif path == '/api/task/summary':
            summary = self.monitor.get_summary()
            self.send_json(summary)
        
        # 失败任务
        elif path == '/api/task/failed':
            hours = int(self.get_param('hours', 24))
            failed = self.monitor.get_failed_tasks(hours)
            self.send_json({"failed": failed, "count": len(failed)})
        
        else:
            self.send_json({"error": "Not Found"}, 404)
    
    def do_POST(self):
        path = self.path
        
        # 报告任务失败 - 自动触发重试和告警
        if path == '/api/task/fail':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            
            task_id = data.get('task_id')
            agent_id = data.get('agent_id')
            error = data.get('error', 'Unknown error')
            retry_count = data.get('retry_count', 0)
            task_data = data.get('task_data', {})
            
            if not task_id or not agent_id:
                self.send_json({"error": "task_id and agent_id required"}, 400)
                return
            
            # 1. 记录到监控
            self.monitor.log_execution(
                execution_id=task_id,
                task=task_data.get('task_name', task_id),
                agent_id=agent_id,
                status="failed",
                start_time=data.get('start_time', datetime.now().isoformat()),
                end_time=datetime.now().isoformat(),
                error=error
            )
            
            # 2. 自动重试
            retry_result = None
            if retry_count < self.retry_system.max_retries:
                retry_id = self.retry_system.schedule_retry(
                    task_id=task_id,
                    agent_id=agent_id,
                    task_data=task_data,
                    retry_count=retry_count,
                    max_retries=data.get('max_retries', self.retry_system.max_retries)
                )
                retry_result = {"scheduled": True, "retry_id": retry_id, "retry_count": retry_count + 1}
            else:
                retry_result = {"scheduled": False, "reason": "max_retries_exceeded"}
            
            # 3. 检查是否需要告警
            alert_result = self.alert_system.check_failure(
                task_id=task_id,
                agent_id=agent_id,
                error=error,
                retry_count=retry_count
            )
            
            self.send_json({
                "status": "processed",
                "task_id": task_id,
                "retry": retry_result,
                "alert": {"sent": alert_result is not None, "details": alert_result} if alert_result else None
            })
        
        # 报告任务成功 - 清除相关告警
        elif path == '/api/task/success':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            
            task_id = data.get('task_id')
            agent_id = data.get('agent_id')
            
            if not task_id:
                self.send_json({"error": "task_id required"}, 400)
                return
            
            # 记录到监控
            self.monitor.log_execution(
                execution_id=task_id,
                task=data.get('task_name', task_id),
                agent_id=agent_id or 'unknown',
                status="completed",
                start_time=data.get('start_time', datetime.now().isoformat()),
                end_time=datetime.now().isoformat(),
                duration=data.get('duration')
            )
            
            # 清除告警
            self.alert_system.check_success(task_id)
            
            # 取消待处理的重试
            self.retry_system.cancel_retry(task_id)
            
            self.send_json({
                "status": "success",
                "task_id": task_id,
                "alert_cleared": True,
                "retry_cancelled": True
            })
        
        # 手动安排重试
        elif path == '/api/retry/schedule':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            
            retry_id = self.retry_system.schedule_retry(
                task_id=data['task_id'],
                agent_id=data['agent_id'],
                task_data=data.get('task_data', {}),
                retry_count=data.get('retry_count', 0),
                max_retries=data.get('max_retries'),
                delay=data.get('delay')
            )
            
            self.send_json({"status": "scheduled", "retry_id": retry_id})
        
        else:
            self.send_json({"error": "Not Found"}, 404)


def main():
    """启动API服务"""
    # 启动重试调度器
    handler = TaskAlertRetryHandler
    handler.retry_system.start_scheduler()
    
    server = HTTPServer(('0.0.0.0', PORT), handler)
    print(f"[TaskAlertRetryAPI] Starting on port {PORT}")
    print(f"[TaskAlertRetryAPI] Endpoints:")
    print(f"  - GET  /api/integrated/status - 集成状态")
    print(f"  - GET  /api/alert/stats - 告警统计")
    print(f"  - GET  /api/alert/active - 活跃告警")
    print(f"  - GET  /api/retry/stats - 重试统计")
    print(f"  - GET  /api/retry/pending - 待重试")
    print(f"  - POST /api/task/fail - 报告失败")
    print(f"  - POST /api/task/success - 报告成功")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[TaskAlertRetryAPI] Shutting down...")
        handler.retry_system.stop_scheduler()
        server.shutdown()


if __name__ == "__main__":
    main()