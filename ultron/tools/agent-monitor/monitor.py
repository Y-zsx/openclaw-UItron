#!/usr/bin/env python3
"""
Agent服务监控与告警系统
端口: 18146
功能: 实时监控Agent服务健康状态、指标收集、告警触发
"""
import os
import sys
import time
import socket
import psutil
import json
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 配置
PORT = 18148
ALERT_THRESHOLDS = {
    'cpu_percent': 80,      # CPU使用率 > 80% 告警
    'memory_percent': 85,   # 内存使用率 > 85% 告警
    'disk_percent': 90,     # 磁盘使用率 > 90% 告警
    'port_down': 1          # 端口故障告警
}

# 告警历史
alerts = []
alert_stats = {
    'total': 0,
    'critical': 0,
    'warning': 0,
    'info': 0
}

# 服务端口列表
AGENT_PORTS = {
    18120: 'Decision Engine',
    18122: 'Alert Rules',
    18123: 'Monitor Panel',
    18124: 'Notifier',
    18125: 'Predictor',
    18132: 'Workflow',
    18135: 'Decision-Action',
    18143: 'Auto Scale',
    18144: 'Load Balancer',
    18145: 'Admin Panel',
    18148: 'Agent Monitor',
    18149: 'Predictive Maintenance'
}

class MonitorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == '/health' or path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            resp = {'status': 'ok', 'service': 'agent-monitor', 'port': PORT}
            self.wfile.write(json.dumps(resp).encode())
            
        elif path == '/metrics':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            metrics = get_metrics()
            self.wfile.write(json.dumps(metrics, indent=2).encode())
            
        elif path == '/status':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            status = get_service_status()
            self.wfile.write(json.dumps(status, indent=2).encode())
            
        elif path == '/alerts':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            resp = {
                'alerts': alerts[-50:],  # 最近50条
                'stats': alert_stats
            }
            self.wfile.write(json.dumps(resp, indent=2).encode())
            
        elif path == '/thresholds':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(ALERT_THRESHOLDS, indent=2).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
            
    def log_message(self, format, *args):
        pass

def check_port(port):
    """检查端口是否开放"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except:
        return False

def get_metrics():
    """获取系统指标"""
    return {
        'timestamp': datetime.now().isoformat(),
        'cpu_percent': psutil.cpu_percent(interval=0.5),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_percent': psutil.disk_usage('/').percent,
        'load_avg': os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0],
        'process_count': len(psutil.pids())
    }

def get_service_status():
    """获取所有Agent服务状态"""
    status = {}
    for port, name in AGENT_PORTS.items():
        is_up = check_port(port)
        status[port] = {
            'name': name,
            'port': port,
            'up': is_up,
            'status': 'UP' if is_up else 'DOWN'
        }
    
    # 总体健康状态
    up_count = sum(1 for s in status.values() if s['up'])
    total = len(status)
    health = 'healthy' if up_count == total else ('degraded' if up_count > total/2 else 'critical')
    
    return {
        'services': status,
        'summary': {
            'total': total,
            'up': up_count,
            'down': total - up_count,
            'health': health
        },
        'timestamp': datetime.now().isoformat()
    }

def check_and_alert():
    """检查指标并触发告警"""
    global alerts, alert_stats
    
    metrics = get_metrics()
    service_status = get_service_status()
    
    # 检查系统指标告警
    for key, threshold in ALERT_THRESHOLDS.items():
        if key == 'port_down':
            for port, info in service_status['services'].items():
                if not info['up']:
                    alert = {
                        'type': 'port_down',
                        'severity': 'critical',
                        'message': f"服务端口 {port} ({info['name']}) 不可用",
                        'port': port,
                        'timestamp': datetime.now().isoformat()
                    }
                    alerts.append(alert)
                    alert_stats['total'] += 1
                    alert_stats['critical'] += 1
        else:
            value = metrics.get(key)
            if value and value > threshold:
                severity = 'critical' if value > threshold * 1.1 else 'warning'
                alert = {
                    'type': key,
                    'severity': severity,
                    'message': f"{key} = {value:.1f}% (阈值: {threshold}%)",
                    'value': value,
                    'threshold': threshold,
                    'timestamp': datetime.now().isoformat()
                }
                alerts.append(alert)
                alert_stats['total'] += 1
                if severity == 'critical':
                    alert_stats['critical'] += 1
                else:
                    alert_stats['warning'] += 1
    
    # 保持告警历史不超过1000条
    if len(alerts) > 1000:
        alerts = alerts[-1000:]

def background_monitor(interval=30):
    """后台监控线程"""
    while True:
        check_and_alert()
        time.sleep(interval)

if __name__ == '__main__':
    # 启动后台监控线程
    monitor_thread = threading.Thread(target=background_monitor, daemon=True)
    monitor_thread.start()
    
    # 启动HTTP服务
    server = HTTPServer(('0.0.0.0', PORT), MonitorHandler)
    print(f"Agent Monitor Service started on port {PORT}")
    print(f"Endpoints:")
    print(f"  /health  - 健康检查")
    print(f"  /metrics - 系统指标")
    print(f"  /status  - 服务状态")
    print(f"  /alerts  - 告警历史")
    print(f"  /thresholds - 告警阈值")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()