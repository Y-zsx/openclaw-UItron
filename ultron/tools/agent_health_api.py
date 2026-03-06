#!/usr/bin/env python3
"""Agent健康检查与自愈系统API - 端口18196"""
import json
import subprocess
import time
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DATA_DIR = "/root/.openclaw/workspace/ultron/data"
HEALTH_DB = f"{DATA_DIR}/health_db.json"

# Agent端点配置
AGENT_ENDPOINTS = {
    "gateway": {"url": "http://localhost:18789", "name": "OpenClaw Gateway"},
    "monitor_api": {"url": "http://localhost:18195", "name": "任务监控API"},
    "agent_api": {"url": "http://localhost:18131", "name": "Agent API Gateway"},
    "orchestrator": {"url": "http://localhost:18220", "name": "Agent Orchestrator"},
    "service_mesh": {"url": "http://localhost:18270", "name": "Service Mesh"},
    "scaling_api": {"url": "http://localhost:16046", "name": "Scaling API"},
}

def load_health_db():
    """加载健康数据库"""
    if os.path.exists(HEALTH_DB):
        with open(HEALTH_DB, 'r') as f:
            return json.load(f)
    return {"checks": [], "heal_actions": []}

def save_health_db(data):
    """保存健康数据库"""
    with open(HEALTH_DB, 'w') as f:
        json.dump(data, f, indent=2)

def check_endpoint(url, timeout=3):
    """检查端点健康状态"""
    try:
        start = time.time()
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=timeout
        )
        elapsed = (time.time() - start) * 1000
        code = result.stdout.strip()
        
        if code in ["200", "201", "204"]:
            return {"status": "healthy", "latency_ms": round(elapsed, 1), "code": code}
        elif code:
            return {"status": "degraded", "latency_ms": round(elapsed, 1), "code": code}
        else:
            return {"status": "unhealthy", "error": "No response"}
    except subprocess.TimeoutExpired:
        return {"status": "unhealthy", "error": "Timeout"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

def check_processes():
    """检查关键进程状态"""
    critical_processes = [
        "openclaw", "gateway", "browser"
    ]
    
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    running = []
    
    for proc in critical_processes:
        if proc.lower() in result.stdout.lower():
            running.append(proc)
    
    return running

def check_system_resources():
    """检查系统资源"""
    # CPU
    cpu_result = subprocess.run(
        ["top", "-bn1"], capture_output=True, text=True
    )
    cpu_idle = 0
    for line in cpu_result.stdout.split('\n'):
        if 'Cpu(s)' in line:
            parts = line.split()
            for i, p in enumerate(parts):
                if 'id' in p and i > 0:
                    try:
                        cpu_idle = float(parts[i-1].replace(',', '.'))
                    except:
                        pass
    
    cpu_usage = 100 - cpu_idle
    
    # Memory
    mem_result = subprocess.run(
        ["free", "-m"], capture_output=True, text=True
    )
    mem_total = 0
    mem_used = 0
    for line in mem_result.stdout.split('\n'):
        if 'Mem:' in line:
            parts = line.split()
            mem_total = int(parts[1])
            mem_used = int(parts[2])
    
    mem_percent = round(mem_used / mem_total * 100, 1) if mem_total > 0 else 0
    
    # Disk
    disk_result = subprocess.run(
        ["df", "-h", "/"], capture_output=True, text=True
    )
    disk_used = "N/A"
    for line in disk_result.stdout.split('\n'):
        if '/' in line:
            parts = line.split()
            if len(parts) >= 5:
                disk_used = parts[4]
    
    return {
        "cpu_usage": round(cpu_usage, 1),
        "memory_used_mb": mem_used,
        "memory_total_mb": mem_total,
        "memory_percent": mem_percent,
        "disk_used": disk_used
    }

def perform_health_check():
    """执行完整健康检查"""
    timestamp = datetime.now().isoformat()
    
    # 检查端点
    endpoint_results = {}
    for key, info in AGENT_ENDPOINTS.items():
        endpoint_results[key] = {
            "name": info["name"],
            **check_endpoint(info["url"])
        }
    
    # 检查进程
    running_procs = check_processes()
    
    # 系统资源
    resources = check_system_resources()
    
    # 计算健康分数
    healthy_count = sum(1 for r in endpoint_results.values() if r.get("status") == "healthy")
    total_endpoints = len(AGENT_ENDPOINTS)
    endpoint_score = healthy_count / total_endpoints * 100 if total_endpoints > 0 else 0
    
    process_score = min(len(running_procs) / 3 * 100, 100)  # 至少需要3个关键进程
    
    resource_score = 100
    if resources["cpu_usage"] > 90: resource_score -= 30
    if resources["memory_percent"] > 90: resource_score -= 30
    if resources["disk_used"] != "N/A":
        disk_pct = int(resources["disk_used"].replace('%', ''))
        if disk_pct > 90: resource_score -= 20
    
    overall_score = (endpoint_score * 0.5 + process_score * 0.25 + resource_score * 0.25)
    
    result = {
        "timestamp": timestamp,
        "endpoints": endpoint_results,
        "processes": running_procs,
        "resources": resources,
        "scores": {
            "endpoints": round(endpoint_score, 1),
            "processes": round(process_score, 1),
            "resources": round(resource_score, 1),
            "overall": round(overall_score, 1)
        },
        "status": "healthy" if overall_score > 80 else "degraded" if overall_score > 50 else "critical"
    }
    
    # 保存到数据库
    db = load_health_db()
    db["checks"] = (db.get("checks", []) + [result])[-100:]  # 保留最近100条
    db["last_check"] = result
    save_health_db(db)
    
    return result

def attempt_self_heal(failed_endpoint):
    """尝试自愈"""
    action = {
        "timestamp": datetime.now().isoformat(),
        "endpoint": failed_endpoint,
        "action": "none",
        "result": "pending"
    }
    
    # 根据失败的服务尝试重启
    heal_map = {
        "gateway": "openclaw gateway restart",
    }
    
    cmd = heal_map.get(failed_endpoint)
    if cmd:
        try:
            result = subprocess.run(cmd.split(), capture_output=True, text=True, timeout=30)
            action["action"] = f"Executed: {cmd}"
            action["result"] = "success" if result.returncode == 0 else "failed"
            action["output"] = result.stdout[:200]
        except Exception as e:
            action["result"] = "error"
            action["error"] = str(e)
    
    # 保存自愈记录
    db = load_health_db()
    db["heal_actions"] = (db.get("heal_actions", []) + [action])[-50:]
    save_health_db(db)
    
    return action

class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/api/health":
            result = perform_health_check()
            self.send_json(result)
        elif path == "/api/status":
            db = load_health_db()
            self.send_json(db.get("last_check", {}))
        elif path == "/api/endpoints":
            db = load_health_db()
            self.send_json(db.get("last_check", {}).get("endpoints", {}))
        elif path == "/api/resources":
            db = load_health_db()
            self.send_json(db.get("last_check", {}).get("resources", {}))
        elif path == "/api/scores":
            db = load_health_db()
            self.send_json(db.get("last_check", {}).get("scores", {}))
        elif path == "/api/history":
            db = load_health_db()
            self.send_json(db.get("checks", []))
        elif path == "/api/heal-actions":
            db = load_health_db()
            self.send_json(db.get("heal_actions", []))
        elif path == "/" or path == "/dashboard":
            self.serve_dashboard()
        else:
            self.send_error(404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/heal":
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            data = json.loads(body)
            endpoint = data.get("endpoint", "")
            result = attempt_self_heal(endpoint)
            self.send_json(result)
        else:
            self.send_error(404)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def serve_dashboard(self):
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent健康检查与自愈系统</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); min-height: 100vh; color: #fff; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 30px; font-size: 2em; }
        .status-bar { display: flex; justify-content: space-around; margin-bottom: 30px; }
        .status-card { background: rgba(255,255,255,0.1); border-radius: 15px; padding: 20px; text-align: center; min-width: 150px; backdrop-filter: blur(10px); }
        .status-card h3 { font-size: 0.9em; opacity: 0.8; margin-bottom: 10px; }
        .status-card .value { font-size: 2em; font-weight: bold; }
        .score-healthy { color: #4ade80; }
        .score-degraded { color: #fbbf24; }
        .score-critical { color: #f87171; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 20px; }
        .card h2 { margin-bottom: 15px; font-size: 1.2em; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 10px; }
        .endpoint { display: flex; justify-content: space-between; align-items: center; padding: 10px; border-radius: 8px; margin-bottom: 8px; }
        .endpoint.healthy { background: rgba(74, 222, 128, 0.1); }
        .endpoint.degraded { background: rgba(251, 191, 36, 0.1); }
        .endpoint.unhealthy { background: rgba(248, 113, 113, 0.1); }
        .endpoint-name { font-weight: 500; }
        .endpoint-status { padding: 4px 12px; border-radius: 20px; font-size: 0.85em; }
        .status-healthy { background: #4ade80; color: #000; }
        .status-degraded { background: #fbbf24; color: #000; }
        .status-unhealthy { background: #f87171; color: #000; }
        .resource { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .resource-label { opacity: 0.7; }
        .progress-bar { height: 8px; background: rgba(255,255,255,0.1); border-radius: 4px; margin-top: 5px; overflow: hidden; }
        .progress-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
        .processes { display: flex; flex-wrap: wrap; gap: 8px; }
        .process-tag { background: rgba(74, 222, 128, 0.2); padding: 5px 12px; border-radius: 15px; font-size: 0.85em; }
        .timestamp { text-align: center; opacity: 0.5; margin-top: 20px; }
        .btn { background: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; margin-top: 10px; }
        .btn:hover { background: #2563eb; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ Agent健康检查与自愈系统</h1>
        
        <div class="status-bar">
            <div class="status-card">
                <h3>健康评分</h3>
                <div class="value" id="overall-score">--</div>
            </div>
            <div class="status-card">
                <h3>端点状态</h3>
                <div class="value" id="endpoint-score">--</div>
            </div>
            <div class="status-card">
                <h3>进程状态</h3>
                <div class="value" id="process-score">--</div>
            </div>
            <div class="status-card">
                <h3>资源状态</h3>
                <div class="value" id="resource-score">--</div>
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <h2>🔌 端点健康</h2>
                <div id="endpoints-list"></div>
            </div>
            
            <div class="card">
                <h2>💻 系统资源</h2>
                <div id="resources-list"></div>
            </div>
            
            <div class="card">
                <h2>⚙️ 运行进程</h2>
                <div class="processes" id="processes-list"></div>
            </div>
            
            <div class="card">
                <h2>🔧 自愈记录</h2>
                <div id="heal-actions"></div>
            </div>
        </div>
        
        <div class="timestamp" id="timestamp"></div>
    </div>
    
    <script>
        async function loadData() {
            try {
                const healthRes = await fetch('/api/health');
                const health = await healthRes.json();
                
                // 更新分数
                const scores = health.scores || {};
                updateScore('overall-score', scores.overall);
                updateScore('endpoint-score', scores.endpoints);
                updateScore('process-score', scores.processes);
                updateScore('resource-score', scores.resources);
                
                // 更新端点列表
                const endpoints = health.endpoints || {};
                document.getElementById('endpoints-list').innerHTML = Object.entries(endpoints).map(([key, val]) => `
                    <div class="endpoint ${val.status}">
                        <span class="endpoint-name">${val.name}</span>
                        <span class="endpoint-status status-${val.status}">${val.status}</span>
                    </div>
                `).join('');
                
                // 更新资源
                const res = health.resources || {};
                document.getElementById('resources-list').innerHTML = `
                    <div class="resource">
                        <span class="resource-label">CPU使用率</span>
                        <span>${res.cpu_usage}%</span>
                    </div>
                    <div class="progress-bar"><div class="progress-fill" style="width:${res.cpu_usage}%;background:${getColor(res.cpu_usage)}"></div></div>
                    <div class="resource">
                        <span class="resource-label">内存使用</span>
                        <span>${res.memory_used_mb}MB / ${res.memory_total_mb}MB (${res.memory_percent}%)</span>
                    </div>
                    <div class="progress-bar"><div class="progress-fill" style="width:${res.memory_percent}%;background:${getColor(res.memory_percent)}"></div></div>
                    <div class="resource">
                        <span class="resource-label">磁盘使用</span>
                        <span>${res.disk_used}</span>
                    </div>
                `;
                
                // 更新进程
                document.getElementById('processes-list').innerHTML = (health.processes || []).map(p => 
                    `<span class="process-tag">${p}</span>`
                ).join('') || '<span style="opacity:0.5">无运行进程</span>';
                
                document.getElementById('timestamp').textContent = `最后更新: ${health.timestamp}`;
                
                // 加载自愈记录
                const healRes = await fetch('/api/heal-actions');
                const healActions = await healRes.json();
                document.getElementById('heal-actions').innerHTML = (healActions || []).slice(-5).reverse().map(a => `
                    <div class="endpoint ${a.result === 'success' ? 'healthy' : 'unhealthy'}">
                        <span>${a.endpoint} - ${a.action}</span>
                        <span class="endpoint-status status-${a.result === 'success' ? 'healthy' : 'unhealthy'}">${a.result}</span>
                    </div>
                `).join('') || '<span style="opacity:0.5">暂无自愈记录</span>';
                
            } catch(e) {
                console.error(e);
            }
        }
        
        function updateScore(id, value) {
            const el = document.getElementById(id);
            el.textContent = value || '--';
            el.className = 'value ' + (value > 80 ? 'score-healthy' : value > 50 ? 'score-degraded' : 'score-critical');
        }
        
        function getColor(val) {
            return val > 80 ? '#f87171' : val > 50 ? '#fbbf24' : '#4ade80';
        }
        
        loadData();
        setInterval(loadData, 10000);
    </script>
</body>
</html>"""
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

def main():
    port = 18196
    server = HTTPServer(('0.0.0.0', port), RequestHandler)
    print(f"🤖 Agent健康检查API启动: http://localhost:{port}")
    print(f"📊 Dashboard: http://localhost:{port}/")
    server.serve_forever()

if __name__ == "__main__":
    main()