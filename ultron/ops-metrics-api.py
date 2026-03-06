#!/usr/bin/env python3
"""
智能运维助手 - 实时指标API服务
为增强版仪表板提供实时数据
"""

import json
import os
import sys
import time
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime
from pathlib import Path
import threading

# 尝试导入psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️ psutil not available, using basic metrics")

_ops_dir = os.path.dirname(os.path.abspath(__file__))
os.chdir(_ops_dir)

class MetricsHandler(SimpleHTTPRequestHandler):
    """处理指标请求"""
    
    def do_GET(self):
        if self.path == '/api/metrics' or self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            metrics = self.collect_metrics()
            self.wfile.write(json.dumps(metrics, default=str).encode())
        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            status = {
                "status": "running",
                "service": "ops-metrics-api",
                "port": self.server.server_address[1],
                "timestamp": datetime.now().isoformat(),
                "endpoints": ["/api/metrics", "/metrics", "/status", "/health"]
            }
            self.wfile.write(json.dumps(status, default=str).encode())
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        elif self.path == '/procs':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            procs = self.get_processes()
            self.wfile.write(json.dumps(procs, default=str).encode())
        else:
            # 静态文件服务
            super().do_GET()
    
    def collect_metrics(self):
        """采集系统指标"""
        now = datetime.now().isoformat()
        
        if PSUTIL_AVAILABLE:
            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net_io = psutil.net_io_counters()
            load = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
            
            return {
                "timestamp": now,
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": psutil.cpu_count()
                },
                "memory": {
                    "percent": memory.percent,
                    "used": memory.used,
                    "total": memory.total,
                    "available": memory.available
                },
                "disk": {
                    "disks": [{
                        "percent": disk.percent,
                        "used": disk.used,
                        "total": disk.total
                    }]
                },
                "network": {
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv,
                    "errin": net_io.errin,
                    "errout": net_io.errout
                },
                "load": {
                    "1min": load[0],
                    "5min": load[1],
                    "15min": load[2]
                },
                "processes": len(psutil.pids())
            }
        else:
            # 基础指标
            return {
                "timestamp": now,
                "cpu": {"usage_percent": 0},
                "memory": {"percent": 0},
                "disk": {"disks": [{"percent": 0}]},
                "network": {}
            }
    
    def get_processes(self):
        """获取进程列表"""
        if not PSUTIL_AVAILABLE:
            return []
        
        processes = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                pinfo = p.info
                if pinfo['name']:
                    processes.append({
                        'pid': pinfo['pid'],
                        'name': pinfo['name'][:50],  # 限制长度
                        'cpu': pinfo['cpu_percent'] or 0,
                        'memory': pinfo['memory_percent'] or 0,
                        'status': pinfo['status'] or 'unknown'
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # 按CPU排序，返回前15个
        processes.sort(key=lambda x: x['cpu'], reverse=True)
        return processes[:15]
    
    def log_message(self, format, *args):
        # 减少日志输出
        pass


def run_server(port=8080):
    """启动API服务"""
    server = HTTPServer(('0.0.0.0', port), MetricsHandler)
    print(f"🚀 智能运维API服务启动: http://0.0.0.0:{port}")
    print(f"📊 指标端点: http://0.0.0.0:{port}/api/metrics")
    print(f"📁 静态文件: {os.getcwd()}")
    print("\n按 Ctrl+C 停止服务\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 服务已停止")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="智能运维API服务")
    parser.add_argument("--port", type=int, default=8080, help="服务端口")
    args = parser.parse_args()
    
    run_server(args.port)