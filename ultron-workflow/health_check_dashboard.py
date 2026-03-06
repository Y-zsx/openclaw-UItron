#!/usr/bin/env python3
"""
健康检查Dashboard可视化 - Health Check Dashboard Visualization
Port: 18205
整合服务治理API数据，提供专业的健康检查可视化
"""
import json
import time
import psutil
import sqlite3
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template_string, jsonify, request, send_from_directory
from threading import Thread, Lock

app = Flask(__name__)
data_lock = Lock()

# Service Governance API
SERVICE_GOV_API = "http://localhost:18250"

# Dashboard data cache
dashboard_data = {
    "services": [],
    "stats": {},
    "system": {},
    "history": [],
    "last_update": None
}

# SQLite for history
DB_PATH = "/root/.openclaw/workspace/ultron-workflow/health_history.db"

def init_db():
    """Initialize history database"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS health_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        total_services INTEGER,
        running_services INTEGER,
        health_percentage REAL,
        avg_response_time REAL,
        down_services TEXT
    )''')
    conn.commit()
    conn.close()

def save_history(total, running, health_pct, avg_time, down_services):
    """Save health history"""
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''INSERT INTO health_history 
        (timestamp, total_services, running_services, health_percentage, avg_response_time, down_services)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (datetime.now().isoformat(), total, running, health_pct, avg_time, json.dumps(down_services)))
    conn.commit()
    conn.close()

def get_history(hours=24):
    """Get health history"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.execute('''SELECT timestamp, total_services, running_services, 
        health_percentage, avg_response_time FROM health_history 
        WHERE timestamp > datetime('now', '-{} hours')
        ORDER BY timestamp ASC'''.format(hours))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "timestamp": r[0],
            "total": r[1],
            "running": r[2],
            "health": r[3],
            "response_time": r[4]
        }
        for r in rows
    ]

def refresh_data():
    """Refresh all dashboard data"""
    global dashboard_data
    
    with data_lock:
        try:
            # Get service stats
            stats_resp = requests.get(f"{SERVICE_GOV_API}/services/stats", timeout=5)
            stats = stats_resp.json()
            
            # Get all services
            all_resp = requests.get(f"{SERVICE_GOV_API}/services/all", timeout=5)
            services_data = all_resp.json()
            services = services_data.get("services", [])
            
            # Get system metrics
            system = {
                "cpu": psutil.cpu_percent(interval=0.5),
                "memory": psutil.virtual_memory().percent,
                "disk": psutil.disk_usage('/').percent,
                "load": psutil.getloadavg(),
                "network_in": psutil.net_io_counters().bytes_recv / 1024 / 1024,
                "network_out": psutil.net_io_counters().bytes_sent / 1024 / 1024,
            }
            
            # Calculate avg response time
            response_times = [s.get("response_time", 0) * 1000 for s in services if s.get("response_time")]
            avg_response = sum(response_times) / len(response_times) if response_times else 0
            
            # Find down services
            down_services = [s for s in services if s.get("status") != "up"]
            
            # Save to history
            save_history(
                stats.get("total_services", 0),
                stats.get("running_services", 0),
                stats.get("health_percentage", 0),
                avg_response,
                [s.get("name") for s in down_services]
            )
            
            # Get history for charts
            history = get_history(24)
            
            # Update dashboard data
            dashboard_data = {
                "services": services,
                "stats": stats,
                "system": system,
                "history": history,
                "avg_response_time": avg_response,
                "last_update": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Error refreshing data: {e}")
            dashboard_data["error"] = str(e)

# Background refresh
def background_refresh():
    while True:
        refresh_data()
        time.sleep(15)

@app.route('/')
def index():
    """Main dashboard - Enhanced version"""
    try:
        # 尝试从外部HTML文件加载（增强版）
        html_path = "/root/.openclaw/workspace/ultron/tools/healthcheck_dashboard.html"
        with open(html_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return html
    except Exception:
        pass
    
    refresh_data()
    
    with data_lock:
        stats = dashboard_data.get("stats", {})
        services = dashboard_data.get("services", [])
        system = dashboard_data.get("system", {})
        history = dashboard_data.get("history", [])
        avg_response = dashboard_data.get("avg_response_time", 0)
    
    # Prepare chart data
    chart_labels = [h["timestamp"][11:16] for h in history[-60:]]  # Last 60 records
    chart_health = [h["health"] for h in history[-60:]]
    chart_response = [h["response_time"] for h in history[-60:]]
    
    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>健康检查仪表盘 - Health Check Dashboard</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); min-height: 100vh; }
        .card { background: rgba(30, 41, 59, 0.8); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
        .status-up { color: #22c55e; }
        .status-down { color: #ef4444; }
        .status-pending { color: #f59e0b; }
        .glow-green { box-shadow: 0 0 20px rgba(34, 197, 94, 0.3); }
        .glow-red { box-shadow: 0 0 20px rgba(239, 68, 68, 0.3); }
    </style>
</head>
<body class="text-white p-4">
    <div class="max-w-7xl mx-auto">
        <!-- Header -->
        <div class="flex justify-between items-center mb-6">
            <div>
                <h1 class="text-2xl font-bold"><i class="fas fa-heartbeat text-red-500 mr-2"></i>健康检查仪表盘</h1>
                <p class="text-gray-400 text-sm">Health Check Dashboard - 第132世</p>
            </div>
            <div class="text-right">
                <div class="text-xl font-mono" id="clock"></div>
                <div class="text-gray-500 text-xs">最后更新: {{ last_update }}</div>
            </div>
        </div>
        
        <!-- Stats Cards -->
        <div class="grid grid-cols-5 gap-4 mb-6">
            <div class="card rounded-lg p-4 {% if stats.health_percentage >= 90 %}glow-green{% endif %}">
                <div class="text-gray-400 text-xs">健康率</div>
                <div class="text-3xl font-bold {% if stats.health_percentage >= 90 %}text-green-400{% elif stats.health_percentage >= 70 %}text-yellow-400{% else %}text-red-400{% endif %}">
                    {{ "%.1f"|format(stats.health_percentage) }}%
                </div>
            </div>
            <div class="card rounded-lg p-4">
                <div class="text-gray-400 text-xs">总服务数</div>
                <div class="text-3xl font-bold text-blue-400">{{ stats.total_services }}</div>
            </div>
            <div class="card rounded-lg p-4">
                <div class="text-gray-400 text-xs">运行中</div>
                <div class="text-3xl font-bold text-green-400">{{ stats.running_services }}</div>
            </div>
            <div class="card rounded-lg p-4 {% if stats.down_services > 0 %}glow-red{% endif %}">
                <div class="text-gray-400 text-xs">离线</div>
                <div class="text-3xl font-bold {% if stats.down_services > 0 %}text-red-400{% else %}text-gray-400{% endif %}">{{ stats.down_services }}</div>
            </div>
            <div class="card rounded-lg p-4">
                <div class="text-gray-400 text-xs">平均响应</div>
                <div class="text-3xl font-bold {% if avg_response > 500 %}text-red-400{% elif avg_response > 200 %}text-yellow-400{% else %}text-green-400{% endif %}">
                    {{ "%.0f"|format(avg_response) }}ms
                </div>
            </div>
        </div>
        
        <!-- System Metrics -->
        <div class="grid grid-cols-4 gap-4 mb-6">
            <div class="card rounded-lg p-3">
                <div class="text-gray-400 text-xs">CPU</div>
                <div class="text-2xl font-bold {% if system.cpu > 80 %}text-red-400{% elif system.cpu > 60 %}text-yellow-400{% else %}text-green-400{% endif %}">
                    {{ "%.1f"|format(system.cpu) }}%
                </div>
            </div>
            <div class="card rounded-lg p-3">
                <div class="text-gray-400 text-xs">内存</div>
                <div class="text-2xl font-bold {% if system.memory > 80 %}text-red-400{% elif system.memory > 60 %}text-yellow-400{% else %}text-green-400{% endif %}">
                    {{ "%.1f"|format(system.memory) }}%
                </div>
            </div>
            <div class="card rounded-lg p-3">
                <div class="text-gray-400 text-xs">磁盘</div>
                <div class="text-2xl font-bold {% if system.disk > 90 %}text-red-400{% elif system.disk > 75 %}text-yellow-400{% else %}text-green-400{% endif %}">
                    {{ "%.1f"|format(system.disk) }}%
                </div>
            </div>
            <div class="card rounded-lg p-3">
                <div class="text-gray-400 text-xs">负载</div>
                <div class="text-2xl font-bold {% if system.load[0] > 4 %}text-red-400{% elif system.load[0] > 2 %}text-yellow-400{% else %}text-green-400{% endif %}">
                    {{ "%.2f"|format(system.load[0]) }}
                </div>
            </div>
        </div>
        
        <!-- Charts -->
        <div class="grid grid-cols-2 gap-4 mb-6">
            <div class="card rounded-lg p-4">
                <h3 class="text-sm font-bold mb-2">健康率趋势 (24h)</h3>
                <canvas id="healthChart" height="100"></canvas>
            </div>
            <div class="card rounded-lg p-4">
                <h3 class="text-sm font-bold mb-2">响应时间趋势 (24h)</h3>
                <canvas id="responseChart" height="100"></canvas>
            </div>
        </div>
        
        <!-- Services Table -->
        <div class="card rounded-lg p-4">
            <h3 class="text-lg font-bold mb-4"><i class="fas fa-server mr-2"></i>服务状态详情</h3>
            <div class="overflow-x-auto">
                <table class="w-full text-sm">
                    <thead>
                        <tr class="text-gray-400 border-b border-gray-700">
                            <th class="text-left py-2">服务名</th>
                            <th class="text-left py-2">端口</th>
                            <th class="text-center py-2">状态</th>
                            <th class="text-right py-2">响应时间</th>
                            <th class="text-left py-2">详情</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for svc in services %}
                        <tr class="border-b border-gray-800 hover:bg-gray-800/50">
                            <td class="py-2 font-medium">{{ svc.name }}</td>
                            <td class="py-2 text-gray-400">{{ svc.port }}</td>
                            <td class="text-center py-2">
                                <span class="{% if svc.status == 'up' %}text-green-400{% else %}text-red-400{% endif %}">
                                    <i class="fas fa-{% if svc.status == 'up' %}check-circle{% else %}times-circle{% endif %}"></i>
                                    {{ svc.status }}
                                </span>
                            </td>
                            <td class="text-right py-2 {% if svc.response_time and svc.response_time * 1000 > 500 %}text-red-400{% elif svc.response_time and svc.response_time * 1000 > 200 %}text-yellow-400{% else %}text-green-400{% endif %}">
                                {% if svc.response_time %}{{ "%.1f"|format(svc.response_time * 1000) }}ms{% else %}-{% endif %}
                            </td>
                            <td class="py-2 text-gray-500 text-xs">
                                {% if svc.details %}{% for k,v in svc.details.items() %}{{ k }} {% endfor %}{% else %}Normal{% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
        
        <!-- Footer -->
        <div class="mt-6 text-center text-gray-500 text-xs">
            <i class="fas fa-robot mr-1"></i> 奥创健康检查系统 v2.0 | 第132世
        </div>
    </div>
    
    <script>
        function updateClock() {
            const now = new Date();
            document.getElementById('clock').textContent = now.toLocaleTimeString('zh-CN');
        }
        setInterval(updateClock, 1000);
        updateClock();
        
        // Charts
        const healthCtx = document.getElementById('healthChart').getContext('2d');
        const responseCtx = document.getElementById('responseChart').getContext('2d');
        
        new Chart(healthCtx, {
            type: 'line',
            data: {
                labels: {{ chart_labels|tojson }},
                datasets: [{
                    label: '健康率 %',
                    data: {{ chart_health|tojson }},
                    borderColor: '#22c55e',
                    backgroundColor: 'rgba(34, 197, 94, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,0.1)' } },
                    x: { grid: { display: false } }
                }
            }
        });
        
        new Chart(responseCtx, {
            type: 'line',
            data: {
                labels: {{ chart_labels|tojson }},
                datasets: [{
                    label: '响应时间 ms',
                    data: {{ chart_response|tojson }},
                    borderColor: '#3b82f6',
                    backgroundColor: 'rgba(59, 130, 246, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    y: { grid: { color: 'rgba(255,255,255,0.1)' } },
                    x: { grid: { display: false } }
                }
            }
        });
        
        // Auto refresh
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>'''
    
    return render_template_string(html,
        last_update=dashboard_data.get("last_update", "N/A"),
        stats=stats,
        services=services,
        system=system,
        avg_response=avg_response,
        chart_labels=chart_labels,
        chart_health=chart_health,
        chart_response=chart_response
    )

@app.route('/api/status')
def api_status():
    """API endpoint for status data"""
    with data_lock:
        return jsonify({
            "timestamp": datetime.now().isoformat(),
            "services": dashboard_data.get("services", []),
            "stats": dashboard_data.get("stats", {}),
            "system": dashboard_data.get("system", {}),
            "avg_response_time": dashboard_data.get("avg_response_time", 0)
        })

@app.route('/api/history')
def api_history():
    """Get health history"""
    hours = int(request.args.get('hours', 24))
    return jsonify(get_history(hours))

@app.route('/health')
def health():
    """Health check"""
    return jsonify({"status": "ok", "service": "health-check-dashboard", "port": 18205})

if __name__ == '__main__':
    init_db()
    
    # Start background refresh
    Thread(target=background_refresh, daemon=True).start()
    
    print("🚀 健康检查仪表盘启动 - Port 18205")
    app.run(host='0.0.0.0', port=18205, debug=False)