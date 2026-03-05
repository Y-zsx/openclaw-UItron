#!/usr/bin/env python3
"""
统一运维Dashboard - 整合所有运维服务（增强版）
Port: 18200
新增: Agent协作网络、工作流引擎、决策引擎、趋势数据
"""
import json
import time
import sqlite3
import os
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import subprocess
import requests

PORT = 18200
HISTORY_DB = "/root/.openclaw/workspace/ultron/data/metrics_history.db"

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
    "workflow_engine": 18100,
    "decision_engine": 18120,
    "agent_network": 18150,
}

# 核心服务（用于健康检查）
CORE_SERVICES = {
    "workflow_engine": 18100,
    "decision_engine": 18120,
    "agent_network": 18150,
}

def init_history_db():
    """初始化历史数据库"""
    os.makedirs(os.path.dirname(HISTORY_DB), exist_ok=True)
    conn = sqlite3.connect(HISTORY_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS metrics_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            cpu_usage REAL,
            memory_usage REAL,
            disk_usage REAL,
            load_avg REAL,
            service_count INTEGER,
            online_count INTEGER,
            overall_health REAL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON metrics_history(timestamp)")
    conn.commit()
    conn.close()

def save_metrics_to_history(metrics):
    """保存指标到历史数据库"""
    try:
        conn = sqlite3.connect(HISTORY_DB)
        conn.execute("""
            INSERT INTO metrics_history (timestamp, cpu_usage, memory_usage, disk_usage, load_avg, service_count, online_count, overall_health)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
            metrics.get("cpu_usage", 0),
            metrics.get("memory_usage", 0),
            metrics.get("disk_usage", 0),
            metrics.get("load_avg", 0),
            metrics.get("services_total", 0),
            metrics.get("services_online", 0),
            metrics.get("overall_health", 0)
        ))
        conn.commit()
        conn.close()
        # 只保留最近24小时数据
        conn = sqlite3.connect(HISTORY_DB)
        conn.execute("DELETE FROM metrics_history WHERE timestamp < datetime('now', '-1 day')")
        conn.commit()
        conn.close()
    except Exception as e:
        pass

def get_metrics_history(hours=6):
    """获取历史指标数据"""
    try:
        conn = sqlite3.connect(HISTORY_DB)
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT timestamp, cpu_usage, memory_usage, load_avg, overall_health, online_count
            FROM metrics_history
            WHERE timestamp > datetime('now', '-{hours} hours')
            ORDER BY timestamp ASC
        """)
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "timestamp": r[0],
                "cpu": r[1],
                "memory": r[2],
                "load": r[3],
                "health": r[4],
                "services": r[5]
            }
            for r in rows
        ]
    except Exception as e:
        return []

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

def get_core_services_status():
    """获取核心服务状态（工作流、决策、Agent网络）"""
    result = {}
    for name, port in CORE_SERVICES.items():
        result[name] = get_service_status(port)
        result[name]["port"] = port
    return result

def get_workflow_stats():
    """获取工作流统计"""
    try:
        resp = requests.get("http://localhost:18100/api/stats", timeout=3)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return {}

def get_decision_stats():
    """获取决策引擎统计"""
    try:
        resp = requests.get("http://localhost:18120/api/stats", timeout=3)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return {}

def get_agent_network_stats():
    """获取Agent网络统计"""
    try:
        resp = requests.get("http://localhost:18150/api/stats", timeout=3)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return {}

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
    core_services = get_core_services_status()
    alerts = get_recent_alerts()
    logs = get_recent_logs()
    
    # 计算健康分
    online_count = sum(1 for s in services.values() if s.get("status") == "online")
    total_count = len(services)
    service_health = (online_count / total_count) * 100 if total_count > 0 else 0
    
    # 核心服务健康
    core_online = sum(1 for s in core_services.values() if s.get("status") == "online")
    core_total = len(core_services)
    core_health = (core_online / core_total) * 100 if core_total > 0 else 0
    
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
    
    # 综合健康分（核心服务权重更高）
    overall_health = (
        core_health * 0.3 + 
        service_health * 0.3 + 
        system_health * 0.25 + 
        max(0, alert_health) * 0.15
    )
    
    result = {
        "overall_health": round(overall_health, 1),
        "core_health": round(core_health, 1),
        "service_health": round(service_health, 1),
        "system_health": round(system_health, 1),
        "alert_health": round(max(0, alert_health), 1),
        "services_online": online_count,
        "services_total": total_count,
        "core_online": core_online,
        "core_total": core_total,
        "recent_alerts_count": len(alerts),
        "critical_alerts": len(critical_alerts),
        "last_hour_logs": sum(l.get("count", 0) for l in logs),
        "timestamp": datetime.now().isoformat()
    }
    
    # 保存到历史数据库
    save_metrics_to_history(result)
    
    return result

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == "/" or path == "/dashboard":
            # 完整Dashboard
            summary = get_dashboard_summary()
            services = get_all_services_status()
            core_services = get_core_services_status()
            alerts = get_recent_alerts()
            system = get_system_metrics()
            history = get_metrics_history(6)
            
            # 工作流统计
            wf_stats = get_workflow_stats()
            # 决策引擎统计
            decision_stats = get_decision_stats()
            # Agent网络统计
            agent_stats = get_agent_network_stats()
            
            # 趋势数据JSON
            history_json = json.dumps(history)
            
            health_color = "#3fb950" if summary["overall_health"] > 70 else "#d29922" if summary["overall_health"] > 40 else "#f85149"
            
            html = f"""<!DOCTYPE html>
<html>
<head>
    <title>奥创运维中心 v2</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * {{ box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #0d1117; color: #c9d1d9; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ color: #58a6ff; margin: 0; font-size: 28px; }}
        .score {{ font-size: 80px; font-weight: bold; color: {health_color}; margin: 10px 0; }}
        .score-small {{ font-size: 24px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; }}
        .card {{ background: #161b22; border-radius: 8px; padding: 20px; border: 1px solid #30363d; }}
        .card h2 {{ color: #58a6ff; margin-top: 0; font-size: 16px; display: flex; align-items: center; gap: 8px; }}
        .card h2 .badge {{ background: #21262d; padding: 2px 8px; border-radius: 12px; font-size: 12px; color: #8b949e; }}
        .metric {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #30363d; }}
        .metric:last-child {{ border-bottom: none; }}
        .metric-value {{ font-weight: bold; }}
        .service {{ display: flex; justify-content: space-between; align-items: center; padding: 8px 10px; margin: 4px 0; background: #21262d; border-radius: 6px; font-size: 13px; }}
        .status-online {{ color: #3fb950; }}
        .status-offline {{ color: #f85149; }}
        .status-error {{ color: #d29922; }}
        .alert-critical {{ color: #f85149; }}
        .alert-warning {{ color: #d29922; }}
        .alert-info {{ color: #58a6ff; }}
        .btn {{ display: inline-block; padding: 8px 16px; background: #238636; color: white; text-decoration: none; border-radius: 6px; margin: 5px; font-size: 13px; }}
        .btn-secondary {{ background: #21262d; border: 1px solid #30363d; }}
        .progress-bar {{ height: 8px; background: #21262d; border-radius: 4px; overflow: hidden; margin-top: 5px; }}
        .progress-fill {{ height: 100%; border-radius: 4px; transition: width 0.3s; }}
        .core-badge {{ display: inline-block; padding: 2px 6px; background: #f8514920; color: #f85149; border-radius: 4px; font-size: 10px; border: 1px solid #f8514930; }}
        .time {{ font-size: 12px; color: #8b949e; text-align: center; margin-top: 20px; }}
        #trendChart {{ width: 100%; height: 150px; }}
    </style>
    <script>
        const historyData = {history_json};
        
        function drawTrend() {{
            const canvas = document.getElementById('trendChart');
            if (!canvas || historyData.length === 0) return;
            const ctx = canvas.getContext('2d');
            const w = canvas.width = canvas.offsetWidth;
            const h = canvas.height = canvas.offsetHeight;
            
            const padding = 30;
            const chartW = w - padding * 2;
            const chartH = h - padding * 2;
            
            // 找最大值
            let maxVal = 100;
            historyData.forEach(d => {{
                maxVal = Math.max(maxVal, d.health || 0, d.cpu || 0, d.memory || 0);
            }});
            
            ctx.clearRect(0, 0, w, h);
            
            // 画网格
            ctx.strokeStyle = '#30363d';
            ctx.lineWidth = 1;
            for (let i = 0; i <= 4; i++) {{
                const y = padding + (chartH / 4) * i;
                ctx.beginPath();
                ctx.moveTo(padding, y);
                ctx.lineTo(w - padding, y);
                ctx.stroke();
            }}
            
            // 画数据线
            const drawLine = (key, color) => {{
                ctx.strokeStyle = color;
                ctx.lineWidth = 2;
                ctx.beginPath();
                historyData.forEach((d, i) => {{
                    const x = padding + (chartW / (historyData.length - 1 || 1)) * i;
                    const y = padding + chartH - (chartH * (d[key] || 0) / maxVal);
                    if (i === 0) ctx.moveTo(x, y);
                    else ctx.lineTo(x, y);
                }});
                ctx.stroke();
            }};
            
            drawLine('health', '#3fb950');
            drawLine('cpu', '#f85149');
            drawLine('memory', '#d29922');
            
            // 图例
            ctx.font = '11px sans-serif';
            ctx.fillStyle = '#3fb950';
            ctx.fillText('健康分', 10, 15);
            ctx.fillStyle = '#f85149';
            ctx.fillText('CPU', 70, 15);
            ctx.fillStyle = '#d29922';
            ctx.fillText('内存', 110, 15);
        }}
        
        // 自动刷新
        setInterval(() => location.reload(), 30000);
        
        window.onload = drawTrend;
    </script>
</head>
<body>
    <div class="header">
        <h1>🦞 奥创运维中心 v2</h1>
        <div class="score">{summary["overall_health"]}%</div>
        <p class="score-small">综合健康分 • 核心服务 {summary["core_online"]}/{summary["core_total"]} | 服务 {summary["services_online"]}/{summary["services_total"]}</p>
    </div>
    
    <div class="grid">
        <div class="card">
            <h2>📊 系统状态 <span class="badge">{summary["system_health"]:.0f}%</span></h2>
            <div class="metric"><span>CPU</span><span class="metric-value">{system.get("cpu_usage", 0):.1f}%</span></div>
            <div class="metric"><span>内存</span><span class="metric-value">{system.get("memory_usage", 0):.1f}%</span></div>
            <div class="metric"><span>磁盘</span><span class="metric-value">{system.get("disk_usage", 0):.1f}%</span></div>
            <div class="metric"><span>负载</span><span class="metric-value">{system.get("load_avg", 0):.2f}</span></div>
            <div style="margin-top:10px">
                <div class="metric"><span>系统健康</span><span class="metric-value">{summary["system_health"]:.1f}%</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width:{summary['system_health']}%;background:#3fb950"></div></div>
            </div>
        </div>
        
        <div class="card">
            <h2>🔥 核心服务 <span class="badge">{summary["core_health"]:.0f}%</span></h2>
            <div class="service"><span class="core-badge">工作流引擎</span><span class="status-{core_services.get('workflow_engine', {}).get('status', 'offline')}">{core_services.get('workflow_engine', {}).get('status', 'offline')}</span></div>
            <div class="service"><span class="core-badge">决策引擎</span><span class="status-{core_services.get('decision_engine', {}).get('status', 'offline')}">{core_services.get('decision_engine', {}).get('status', 'offline')}</span></div>
            <div class="service"><span class="core-badge">Agent网络</span><span class="status-{core_services.get('agent_network', {}).get('status', 'offline')}">{core_services.get('agent_network', {}).get('status', 'offline')}</span></div>
            <div style="margin-top:10px">
                <div class="metric"><span>工作流统计</span><span class="metric-value">{wf_stats.get('total_workflows', '-')}</span></div>
                <div class="metric"><span>决策统计</span><span class="metric-value">{decision_stats.get('total_decisions', '-')}</span></div>
                <div class="metric"><span>Agent数量</span><span class="metric-value">{agent_stats.get('total_agents', '-')}</span></div>
            </div>
        </div>
        
        <div class="card">
            <h2>🚨 告警 <span class="badge">{summary["recent_alerts_count"]}</span></h2>
            {''.join(f'<div class="metric alert-{a.get("level")}"><span>{a.get("service")}</span><span>{a.get("message", "")[:25]}</span></div>' for a in alerts[:5]) if alerts else '<p style="color:#3fb950">暂无告警</p>'}
            {f'<p style="color:#f85149;margin-top:10px">严重告警: {summary["critical_alerts"]}</p>' if summary["critical_alerts"] > 0 else ''}
        </div>
        
        <div class="card">
            <h2>📈 趋势 (6小时)</h2>
            <canvas id="trendChart"></canvas>
        </div>
        
        <div class="card">
            <h2>⚙️ 运维服务 <span class="badge">{summary["services_online"]}/{summary["services_total"]}</span></h2>
            {''.join(f'<div class="service"><span>{name}</span><span class="status-{s.get("status")}">{s.get("status")}</span></div>' for name, s in services.items())}
        </div>
        
        <div class="card">
            <h2>🔗 快速访问</h2>
            <a class="btn" href="/api/summary">API</a>
            <a class="btn btn-secondary" href="/api/services">服务</a>
            <a class="btn btn-secondary" href="/api/alerts">告警</a>
            <a class="btn btn-secondary" href="/api/metrics">指标</a>
            <a class="btn btn-secondary" href="/api/core">核心</a>
            <a class="btn btn-secondary" href="/api/history">历史</a>
        </div>
    </div>
    
    <p class="time">更新时间: {summary["timestamp"]} • 自动刷新: 30秒</p>
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
        elif path == "/api/core":
            self.send_json(get_core_services_status())
        elif path == "/api/alerts":
            self.send_json(get_recent_alerts())
        elif path == "/api/metrics":
            self.send_json(get_system_metrics())
        elif path == "/api/logs":
            self.send_json(get_recent_logs())
        elif path == "/api/history":
            hours = int(parse_qs(urlparse(self.path).query).get('hours', [6])[0])
            self.send_json(get_metrics_history(hours))
        elif path == "/api/workflow":
            self.send_json(get_workflow_stats())
        elif path == "/api/decision":
            self.send_json(get_decision_stats())
        elif path == "/api/agents":
            self.send_json(get_agent_network_stats())
        elif path == "/health":
            self.send_json({"status": "ok", "service": "unified_ops_dashboard_v2", "version": "2.0"})
        else:
            self.send_error(404)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

def main():
    init_history_db()
    server = HTTPServer(("", PORT), Handler)
    print(f"统一运维Dashboard v2 启动于 port {PORT}")
    server.serve_forever()

if __name__ == "__main__":
    main()