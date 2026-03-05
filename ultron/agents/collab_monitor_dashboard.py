#!/usr/bin/env python3
"""
Agent协作网络监控面板
Web Dashboard for Agent Collaboration Network Monitoring
"""

import json
import time
import os
import sqlite3
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import socket

# 配置
DATA_DIR = "/root/.openclaw/workspace/ultron/agents/data"
DB_PATH = os.path.join(DATA_DIR, "collab_monitor.db")
PORT = 18093

# HTML模板
DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent协作网络监控面板</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #eee;
            min-height: 100vh;
            padding: 20px;
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5em;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .status-bar {
            display: flex;
            justify-content: center;
            gap: 30px;
            margin-bottom: 30px;
        }
        .status-item {
            background: rgba(255,255,255,0.1);
            padding: 15px 30px;
            border-radius: 10px;
            text-align: center;
        }
        .status-item .label { font-size: 0.9em; color: #aaa; }
        .status-item .value { font-size: 2em; font-weight: bold; }
        .status-item .value.ok { color: #4ade80; }
        .status-item .value.warning { color: #fbbf24; }
        .status-item .value.critical { color: #f87171; }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
        }
        .card h3 {
            margin-bottom: 15px;
            color: #00d4ff;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            padding-bottom: 10px;
        }
        
        .alerts-list { max-height: 300px; overflow-y: auto; }
        .alert-item {
            padding: 12px;
            margin-bottom: 10px;
            border-radius: 8px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .alert-item.warning { background: rgba(251, 191, 36, 0.2); border-left: 4px solid #fbbf24; }
        .alert-item.critical { background: rgba(248, 113, 113, 0.2); border-left: 4px solid #f87171; }
        .alert-item.emergency { background: rgba(239, 68, 68, 0.3); border-left: 4px solid #ef4444; }
        .alert-item.info { background: rgba(96, 165, 250, 0.2); border-left: 4px solid #60a5fa; }
        
        .metric-row {
            display: flex;
            justify-content: space-between;
            padding: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .metric-row:last-child { border-bottom: none; }
        .metric-name { color: #aaa; }
        .metric-value { font-weight: bold; }
        
        .chart-container { height: 200px; }
        
        .agents-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            gap: 15px;
        }
        .agent-card {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            text-align: center;
        }
        .agent-card .status {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin: 0 auto 10px;
        }
        .agent-card .status.online { background: #4ade80; }
        .agent-card .status.offline { background: #f87171; }
        
        .footer {
            text-align: center;
            color: #666;
            margin-top: 30px;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .live-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            background: #4ade80;
            border-radius: 50%;
            animation: pulse 2s infinite;
            margin-right: 5px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🦞 奥创 Agent协作网络监控</h1>
        <p><span class="live-indicator"></span>实时监控 · <span id="updateTime">--</span></p>
    </div>
    
    <div class="status-bar">
        <div class="status-item">
            <div class="label">在线Agent</div>
            <div class="value ok" id="onlineAgents">--</div>
        </div>
        <div class="status-item">
            <div class="label">活跃任务</div>
            <div class="value" id="activeTasks">--</div>
        </div>
        <div class="status-item">
            <div class="label">告警数量</div>
            <div class="value" id="alertCount">--</div>
        </div>
        <div class="status-item">
            <div class="label">系统状态</div>
            <div class="value ok" id="systemStatus">正常</div>
        </div>
    </div>
    
    <div class="grid">
        <div class="card">
            <h3>📊 实时指标</h3>
            <div id="metricsList">
                <div class="metric-row"><span class="metric-name">CPU使用率</span><span class="metric-value" id="cpuUsage">--%</span></div>
                <div class="metric-row"><span class="metric-name">内存使用率</span><span class="metric-value" id="memoryUsage">--%</span></div>
                <div class="metric-row"><span class="metric-name">任务队列长度</span><span class="metric-value" id="taskQueue">--</span></div>
                <div class="metric-row"><span class="metric-name">消息延迟</span><span class="metric-value" id="msgLatency">--ms</span></div>
                <div class="metric-row"><span class="metric-name">网络负载</span><span class="metric-value" id="networkLoad">--%</span></div>
            </div>
        </div>
        
        <div class="card">
            <h3>🚨 活跃告警</h3>
            <div class="alerts-list" id="alertsList">
                <p style="color:#666;text-align:center;padding:20px;">暂无告警</p>
            </div>
        </div>
    </div>
    
    <div class="grid">
        <div class="card">
            <h3>📈 指标趋势 (最近30分钟)</h3>
            <div class="chart-container">
                <canvas id="metricsChart"></canvas>
            </div>
        </div>
        
        <div class="card">
            <h3>🤖 Agent状态</h3>
            <div class="agents-grid" id="agentsGrid">
                <div class="agent-card">
                    <div class="status online"></div>
                    <div>Monitor</div>
                </div>
                <div class="agent-card">
                    <div class="status online"></div>
                    <div>Executor</div>
                </div>
                <div class="agent-card">
                    <div class="status online"></div>
                    <div>Analyzer</div>
                </div>
                <div class="agent-card">
                    <div class="status online"></div>
                    <div>Coordinator</div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="footer">
        <p>Agent Collaboration Network Monitor · 奥创主脑</p>
        <p>每5秒自动刷新 · <span id="lastUpdate">--</span></p>
    </div>
    
    <script>
        let chart = null;
        
        async function fetchData() {
            try {
                const [statusRes, alertsRes, metricsRes] = await Promise.all([
                    fetch('/api/status'),
                    fetch('/api/alerts'),
                    fetch('/api/metrics?limit=100')
                ]);
                
                const status = await statusRes.json();
                const alerts = await alertsRes.json();
                const metrics = await metricsRes.json();
                
                updateStatus(status);
                updateAlerts(alerts);
                updateMetrics(metrics);
                updateChart(metrics);
                
                document.getElementById('updateTime').textContent = new Date().toLocaleTimeString();
                document.getElementById('lastUpdate').textContent = new Date().toLocaleString();
            } catch(e) {
                console.error('Fetch error:', e);
            }
        }
        
        function updateStatus(status) {
            document.getElementById('onlineAgents').textContent = status.online_agents || 0;
            document.getElementById('activeTasks').textContent = status.active_tasks || 0;
            
            const alertCount = status.alerts || 0;
            const alertEl = document.getElementById('alertCount');
            alertEl.textContent = alertCount;
            alertEl.className = 'value ' + (alertCount > 0 ? 'warning' : 'ok');
            
            const sysStatus = document.getElementById('systemStatus');
            if (status.critical_alerts > 0) {
                sysStatus.textContent = '告警';
                sysStatus.className = 'value critical';
            } else if (alertCount > 0) {
                sysStatus.textContent = '警告';
                sysStatus.className = 'value warning';
            } else {
                sysStatus.textContent = '正常';
                sysStatus.className = 'value ok';
            }
        }
        
        function updateAlerts(alerts) {
            const container = document.getElementById('alertsList');
            if (!alerts || alerts.length === 0) {
                container.innerHTML = '<p style="color:#4ade80;text-align:center;padding:20px;">✅ 运行正常，无告警</p>';
                return;
            }
            
            container.innerHTML = alerts.map(a => `
                <div class="alert-item ${a.level}">
                    <div>
                        <strong>${a.title}</strong>
                        <div style="font-size:0.8em;color:#aaa;">${a.message}</div>
                    </div>
                    <div style="font-size:0.8em;color:#888;">
                        ${new Date(a.timestamp * 1000).toLocaleTimeString()}
                    </div>
                </div>
            `).join('');
        }
        
        function updateMetrics(metrics) {
            const latest = {};
            metrics.forEach(m => {
                if (!latest[m.metric_type] || m.timestamp > latest[m.metric_type].timestamp) {
                    latest[m.metric_type] = m;
                }
            });
            
            if (latest['cpu_usage']) {
                document.getElementById('cpuUsage').textContent = latest['cpu_usage'].value.toFixed(1) + '%';
            }
            if (latest['memory_usage']) {
                document.getElementById('memoryUsage').textContent = latest['memory_usage'].value.toFixed(1) + '%';
            }
            if (latest['task_queue_length']) {
                document.getElementById('taskQueue').textContent = Math.round(latest['task_queue_length'].value);
            }
            if (latest['message_latency']) {
                document.getElementById('msgLatency').textContent = latest['message_latency'].value.toFixed(1) + 'ms';
            }
            if (latest['network_load']) {
                document.getElementById('networkLoad').textContent = (latest['network_load'].value * 100).toFixed(1) + '%';
            }
        }
        
        function updateChart(metrics) {
            const ctx = document.getElementById('metricsChart').getContext('2d');
            
            // 按时间分组
            const buckets = {};
            metrics.forEach(m => {
                const time = Math.floor(m.timestamp / 60) * 60;
                if (!buckets[time]) buckets[time] = {};
                if (!buckets[time][m.metric_type]) buckets[time][m.metric_type] = [];
                buckets[time][m.metric_type].push(m.value);
            });
            
            const times = Object.keys(buckets).sort();
            const cpuData = times.map(t => {
                const vals = buckets[t]['cpu_usage'];
                return vals ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
            });
            const memData = times.map(t => {
                const vals = buckets[t]['memory_usage'];
                return vals ? vals.reduce((a,b)=>a+b,0)/vals.length : null;
            });
            
            if (chart) chart.destroy();
            
            chart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: times.map(t => new Date(t*1000).toLocaleTimeString()),
                    datasets: [
                        {
                            label: 'CPU %',
                            data: cpuData,
                            borderColor: '#00d4ff',
                            backgroundColor: 'rgba(0,212,255,0.1)',
                            fill: true
                        },
                        {
                            label: 'Memory %',
                            data: memData,
                            borderColor: '#7b2cbf',
                            backgroundColor: 'rgba(123,44,191,0.1)',
                            fill: true
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, max: 100, grid: { color: 'rgba(255,255,255,0.1)' } },
                        x: { grid: { color: 'rgba(255,255,255,0.1)' } }
                    },
                    plugins: { legend: { labels: { color: '#aaa' } } }
                }
            });
        }
        
        // 初始化
        fetchData();
        setInterval(fetchData, 5000);
    </script>
</body>
</html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器"""
    
    def log_message(self, format, *args):
        pass  # 抑制日志
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/':
            self.send_html(DASHBOARD_HTML)
        elif parsed.path == '/api/status':
            self.handle_status()
        elif parsed.path == '/api/alerts':
            self.handle_alerts()
        elif parsed.path == '/api/metrics':
            self.handle_metrics(parsed)
        else:
            self.send_response(404)
            self.end_headers()
    
    def handle_status(self):
        """获取状态"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        now = time.time()
        last_5min = now - 300
        
        # 活跃告警
        c.execute('SELECT COUNT(*) FROM alerts WHERE resolved = 0')
        alerts = c.fetchone()[0]
        
        c.execute('SELECT COUNT(*) FROM alerts WHERE resolved = 0 AND level = ?', ('critical',))
        critical = c.fetchone()[0]
        
        # 任务队列
        task_queue_file = os.path.join(DATA_DIR, "collab_tasks.json")
        active_tasks = 0
        if os.path.exists(task_queue_file):
            try:
                with open(task_queue_file) as f:
                    data = json.load(f)
                    active_tasks = len(data.get('pending_tasks', []))
            except:
                pass
        
        # Agent数量
        online_agents = 4  # 假设4个核心Agent
        
        conn.close()
        
        self.send_json({
            'online_agents': online_agents,
            'active_tasks': active_tasks,
            'alerts': alerts,
            'critical_alerts': critical,
            'timestamp': now
        })
    
    def handle_alerts(self):
        """获取告警"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT id, level, title, message, timestamp, agent_id, metric_type, value, threshold FROM alerts WHERE resolved = 0 ORDER BY timestamp DESC LIMIT 20')
        
        alerts = []
        for row in c.fetchall():
            alerts.append({
                'id': row[0],
                'level': row[1],
                'title': row[2],
                'message': row[3],
                'timestamp': row[4],
                'agent_id': row[5],
                'metric_type': row[6],
                'value': row[7],
                'threshold': row[8]
            })
        
        conn.close()
        self.send_json(alerts)
    
    def handle_metrics(self, parsed):
        """获取指标"""
        params = parse_qs(parsed.query)
        limit = int(params.get('limit', [100])[0])
        metric_type = params.get('type', [None])[0]
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        query = 'SELECT timestamp, metric_type, value, agent_id FROM metrics'
        params = []
        if metric_type:
            query += ' WHERE metric_type = ?'
            params.append(metric_type)
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        c.execute(query, params)
        
        metrics = []
        for row in c.fetchall():
            metrics.append({
                'timestamp': row[0],
                'metric_type': row[1],
                'value': row[2],
                'agent_id': row[3]
            })
        
        conn.close()
        # 反转顺序（从旧到新）
        metrics.reverse()
        self.send_json(metrics)


def get_local_ip():
    """获取本机IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def main():
    """启动监控面板"""
    # 确保数据目录存在
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 初始化数据库（如果不存在）
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL,
        metric_type TEXT,
        value REAL,
        agent_id TEXT,
        tags TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id TEXT PRIMARY KEY,
        level TEXT,
        title TEXT,
        message TEXT,
        timestamp REAL,
        agent_id TEXT,
        metric_type TEXT,
        value REAL,
        threshold REAL,
        acknowledged INTEGER DEFAULT 0,
        resolved INTEGER DEFAULT 0,
        resolved_at REAL
    )''')
    conn.commit()
    conn.close()
    
    # 启动HTTP服务器
    server = HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    local_ip = get_local_ip()
    
    print(f"=" * 50)
    print(f"🦞 Agent协作网络监控面板")
    print(f"=" * 50)
    print(f"本地访问: http://localhost:{PORT}")
    print(f"网络访问: http://{local_ip}:{PORT}")
    print(f"=" * 50)
    print(f"按 Ctrl+C 停止服务")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
        server.shutdown()


if __name__ == "__main__":
    main()