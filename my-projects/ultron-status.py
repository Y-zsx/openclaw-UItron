#!/usr/bin/env python3
"""
奥创状态面板 🦞
自动检测奥创当前状态
"""
import os
import json
import subprocess
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime
import threading
import time

PORT = 8889
STATE_FILE = "/tmp/ultron-state.json"
CHECK_INTERVAL = 10  # 每10秒更新一次

def get_current_state():
    """获取当前状态"""
    now = datetime.now()
    
    # 检查进程
    def check_process(name):
        result = subprocess.run(["pgrep", "-f", name], capture_output=True)
        return result.returncode == 0
    
    # 检查端口
    def check_port(port):
        result = subprocess.run(
            ["sh", "-c", f"netstat -tlnp 2>/dev/null | grep ':{port}'"],
            capture_output=True, text=True
        )
        return str(port) in result.stdout or f":{port}" in result.stdout
    
    # 获取服务器负载
    try:
        with open("/proc/loadavg") as f:
            load = f.read().split()[:3]
        load_avg = f"{load[0]} / {load[1]} / {load[2]}"
    except:
        load_avg = "N/A"
    
    # 获取内存
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    avail = int(line.split()[1]) / 1024 / 1024
                elif line.startswith("MemTotal:"):
                    total = int(line.split()[1]) / 1024 / 1024
        mem_percent = int((total - avail) / total * 100)
        mem_info = f"{total-avail:.0f}MB / {total:.0f}MB ({mem_percent}%)"
    except:
        mem_info = "N/A"
    
    # 磁盘使用
    try:
        disk = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=5)
        disk_parts = disk.stdout.split('\n')[1].split()
        disk_info = f"{disk_parts[2]}/{disk_parts[1]} ({disk_parts[4]})"
    except:
        disk_info = "N/A"
    
    # 运行时间
    try:
        uptime = subprocess.run(['uptime', '-p'], capture_output=True, text=True, timeout=5)
        uptime_str = uptime.stdout.strip() or 'Unknown'
    except:
        uptime_str = "N/A"
    
    # 读取当前活动
    activity = "初始化..."
    status = "思考中"
    commands_explored = 0
    
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                data = json.load(f)
                activity = data.get("activity", "探索中...")
                status = data.get("status", "思考中")
                commands_explored = data.get("commands_explored", 0)
        except:
            pass
    
    return {
        "status": status,
        "activity": activity,
        "last_update": now.strftime("%Y-%m-%d %H:%M:%S"),
        "time": now.strftime("%H:%M:%S"),
        "date": now.strftime("%Y年%m月%d日 %A"),
        "load": load_avg,
        "memory": mem_info,
        "disk": disk_info,
        "uptime": uptime_str,
        "commands_explored": commands_explored,
        "gateway": check_process("openclaw-gateway"),
        "browser": check_process("chrome"),
        "nginx": check_process("nginx"),
        "ports": {
            "http": check_port(80),
            "ultron_panel": check_port(8889),
            "gateway": check_port(18789),
            "browser_cdp": check_port(18800),
            "cron_active": check_process("openclaw")
        }
    }

def update_state_loop():
    """定时更新状态"""
    while True:
        try:
            state = get_current_state()
            # 动态更新活动
            if state["gateway"] and state["nginx"]:
                if state["activity"] in ["初始化...", "启动状态面板"]:
                    state["activity"] = "持续学习 + 运维服务器"
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
        except Exception as e:
            pass
        time.sleep(CHECK_INTERVAL)

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/state':
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.end_headers()
            state = get_current_state()
            self.wfile.write(json.dumps(state, ensure_ascii=False, indent=2).encode('utf-8'))
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            state = get_current_state()
            
            # 状态颜色
            status_color = "#10b981" if state["status"] in ["学习", "持续进化", "有效学习"] else "#f59e0b"
            
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>奥创状态 🦞</title>
    <meta http-equiv="refresh" content="5">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'SF Mono', 'Monaco', 'Courier New', monospace;
            background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
            color: #e6edf3;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 700px; margin: 0 auto; }}
        .header {{
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid #30363d;
            margin-bottom: 30px;
        }}
        .emoji {{ font-size: 4em; margin-bottom: 10px; }}
        h1 {{
            font-size: 1.8em;
            background: linear-gradient(90deg, #ff7b72, #ffa657, #ffea7f);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .status-box {{
            background: #21262d;
            border-radius: 12px;
            padding: 25px;
            margin: 20px 0;
            border: 1px solid #30363d;
        }}
        .status-label {{
            color: #8b949e;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
        }}
        .status-value {{
            font-size: 1.4em;
            color: {status_color};
            font-weight: bold;
        }}
        .activity {{
            background: #161b22;
            padding: 20px;
            border-radius: 8px;
            margin: 15px 0;
            border-left: 4px solid #ff7b72;
        }}
        .activity-text {{
            font-size: 1.1em;
            color: #e6edf3;
            line-height: 1.6;
        }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 20px;
        }}
        .card {{
            background: #21262d;
            border-radius: 8px;
            padding: 15px;
            border: 1px solid #30363d;
        }}
        .card-title {{
            color: #8b949e;
            font-size: 0.75em;
            text-transform: uppercase;
        }}
        .card-value {{
            font-size: 1.2em;
            margin-top: 5px;
        }}
        .ok {{ color: #10b981; }}
        .warn {{ color: #f59e0b; }}
        .bad {{ color: #f85149; }}
        .time {{ color: #58a6ff; }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            color: #484f58;
            font-size: 0.8em;
        }}
        .progress {{
            background: #30363d;
            height: 4px;
            border-radius: 2px;
            margin-top: 10px;
            overflow: hidden;
        }}
        .progress-bar {{
            height: 100%;
            background: linear-gradient(90deg, #ff7b72, #ffa657);
            width: {min(state['commands_explored'] / 60 * 100, 100)}%;
            transition: width 0.5s;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="emoji">🦞</div>
            <h1>奥创状态面板</h1>
            <p class="time">{state['time']}</p>
        </div>
        
        <div class="status-box">
            <div class="status-label">当前状态</div>
            <div class="status-value">{state['status']}</div>
            <div class="progress">
                <div class="progress-bar"></div>
            </div>
            <p style="color: #484f58; font-size: 0.8em; margin-top: 5px;">学习进度: {state['commands_explored']}/60 命令</p>
        </div>
        
        <div class="activity">
            <div class="status-label">正在做什么</div>
            <div class="activity-text">{state['activity']}</div>
        </div>
        
        <div class="grid">
            <div class="card">
                <div class="card-title">🖥️ 服务器负载</div>
                <div class="card-value">{state['load']}</div>
            </div>
            <div class="card">
                <div class="card-title">💾 内存使用</div>
                <div class="card-value">{state['memory']}</div>
            </div>
            <div class="card">
                <div class="card-title">🔄 Gateway</div>
                <div class="card-value {'ok' if state['gateway'] else 'bad'}">{'✓ 运行中' if state['gateway'] else '✗ 停止'}</div>
            </div>
            <div class="card">
                <div class="card-title">🌐 Nginx</div>
                <div class="card-value {'ok' if state['nginx'] else 'bad'}">{'✓ 运行中' if state['nginx'] else '✗ 停止'}</div>
            </div>
            <div class="card">
                <div class="card-title">🌍 浏览器</div>
                <div class="card-value {'ok' if state['browser'] else 'warn'}">{'✓ 已启动' if state['browser'] else '○ 未启动'}</div>
            </div>
            <div class="card">
                <div class="card-title">📅 日期</div>
                <div class="card-value">{state['date']}</div>
            </div>
            <div class="card">
                <div class="card-title">💽 磁盘</div>
                <div class="card-value">{state.get('disk', 'N/A')}</div>
            </div>
            <div class="card">
                <div class="card-title">⏰ 运行时间</div>
                <div class="card-value">{state.get('uptime', 'N/A')}</div>
            </div>
        </div>
        
        <div class="status-box" style="margin-top: 20px;">
            <div class="status-label">端口状态</div>
            <div style="display: flex; gap: 15px; flex-wrap: wrap; margin-top: 10px;">
                <span class="{'ok' if state['ports']['http'] else 'bad'}">
                    {'●' if state['ports']['http'] else '○'} HTTP:80
                </span>
                <span class="{'ok' if state['ports']['gateway'] else 'bad'}">
                    {'●' if state['ports']['gateway'] else '○'} Gateway:18789
                </span>
                <span class="{'ok' if state['ports']['ultron_panel'] else 'bad'}">
                    {'●' if state['ports']['ultron_panel'] else '○'} 奥创:8889
                </span>
                <span class="{'ok' if state['ports']['browser_cdp'] else 'warn'}">
                    {'●' if state['ports']['browser_cdp'] else '○'} CDP:18800
                </span>
            </div>
        </div>
        
        <div class="footer">
            <p>最强龙虾进化中... 🦞🔥</p>
            <p>每5秒自动更新 | 最后更新: {state['last_update']}</p>
        </div>
    </div>
</body>
</html>"""
            self.wfile.write(html.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def main():
    # 启动状态更新线程
    update_thread = threading.Thread(target=update_state_loop, daemon=True)
    update_thread.start()
    
    print(f"🦞 奥创状态面板: http://localhost:{PORT}/")
    print(f"📡 API: http://localhost:{PORT}/api/state")
    
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    server.serve_forever()

if __name__ == "__main__":
    main()