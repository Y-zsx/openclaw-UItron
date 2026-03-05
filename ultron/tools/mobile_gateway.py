#!/usr/bin/env python3
"""
移动端API网关 - 为移动设备提供轻量级接口
端口: 18096
"""
import json
import subprocess
import psutil
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

PORT = 18096

def get_system_status():
    """获取系统状态"""
    try:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return {
            "cpu": cpu,
            "memory_percent": mem.percent,
            "memory_used_gb": round(mem.used / (1024**3), 2),
            "memory_total_gb": round(mem.total / (1024**3), 2),
            "disk_percent": disk.percent,
            "uptime": get_uptime()
        }
    except Exception as e:
        return {"error": str(e)}

def get_uptime():
    """获取系统运行时间"""
    try:
        with open('/proc/uptime', 'r') as f:
            seconds = float(f.readline().split()[0])
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    except:
        return "unknown"

def get_services_status():
    """获取服务状态"""
    services = ["openclaw", "gateway"]
    result = {}
    for svc in services:
        try:
            check = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True, timeout=5
            )
            result[svc] = "running" if check.returncode == 0 else "stopped"
        except:
            result[svc] = "unknown"
    return result

def get_openclaw_status():
    """获取OpenClaw状态"""
    try:
        result = subprocess.run(
            ["openclaw", "status", "--json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return {"error": "Failed to get status"}
    except Exception as e:
        return {"error": str(e)}

class MobileHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 静默日志
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_GET(self):
        path = self.path.strip('/')
        
        if path == '' or path == 'status':
            # 简化的状态API
            status = get_system_status()
            services = get_services_status()
            self.send_json({
                "status": "ok",
                "timestamp": datetime.now().isoformat(),
                "system": status,
                "services": services
            })
        
        elif path == 'full':
            # 完整状态
            self.send_json({
                "status": "ok",
                "timestamp": datetime.now().isoformat(),
                "system": get_system_status(),
                "services": get_services_status(),
                "openclaw": get_openclaw_status()
            })
        
        elif path == 'health':
            # 健康检查
            sys_stat = get_system_status()
            if sys_stat.get("error"):
                self.send_json({"healthy": False, "reason": sys_stat["error"]}, 503)
            elif sys_stat.get("cpu", 0) > 90:
                self.send_json({"healthy": False, "reason": "High CPU"}, 503)
            else:
                self.send_json({"healthy": True})
        
        else:
            self.send_json({"error": "Not found"}, 404)

def main():
    server = HTTPServer(('0.0.0.0', PORT), MobileHandler)
    print(f"移动端API网关运行在端口 {PORT}")
    print(f"端点: /status, /full, /health")
    server.serve_forever()

if __name__ == '__main__':
    main()