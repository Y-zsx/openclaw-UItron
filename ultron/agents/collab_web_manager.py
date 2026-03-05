#!/usr/bin/env python3
"""
Agent协作网络Web管理界面
提供图形化界面管理Agent协作网络
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
from datetime import datetime

# 数据文件路径
DATA_DIR = "/root/.openclaw/workspace/ultron/agents/data"
STATE_FILE = f"{DATA_DIR}/collab_state.json"

class CollabWebManager:
    """Web管理界面主类"""
    
    def __init__(self, port=8089):
        self.port = port
        self.server = None
        
    def load_state(self):
        """加载协作网络状态"""
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return {"agents": [], "tasks": [], "messages": []}
    
    def generate_html(self, state):
        """生成Web界面HTML"""
        agents = state.get("agents", [])
        tasks = state.get("tasks", [])
        
        # 统计信息
        active_agents = sum(1 for a in agents if a.get("status") == "active")
        total_tasks = len(tasks)
        pending_tasks = sum(1 for t in tasks if t.get("status") == "pending")
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent协作网络管理界面</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        
        header {{
            text-align: center;
            margin-bottom: 30px;
            padding: 30px;
            background: rgba(255,255,255,0.1);
            border-radius: 16px;
            backdrop-filter: blur(10px);
        }}
        h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        .subtitle {{ color: #888; font-size: 1.1em; }}
        
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 25px;
            text-align: center;
            backdrop-filter: blur(10px);
        }}
        .stat-value {{ font-size: 2.5em; font-weight: bold; color: #00d4ff; }}
        .stat-label {{ color: #888; margin-top: 5px; }}
        
        .section {{
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 25px;
            margin-bottom: 20px;
        }}
        .section h2 {{ 
            color: #00d4ff; 
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        
        .agent-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
        }}
        .agent-card {{
            background: rgba(255,255,255,0.08);
            border-radius: 10px;
            padding: 20px;
            border-left: 4px solid #00d4ff;
        }}
        .agent-card.active {{ border-left-color: #00ff88; }}
        .agent-card.inactive {{ border-left-color: #ff4444; }}
        .agent-name {{ font-size: 1.2em; font-weight: bold; }}
        .agent-type {{ color: #888; font-size: 0.9em; margin: 5px 0; }}
        .agent-status {{
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
            margin-top: 10px;
        }}
        .status-active {{ background: rgba(0,255,136,0.2); color: #00ff88; }}
        .status-inactive {{ background: rgba(255,68,68,0.2); color: #ff4444; }}
        
        .task-list {{ max-height: 400px; overflow-y: auto; }}
        .task-item {{
            background: rgba(255,255,255,0.05);
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .task-info {{ flex: 1; }}
        .task-title {{ font-weight: bold; }}
        .task-agent {{ color: #888; font-size: 0.9em; }}
        .task-status {{
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85em;
        }}
        .task-pending {{ background: rgba(255,193,7,0.2); color: #ffc107; }}
        .task-running {{ background: rgba(0,212,255,0.2); color: #00d4ff; }}
        .task-completed {{ background: rgba(0,255,136,0.2); color: #00ff88; }}
        
        .empty-state {{ 
            text-align: center; 
            padding: 40px; 
            color: #666; 
        }}
        
        .refresh-btn {{
            background: linear-gradient(135deg, #00d4ff, #0099cc);
            border: none;
            color: white;
            padding: 10px 25px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 1em;
            margin-top: 20px;
        }}
        .refresh-btn:hover {{ opacity: 0.9; }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔷 Agent协作网络管理</h1>
            <p class="subtitle">多智能体协作系统监控面板 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </header>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-value">{len(agents)}</div>
                <div class="stat-label">Agent总数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{active_agents}</div>
                <div class="stat-label">活跃Agent</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{total_tasks}</div>
                <div class="stat-label">任务总数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{pending_tasks}</div>
                <div class="stat-label">待处理任务</div>
            </div>
        </div>
        
        <div class="section">
            <h2>🤖 Agent列表</h2>
            {self._generate_agent_cards(agents)}
        </div>
        
        <div class="section">
            <h2>📋 任务队列</h2>
            {self._generate_task_list(tasks)}
        </div>
        
        <div style="text-align: center;">
            <button class="refresh-btn" onclick="location.reload()">🔄 刷新页面</button>
        </div>
    </div>
    
    <script>
        // 每10秒自动刷新
        setInterval(() => {{
            // 只刷新数据，不闪烁
            fetch(window.location.href)
                .then(response => response.text())
                .then(html => {{
                    document.body.innerHTML = html.split('<body>')[1].split('</body>')[0];
                }})
                .catch(() => location.reload());
        }}, 10000);
    </script>
</body>
</html>"""
        return html
    
    def _generate_agent_cards(self, agents):
        if not agents:
            return '<div class="empty-state">暂无Agent数据</div>'
        
        cards = []
        for agent in agents:
            status = agent.get("status", "inactive")
            status_class = "active" if status == "active" else "inactive"
            status_text = "在线" if status == "active" else "离线"
            cards.append(f"""
            <div class="agent-card {status_class}">
                <div class="agent-name">{agent.get('name', 'Unknown')}</div>
                <div class="agent-type">类型: {agent.get('type', 'general')}</div>
                <div class="task-agent">能力: {', '.join(agent.get('capabilities', []))}</div>
                <span class="agent-status status-{status}">{status_text}</span>
            </div>
            """)
        return '<div class="agent-grid">' + ''.join(cards) + '</div>'
    
    def _generate_task_list(self, tasks):
        if not tasks:
            return '<div class="empty-state">暂无任务数据</div>'
        
        items = []
        for task in tasks:
            status = task.get("status", "pending")
            status_class = f"task-{status}"
            items.append(f"""
            <div class="task-item">
                <div class="task-info">
                    <div class="task-title">{task.get('title', 'Unknown Task')}</div>
                    <div class="task-agent">分配给: {task.get('agent', 'N/A')}</div>
                </div>
                <span class="task-status {status_class}">{status}</span>
            </div>
            """)
        return '<div class="task-list">' + ''.join(items) + '</div>'

class WebHandler(BaseHTTPRequestHandler):
    manager = CollabWebManager()
    
    def do_GET(self):
        state = self.manager.load_state()
        html = self.manager.generate_html(state)
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))
    
    def log_message(self, format, *args):
        pass  # 抑制日志

def start_server(port=8089):
    """启动Web服务器"""
    server = HTTPServer(('0.0.0.0', port), WebHandler)
    print(f"🤖 Agent协作网络Web管理界面已启动: http://localhost:{port}")
    server.serve_forever()

if __name__ == "__main__":
    start_server()