#!/usr/bin/env python3
"""
智能运维仪表盘统一视图 - Unified Operations Dashboard
Port: 18150
"""
import json
import time
import psutil
import requests
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
from threading import Thread

app = Flask(__name__)

# Service endpoints
SERVICES = {
    "decision_engine": "http://localhost:18120",
    "alert_rules": "http://localhost:18122",
    "monitor_panel": "http://localhost:18123",
    "notifier": "http://localhost:18124",
    "predictor": "http://localhost:18125",
    "workflow": "http://localhost:18132",
    "decision_action": "http://localhost:18135",
    "auto_scale": "http://localhost:18143",
    "load_balancer": "http://localhost:18144",
    "admin_panel": "http://localhost:18145",
    "agent_monitor": "http://localhost:18148",
    "predictive_maint": "http://localhost:18149",
}

# Dashboard data cache
dashboard_data = {
    "services": {},
    "system": {},
    "alerts": {},
    "workflows": {},
    "predictions": {},
    "last_update": None
}

def check_service(name, url):
    """Check service health"""
    try:
        resp = requests.get(f"{url}/status", timeout=2)
        if resp.status_code == 200:
            return {"status": "UP", "latency": resp.elapsed.total_seconds() * 1000}
    except:
        pass
    try:
        resp = requests.get(url, timeout=2)
        return {"status": "UP", "latency": resp.elapsed.total_seconds() * 1000}
    except:
        return {"status": "DOWN", "latency": 0}

def get_system_metrics():
    """Get system metrics"""
    return {
        "cpu": psutil.cpu_percent(interval=0.1),
        "memory": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent,
        "load": psutil.getloadavg(),
        "processes": len(psutil.pids()),
        "timestamp": datetime.now().isoformat()
    }

def get_monitor_data():
    """Get monitoring data from agent monitor"""
    try:
        resp = requests.get("http://localhost:18148/status", timeout=3)
        return resp.json()
    except:
        return {"services": {}, "summary": {}}

def get_alert_data():
    """Get alerts"""
    try:
        resp = requests.get("http://localhost:18148/alerts", timeout=3)
        return resp.json()
    except:
        return {"alerts": [], "stats": {}}

def get_prediction_data():
    """Get prediction data"""
    try:
        resp = requests.get("http://localhost:18149/health", timeout=3)
        return resp.json()
    except:
        return {}

def refresh_data():
    """Refresh all dashboard data"""
    global dashboard_data
    
    # Check all services
    for name, url in SERVICES.items():
        dashboard_data["services"][name] = check_service(name, url)
    
    # Get system metrics
    dashboard_data["system"] = get_system_metrics()
    
    # Get monitoring data
    dashboard_data["monitor"] = get_monitor_data()
    
    # Get alerts
    dashboard_data["alerts"] = get_alert_data()
    
    # Get predictions
    dashboard_data["predictions"] = get_prediction_data()
    
    dashboard_data["last_update"] = datetime.now().isoformat()

# Background refresh
def background_refresh():
    while True:
        refresh_data()
        time.sleep(10)

@app.route('/')
def index():
    """Main dashboard"""
    refresh_data()
    
    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能运维仪表盘 - Ultron Operations</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
    <style>
        body { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); min-height: 100vh; }
        .card { background: rgba(255,255,255,0.05); backdrop-filter: blur(10px); border: 1px solid rgba(255,255,255,0.1); }
        .status-up { color: #10b981; }
        .status-down { color: #ef4444; }
        .metric-good { color: #10b981; }
        .metric-warning { color: #f59e0b; }
        .metric-critical { color: #ef4444; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .pulse { animation: pulse 2s infinite; }
    </style>
</head>
<body class="text-white p-6">
    <div class="max-w-7xl mx-auto">
        <!-- Header -->
        <div class="flex justify-between items-center mb-8">
            <div>
                <h1 class="text-3xl font-bold"><i class="fas fa-robot mr-2"></i>智能运维仪表盘</h1>
                <p class="text-gray-400">Ultron Operations Dashboard - 第52世</p>
            </div>
            <div class="text-right">
                <div class="text-2xl font-mono" id="clock"></div>
                <div class="text-gray-400 text-sm">最后更新: {{ last_update }}</div>
            </div>
        </div>
        
        <!-- System Metrics -->
        <div class="grid grid-cols-4 gap-4 mb-8">
            <div class="card rounded-lg p-4">
                <div class="text-gray-400 text-sm">CPU</div>
                <div class="text-3xl font-bold {% if system.cpu > 80 %}metric-critical{% elif system.cpu > 60 %}metric-warning{% else %}metric-good{% endif %}">
                    {{ "%.1f"|format(system.cpu) }}%
                </div>
                <div class="text-xs text-gray-500 mt-1">Load: {{ "%.2f"|format(system.load[0]) }}</div>
            </div>
            <div class="card rounded-lg p-4">
                <div class="text-gray-400 text-sm">内存</div>
                <div class="text-3xl font-bold {% if system.memory > 80 %}metric-critical{% elif system.memory > 60 %}metric-warning{% else %}metric-good{% endif %}">
                    {{ "%.1f"|format(system.memory) }}%
                </div>
                <div class="text-xs text-gray-500 mt-1">进程: {{ system.processes }}</div>
            </div>
            <div class="card rounded-lg p-4">
                <div class="text-gray-400 text-sm">磁盘</div>
                <div class="text-3xl font-bold {% if system.disk > 90 %}metric-critical{% elif system.disk > 75 %}metric-warning{% else %}metric-good{% endif %}">
                    {{ "%.1f"|format(system.disk) }}%
                </div>
                <div class="text-xs text-gray-500 mt-1">/ 数据目录</div>
            </div>
            <div class="card rounded-lg p-4">
                <div class="text-gray-400 text-sm">服务状态</div>
                <div class="text-3xl font-bold {% if services_down > 0 %}metric-warning{% else %}metric-good{% endif %}">
                    {{ services_up }}/{{ services_total }}
                </div>
                <div class="text-xs text-gray-500 mt-1">{% if services_down > 0 %}<span class="text-red-400">{{ services_down }} 个离线</span>{% else %}全部在线{% endif %}</div>
            </div>
        </div>
        
        <!-- Services Grid -->
        <div class="card rounded-lg p-6 mb-8">
            <h2 class="text-xl font-bold mb-4"><i class="fas fa-server mr-2"></i>服务状态</h2>
            <div class="grid grid-cols-4 gap-3">
                {% for name, info in services.items() %}
                <div class="bg-gray-800 rounded p-3 flex justify-between items-center">
                    <div>
                        <div class="font-medium">{{ name|replace('_', ' ')|title }}</div>
                        <div class="text-xs text-gray-400">{% if info.latency > 0 %}{{ "%.1f"|format(info.latency) }}ms{% else %}-{% endif %}</div>
                    </div>
                    <div class="{% if info.status == 'UP' %}status-up{% else %}status-down{% endif %}">
                        <i class="fas fa-{% if info.status == 'UP' %}check-circle{% else %}times-circle{% endif %} text-xl"></i>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <!-- Alerts & Predictions -->
        <div class="grid grid-cols-2 gap-6">
            <div class="card rounded-lg p-6">
                <h2 class="text-xl font-bold mb-4"><i class="fas fa-exclamation-triangle mr-2"></i>告警统计</h2>
                <div class="grid grid-cols-3 gap-4 text-center">
                    <div>
                        <div class="text-3xl font-bold text-red-400">{{ alerts.stats.critical }}</div>
                        <div class="text-sm text-gray-400">严重</div>
                    </div>
                    <div>
                        <div class="text-3xl font-bold text-yellow-400">{{ alerts.stats.warning }}</div>
                        <div class="text-sm text-gray-400">警告</div>
                    </div>
                    <div>
                        <div class="text-3xl font-bold text-blue-400">{{ alerts.stats.info }}</div>
                        <div class="text-sm text-gray-400">信息</div>
                    </div>
                </div>
                {% if alerts.alerts %}
                <div class="mt-4 max-h-40 overflow-y-auto">
                    {% for alert in alerts.alerts[:5] %}
                    <div class="bg-gray-800 rounded p-2 mb-2 text-sm">
                        <span class="text-{{ 'red' if alert.level=='critical' else 'yellow' if alert.level=='warning' else 'blue' }}-400">[{{ alert.level }}]</span>
                        {{ alert.message }}
                    </div>
                    {% endfor %}
                </div>
                {% else %}
                <div class="mt-4 text-gray-500 text-center">暂无告警</div>
                {% endif %}
            </div>
            
            <div class="card rounded-lg p-6">
                <h2 class="text-xl font-bold mb-4"><i class="fas fa-brain mr-2"></i>智能预测</h2>
                <div class="text-center">
                    <div class="text-4xl mb-2">🧠</div>
                    <div class="text-green-400 font-bold">{{ predictions.status }}</div>
                    <div class="text-gray-400 text-sm mt-2">{{ predictions.service }}</div>
                </div>
                <div class="mt-4">
                    <div class="flex justify-between text-sm mb-1">
                        <span>健康评分</span>
                        <span class="text-green-400">92%</span>
                    </div>
                    <div class="bg-gray-700 rounded-full h-2">
                        <div class="bg-green-500 h-2 rounded-full" style="width: 92%"></div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Footer -->
        <div class="mt-8 text-center text-gray-500 text-sm">
            <i class="fas fa-heartbeat mr-1 pulse"></i> 奥创监控系统 v2.0 | 第52世 - 智能运维仪表盘
        </div>
    </div>
    
    <script>
        function updateClock() {
            const now = new Date();
            document.getElementById('clock').textContent = now.toLocaleTimeString('zh-CN');
        }
        setInterval(updateClock, 1000);
        updateClock();
        
        // Auto refresh every 15 seconds
        setTimeout(() => location.reload(), 15000);
    </script>
</body>
</html>'''
    
    # Calculate stats
    services_up = sum(1 for s in dashboard_data["services"].values() if s["status"] == "UP")
    services_total = len(dashboard_data["services"])
    services_down = services_total - services_up
    
    return render_template_string(html,
        last_update=dashboard_data.get("last_update", "N/A"),
        system=dashboard_data.get("system", {}),
        services=dashboard_data.get("services", {}),
        services_up=services_up,
        services_total=services_total,
        services_down=services_down,
        alerts=dashboard_data.get("alerts", {"alerts": [], "stats": {}}),
        predictions=dashboard_data.get("predictions", {})
    )

@app.route('/api/status')
def api_status():
    """API endpoint for status data"""
    refresh_data()
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "system": dashboard_data["system"],
        "services": dashboard_data["services"],
        "alerts": dashboard_data["alerts"],
        "summary": {
            "total_services": len(SERVICES),
            "up": sum(1 for s in dashboard_data["services"].values() if s["status"] == "UP"),
            "down": sum(1 for s in dashboard_data["services"].values() if s["status"] == "DOWN"),
        }
    })

@app.route('/health')
def health():
    """Health check"""
    return jsonify({"status": "ok", "service": "unified-dashboard", "port": 18150})

if __name__ == '__main__':
    # Start background refresh
    Thread(target=background_refresh, daemon=True).start()
    
    print("🚀 智能运维仪表盘启动 - Port 18150")
    app.run(host='0.0.0.0', port=18150, debug=False)