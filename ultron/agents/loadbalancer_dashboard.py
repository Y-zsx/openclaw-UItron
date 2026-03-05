#!/usr/bin/env python3
"""
多智能体协作网络 - 智能负载均衡器仪表盘
Intelligent Load Balancer Dashboard
"""

import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 8898

class LoadBalancerDashboard:
    """仪表盘数据收集器"""
    
    def __init__(self):
        self.data = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'avg_response_time': 0,
            'nodes': {},
            'request_log': []
        }
        self._lock = threading.Lock()
    
    def record(self, agent_id: str, response_time: float, success: bool):
        with self._lock:
            self.data['total_requests'] += 1
            if success:
                self.data['successful_requests'] += 1
            else:
                self.data['failed_requests'] += 1
            
            # 更新节点统计
            if agent_id not in self.data['nodes']:
                self.data['nodes'][agent_id] = {
                    'requests': 0,
                    'success': 0,
                    'failed': 0,
                    'avg_time': 0,
                    'times': []
                }
            
            node = self.data['nodes'][agent_id]
            node['requests'] += 1
            node['times'].append(response_time)
            if len(node['times']) > 100:
                node['times'] = node['times'][-100:]
            node['avg_time'] = sum(node['times']) / len(node['times'])
            
            if success:
                node['success'] += 1
            else:
                node['failed'] += 1
            
            # 更新平均响应时间
            all_times = []
            for n in self.data['nodes'].values():
                all_times.extend(n['times'])
            if all_times:
                self.data['avg_response_time'] = sum(all_times) / len(all_times)
            
            # 请求日志
            self.data['request_log'].append({
                'time': time.time(),
                'agent_id': agent_id,
                'response_time': response_time,
                'success': success
            })
            if len(self.data['request_log']) > 200:
                self.data['request_log'] = self.data['request_log'][-200:]
    
    def get_data(self):
        with self._lock:
            return json.dumps(self.data)


class DashboardHandler(BaseHTTPRequestHandler):
    collector = None
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(self.collector.get_data().encode())
        elif parsed.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        else:
            self.send_html(self.get_html())
    
    def send_html(self, html):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def get_html(self):
        return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能负载均衡器 - 监控面板</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2em;
            background: linear-gradient(90deg, #00ff88, #00d4ff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }
        .stat-card .label { color: #aaa; font-size: 0.85em; }
        .stat-card .value { font-size: 2em; font-weight: bold; margin-top: 5px; }
        .stat-card.total .value { color: #00d4ff; }
        .stat-card.success .value { color: #00ff88; }
        .stat-card.failed .value { color: #ff4444; }
        .stat-card.time .value { color: #ffaa00; }
        
        .nodes-section {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
            margin-bottom: 20px;
        }
        .nodes-section h2 { margin-bottom: 15px; color: #00ff88; }
        
        .node-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 15px;
        }
        .node-card {
            background: rgba(0,0,0,0.3);
            border-radius: 10px;
            padding: 15px;
            border-left: 4px solid #00ff88;
        }
        .node-card .name { font-weight: bold; font-size: 1.1em; }
        .node-card .stats { margin-top: 10px; color: #aaa; font-size: 0.9em; }
        .node-card .bar {
            height: 6px;
            background: #333;
            border-radius: 3px;
            margin-top: 8px;
            overflow: hidden;
        }
        .node-card .bar-fill {
            height: 100%;
            background: linear-gradient(90deg, #00ff88, #00d4ff);
            transition: width 0.3s;
        }
        
        .log-section {
            background: rgba(255,255,255,0.05);
            border-radius: 15px;
            padding: 20px;
        }
        .log-section h2 { margin-bottom: 15px; color: #ffaa00; }
        .log-list {
            max-height: 300px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 0.85em;
        }
        .log-item {
            padding: 5px 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .log-item.success { color: #00ff88; }
        .log-item.failed { color: #ff4444; }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚖️ 智能负载均衡器 - 监控面板</h1>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card total">
            <div class="label">总请求数</div>
            <div class="value" id="total">0</div>
        </div>
        <div class="stat-card success">
            <div class="label">成功</div>
            <div class="value" id="success">0</div>
        </div>
        <div class="stat-card failed">
            <div class="label">失败</div>
            <div class="value" id="failed">0</div>
        </div>
        <div class="stat-card time">
            <div class="label">平均响应</div>
            <div class="value" id="avg-time">0ms</div>
        </div>
    </div>
    
    <div class="nodes-section">
        <h2>🤖 Agent节点状态</h2>
        <div class="node-grid" id="nodes"></div>
    </div>
    
    <div class="log-section">
        <h2>📋 请求日志</h2>
        <div class="log-list" id="logs"></div>
    </div>
    
    <script>
        async function refresh() {
            const data = await fetch('/api/data').then(r => r.json());
            
            document.getElementById('total').textContent = data.total_requests;
            document.getElementById('success').textContent = data.successful_requests;
            document.getElementById('failed').textContent = data.failed_requests;
            document.getElementById('avg-time').textContent = data.avg_response_time.toFixed(1) + 'ms';
            
            // 节点列表
            const nodesHtml = Object.entries(data.nodes).map(([id, n]) => {
                const successRate = n.requests > 0 ? (n.success / n.requests * 100).toFixed(1) : 0;
                return `<div class="node-card">
                    <div class="name">${id}</div>
                    <div class="stats">
                        请求: ${n.requests} | 成功: ${n.success} | 失败: ${n.failed}<br>
                        成功率: ${successRate}% | 响应: ${n.avg_time.toFixed(1)}ms
                    </div>
                    <div class="bar"><div class="bar-fill" style="width: ${successRate}%"></div></div>
                </div>`;
            }).join('');
            document.getElementById('nodes').innerHTML = nodesHtml || '<p style="color:#666">暂无节点</p>';
            
            // 日志
            const logsHtml = data.request_log.slice(-20).reverse().map(l => {
                const cls = l.success ? 'success' : 'failed';
                const icon = l.success ? '✅' : '❌';
                const time = new Date(l.time * 1000).toLocaleTimeString();
                return `<div class="log-item ${cls}">${icon} ${time} - ${l.agent_id} - ${l.response_time.toFixed(1)}ms</div>`;
            }).join('');
            document.getElementById('logs').innerHTML = logsHtml || '<p style="color:#666">暂无日志</p>';
        }
        
        refresh();
        setInterval(refresh, 3000);
    </script>
</body>
</html>'''


def run_server():
    collector = LoadBalancerDashboard()
    DashboardHandler.collector = collector
    
    # 添加一些模拟数据
    for i in range(5):
        collector.record(f'agent-00{i+1}', 15.2 + i * 5, True)
    
    server = HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    print(f"🚀 Load Balancer Dashboard running on http://0.0.0.0:{PORT}")
    server.serve_forever()


if __name__ == '__main__':
    run_server()