#!/usr/bin/env python3
"""
Agent健康告警DingTalk通知服务
监控Agent健康状态，当发生告警时发送DingTalk通知
"""
import json
import subprocess
import time
import os
import requests
import sqlite3
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

DATA_DIR = "/root/.openclaw/workspace/ultron/data"
ALERT_DB = f"{DATA_DIR}/agent_alerts.db"

# DingTalk配置 - 从环境变量或配置文件读取
DINGTALK_WEBHOOK = os.environ.get("DINGTALK_WEBHOOK", "")
DINGTALK_SECRET = os.environ.get("DINGTALK_SECRET", "")

# 告警配置
ALERT_CONFIG = {
    "check_interval": 60,  # 检查间隔（秒）
    "critical_threshold": 30,  # 严重告警阈值
    "warning_threshold": 60,  # 警告阈值
    "cool_down": 300,  # 告警冷却时间（秒）
}

# 上一条告警时间
last_alert_time = {}
last_alert_status = {}

def init_alert_db():
    """初始化告警数据库"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(ALERT_DB)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS health_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        service_name TEXT,
        message TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        notification_sent INTEGER DEFAULT 0,
        dingtalk_sent INTEGER DEFAULT 0
    )''')
    
    conn.commit()
    conn.close()

def get_health_status():
    """获取健康状态"""
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:18210/health"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
        return None
    except:
        return None

def send_dingtalk_message(message, webhook=None):
    """发送DingTalk消息"""
    webhook = webhook or DINGTALK_WEBHOOK
    if not webhook:
        # 尝试从配置文件读取
        config_path = "/root/.openclaw/workspace/ultron/config/notification_channels.json"
        if os.path.exists(config_path):
            try:
                with open(config_path) as f:
                    config = json.load(f)
                for ch in config.get("channels", []):
                    if ch.get("channel_type") == "dingtalk" and ch.get("enabled"):
                        webhook = ch.get("config", {}).get("webhook_url", "")
                        if webhook and "dummy" not in webhook:
                            break
            except:
                pass
    
    if not webhook or "dummy" in webhook:
        # 使用OpenClaw message工具作为后备
        return {"status": "using_openclaw_message", "message": message}
    
    try:
        # 构造消息体
        msg_data = {
            "msgtype": "text",
            "text": {
                "content": f"🦞 奥创告警\n\n{message}"
            }
        }
        
        response = requests.post(webhook, json=msg_data, timeout=10)
        return {"status": "success", "response": response.text}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def check_and_alert():
    """检查健康状态并发送告警"""
    global last_alert_time, last_alert_status
    
    health = get_health_status()
    if not health:
        return
    
    timestamp = datetime.now().isoformat()
    current_status = health.get("status", "unknown")
    metrics = health.get("metrics", {})
    
    # 检查是否有服务不健康
    services = metrics.get("services", [])
    issues = []
    
    for svc in services:
        svc_name = svc.get("name", "unknown")
        svc_status = svc.get("status", "unknown")
        
        if svc_status != "healthy":
            issues.append(f"• {svc_name}: {svc_status}")
    
    # 检查整体健康分
    health_score = metrics.get("health_score", 100)
    alert_key = "overall"
    
    # 判断告警级别
    if health_score < ALERT_CONFIG["critical_threshold"]:
        severity = "critical"
    elif health_score < ALERT_CONFIG["warning_threshold"]:
        severity = "warning"
    else:
        severity = None
    
    # 发送告警
    now = time.time()
    cooldown = ALERT_CONFIG["cool_down"]
    
    # 检查是否需要发送告警
    should_alert = False
    alert_message = ""
    
    if severity == "critical":
        if issues:
            alert_message = f"🔴 严重告警 - 健康分: {health_score}%\n\n故障服务:\n" + "\n".join(issues)
        else:
            alert_message = f"🔴 严重告警 - 健康分: {health_score}%"
        should_alert = True
        
    elif severity == "warning" and issues:
        alert_message = f"🟡 警告 - 健康分: {health_score}%\n\n问题服务:\n" + "\n".join(issues)
        should_alert = True
    
    # 检查是否需要发送
    if should_alert:
        last_time = last_alert_time.get(alert_key, 0)
        last_status = last_alert_status.get(alert_key, "")
        
        if now - last_time > cooldown or last_status != alert_message:
            # 发送DingTalk通知
            result = send_dingtalk_message(alert_message)
            
            # 记录告警
            conn = sqlite3.connect(ALERT_DB)
            c = conn.cursor()
            c.execute('''INSERT INTO health_alerts 
                (alert_type, severity, service_name, message, notification_sent, dingtalk_sent)
                VALUES (?, ?, ?, ?, ?, ?)''',
                ("health_check", severity, "agent_health", alert_message, 1, 1 if result.get("status") == "success" else 0)
            )
            conn.commit()
            conn.close()
            
            last_alert_time[alert_key] = now
            last_alert_status[alert_key] = alert_message
            
            print(f"[{timestamp}] 告警已发送: {alert_message[:50]}...")
        else:
            print(f"[{timestamp}] 告警冷却中，跳过")
    else:
        print(f"[{timestamp}] 健康状态正常: {current_status}, 分数: {health_score}%")

class AlertHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器"""
    
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {
                "status": "running",
                "service": "agent_alert_dingtalk",
                "timestamp": datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path == "/status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            conn = sqlite3.connect(ALERT_DB)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM health_alerts WHERE dingtalk_sent = 1")
            sent_count = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM health_alerts WHERE notification_sent = 1")
            total_count = c.fetchone()[0]
            conn.close()
            
            response = {
                "alert_service": "agent_alert_dingtalk",
                "total_alerts": total_count,
                "dingtalk_sent": sent_count,
                "last_alerts": last_alert_status,
                "config": ALERT_CONFIG
            }
            self.wfile.write(json.dumps(response).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def start_server(port=18215):
    """启动告警服务"""
    server = HTTPServer(("", port), AlertHandler)
    print(f"Agent告警服务已启动: http://localhost:{port}")
    server.serve_forever()

def run_monitor():
    """运行监控循环"""
    print("开始监控Agent健康状态...")
    while True:
        try:
            check_and_alert()
        except Exception as e:
            print(f"监控错误: {e}")
        time.sleep(ALERT_CONFIG["check_interval"])

if __name__ == "__main__":
    init_alert_db()
    
    # 启动HTTP服务器
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # 启动监控循环
    run_monitor()