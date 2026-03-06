#!/usr/bin/env python3
"""
任务执行监控API服务
提供REST API访问任务执行监控数据
端口: 18190
"""

import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from pathlib import Path
import threading
import time

# 添加路径
sys.path.insert(0, str(Path(__file__).parent))

from task_monitor import TaskMonitor

PORT = 18195
WORKSPACE = "/root/.openclaw/workspace"

class TaskMonitorHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器"""
    
    monitor = TaskMonitor(WORKSPACE)
    
    def log_message(self, format, *args):
        """日志输出"""
        print(f"[TaskMonitorAPI] {args[0]}")
    
    def send_json(self, data, status=200):
        """发送JSON响应"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_GET(self):
        """处理GET请求"""
        path = self.path.split('?')[0]
        
        # 根路径
        if path == '/' or path == '':
            self.send_json({
                "service": "Task Monitor API",
                "version": "1.0",
                "port": PORT,
                "endpoints": [
                    "/api/status - 系统状态",
                    "/api/metrics - 监控指标",
                    "/api/executions - 执行记录",
                    "/api/executions/<id> - 单条执行记录",
                    "/api/running - 运行中任务",
                    "/api/failed - 失败任务",
                    "/api/success-rate - 成功率",
                    "/api/duration-stats - 执行时间统计",
                    "/api/summary - 监控摘要"
                ]
            })
        
        # 监控指标
        elif path == '/api/metrics':
            self.send_json(self.monitor.get_metrics())
        
        # 执行记录列表
        elif path == '/api/executions':
            limit = int(self.get_param('limit', 50))
            status = self.get_param('status', None)
            agent_id = self.get_param('agent_id', None)
            results = self.monitor.get_executions(
                agent_id=agent_id,
                status=status,
                limit=limit
            )
            self.send_json({"executions": results, "count": len(results)})
        
        # 运行中任务
        elif path == '/api/running':
            results = self.monitor.get_running_tasks()
            self.send_json({"running": results, "count": len(results)})
        
        # 失败任务
        elif path == '/api/failed':
            hours = int(self.get_param('hours', 24))
            results = self.monitor.get_failed_tasks(hours)
            self.send_json({"failed": results, "count": len(results)})
        
        # 成功率
        elif path == '/api/success-rate':
            hours = int(self.get_param('hours', 24))
            self.send_json(self.monitor.get_success_rate(hours))
        
        # 执行时间统计
        elif path == '/api/duration-stats':
            hours = int(self.get_param('hours', 24))
            self.send_json(self.monitor.get_duration_stats(hours))
        
        # 监控摘要
        elif path == '/api/summary':
            self.send_json(self.monitor.get_summary())
        
        # 系统状态
        elif path == '/api/status':
            summary = self.monitor.get_summary()
            self.send_json({
                "status": "running",
                "timestamp": datetime.now().isoformat(),
                "metrics": summary
            })
        
        else:
            self.send_json({"error": "Not Found"}, 404)
    
    def do_POST(self):
        """处理POST请求"""
        path = self.path
        
        # 记录执行
        if path == '/api/log':
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode())
            
            self.monitor.log_execution(
                execution_id=data.get('execution_id'),
                task=data.get('task'),
                agent_id=data.get('agent_id'),
                status=data.get('status'),
                start_time=data.get('start_time'),
                end_time=data.get('end_time'),
                duration=data.get('duration'),
                error=data.get('error'),
                stdout=data.get('stdout'),
                stderr=data.get('stderr')
            )
            
            self.send_json({"status": "ok", "message": "Execution logged"})
        
        else:
            self.send_json({"error": "Not Found"}, 404)
    
    def get_param(self, name, default=None):
        """获取查询参数"""
        query = self.path.split('?')[1] if '?' in self.path else ''
        params = dict(p.split('=') for p in query.split('&') if '=' in p)
        return params.get(name, default)


def main():
    """启动API服务"""
    server = HTTPServer(('0.0.0.0', PORT), TaskMonitorHandler)
    print(f"[TaskMonitorAPI] Starting on port {PORT}")
    print(f"[TaskMonitorAPI] Dashboard: http://localhost:{PORT}/")
    print(f"[TaskMonitorAPI] Endpoints:")
    print(f"  - GET  /api/metrics")
    print(f"  - GET  /api/executions")
    print(f"  - GET  /api/running")
    print(f"  - GET  /api/failed")
    print(f"  - GET  /api/success-rate")
    print(f"  - GET  /api/summary")
    print(f"  - POST /api/log")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[TaskMonitorAPI] Shutting down...")
        server.shutdown()


if __name__ == "__main__":
    main()