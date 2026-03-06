#!/usr/bin/env python3
"""
智能运维助手 - 实时指标API服务 (增强版)
为增强版仪表板提供实时数据
端口: 18220 (默认)
"""

import json
import os
import sys
import time
import subprocess
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

# 增强: 存储历史数据用于趋势分析
_metrics_history = []
MAX_HISTORY = 60  # 保留60条历史记录

class MetricsHandler(SimpleHTTPRequestHandler):
    """处理指标请求"""
    
    def do_GET(self):
        if self.path == '/api/metrics' or self.path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            metrics = self.collect_metrics()
            # 添加到历史记录
            self._add_to_history(metrics)
            self.wfile.write(json.dumps(metrics, default=str).encode())
            
        elif self.path == '/api/trends':
            # 新增: 趋势数据
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            trends = self.get_trends()
            self.wfile.write(json.dumps(trends, default=str).encode())
            
        elif self.path == '/api/services':
            # 新增: 服务状态
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            services = self.get_services_status()
            self.wfile.write(json.dumps(services, default=str).encode())
            
        elif self.path == '/api/openclaw':
            # 新增: OpenClaw状态
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            oc_status = self.get_openclaw_status()
            self.wfile.write(json.dumps(oc_status, default=str).encode())
            
        elif self.path == '/api/alerts':
            # 新增: 告警状态
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            alerts = self.get_alert_summary()
            self.wfile.write(json.dumps(alerts, default=str).encode())
            
        elif self.path == '/api/summary':
            # 新增: 综合摘要
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            summary = self.get_summary()
            self.wfile.write(json.dumps(summary, default=str).encode())
            
        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            status = {
                "status": "running",
                "service": "ops-metrics-api-enhanced",
                "port": self.server.server_address[1],
                "timestamp": datetime.now().isoformat(),
                "endpoints": [
                    "/api/metrics", "/api/trends", "/api/services",
                    "/api/openclaw", "/api/alerts", "/api/summary",
                    "/metrics", "/status", "/health", "/procs"
                ],
                "version": "2.0"
            }
            self.wfile.write(json.dumps(status, default=str).encode())
            
        elif self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "ops-metrics-api"}).encode())
            
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
    
    def _add_to_history(self, metrics):
        """添加到历史记录"""
        global _metrics_history
        _metrics_history.append({
            "timestamp": metrics.get("timestamp"),
            "cpu": metrics.get("cpu", {}).get("usage_percent", 0),
            "memory": metrics.get("memory", {}).get("percent", 0),
            "disk": metrics.get("disk", {}).get("disks", [{}])[0].get("percent", 0)
        })
        if len(_metrics_history) > MAX_HISTORY:
            _metrics_history = _metrics_history[-MAX_HISTORY:]
    
    def get_trends(self):
        """获取趋势数据"""
        global _metrics_history
        return {
            "history": _metrics_history,
            "count": len(_metrics_history)
        }
    
    def collect_metrics(self):
        """采集系统指标"""
        now = datetime.now().isoformat()
        
        if PSUTIL_AVAILABLE:
            cpu_percent = psutil.cpu_percent(interval=0.5)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            net_io = psutil.net_io_counters()
            load = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
            
            # 获取温度 (如果可用)
            temps = {}
            try:
                if hasattr(psutil, "sensors_temperatures"):
                    temps = psutil.sensors_temperatures()
            except:
                pass
            
            return {
                "timestamp": now,
                "cpu": {
                    "usage_percent": cpu_percent,
                    "count": psutil.cpu_count(),
                    "load": load
                },
                "memory": {
                    "percent": memory.percent,
                    "used": memory.used,
                    "total": memory.total,
                    "available": memory.available,
                    "used_mb": round(memory.used / 1024 / 1024, 2),
                    "total_mb": round(memory.total / 1024 / 1024, 2)
                },
                "disk": {
                    "disks": [{
                        "percent": disk.percent,
                        "used": disk.used,
                        "total": disk.total,
                        "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                        "total_gb": round(disk.total / 1024 / 1024 / 1024, 2)
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
                "processes": len(psutil.pids()),
                "temperatures": temps
            }
        else:
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
                        'name': pinfo['name'][:50],
                        'cpu': round(pinfo['cpu_percent'] or 0, 1),
                        'memory': round(pinfo['memory_percent'] or 0, 2),
                        'status': pinfo['status'] or 'unknown'
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        processes.sort(key=lambda x: x['cpu'], reverse=True)
        return processes[:20]
    
    def get_services_status(self):
        """获取关键服务状态"""
        services = []
        
        # 检查OpenClaw Gateway
        services.append(self._check_service("openclaw-gateway", "Gateway", 18789))
        
        # 检查各类服务端口
        service_ports = {
            "ops-metrics-api": 18220,
            "health-check-api": 18210,
            "integration-tester": 18228,
            "self-healer": 18227,
            "scheduler-perf": 18218,
            "alert-history": 18217,
            "task-monitor": 18219,
        }
        
        for name, port in service_ports.items():
            services.append(self._check_port(name, port))
        
        return services
    
    def _check_service(self, process_name, display_name, port=None):
        """检查服务状态"""
        status = "stopped"
        pid = None
        
        if PSUTIL_AVAILABLE:
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    if process_name in p.info['name'].lower():
                        status = "running"
                        pid = p.info['pid']
                        break
                except:
                    pass
        
        result = {
            "name": display_name,
            "process": process_name,
            "status": status,
            "pid": pid
        }
        
        if port:
            result["port"] = port
            
        return result
    
    def _check_port(self, name, port):
        """检查端口是否在监听"""
        status = "stopped"
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            status = "running" if result == 0 else "stopped"
        except:
            pass
        
        return {"name": name, "port": port, "status": status}
    
    def get_openclaw_status(self):
        """获取OpenClaw状态"""
        status = {
            "gateway": "unknown",
            "browser": "unknown",
            "channels": [],
            "tools": "unknown"
        }
        
        # 检查Gateway进程
        if PSUTIL_AVAILABLE:
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    name = p.info.get('name', '')
                    if 'openclaw-gateway' in name.lower() or 'gateway' in name.lower():
                        status["gateway"] = "running"
                        status["gateway_pid"] = p.info.get('pid')
                        break
                except:
                    pass
        
        # 检查浏览器
        for p in psutil.process_iter(['pid', 'name']):
            try:
                if 'chrome' in p.info['name'].lower() or 'chromium' in p.info['name'].lower():
                    status["browser"] = "running"
                    break
            except:
                pass
        
        # 简化: 检查渠道相关进程
        channels = []
        for p in psutil.process_iter(['pid', 'name']):
            try:
                name = p.info.get('name', '').lower()
                if 'clawdbot' in name or 'telegram' in name or 'discord' in name:
                    channels.append(p.info['name'])
            except:
                pass
        
        status["channels"] = channels if channels else ["dingtalk"]
        
        return status
    
    def get_alert_summary(self):
        """获取告警摘要"""
        # 尝试从数据库或API获取
        alerts = {
            "critical": 0,
            "warning": 0,
            "info": 0,
            "total": 0,
            "recent": []
        }
        
        # 检查告警相关进程
        if PSUTIL_AVAILABLE:
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    name = p.info.get('name', '').lower()
                    if 'alert' in name or 'healer' in name:
                        # 简化: 标记为有告警系统运行
                        alerts["has_alert_system"] = True
                except:
                    pass
        
        return alerts
    
    def get_summary(self):
        """获取综合摘要"""
        metrics = self.collect_metrics()
        services = self.get_services_status()
        oc_status = self.get_openclaw_status()
        
        # 计算健康分数
        health_score = 100
        running_services = sum(1 for s in services if s.get("status") == "running")
        total_services = len(services)
        
        if total_services > 0:
            service_ratio = running_services / total_services
            health_score = round(service_ratio * 100)
        
        # CPU和内存扣分
        cpu = metrics.get("cpu", {}).get("usage_percent", 0)
        mem = metrics.get("memory", {}).get("percent", 0)
        
        if cpu > 90:
            health_score -= 20
        elif cpu > 80:
            health_score -= 10
            
        if mem > 90:
            health_score -= 20
        elif mem > 80:
            health_score -= 10
        
        health_score = max(0, min(100, health_score))
        
        return {
            "timestamp": metrics.get("timestamp"),
            "health_score": health_score,
            "status": "healthy" if health_score >= 70 else "warning" if health_score >= 50 else "critical",
            "cpu": cpu,
            "memory": mem,
            "disk": metrics.get("disk", {}).get("disks", [{}])[0].get("percent", 0),
            "services": {
                "total": total_services,
                "running": running_services,
                "stopped": total_services - running_services
            },
            "uptime": self._get_uptime(),
            "openclaw": oc_status.get("gateway", "unknown")
        }
    
    def _get_uptime(self):
        """获取系统运行时间"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.readline().split()[0])
                days = int(uptime_seconds / 86400)
                hours = int((uptime_seconds % 86400) / 3600)
                minutes = int((uptime_seconds % 3600) / 60)
                return f"{days}天 {hours}小时 {minutes}分钟"
        except:
            return "unknown"
    
    def log_message(self, format, *args):
        pass


def run_server(port=18220):
    """启动API服务"""
    server = HTTPServer(('0.0.0.0', port), MetricsHandler)
    print(f"🚀 智能运维API服务(增强版)启动: http://0.0.0.0:{port}")
    print(f"📊 指标端点: http://0.0.0.0:{port}/api/metrics")
    print(f"📈 趋势端点: http://0.0.0.0:{port}/api/trends")
    print(f"🔧 服务状态: http://0.0.0.0:{port}/api/services")
    print(f"🤖 OpenClaw: http://0.0.0.0:{port}/api/openclaw")
    print(f"📋 综合摘要: http://0.0.0.0:{port}/api/summary")
    print(f"📁 静态文件: {os.getcwd()}")
    print("\n按 Ctrl+C 停止服务\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 服务已停止")
        server.shutdown()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="智能运维API服务(增强版)")
    parser.add_argument("--port", type=int, default=18220, help="服务端口")
    args = parser.parse_args()
    
    run_server(args.port)