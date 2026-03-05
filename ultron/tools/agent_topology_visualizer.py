#!/usr/bin/env python3
"""
Agent Network Topology Visualizer
第110世: Agent网络拓扑可视化
Discovers and visualizes the agent network topology
"""

import json
import socket
import time
from datetime import datetime
from flask import Flask, jsonify, render_template_string
import requests

app = Flask(__name__)

# Service endpoints to check
SERVICES = {
    "agent-gateway": {"port": 8089, "health": "/health", "agents": "/api/agents"},
    "decision-engine": {"port": 18120, "health": "/health", "stats": "/stats"},
    "automation": {"port": 18128, "health": "/health", "workflows": "/api/workflows"},
    "workflow": {"port": 18132, "health": "/health", "stats": "/api/stats"},
    "executor": {"port": 8096, "health": "/health", "tasks": "/api/tasks"},
    "unified-dashboard": {"port": 18150, "health": "/health"},
}

# Topology templates
TOPOLOGY_TEMPLATES = {
    "star": {"type": "star", "description": "星型拓扑 - 中心辐射"},
    "mesh": {"type": "mesh", "description": "网状拓扑 - 全互联"},
    "hierarchical": {"type": "hierarchical", "description": "层级拓扑 - 树状结构"},
}


def check_service(port, path="/health", timeout=2):
    """Check if a service is running and responsive"""
    try:
        response = requests.get(f"http://localhost:{port}{path}", timeout=timeout)
        return {
            "status": "up" if response.status_code == 200 else "down",
            "response": response.json() if response.headers.get("content-type", "").find("json") >= 0 else response.text[:200],
            "latency_ms": int(response.elapsed.total_seconds() * 1000)
        }
    except requests.exceptions.ConnectionError:
        return {"status": "down", "error": "Connection refused", "latency_ms": None}
    except requests.exceptions.Timeout:
        return {"status": "down", "error": "Timeout", "latency_ms": None}
    except Exception as e:
        return {"status": "down", "error": str(e), "latency_ms": None}


def discover_services():
    """Discover all agent-related services"""
    discovered = []
    for name, config in SERVICES.items():
        result = check_service(config["port"], config.get("health", "/health"))
        service_info = {
            "name": name,
            "port": config["port"],
            "status": result.get("status", "unknown"),
            "latency_ms": result.get("latency_ms"),
            "info": result.get("response", {}),
            "timestamp": datetime.now().isoformat()
        }
        
        # Get additional info based on service type
        if result.get("status") == "up":
            if "agents" in config:
                try:
                    resp = requests.get(f"http://localhost:{config['port']}{config['agents']}", timeout=2)
                    service_info["agents"] = resp.json()
                except:
                    pass
            if "stats" in config:
                try:
                    resp = requests.get(f"http://localhost:{config['port']}{config['stats']}", timeout=2)
                    service_info["stats"] = resp.json()
                except:
                    pass
        
        discovered.append(service_info)
    return discovered


def build_topology():
    """Build the agent network topology"""
    services = discover_services()
    
    # Build nodes
    nodes = []
    links = []
    
    for svc in services:
        node = {
            "id": svc["name"],
            "label": svc["name"],
            "port": svc["port"],
            "status": svc["status"],
            "type": "core" if svc["port"] in [8089, 18120] else "service"
        }
        
        # Add stats info
        if "stats" in svc:
            node["stats"] = svc["stats"]
        if "agents" in svc:
            node["agents"] = svc.get("agents", {})
            
        nodes.append(node)
    
    # Build links based on service relationships
    # Decision engine is the central hub
    core_services = [s for s in services if s["status"] == "up"]
    
    for svc in core_services:
        if svc["name"] != "decision-engine" and svc["name"] != "unified-dashboard":
            links.append({
                "source": svc["name"],
                "target": "decision-engine",
                "type": "api_call",
                "status": "active"
            })
    
    # Executor connects to gateway
    executor = next((s for s in core_services if s["name"] == "executor"), None)
    gateway = next((s for s in core_services if s["name"] == "agent-gateway"), None)
    if executor and gateway:
        links.append({
            "source": "agent-gateway",
            "target": "executor",
            "type": "task_exec",
            "status": "active"
        })
    
    # Automation connects to workflow
    automation = next((s for s in core_services if s["name"] == "automation"), None)
    workflow = next((s for s in core_services if s["name"] == "workflow"), None)
    if automation and workflow:
        links.append({
            "source": "automation",
            "target": "workflow",
            "type": "workflow_trigger",
            "status": "active"
        })
    
    return {
        "nodes": nodes,
        "links": links,
        "topology_type": "star",
        "timestamp": datetime.now().isoformat()
    }


# HTML Template for visualization
TOPOLOGY_HTML = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent网络拓扑 - Ultron</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/d3@7"></script>
    <style>
        body { background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); min-height: 100vh; }
        .card { background: rgba(30, 41, 59, 0.8); backdrop-filter: blur(10px); border: 1px solid rgba(100, 116, 139, 0.3); }
        .node { cursor: pointer; transition: all 0.3s; }
        .node:hover { transform: scale(1.1); }
        .link { stroke-opacity: 0.6; transition: stroke-opacity 0.3s; }
        .link:hover { stroke-opacity: 1; }
        .status-up { fill: #10b981; }
        .status-down { fill: #ef4444; }
        @keyframes pulse { 0%, 100% { r: 20; } 50% { r: 25; } }
        .pulsing { animation: pulse 2s infinite; }
    </style>
</head>
<body class="text-white p-6">
    <div class="max-w-7xl mx-auto">
        <!-- Header -->
        <div class="flex justify-between items-center mb-6">
            <div>
                <h1 class="text-3xl font-bold"><i class="fas fa-project-diagram mr-2"></i>Agent网络拓扑可视化</h1>
                <p class="text-gray-400">Agent Network Topology - 第110世</p>
            </div>
            <div class="flex gap-3">
                <button onclick="refreshTopology()" class="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg">
                    <i class="fas fa-sync-alt mr-2"></i>刷新
                </button>
            </div>
        </div>
        
        <!-- Stats Cards -->
        <div class="grid grid-cols-4 gap-4 mb-6">
            <div class="card rounded-lg p-4">
                <div class="text-gray-400 text-sm">服务节点</div>
                <div class="text-3xl font-bold" id="node-count">-</div>
            </div>
            <div class="card rounded-lg p-4">
                <div class="text-gray-400 text-sm">活跃连接</div>
                <div class="text-3xl font-bold text-green-400" id="link-count">-</div>
            </div>
            <div class="card rounded-lg p-4">
                <div class="text-gray-400 text-sm">在线服务</div>
                <div class="text-3xl font-bold text-green-400" id="online-count">-</div>
            </div>
            <div class="card rounded-lg p-4">
                <div class="text-gray-400 text-sm">离线服务</div>
                <div class="text-3xl font-bold text-red-400" id="offline-count">-</div>
            </div>
        </div>
        
        <!-- Main Visualization -->
        <div class="card rounded-lg p-4 mb-6">
            <div id="topology-viz" class="w-full" style="height: 500px;"></div>
        </div>
        
        <!-- Service Details -->
        <div class="grid grid-cols-2 gap-4">
            <div class="card rounded-lg p-4">
                <h3 class="text-lg font-bold mb-3">服务列表</h3>
                <div id="service-list" class="space-y-2"></div>
            </div>
            <div class="card rounded-lg p-4">
                <h3 class="text-lg font-bold mb-3">连接关系</h3>
                <div id="link-list" class="space-y-2"></div>
            </div>
        </div>
    </div>
    
    <script>
        let topologyData = null;
        
        function refreshTopology() {
            fetch('/api/topology')
                .then(r => r.json())
                .then(data => {
                    topologyData = data;
                    renderTopology(data);
                    updateStats(data);
                });
        }
        
        function updateStats(data) {
            document.getElementById('node-count').textContent = data.nodes.length;
            document.getElementById('link-count').textContent = data.links.length;
            const online = data.nodes.filter(n => n.status === 'up').length;
            const offline = data.nodes.filter(n => n.status !== 'up').length;
            document.getElementById('online-count').textContent = online;
            document.getElementById('offline-count').textContent = offline;
        }
        
        function renderTopology(data) {
            const container = document.getElementById('topology-viz');
            container.innerHTML = '';
            
            const width = container.clientWidth;
            const height = 500;
            
            // Create SVG
            const svg = d3.select('#topology-viz')
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            // Define arrow marker
            svg.append('defs').append('marker')
                .attr('id', 'arrowhead')
                .attr('viewBox', '-0 -5 10 10')
                .attr('refX', 25)
                .attr('refY', 0)
                .attr('orient', 'auto')
                .attr('markerWidth', 6)
                .attr('markerHeight', 6)
                .append('path')
                .attr('d', 'M 0,-5 L 10 ,0 L 0,5')
                .attr('fill', '#64748b');
            
            // Calculate node positions (star topology)
            const centerX = width / 2;
            const centerY = height / 2;
            const radius = Math.min(width, height) / 3;
            
            const nodes = data.nodes.map((n, i) => {
                if (n.name === 'decision-engine') {
                    return { ...n, x: centerX, y: centerY };
                }
                const angle = (2 * Math.PI * i / data.nodes.length) - Math.PI/2;
                return {
                    ...n,
                    x: centerX + radius * Math.cos(angle),
                    y: centerY + radius * Math.sin(angle)
                };
            });
            
            const nodeMap = {};
            nodes.forEach(n => nodeMap[n.name] = n);
            
            // Draw links
            svg.selectAll('.link')
                .data(data.links)
                .enter()
                .append('line')
                .attr('class', 'link')
                .attr('x1', d => nodeMap[d.source].x)
                .attr('y1', d => nodeMap[d.source].y)
                .attr('x2', d => nodeMap[d.target].x)
                .attr('y2', d => nodeMap[d.target].y)
                .attr('stroke', d => d.status === 'active' ? '#10b981' : '#64748b')
                .attr('stroke-width', 2)
                .attr('marker-end', 'url(#arrowhead)');
            
            // Draw nodes
            const nodeGroups = svg.selectAll('.node')
                .data(nodes)
                .enter()
                .append('g')
                .attr('class', 'node')
                .attr('transform', d => `translate(${d.x}, ${d.y})`);
            
            // Node circles
            nodeGroups.append('circle')
                .attr('r', 20)
                .attr('fill', d => d.status === 'up' ? '#10b981' : '#ef4444')
                .attr('stroke', '#fff')
                .attr('stroke-width', 2);
            
            // Node labels
            nodeGroups.append('text')
                .attr('dy', 35)
                .attr('text-anchor', 'middle')
                .attr('fill', '#fff')
                .attr('font-size', '12px')
                .text(d => d.label);
            
            // Port labels
            nodeGroups.append('text')
                .attr('dy', 50)
                .attr('text-anchor', 'middle')
                .attr('fill', '#94a3b8')
                .attr('font-size', '10px')
                .text(d => `:${d.port}`);
            
            // Update service list
            const serviceList = document.getElementById('service-list');
            serviceList.innerHTML = nodes.map(n => `
                <div class="flex items-center justify-between p-2 rounded bg-slate-700">
                    <span class="font-mono">${n.label}</span>
                    <span class="px-2 py-1 rounded text-xs ${n.status === 'up' ? 'bg-green-600' : 'bg-red-600'}">
                        ${n.status} (:${n.port})
                    </span>
                </div>
            `).join('');
            
            // Update link list
            const linkList = document.getElementById('link-list');
            linkList.innerHTML = data.links.map(l => `
                <div class="flex items-center justify-between p-2 rounded bg-slate-700">
                    <span class="font-mono text-sm">${l.source}</span>
                    <span class="text-gray-400">→</span>
                    <span class="font-mono text-sm">${l.target}</span>
                </div>
            `).join('');
        }
        
        // Initial load
        refreshTopology();
        
        // Auto-refresh every 30 seconds
        setInterval(refreshTopology, 30000);
    </script>
</body>
</html>
"""


@app.route('/')
def index():
    return render_template_string(TOPOLOGY_HTML)


@app.route('/api/topology')
def api_topology():
    return jsonify(build_topology())


@app.route('/api/services')
def api_services():
    return jsonify(discover_services())


@app.route('/health')
def health():
    return jsonify({
        "service": "agent-topology-visualizer",
        "status": "ok",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    })


if __name__ == '__main__':
    print("=" * 50)
    print("Agent Network Topology Visualizer")
    print("第110世: Agent网络拓扑可视化")
    print("=" * 50)
    print(f"Starting server on port 18160...")
    app.run(host='0.0.0.0', port=18173, debug=False)