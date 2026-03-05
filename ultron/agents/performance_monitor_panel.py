#!/usr/bin/env python3
"""
多智能体协作网络 - 性能监控面板
Performance Monitoring Panel for Multi-Agent Collaboration Network
"""

import json
import time
import sqlite3
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import os

DB_PATH = "/root/.openclaw/workspace/ultron/agents/performance.db"
PORT = 8899

class PerformanceCollector:
    """性能数据收集器"""
    
    def __init__(self):
        self._init_db()
        self.metrics = {
            'requests_total': 0,
            'requests_success': 0,
            'requests_failed': 0,
            'avg_response_time': 0,
            'active_agents': 0,
            'tasks_queued': 0,
            'tasks_completed': 0,
            'tasks_failed': 0,
        }
        self.response_times = []
        self._lock = threading.Lock()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS performance_metrics
                     (timestamp TEXT, metric_name TEXT, value REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS agent_metrics
                     (timestamp TEXT, agent_id TEXT, agent_type TEXT,
                      cpu_usage REAL, memory_usage REAL, tasks_completed INTEGER)''')
        c.execute('''CREATE TABLE IF NOT EXISTS request_logs
                     (timestamp TEXT, endpoint TEXT, method TEXT,
                      status_code INTEGER, response_time REAL)''')
        conn.commit()
        conn.close()
    
    def record_request(self, endpoint, method, status_code, response_time):
        """记录请求"""
        with self._lock:
            self.metrics['requests_total'] += 1
            if status_code >= 200 and status_code < 300:
                self.metrics['requests_success'] += 1
            else:
                self.metrics['requests_failed'] += 1
            
            self.response_times.append(response_time)
            if len(self.response_times) > 1000:
                self.response_times = self.response_times[-1000:]
            
            if self.response_times:
                self.metrics['avg_response_time'] = sum(self.response_times) / len(self.response_times)
        
        # 写入数据库
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO request_logs VALUES (?, ?, ?, ?, ?)",
                  (datetime.now().isoformat(), endpoint, method, status_code, response_time))
        conn.commit()
        conn.close()
    
    def update_agent_metrics(self, agent_id, agent_type, cpu_usage, memory_usage, tasks_completed):
        """更新Agent性能指标"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO agent_metrics VALUES (?, ?, ?, ?, ?, ?)",
                  (datetime.now().isoformat(), agent_id, agent_type, cpu_usage, memory_usage, tasks_completed))
        conn.commit()
        conn.close()
        
        with self._lock:
            self.metrics['active_agents'] += 1
            self.metrics['tasks_completed'] = tasks_completed
    
    def update_queue_metrics(self, queued, completed, failed):
        """更新队列指标"""
        with self._lock:
            self.metrics['tasks_queued'] = queued
            self.metrics['tasks_completed'] = completed
            self.metrics['tasks_failed'] = failed
    
    def get_metrics(self):
        """获取当前指标"""
        with self._lock:
            return self.metrics.copy()
    
    def get_historical_data(self, hours=1):
        """获取历史数据"""
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # 请求趋势
        c.execute("""SELECT substr(timestamp, 1, 16) as minute,
                            COUNT(*) as count, AVG(response_time) as avg_time
                     FROM request_logs
                     WHERE timestamp > ?
                     GROUP BY minute
                     ORDER BY minute""", (since,))
        request_trend = c.fetchall()
        
        # Agent性能
        c.execute("""SELECT agent_id, agent_type,
                            AVG(cpu_usage) as avg_cpu, AVG(memory_usage) as avg_mem,
                            MAX(tasks_completed) as tasks
                     FROM agent_metrics
                     WHERE timestamp > ?
                     GROUP BY agent_id""", (since,))
        agent_perf = c.fetchall()
        
        conn.close()
        return {
            'request_trend': request_trend,
            'agent_performance': agent_perf
        }


class PerformanceDashboardHandler(BaseHTTPRequestHandler):
    """Dashboard HTTP处理器"""
    
    collector = None
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/api/metrics':
            self.send_json(self.collector.get_metrics())
        elif parsed.path == '/api/history':
            params = parse_qs(parsed.query)
            hours = int(params.get('hours', [1])[0])
            self.send_json(self.collector.get_historical_data(hours))
        elif parsed.path == '/health':
            self.send_json({'status': 'ok', 'timestamp': datetime.now().isoformat()})
        else:
            self.send_html(self.get_dashboard_html())
    
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
    
    def get_dashboard_html(self):
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>多智能体协作网络 - 性能监控面板</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 30px 0;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5em;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .header p { color: #888; margin-top: 10px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 25px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.3s;
        }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-card .label { color: #888; font-size: 0.9em; }
        .stat-card .value {
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }
        .stat-card.success .value { color: #00ff88; }
        .stat-card.warning .value { color: #ffaa00; }
        .stat-card.danger .value { color: #ff4444; }
        .stat-card.info .value { color: #00d4ff; }
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }
        .chart-card {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .chart-card h3 { margin-bottom: 15px; color: #00d4ff; }
        .refresh-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            border: none;
            color: white;
            padding: 15px 30px;
            border-radius: 30px;
            cursor: pointer;
            font-size: 1em;
            box-shadow: 0 4px 15px rgba(0,212,255,0.4);
        }
        .refresh-btn:hover { transform: scale(1.05); }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 多智能体协作网络 - 性能监控</h1>
        <p>Multi-Agent Collaboration Network Performance Monitor</p>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card info">
            <div class="label">总请求数</div>
            <div class="value" id="total-requests">-</div>
        </div>
        <div class="stat-card success">
            <div class="label">成功请求</div>
            <div class="value" id="success-requests">-</div>
        </div>
        <div class="stat-card danger">
            <div class="label">失败请求</div>
            <div class="value" id="failed-requests">-</div>
        </div>
        <div class="stat-card warning">
            <div class="label">平均响应时间</div>
            <div class="value" id="avg-response">-</div>
        </div>
    </div>
    
    <div class="charts-grid">
        <div class="chart-card">
            <h3>📈 请求趋势</h3>
            <canvas id="requestChart"></canvas>
        </div>
        <div class="chart-card">
            <h3>🔄 Agent性能</h3>
            <canvas id="agentChart"></canvas>
        </div>
    </div>
    
    <button class="refresh-btn" onclick="refreshData()">🔄 刷新数据</button>
    
    <script>
        let requestChart, agentChart;
        
        async function refreshData() {
            const metrics = await fetch('/api/metrics').then(r => r.json());
            
            document.getElementById('total-requests').textContent = metrics.requests_total;
            document.getElementById('success-requests').textContent = metrics.requests_success;
            document.getElementById('failed-requests').textContent = metrics.requests_failed;
            document.getElementById('avg-response').textContent = metrics.avg_response_time.toFixed(2) + 'ms';
            
            const history = await fetch('/api/history?hours=1').then(r => r.json());
            updateCharts(history);
        }
        
        function updateCharts(history) {
            const labels = history.request_trend.map(x => x[0].slice(11,16));
            const counts = history.request_trend.map(x => x[1]);
            const times = history.request_trend.map(x => x[2] || 0);
            
            if (requestChart) requestChart.destroy();
            requestChart = new Chart(document.getElementById('requestChart'), {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: '请求数',
                        data: counts,
                        borderColor: '#00d4ff',
                        backgroundColor: 'rgba(0,212,255,0.1)',
                        fill: true
                    }, {
                        label: '响应时间(ms)',
                        data: times,
                        borderColor: '#ffaa00',
                        yAxisID: 'y1'
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: { beginAtZero: true },
                        y1: { position: 'right', beginAtZero: true }
                    }
                }
            });
            
            if (agentChart) agentChart.destroy();
            agentChart = new Chart(document.getElementById('agentChart'), {
                type: 'bar',
                data: {
                    labels: history.agent_performance.map(x => x[0]),
                    datasets: [{
                        label: 'CPU %',
                        data: history.agent_performance.map(x => x[2]),
                        backgroundColor: '#00ff88'
                    }, {
                        label: 'Memory %',
                        data: history.agent_performance.map(x => x[3]),
                        backgroundColor: '#7b2cbf'
                    }]
                },
                options: { responsive: true, scales: { y: { beginAtZero: true, max: 100 } } }
            });
        }
        
        refreshData();
        setInterval(refreshData, 5000);
    </script>
</body>
</html>'''


def run_server():
    """运行服务器"""
    collector = PerformanceCollector()
    PerformanceDashboardHandler.collector = collector
    
    # 模拟一些初始数据
    collector.record_request('/api/agents', 'GET', 200, 15.2)
    collector.record_request('/api/tasks', 'POST', 201, 32.5)
    collector.record_request('/api/health', 'GET', 200, 5.1)
    
    server = HTTPServer(('0.0.0.0', PORT), PerformanceDashboardHandler)
    print(f"🚀 Performance Monitor Panel running on http://0.0.0.0:{PORT}")
    print(f"📊 Dashboard: http://localhost:{PORT}/")
    print(f"📈 API: http://localhost:{PORT}/api/metrics")
    server.serve_forever()


if __name__ == '__main__':
    run_server()