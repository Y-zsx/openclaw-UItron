#!/usr/bin/env python3
"""
增强版健康报告API服务
集成健康检查日志，提供历史趋势分析和可视化数据
"""
import json
import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import socket

# 配置
PORT = 18140
DB_PATH = Path("/root/.openclaw/workspace/ultron/data/health_check_logs.db")
REPORTS_DIR = Path("/root/.openclaw/workspace/ultron/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def init_db():
    """初始化数据库"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            service_name TEXT NOT NULL,
            port INTEGER,
            port_status INTEGER,
            http_status INTEGER,
            latency_ms REAL,
            status TEXT,
            details TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            service_name TEXT NOT NULL,
            alert_type TEXT,
            message TEXT,
            resolved INTEGER DEFAULT 0,
            resolved_at TEXT
        )
    ''')
    
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hc_timestamp ON health_checks(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hc_service ON health_checks(service_name)')
    
    conn.commit()
    conn.close()

def check_port(host, port, timeout=2):
    """检查端口"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def perform_health_check():
    """执行健康检查并记录"""
    services = {
        "gateway": {"host": "127.0.0.1", "port": 18789},
        "browser": {"host": "127.0.0.1", "port": 18800},
        "executor_api": {"host": "127.0.0.1", "port": 18210},
        "decision_api": {"host": "127.0.0.1", "port": 18120},
        "automation_api": {"host": "127.0.0.1", "port": 18128},
        "workflow_api": {"host": "127.0.0.1", "port": 18100},
        "agent_network": {"host": "127.0.0.1", "port": 18150},
        "collab_api": {"host": "127.0.0.1", "port": 8100},
    }
    
    import requests
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    results = []
    
    for name, config in services.items():
        host, port = config['host'], config['port']
        port_ok = check_port(host, port)
        http_ok = False
        latency = 0
        
        if port_ok:
            try:
                import time
                start = time.time()
                r = requests.get(f'http://{host}:{port}/health', timeout=3)
                latency = (time.time() - start) * 1000
                http_ok = r.status_code == 200
            except:
                pass
        
        status = "healthy" if port_ok and http_ok else "unhealthy"
        
        cursor.execute('''
            INSERT INTO health_checks 
            (timestamp, service_name, port, port_status, http_status, latency_ms, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (timestamp, name, port, port_ok, 200 if http_ok else 0, latency, status))
        
        results.append({
            "service": name,
            "port": port,
            "status": status,
            "latency_ms": round(latency, 2)
        })
    
    conn.commit()
    conn.close()
    
    return results

def get_availability(hours=24):
    """获取可用性统计"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    cursor.execute('''
        SELECT 
            service_name,
            COUNT(*) as total,
            SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy,
            AVG(latency_ms) as avg_latency
        FROM health_checks
        WHERE timestamp >= ?
        GROUP BY service_name
    ''', (since,))
    
    results = []
    for row in cursor.fetchall():
        service, total, healthy, avg_lat = row
        uptime = (healthy / total * 100) if total > 0 else 0
        results.append({
            "service": service,
            "total_checks": total,
            "healthy_checks": healthy,
            "uptime_percent": round(uptime, 2),
            "avg_latency_ms": round(avg_lat, 2) if avg_lat else 0
        })
    
    conn.close()
    return results

def get_trend(service_name, hours=24):
    """获取趋势数据"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    # 按分钟聚合
    cursor.execute('''
        SELECT 
            strftime('%Y-%m-%d %H:%M', timestamp) as minute,
            COUNT(*) as total,
            SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy,
            AVG(latency_ms) as avg_latency
        FROM health_checks
        WHERE service_name = ? AND timestamp >= ?
        GROUP BY minute
        ORDER BY minute
    ''', (service_name, since))
    
    trend = []
    for row in cursor.fetchall():
        minute, total, healthy, avg_lat = row
        uptime = (healthy / total * 100) if total > 0 else 0
        trend.append({
            "time": minute,
            "uptime_percent": round(uptime, 2),
            "latency_ms": round(avg_lat, 2) if avg_lat else 0
        })
    
    conn.close()
    return trend

def generate_report():
    """生成健康报告"""
    availability = get_availability(24)
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # 最近失败事件
    cursor.execute('''
        SELECT timestamp, service_name, status, latency_ms
        FROM health_checks
        WHERE status = 'unhealthy'
        ORDER BY timestamp DESC
        LIMIT 10
    ''')
    failures = [{"timestamp": r[0], "service": r[1], "status": r[2], "latency": r[3]} for r in cursor.fetchall()]
    
    # 活跃告警
    cursor.execute('''
        SELECT id, timestamp, service_name, alert_type, message
        FROM health_alerts
        WHERE resolved = 0
        ORDER BY timestamp DESC
    ''')
    alerts = [{"id": r[0], "timestamp": r[1], "service": r[2], "type": r[3], "message": r[4]} for r in cursor.fetchall()]
    
    conn.close()
    
    # 计算健康分数
    total = len(availability)
    healthy = sum(1 for a in availability if a["uptime_percent"] >= 99)
    health_score = (healthy / total * 100) if total > 0 else 0
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "health_score": round(health_score, 2),
        "services": availability,
        "recent_failures": failures,
        "active_alerts": alerts,
        "recommendation": "All systems operational" if health_score >= 95 else "Needs attention"
    }
    
    # 保存报告
    report_file = REPORTS_DIR / f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return report

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        
        elif path == '/check':
            # 执行健康检查
            results = perform_health_check()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"results": results}).encode())
        
        elif path == '/availability':
            hours = int(params.get('hours', [24])[0])
            data = get_availability(hours)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        
        elif path == '/trend':
            service = params.get('service', ['gateway'])[0]
            hours = int(params.get('hours', [24])[0])
            data = get_trend(service, hours)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        
        elif path == '/report':
            data = generate_report()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data, indent=2).encode())
        
        elif path == '/summary':
            # 简洁汇总
            availability = get_availability(24)
            total = len(availability)
            healthy = sum(1 for a in availability if a["uptime_percent"] >= 99)
            health_score = (healthy / total * 100) if total > 0 else 0
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "score": round(health_score, 2),
                "services": total,
                "healthy": healthy,
                "timestamp": datetime.now().isoformat()
            }).encode())
        
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # 抑制日志

def main():
    init_db()
    
    # 先执行一次健康检查
    print("执行初始健康检查...")
    results = perform_health_check()
    print(f"检查了 {len(results)} 个服务")
    
    # 启动API服务
    server = HTTPServer(('0.0.0.0', PORT), RequestHandler)
    print(f"健康报告API服务运行在端口 {PORT}")
    print(f"端点:")
    print(f"  /health     - 健康检查")
    print(f"  /check      - 执行健康检查")
    print(f"  /availability?hours=24 - 可用性统计")
    print(f"  /trend?service=gateway&hours=24 - 趋势数据")
    print(f"  /report     - 生成报告")
    print(f"  /summary    - 简洁汇总")
    
    server.serve_forever()

if __name__ == "__main__":
    main()