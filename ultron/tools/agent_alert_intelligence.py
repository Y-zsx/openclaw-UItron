#!/usr/bin/env python3
"""
Agent协作网络智能告警系统 v2.0
- 智能告警关联分析
- 多维度阈值检测
- 自动告警升级机制
- Agent协作网络健康监控
"""
import json
import subprocess
import time
import os
import sqlite3
import requests
from datetime import datetime, timedelta
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread, Lock
import threading

DATA_DIR = "/root/.openclaw/workspace/ultron/data"
ALERT_DB = f"{DATA_DIR}/agent_alerts_v2.db"

# 告警配置
ALERT_CONFIG = {
    "check_interval": 30,
    "critical_threshold": 30,
    "warning_threshold": 60,
    "cool_down": 120,
    "escalation_threshold": 3,  # 连续告警次数触发升级
    "correlation_window": 300,  # 告警关联时间窗口(秒)
}

# 状态跟踪
last_alert_time = {}
last_alert_status = {}
alert_counter = defaultdict(int)  # 连续告警计数
alert_history = []  # 告警历史(用于关联分析)
lock = Lock()

def init_alert_db():
    """初始化智能告警数据库"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(ALERT_DB)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS intelligent_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type TEXT NOT NULL,
        severity TEXT NOT NULL,
        service_name TEXT,
        message TEXT,
        metrics_json TEXT,
        correlated BOOLEAN DEFAULT 0,
        escalated BOOLEAN DEFAULT 0,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS alert_correlations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        root_cause TEXT,
        related_alerts TEXT,
        first_timestamp DATETIME,
        last_timestamp DATETIME,
        resolved BOOLEAN DEFAULT 0
    )''')
    
    conn.commit()
    conn.close()

def get_agent_network_status():
    """获取Agent协作网络状态"""
    status = {
        "healthy": True,
        "services": [],
        "metrics": {},
        "collaboration_score": 0
    }
    
    # 检查多个API端口
    apis = [
        (18210, "agent_health"),
        (18220, "ops_metrics"),
        (18227, "self_healer"),
        (18228, "integration_tester"),
    ]
    
    healthy_count = 0
    service_details = []
    
    for port, name in apis:
        try:
            result = subprocess.run(
                ["curl", "-s", f"http://localhost:{port}/health"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                data = json.loads(result.stdout)
                is_healthy = data.get("status") == "running" or data.get("status") == "healthy"
                service_details.append({
                    "name": name,
                    "port": port,
                    "status": "healthy" if is_healthy else "degraded",
                    "response": data
                })
                if is_healthy:
                    healthy_count += 1
            else:
                service_details.append({
                    "name": name,
                    "port": port,
                    "status": "down",
                    "error": result.stderr
                })
        except Exception as e:
            service_details.append({
                "name": name,
                "port": port,
                "status": "unreachable",
                "error": str(e)
            })
    
    status["services"] = service_details
    status["healthy"] = healthy_count == len(apis)
    status["collaboration_score"] = int(healthy_count / len(apis) * 100) if apis else 0
    
    # 获取系统资源
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:18220/metrics"],
            capture_output=True, text=True, timeout=3
        )
        if result.returncode == 0:
            status["metrics"] = json.loads(result.stdout)
    except:
        pass
    
    return status

def analyze_correlation(new_alert):
    """智能告警关联分析"""
    with lock:
        current_time = time.time()
        window = ALERT_CONFIG["correlation_window"]
        
        # 查找时间窗口内的相关告警
        related = []
        for alert in alert_history:
            if current_time - alert["timestamp"] < window:
                # 检查是否有共同的特征
                if (alert["service_name"] == new_alert["service_name"] or
                    alert["alert_type"] == new_alert["alert_type"]):
                    related.append(alert)
        
        if len(related) >= 2:
            # 发现关联告警
            new_alert["correlated"] = True
            return {
                "is_correlated": True,
                "related_count": len(related),
                "correlation_type": "service_cluster" if all(a["service_name"] == new_alert["service_name"] for a in related) else "type_cluster"
            }
        
        return {"is_correlated": False}

def check_escalation(alert_key):
    """检查是否需要升级告警"""
    with lock:
        count = alert_counter[alert_key] + 1
        alert_counter[alert_key] = count
        
        if count >= ALERT_CONFIG["escalation_threshold"]:
            return {
                "should_escalate": True,
                "level": "critical",
                "reason": f"连续{count}次告警"
            }
        return {"should_escalate": False}

def send_intelligent_alert(message, severity, service_name, metrics=None):
    """发送智能告警通知"""
    # 记录到数据库
    conn = sqlite3.connect(ALERT_DB)
    c = conn.cursor()
    c.execute('''INSERT INTO intelligent_alerts 
        (alert_type, severity, service_name, message, metrics_json, correlated, escalated)
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        ("agent_network", severity, service_name, message, 
         json.dumps(metrics) if metrics else None,
         1 if metrics and metrics.get("correlated") else 0,
         1 if metrics and metrics.get("escalated") else 0)
    )
    conn.commit()
    conn.close()
    
    # 发送通知
    emoji = "🔴" if severity == "critical" else "🟡" if severity == "warning" else "✅"
    full_message = f"{emoji} Agent协作网络告警\n\n{message}"
    
    # 尝试通过OpenClaw message工具发送
    print(f"[{datetime.now().isoformat()}] {full_message[:100]}...")

def run_intelligent_check():
    """运行智能检查"""
    global alert_history
    
    status = get_agent_network_status()
    timestamp = datetime.now().isoformat()
    
    issues = []
    alert_key = "agent_network"
    
    # 检查服务健康状态
    for svc in status.get("services", []):
        if svc["status"] != "healthy":
            issues.append(f"• {svc['name']} ({svc['port']}): {svc['status']}")
    
    # 计算健康分
    health_score = status.get("collaboration_score", 0)
    
    # 判断告警级别
    if health_score < ALERT_CONFIG["critical_threshold"]:
        severity = "critical"
    elif health_score < ALERT_CONFIG["warning_threshold"]:
        severity = "warning"
    else:
        severity = None
    
    now = time.time()
    cooldown = ALERT_CONFIG["cool_down"]
    
    if severity:
        # 构造告警消息
        if issues:
            alert_msg = f"健康分: {health_score}%\n故障服务:\n" + "\n".join(issues)
        else:
            alert_msg = f"健康分: {health_score}%"
        
        # 关联分析
        new_alert = {
            "alert_type": "agent_network",
            "service_name": "agent_network",
            "timestamp": now,
            "severity": severity
        }
        correlation = analyze_correlation(new_alert)
        
        # 检查升级
        escalation = check_escalation(alert_key)
        
        last_time = last_alert_time.get(alert_key, 0)
        
        if now - last_time > cooldown:
            metrics = {
                "correlation": correlation,
                "escalation": escalation,
                "services": status.get("services", [])
            }
            send_intelligent_alert(alert_msg, severity, "agent_network", metrics)
            
            last_alert_time[alert_key] = now
            last_alert_status[alert_key] = alert_msg
            
            # 更新历史
            alert_history.append(new_alert)
            # 保持历史精简
            alert_history = alert_history[-50:]
        else:
            print(f"[{timestamp}] 冷却中 (健康分: {health_score}%)")
    else:
        # 重置告警计数
        with lock:
            alert_counter[alert_key] = 0
        print(f"[{timestamp}] Agent协作网络健康: {health_score}%")
    
    return status

class AlertHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器"""
    
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {
                "status": "running",
                "service": "agent_alert_intelligence_v2",
                "version": "2.0",
                "timestamp": datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(response).encode())
        elif self.path == "/status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            conn = sqlite3.connect(ALERT_DB)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM intelligent_alerts WHERE severity = 'critical'")
            critical = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM intelligent_alerts WHERE severity = 'warning'")
            warning = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM intelligent_alerts WHERE correlated = 1")
            correlated = c.fetchone()[0]
            conn.close()
            
            response = {
                "service": "agent_alert_intelligence_v2",
                "config": ALERT_CONFIG,
                "stats": {
                    "critical_alerts": critical,
                    "warning_alerts": warning,
                    "correlated_alerts": correlated,
                    "active_counter": dict(alert_counter)
                },
                "network_status": get_agent_network_status()
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def start_server(port=18235):
    """启动智能告警服务"""
    server = HTTPServer(("", port), AlertHandler)
    print(f"🤖 Agent智能告警服务 v2.0 已启动: http://localhost:{port}")
    server.serve_forever()

def run_monitor():
    """运行监控循环"""
    print("开始Agent协作网络智能监控...")
    while True:
        try:
            run_intelligent_check()
        except Exception as e:
            print(f"监控错误: {e}")
        time.sleep(ALERT_CONFIG["check_interval"])

if __name__ == "__main__":
    init_alert_db()
    
    # 启动HTTP服务器
    server_thread = Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # 启动监控循环
    run_monitor()