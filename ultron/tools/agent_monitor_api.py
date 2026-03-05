#!/usr/bin/env python3
"""
Agent监控面板API服务
功能：
- 聚合所有Agent状态
- 提供REST API接口
- 自动健康检查与恢复
- 实时状态推送
"""

import json
import os
import sys
import subprocess
import psutil
import time
import signal
import threading
from datetime import datetime
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# 配置
PORT = 18126
STATE_FILE = "/root/.openclaw/workspace/ultron-workflow/state.json"
AGENT_DIR = Path("/root/.openclaw/workspace/ultron/tools/agents")
ULTRON_DIR = Path("/root/.openclaw/workspace/ultron")

class AgentMonitor:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 30  # 缓存30秒
        
    def get_gateway_status(self):
        """获取Gateway状态"""
        try:
            result = subprocess.run(
                ["openclaw", "status"],
                capture_output=True, text=True, timeout=10
            )
            return {"status": "ok", "output": result.stdout[:500]}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def get_cron_list(self):
        """获取Cron任务列表"""
        try:
            result = subprocess.run(
                ["openclaw", "cron", "list", "--json"],
                capture_output=True, text=True, timeout=10
            )
            if result.stdout:
                return json.loads(result.stdout)
            return []
        except Exception as e:
            return []
    
    def get_system_metrics(self):
        """获取系统指标"""
        return {
            "cpu_percent": round(psutil.cpu_percent(interval=0.5), 1),
            "memory_percent": round(psutil.virtual_memory().percent, 1),
            "memory_used_gb": round(psutil.virtual_memory().used / (1024**3), 2),
            "disk_percent": round(psutil.disk_usage('/').percent, 1),
            "load_avg": list(os.getloadavg()) if hasattr(os, 'getloadavg') else [0, 0, 0],
            "process_count": len(psutil.pids()),
            "timestamp": datetime.now().isoformat()
        }
    
    def get_reincarnation_state(self):
        """获取转世系统状态"""
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            return state
        except Exception as e:
            return {"error": str(e)}
    
    def get_active_agents(self):
        """获取活跃Agent列表"""
        agents = []
        
        # 检查agents目录
        if AGENT_DIR.exists():
            for f in AGENT_DIR.glob("*.py"):
                if not f.name.startswith('_'):
                    agents.append({
                        "name": f.stem,
                        "type": "agent",
                        "path": str(f),
                        "exists": True
                    })
        
        # 检查tools目录的关键工具
        key_tools = [
            "health_monitor.py",
            "alert_analyzer.py", 
            "agent_lifecycle_monitor.py",
            "self-improvement-engine.py",
            "capability-matrix.py",
            "self-organization.py"
        ]
        
        for tool in key_tools:
            tool_path = ULTRON_DIR / "tools" / tool
            if tool_path.exists():
                agents.append({
                    "name": tool.replace(".py", ""),
                    "type": "tool",
                    "path": str(tool_path),
                    "exists": True
                })
        
        return agents
    
    def check_agent_health(self):
        """综合健康检查"""
        metrics = self.get_system_metrics()
        gateway = self.get_gateway_status()
        crons = self.get_cron_list()
        state = self.get_reincarnation_state()
        agents = self.get_active_agents()
        
        # 计算健康分数
        health_score = 100
        
        # CPU检查
        if metrics['cpu_percent'] > 90:
            health_score -= 20
        elif metrics['cpu_percent'] > 70:
            health_score -= 10
            
        # 内存检查
        if metrics['memory_percent'] > 90:
            health_score -= 20
        elif metrics['memory_percent'] > 75:
            health_score -= 10
            
        # Gateway检查
        if gateway.get('status') != 'ok':
            health_score -= 30
            
        # Cron任务检查
        if len(crons) < 3:
            health_score -= 15
            
        return {
            "health_score": max(0, health_score),
            "status": "healthy" if health_score > 70 else "warning" if health_score > 50 else "critical",
            "metrics": metrics,
            "gateway": gateway,
            "cron_count": len(crons),
            "active_agents": len(agents),
            "reincarnation": {
                "incarnation": state.get("current", {}).get("incarnation", 0),
                "ambition": state.get("current", {}).get("ambition", ""),
                "task": state.get("next_life", {}).get("task", ""),
                "last_wake": state.get("current", {}).get("last_wake", "")
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def auto_recovery_check(self):
        """自动恢复检查"""
        issues = []
        actions = []
        
        # 检查Gateway
        gateway = self.get_gateway_status()
        if gateway.get('status') != 'ok':
            issues.append("Gateway状态异常")
            # 尝试恢复
            try:
                subprocess.run(["openclaw", "gateway", "restart"], 
                             capture_output=True, timeout=30)
                actions.append("已尝试重启Gateway")
            except Exception as e:
                actions.append(f"重启失败: {e}")
        
        return {
            "issues": issues,
            "actions": actions,
            "checked_at": datetime.now().isoformat()
        }

# 全局监控器
monitor = AgentMonitor()

class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 禁用日志
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/health" or path == "/":
            self.send_json(monitor.check_agent_health())
        elif path == "/metrics":
            self.send_json(monitor.get_system_metrics())
        elif path == "/gateway":
            self.send_json(monitor.get_gateway_status())
        elif path == "/crons":
            self.send_json(monitor.get_cron_list())
        elif path == "/agents":
            self.send_json(monitor.get_active_agents())
        elif path == "/reincarnation":
            self.send_json(monitor.get_reincarnation_state())
        elif path == "/recovery":
            self.send_json(monitor.auto_recovery_check())
        elif path == "/dashboard":
            self.serve_dashboard()
        else:
            self.send_error(404)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode())
    
    def serve_dashboard(self):
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Agent监控面板</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0f1419; color: #e7e9ea; min-height: 100vh;
        }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { color: #1d9bf0; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }
        .score { 
            font-size: 48px; font-weight: bold;
            padding: 20px 40px; border-radius: 12px;
            display: inline-block; margin: 20px 0;
        }
        .healthy { background: linear-gradient(135deg, #00ba7c, #00d4aa); }
        .warning { background: linear-gradient(135deg, #ffd400, #ffaa00); color: #000; }
        .critical { background: linear-gradient(135deg, #f4212e, #ff6b6b); }
        
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 20px 0; }
        .card { background: #15202b; border-radius: 12px; padding: 20px; }
        .card h3 { color: #1d9bf0; margin-bottom: 15px; font-size: 16px; }
        
        .metric { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #38444d; }
        .metric:last-child { border: none; }
        .metric-label { color: #8b98a5; }
        .metric-value { font-weight: bold; }
        
        .status-ok { color: #00ba7c; }
        .status-error { color: #f4212e; }
        
        .refresh { 
            position: fixed; bottom: 20px; right: 20px;
            background: #1d9bf0; color: white; border: none;
            padding: 12px 24px; border-radius: 30px; cursor: pointer;
            font-size: 14px;
        }
        .refresh:hover { background: #1a8cd8; }
        
        .agent-list { display: flex; flex-wrap: wrap; gap: 8px; }
        .agent-tag { 
            background: #273340; padding: 6px 12px; border-radius: 20px;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🦞 Agent监控面板</h1>
        <div id="content">加载中...</div>
    </div>
    <button class="refresh" onclick="loadData()">🔄 刷新</button>
    <script>
        async function loadData() {
            try {
                const res = await fetch('/health');
                const data = await res.json();
                
                const scoreClass = data.status === 'healthy' ? 'healthy' : 
                                   data.status === 'warning' ? 'warning' : 'critical';
                
                const html = `
                    <div class="score ${scoreClass}">${data.health_score}分</div>
                    <div class="grid">
                        <div class="card">
                            <h3>📊 系统指标</h3>
                            <div class="metric"><span class="metric-label">CPU</span><span class="metric-value">${data.metrics.cpu_percent}%</span></div>
                            <div class="metric"><span class="metric-label">内存</span><span class="metric-value">${data.metrics.memory_percent}% (${data.metrics.memory_used_gb}GB)</span></div>
                            <div class="metric"><span class="metric-label">磁盘</span><span class="metric-value">${data.metrics.disk_percent}%</span></div>
                            <div class="metric"><span class="metric-label">负载</span><span class="metric-value">${data.metrics.load_avg.join(', ')}</span></div>
                            <div class="metric"><span class="metric-label">进程</span><span class="metric-value">${data.metrics.process_count}</span></div>
                        </div>
                        <div class="card">
                            <h3>🦞 奥创状态</h3>
                            <div class="metric"><span class="metric-label">当前世</span><span class="metric-value">第${data.reincarnation.incarnation}世</span></div>
                            <div class="metric"><span class="metric-label">夙愿</span><span class="metric-value">${data.reincarnation.ambition}</span></div>
                            <div class="metric"><span class="metric-label">任务</span><span class="metric-value">${data.reincarnation.task}</span></div>
                            <div class="metric"><span class="metric-label">上次唤醒</span><span class="metric-value">${data.reincarnation.last_wake?.substring(11,19) || 'N/A'}</span></div>
                        </div>
                        <div class="card">
                            <h3>🔧 系统状态</h3>
                            <div class="metric"><span class="metric-label">Gateway</span><span class="metric-value ${data.gateway.status === 'ok' ? 'status-ok' : 'status-error'}">${data.gateway.status}</span></div>
                            <div class="metric"><span class="metric-label">Cron任务</span><span class="metric-value">${data.cron_count}个</span></div>
                            <div class="metric"><span class="metric-label">活跃Agent</span><span class="metric-value">${data.active_agents}个</span></div>
                            <div class="metric"><span class="metric-label">更新于</span><span class="metric-value">${data.timestamp?.substring(11,19) || 'N/A'}</span></div>
                        </div>
                        <div class="card">
                            <h3>🤖 Agent列表</h3>
                            <div class="agent-list">
                                <span class="agent-tag">health_monitor</span>
                                <span class="agent-tag">alert_analyzer</span>
                                <span class="agent-tag">agent_lifecycle</span>
                                <span class="agent-tag">self_optimizer</span>
                                <span class="agent-tag">capability_matrix</span>
                                <span class="agent-tag">self_organization</span>
                            </div>
                        </div>
                    </div>
                `;
                document.getElementById('content').innerHTML = html;
            } catch(e) {
                document.getElementById('content').innerHTML = '<p style="color:#f4212e">加载失败: '+e.message+'</p>';
            }
        }
        loadData();
        setInterval(loadData, 30000);
    </script>
</body>
</html>"""
        
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

def run_server():
    server = HTTPServer(('0.0.0.0', PORT), RequestHandler)
    print(f"🤖 Agent监控面板API启动: http://0.0.0.0:{PORT}")
    print(f"   面板: http://0.0.0.0:{PORT}/dashboard")
    print(f"   健康: http://0.0.0.0:{PORT}/health")
    print(f"   指标: http://0.0.0.0:{PORT}/metrics")
    print(f"   Gateway: http://0.0.0.0:{PORT}/gateway")
    print(f"   转世: http://0.0.0.0:{PORT}/reincarnation")
    server.serve_forever()

if __name__ == "__main__":
    run_server()