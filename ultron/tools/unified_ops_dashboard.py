#!/usr/bin/env python3
"""
统一运维Dashboard - 整合所有运维服务
Port: 18200
"""
import json
import time
import sqlite3
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import subprocess
import requests

PORT = 18200

# 服务端口映射
SERVICES = {
    "health_monitor": 18140,
    "performance_monitor": 18141,
    "deployment_manager": 18145,
    "monitor_alert": 18146,
    "log_aggregator": 18147,
    "auto_scaler": 18160,
    "load_balancer": 18161,
    "fault_predictor": 18170,
    "auto_healer": 18180,
    "auto_report": 18190,
    "queue_lb_unified": 18162,
    "config_manager": 18163,
}

def get_service_status(port):
    """检查服务状态"""
    try:
        resp = requests.get(f"http://localhost:{port}/health", timeout=2)
        return {"status": "online", "code": resp.status_code}
    except requests.exceptions.ConnectionError:
        return {"status": "offline", "code": 0}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def get_system_metrics():
    """获取系统指标"""
    try:
        # CPU
        cpu = subprocess.check_output(
            "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1",
            shell=True
        ).decode().strip() or "0"
        
        # 内存
        mem = subprocess.check_output(
            "free | grep Mem | awk '{printf \"%.1f\", $3/$2 * 100}'",
            shell=True
        ).decode().strip() or "0"
        
        # 磁盘
        disk = subprocess.check_output(
            "df -h / | tail -1 | awk '{print $5}' | cut -d'%' -f1",
            shell=True
        ).decode().strip() or "0"
        
        # 负载
        load = subprocess.check_output(
            "uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | cut -d',' -f1",
            shell=True
        ).decode().strip() or "0"
        
        return {
            "cpu_usage": float(cpu) if cpu else 0,
            "memory_usage": float(mem) if mem else 0,
            "disk_usage": float(disk) if disk else 0,
            "load_avg": float(load) if load else 0,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

def get_all_services_status():
    """获取所有运维服务状态"""
    result = {}
    for name, port in SERVICES.items():
        result[name] = get_service_status(port)
        result[name]["port"] = port
    return result

def get_recent_alerts():
    """获取最近告警"""
    alerts = []
    try:
        conn = sqlite3.connect('/root/.openclaw/workspace/ultron/tools/alerts.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, service, level, message, created_at 
            FROM alerts 
            ORDER BY created_at DESC LIMIT 10
        """)
        for row in cursor.fetchall():
            alerts.append({
                "id": row[0],
                "service": row[1],
                "level": row[2],
                "message": row[3],
                "created_at": row[4]
            })
        conn.close()
    except:
        pass
    return alerts

def get_recent_logs():
    """获取最近日志统计"""
    try:
        conn = sqlite3.connect('/root/.openclaw/workspace/ultron/tools/logs.db')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) as total, level, source 
            FROM logs 
            WHERE timestamp > datetime('now', '-1 hour')
            GROUP BY level, source
            LIMIT 20
        """)
        stats = []
        for row in cursor.fetchall():
            stats.append({
                "count": row[0],
                "level": row[1],
                "source": row[2]
            })
        conn.close()
        return stats
    except Exception as e:
        return [{"error": str(e)}]

def get_dashboard_summary():
    """获取Dashboard摘要"""
    system = get_system_metrics()
    services = get_all_services_status()
    alerts = get_recent_alerts()
    logs = get_recent_logs()
    
    # 计算健康分
    online_count = sum(1 for s in services.values() if s.get("status") == "online")
    total_count = len(services)
    service_health = (online_count / total_count) * 100 if total_count > 0 else 0
    
    # 系统资源健康
    system_health = 100
    if system.get("cpu_usage", 0) > 80: system_health -= 20
    if system.get("memory_usage", 0) > 80: system_health -= 20
    if system.get("disk_usage", 0) > 80: system_health -= 20
    if system.get("load_avg", 0) > 4: system_health -= 10
    
    # 告警健康
    alert_health = 100
    critical_alerts = [a for a in alerts if a.get("level") == "critical"]
    alert_health -= len(critical_alerts) * 15
    
    # 综合健康分
    overall_health = (service_health * 0.4 + system_health * 0.4 + max(0, alert_health) * 0.2)
    
    return {
        "overall_health": round(overall_health, 1),
        "service_health": round(service_health, 1),
        "system_health": round(system_health, 1),
        "alert_health": round(max(0, alert_health), 1),
        "services_online": online_count,
        "services_total": total_count,
        "recent_alerts_count": len(alerts),
        "critical_alerts": len(critical_alerts),
        "last_hour_logs": sum(l.get("count", 0) for l in logs),
        "timestamp": datetime.now().isoformat()
    }

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == "/" or path == "/dashboard":
            # 完整Dashboard
            summary = get_dashboard_summary()
            services = get_all_services_status()
            alerts = get_recent_alerts()
            system = get_system_metrics()
            
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>奥创运维中心</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #0d1117; color: #c9d1d9; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ color: #58a6ff; margin: 0; }}
        .score {{ font-size: 72px; font-weight: bold; color: {"#3fb950" if summary["overall_health"] > 70 else "#d29922" if summary["overall_health"] > 40 else "#f85149"}; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; }}
        .card {{ background: #161b22; border-radius: 8px; padding: 20px; border: 1px solid #30363d; }}
        .card h2 {{ color: #58a6ff; margin-top: 0; font-size: 18px; }}
        .metric {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #30363d; }}
        .metric:last-child {{ border-bottom: none; }}
        .service {{ display: flex; justify-content: space-between; align-items: center; padding: 10px; margin: 5px 0; background: #21262d; border-radius: 6px; }}
        .status-online {{ color: #3fb950; }}
        .status-offline {{ color: #f85149; }}
        .status-error {{ color: #d29922; }}
        .alert-critical {{ color: #f85149; }}
        .alert-warning {{ color: #d29922; }}
        .alert-info {{ color: #58a6ff; }}
        .btn {{ display: inline-block; padding: 8px 16px; background: #238636; color: white; text-decoration: none; border-radius: 6px; margin: 5px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🦞 奥创运维中心</h1>
        <div class="score">{summary["overall_health"]}%</div>
        <p>综合健康分 • {summary["timestamp"]}</p>
    </div>
    
    <div class="grid">
        <div class="card">
            <h2>系统状态</h2>
            <div class="metric"><span>CPU</span><span>{system.get("cpu_usage", 0):.1f}%</span></div>
            <div class="metric"><span>内存</span><span>{system.get("memory_usage", 0):.1f}%</span></div>
            <div class="metric"><span>磁盘</span><span>{system.get("disk_usage", 0):.1f}%</span></div>
            <div class="metric"><span>负载</span><span>{system.get("load_avg", 0):.2f}</span></div>
            <div class="metric"><span>系统健康</span><span>{summary["system_health"]:.1f}%</span></div>
        </div>
        
        <div class="card">
            <h2>服务状态 ({summary["services_online"]}/{summary["services_total"]})</h2>
            {''.join(f'<div class="service"><span>{name}</span><span class="status-{s.get("status")}">{s.get("status")}</span></div>' for name, s in services.items())}
        </div>
        
        <div class="card">
            <h2>告警 ({summary["recent_alerts_count"]})</h2>
            {''.join(f'<div class="metric alert-{a.get("level")}"><span>{a.get("service")}</span><span>{a.get("message", "")[:30]}</span></div>' for a in alerts[:5]) if alerts else '<p>暂无告警</p>'}
        </div>
        
        <div class="card">
            <h2>快速访问</h2>
            <a class="btn" href="/api/summary">API</a>
            <a class="btn" href="/api/services">服务</a>
            <a class="btn" href="/api/alerts">告警</a>
            <a class="btn" href="/api/metrics">指标</a>
        </div>
    </div>
</body>
</html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())
            
        elif path == "/api/summary":
            self.send_json(get_dashboard_summary())
        elif path == "/api/services":
            self.send_json(get_all_services_status())
        elif path == "/api/alerts":
            self.send_json(get_recent_alerts())
        elif path == "/api/metrics":
            self.send_json(get_system_metrics())
        elif path == "/api/logs":
            self.send_json(get_recent_logs())
        elif path == "/health":
            self.send_json({"status": "ok", "service": "unified_ops_dashboard"})
        else:
            self.send_error(404)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

def main():
    server = HTTPServer(("", PORT), Handler)
    print(f"统一运维Dashboard 启动于 port {PORT}")
    server.serve_forever()

if __name__ == "__main__":
    main()