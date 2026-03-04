#!/usr/bin/env python3
"""
简单服务器状态面板 - 奥创自制
"""
import os
import json
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler

PORT = 8888

def get_server_stats():
    """获取服务器状态"""
    # CPU负载
    with open('/proc/loadavg', 'r') as f:
        load = f.read().split()[:3]
    
    # 内存
    mem_info = {}
    with open('/proc/meminfo', 'r') as f:
        for line in f:
            if line.startswith('MemTotal:'):
                mem_info['total'] = int(line.split()[1])
            elif line.startswith('MemAvailable:'):
                mem_info['available'] = int(line.split()[1])
    
    mem_used = mem_info['total'] - mem_info['available']
    mem_percent = (mem_used / mem_info['total']) * 100
    
    # 磁盘
    disk = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
    disk_parts = disk.stdout.split('\n')[1].split()
    disk_used = disk_parts[2]
    disk_total = disk_parts[1]
    disk_percent = int(disk_parts[4].replace('%', ''))
    
    # 运行时间
    uptime = subprocess.run(['uptime', '-p'], capture_output=True, text=True)
    
    return {
        'cpu': round(float(load[0]) * 100 / os.cpu_count(), 1) if os.cpu_count() else 0,
        'load': load,
        'memPercent': round(mem_percent, 1),
        'memUsed': f"{mem_used // 1024}MB",
        'memTotal': f"{mem_info['total'] // 1024}MB",
        'diskPercent': disk_percent,
        'diskUsed': disk_used,
        'diskTotal': disk_total,
        'uptime': uptime.stdout.strip() or 'Unknown'
    }

class MyHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/stats':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            stats = get_server_stats()
            self.wfile.write(json.dumps(stats).encode())
        else:
            super().do_GET()
    
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {args[0]}")

print(f"🚀 状态面板启动中: http://localhost:{PORT}")
print(f"📂 静态文件目录: {os.path.dirname(os.path.abspath(__file__))}")

os.chdir(os.path.dirname(os.path.abspath(__file__)))
server = HTTPServer(('0.0.0.0', PORT), MyHandler)
server.serve_forever()