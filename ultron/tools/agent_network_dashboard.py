#!/usr/bin/env python3
"""
Agent Network Visualization Dashboard
Port: 18296
"""

from flask import Flask, render_template_string, jsonify, request
import requests
import time
import os

app = Flask(__name__)

# Configuration
COLLAB_API_URL = os.getenv("COLLAB_API_URL", "http://localhost:18295")
HEALTH_API_URL = os.getenv("HEALTH_API_URL", "http://localhost:18234")

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent 联邦网络监控</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .header {
            text-align: center;
            padding: 20px;
            margin-bottom: 20px;
        }
        .header h1 {
            font-size: 2.5em;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .stats-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        .stat-card .value {
            font-size: 2.5em;
            font-weight: bold;
            color: #00d9ff;
        }
        .stat-card .label {
            color: #888;
            margin-top: 5px;
        }
        .main-chart {
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        #networkChart { width: 100%; height: 500px; }
        .refresh-btn {
            position: fixed;
            top: 20px;
            right: 20px;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            border: none;
            padding: 10px 20px;
            border-radius: 25px;
            color: #1a1a2e;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.3s;
        }
        .refresh-btn:hover { transform: scale(1.05); }
        .agents-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .agent-card {
            background: rgba(255,255,255,0.08);
            border-radius: 12px;
            padding: 15px;
            border-left: 4px solid #00ff88;
        }
        .agent-card.offline { border-left-color: #ff4757; }
        .agent-card .name { font-weight: bold; font-size: 1.1em; }
        .agent-card .status { color: #00ff88; font-size: 0.9em; }
        .agent-card.offline .status { color: #ff4757; }
        .agent-card .capabilities {
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-top: 10px;
        }
        .tag {
            background: rgba(0,217,255,0.2);
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.8em;
        }
        .last-update {
            text-align: center;
            color: #666;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <button class="refresh-btn" onclick="refreshData()">🔄 刷新</button>
    
    <div class="header">
        <h1>🕸️ Agent 联邦网络监控</h1>
        <p>实时监控多Agent协作网络状态</p>
    </div>
    
    <div class="stats-container">
        <div class="stat-card">
            <div class="value" id="totalNodes">-</div>
            <div class="label">在线Agent数</div>
        </div>
        <div class="stat-card">
            <div class="value" id="totalEdges">-</div>
            <div class="label">协作连接数</div>
        </div>
        <div class="stat-card">
            <div class="value" id="activeTasks">-</div>
            <div class="label">活跃任务</div>
        </div>
        <div class="stat-card">
            <div class="value" id="collabScore">-</div>
            <div class="label">协作分数</div>
        </div>
    </div>
    
    <div class="main-chart">
        <div id="networkChart"></div>
    </div>
    
    <div class="agents-grid" id="agentsGrid"></div>
    
    <div class="last-update">最后更新: <span id="lastUpdate">-</span></div>
    
    <script>
        let chart = null;
        
        function initChart() {
            chart = echarts.init(document.getElementById('networkChart'));
        }
        
        async function fetchData() {
            try {
                const [topology, health, stats] = await Promise.all([
                    fetch('/api/network/topology').then(r=>r.json()).catch(()=>({nodes:[],edges:[]})),
                    fetch('/api/health').then(r=>r.json()).catch(()=>({agents:[]})),
                    fetch('/api/network/stats').then(r=>r.json()).catch(()=>({}))
                ]);
                return { topology, health, stats };
            } catch(e) {
                console.error(e);
                return { topology: {nodes:[],edges:[]}, health: {agents:[]}, stats: {} };
            }
        }
        
        async function refreshData() {
            const data = await fetchData();
            
            // Update stats
            document.getElementById('totalNodes').textContent = data.topology.summary?.total_nodes || 0;
            document.getElementById('totalEdges').textContent = data.topology.summary?.total_edges || 0;
            document.getElementById('activeTasks').textContent = data.stats.active_tasks || 0;
            document.getElementById('collabScore').textContent = (data.stats.collaboration_score || 0) + '%';
            
            // Update chart
            const option = {
                title: { text: '网络拓扑图', left: 'center', textStyle: { color: '#fff' } },
                tooltip: {},
                series: [{
                    type: 'graph',
                    layout: 'force',
                    data: data.topology.nodes.map(n => ({
                        name: n.id,
                        value: n.capabilities?.join(', ') || '',
                        symbolSize: 50,
                        itemStyle: { color: n.status === 'online' ? '#00ff88' : '#ff4757' }
                    })),
                    links: data.topology.edges.map(e => ({ source: e.source, target: e.target })),
                    roam: true,
                    label: { show: true, position: 'right', color: '#fff' },
                    force: { repulsion: 300, edgeLength: 100 }
                }]
            };
            chart.setOption(option);
            
            // Update agents grid
            const grid = document.getElementById('agentsGrid');
            grid.innerHTML = data.topology.nodes.map(agent => `
                <div class="agent-card ${agent.status !== 'online' ? 'offline' : ''}">
                    <div class="name">${agent.id}</div>
                    <div class="status">${agent.status || 'unknown'}</div>
                    <div class="capabilities">
                        ${(agent.capabilities || []).map(c => `<span class="tag">${c}</span>`).join('')}
                    </div>
                </div>
            `).join('') || '<p style="text-align:center;color:#666;">暂无Agent在线</p>';
            
            document.getElementById('lastUpdate').textContent = new Date().toLocaleTimeString();
        }
        
        initChart();
        refreshData();
        setInterval(refreshData, 5000);
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/network/topology')
def network_topology():
    try:
        r = requests.get(f"{COLLAB_API_URL}/api/network/topology", timeout=5)
        return jsonify(r.json())
    except:
        return jsonify({"nodes": [], "edges": [], "summary": {"total_nodes": 0, "total_edges": 0}})

@app.route('/api/network/stats')
def network_stats():
    try:
        r = requests.get(f"{COLLAB_API_URL}/api/network/stats", timeout=5)
        return jsonify(r.json())
    except:
        return jsonify({"active_tasks": 0, "collaboration_score": 0})

@app.route('/api/health')
def health():
    try:
        r = requests.get(f"{HEALTH_API_URL}/health", timeout=5)
        return jsonify(r.json())
    except:
        return jsonify({"agents": []})

if __name__ == '__main__':
    print("🎨 Agent Network Dashboard starting on port 18296...")
    app.run(host='0.0.0.0', port=18296, debug=False)