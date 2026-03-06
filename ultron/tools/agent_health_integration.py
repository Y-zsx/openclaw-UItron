#!/usr/bin/env python3
"""
Agent健康监控集成 - 端口18210
整合多个健康检查源，提供统一的Agent健康状态管理
增强版：增加OpenClaw节点监控、Gateway状态、健康趋势分析
"""
import json
import subprocess
import time
import os
import sqlite3
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import requests

DATA_DIR = "/root/.openclaw/workspace/ultron/data"
INTEGRATION_DB = f"{DATA_DIR}/agent_health_integration.db"

# OpenClaw API配置
OPENCLAW_API = "http://localhost:18789"
GATEWAY_PORT = 18789

# 集成端点配置 - 每个服务配置正确的健康检查端点
INTEGRATED_SERVICES = {
    "health_api": {"url": "http://localhost:18196/", "name": "健康检查API"},
    "task_monitor": {"url": "http://localhost:18195/", "name": "任务监控API"},
    "collab_center": {"url": "http://localhost:18201/health", "name": "协作中心"},
    "task_retry": {"url": "http://localhost:18197/", "name": "任务重试管理器"},
    "system_summary": {"url": "http://localhost:18199/health", "name": "系统总结API"},
    "decision_engine": {"url": "http://localhost:18120/health", "name": "决策引擎"},
    "automation": {"url": "http://localhost:18128/health", "name": "自动化引擎"},
    "workflow": {"url": "http://localhost:18100/health", "name": "工作流引擎"},
    "agent_network": {"url": "http://localhost:18150/health", "name": "Agent网络"},
    "executor": {"url": "http://localhost:8096/health", "name": "Agent执行器"},
}

# Agent健康状态阈值
HEALTH_THRESHOLDS = {
    "critical": 30,      # 低于30%健康分
    "warning": 60,       # 低于60%健康分
    "healthy": 80,       # 高于80%健康分
}

def init_db():
    """初始化数据库"""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(INTEGRATION_DB)
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS agent_health (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        health_score REAL,
        status TEXT,
        cpu_usage REAL,
        memory_usage REAL,
        task_count INTEGER,
        error_count INTEGER,
        last_heartbeat DATETIME,
        details TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS health_integrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_name TEXT NOT NULL,
        last_check DATETIME,
        status TEXT,
        response_time REAL,
        details TEXT
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS health_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_id TEXT,
        alert_type TEXT,
        severity TEXT,
        message TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        acknowledged INTEGER DEFAULT 0
    )''')
    
    conn.commit()
    conn.close()

def check_service_health(url, timeout=3, retries=2):
    """检查服务健康状态 - 带重试机制避免误报"""
    last_error = None
    
    for attempt in range(retries):
        try:
            start = time.time()
            result = requests.get(url, timeout=timeout)
            elapsed = (time.time() - start) * 1000
            
            # 更准确的健康判断: 2xx都是健康的
            if 200 <= result.status_code < 300:
                return {
                    "status": "healthy",
                    "latency_ms": round(elapsed, 1),
                    "code": result.status_code
                }
            elif result.status_code < 400:
                # 3xx重定向也可能表示服务正常
                return {
                    "status": "healthy",
                    "latency_ms": round(elapsed, 1),
                    "code": result.status_code
                }
            else:
                last_error = f"HTTP {result.status_code}"
                if attempt < retries - 1:
                    time.sleep(0.1)  # 短暂等待后重试
                    continue
                    
        except requests.exceptions.Timeout:
            last_error = "Timeout"
            if attempt < retries - 1:
                time.sleep(0.1)
                continue
        except Exception as e:
            last_error = str(e)
            if attempt < retries - 1:
                time.sleep(0.1)
                continue
    
    return {"status": "degraded" if last_error else "unhealthy", "error": last_error}

def fetch_agent_metrics():
    """从各服务获取Agent指标"""
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "services": {},
        "agents": []
    }
    
    # 检查集成服务状态
    for name, config in INTEGRATED_SERVICES.items():
        health = check_service_health(config["url"])
        metrics["services"][name] = {
            "name": config["name"],
            "url": config["url"],
            "status": health.get("status", "unknown"),
            "latency_ms": health.get("latency_ms", 0)
        }
    
    # 从协作中心获取注册Agent信息
    try:
        resp = requests.get("http://localhost:18201/services", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            metrics["agents"] = data.get("services", [])
    except:
        pass
    
    return metrics

def calculate_agent_health_score(agent_data):
    """计算Agent健康分数"""
    score = 100.0
    
    # 基于任务成功率扣分
    if "task_success_rate" in agent_data:
        score -= (100 - agent_data["task_success_rate"]) * 0.3
    
    # 基于错误数扣分
    if "error_count" in agent_data:
        score -= min(agent_data["error_count"] * 5, 30)
    
    # 基于响应时间扣分
    if "avg_response_time" in agent_data:
        if agent_data["avg_response_time"] > 5000:
            score -= 20
        elif agent_data["avg_response_time"] > 2000:
            score -= 10
    
    return max(0, min(100, score))

def check_gateway_status():
    """检查OpenClaw Gateway状态"""
    try:
        # 尝试多种端点
        endpoints = [
            f"http://localhost:{GATEWAY_PORT}/api/status",
            f"http://localhost:{GATEWAY_PORT}/status",
            f"http://localhost:{GATEWAY_PORT}/health",
        ]
        
        for url in endpoints:
            try:
                resp = requests.get(url, timeout=2)
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "status": "healthy",
                        "gateway_status": data.get("status", "running"),
                        "channels": data.get("channels", []),
                        "uptime": data.get("uptime", 0)
                    }
            except:
                continue
        
        # 如果API不可用，检查端口是否开放
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', GATEWAY_PORT))
        sock.close()
        
        if result == 0:
            return {"status": "healthy", "note": "Gateway port open, API not responding"}
        else:
            return {"status": "unhealthy", "error": "Gateway port not accessible"}
    except Exception as e:
        return {"status": "unknown", "error": str(e)}

def get_system_resources():
    """获取系统资源使用情况"""
    try:
        # CPU使用率
        cpu_cmd = "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"
        cpu_result = subprocess.run(cpu_cmd, shell=True, capture_output=True, text=True)
        cpu_usage = float(cpu_result.stdout.strip()) if cpu_result.stdout.strip() else 0
        
        # 内存使用率
        mem_cmd = "free | grep Mem | awk '{printf \"%.1f\", $3/$2 * 100}'"
        mem_result = subprocess.run(mem_cmd, shell=True, capture_output=True, text=True)
        mem_usage = float(mem_result.stdout.strip()) if mem_result.stdout.strip() else 0
        
        # 磁盘使用率
        disk_cmd = "df -h / | tail -1 | awk '{print $5}' | cut -d'%' -f1"
        disk_result = subprocess.run(disk_cmd, shell=True, capture_output=True, text=True)
        disk_usage = float(disk_result.stdout.strip()) if disk_result.stdout.strip() else 0
        
        # 负载平均值
        load_cmd = "uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | cut -d',' -f1"
        load_result = subprocess.run(load_cmd, shell=True, capture_output=True, text=True)
        load_avg = float(load_result.stdout.strip()) if load_result.stdout.strip() else 0
        
        return {
            "cpu_percent": round(cpu_usage, 1),
            "memory_percent": round(mem_usage, 1),
            "disk_percent": round(disk_usage, 1),
            "load_avg_1m": round(load_avg, 2),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e)}

def send_dingtalk_alert(message, severity="warning"):
    """发送钉钉告警通知"""
    try:
        # 从环境变量或配置文件获取钉钉webhook
        webhook = os.environ.get("DINGTALK_WEBHOOK")
        if not webhook:
            # 尝试读取配置文件
            config_path = "/root/.openclaw/workspace/ultron/config/dingtalk.json"
            if os.path.exists(config_path):
                with open(config_path) as f:
                    config = json.load(f)
                    webhook = config.get("webhook")
        
        if not webhook:
            return {"status": "skipped", "reason": "no webhook configured"}
        
        data = {
            "msgtype": "text",
            "text": {
                "content": f"🤖 奥创健康监控告警\n[{severity.upper()}]\n{message}\n时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
        }
        
        resp = requests.post(webhook, json=data, timeout=5)
        if resp.status_code == 200:
            return {"status": "sent", "success": True}
        else:
            return {"status": "error", "code": resp.status_code}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def analyze_health_trends(hours=24):
    """分析健康趋势"""
    conn = sqlite3.connect(INTEGRATION_DB)
    c = conn.cursor()
    
    # 获取历史服务状态
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    c.execute('''SELECT service_name, status, response_time, last_check 
        FROM health_integrations 
        WHERE last_check > ? 
        ORDER BY last_check''', (since,))
    
    trends = {}
    for row in c.fetchall():
        svc = row[0]
        if svc not in trends:
            trends[svc] = {"healthy_count": 0, "unhealthy_count": 0, "avg_response": []}
        
        if row[1] == "healthy":
            trends[svc]["healthy_count"] += 1
        else:
            trends[svc]["unhealthy_count"] += 1
        
        if row[2]:
            trends[svc]["avg_response"].append(row[2])
    
    # 计算统计
    result = {}
    for svc, data in trends.items():
        avg_resp = sum(data["avg_response"]) / len(data["avg_response"]) if data["avg_response"] else 0
        total = data["healthy_count"] + data["unhealthy_count"]
        health_rate = (data["healthy_count"] / total * 100) if total > 0 else 0
        
        result[svc] = {
            "health_rate": round(health_rate, 1),
            "total_checks": total,
            "avg_response_ms": round(avg_resp, 1),
            "status": "healthy" if health_rate >= 95 else "degraded" if health_rate >= 80 else "critical"
        }
    
    conn.close()
    return result

def record_agent_health(agent_id, health_data):
    """记录Agent健康数据"""
    conn = sqlite3.connect(INTEGRATION_DB)
    c = conn.cursor()
    
    c.execute('''INSERT INTO agent_health 
        (agent_id, health_score, status, cpu_usage, memory_usage, 
         task_count, error_count, last_heartbeat, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (agent_id, health_data.get("score", 0), health_data.get("status", "unknown"),
         health_data.get("cpu_usage", 0), health_data.get("memory_usage", 0),
         health_data.get("task_count", 0), health_data.get("error_count", 0),
         datetime.now().isoformat(), json.dumps(health_data))
    )
    
    conn.commit()
    conn.close()

def create_health_alert(agent_id, alert_type, severity, message):
    """创建健康告警"""
    conn = sqlite3.connect(INTEGRATION_DB)
    c = conn.cursor()
    
    c.execute('''INSERT INTO health_alerts 
        (agent_id, alert_type, severity, message) VALUES (?, ?, ?, ?)''',
        (agent_id, alert_type, severity, message))
    
    conn.commit()
    conn.close()

def get_agent_health_summary():
    """获取Agent健康摘要"""
    conn = sqlite3.connect(INTEGRATION_DB)
    c = conn.cursor()
    
    # 获取最新健康数据
    c.execute('''SELECT agent_id, health_score, status, timestamp 
        FROM agent_health ORDER BY timestamp DESC LIMIT 20''')
    
    agents = {}
    for row in c.fetchall():
        aid = row[0]
        if aid not in agents:
            agents[aid] = {"health_score": row[1], "status": row[2], "last_update": row[3]}
    
    # 获取未确认告警
    c.execute('''SELECT COUNT(*) FROM health_alerts WHERE acknowledged = 0''')
    alert_count = c.fetchone()[0]
    
    # 获取服务状态 - 只获取每个服务的最新记录，避免历史数据干扰
    c.execute('''SELECT service_name, status, response_time 
        FROM health_integrations 
        WHERE id IN (
            SELECT MAX(id) FROM health_integrations GROUP BY service_name
        )''')
    services = []
    for row in c.fetchall():
        services.append({"name": row[0], "status": row[1], "response_time": row[2]})
    
    conn.close()
    
    return {
        "agents": agents,
        "alert_count": alert_count,
        "services": services,
        "timestamp": datetime.now().isoformat()
    }

class IntegrationHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def send_json_response(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/health":
            # 整体健康检查
            metrics = get_agent_health_summary()
            self.send_json_response({
                "status": "healthy" if metrics.get("alert_count", 0) < 5 else "degraded",
                "timestamp": datetime.now().isoformat(),
                "metrics": metrics
            })
        
        elif path == "/agents":
            # Agent列表和状态
            summary = get_agent_health_summary()
            self.send_json_response(summary)
        
        elif path == "/services":
            # 集成服务状态
            services_status = {}
            for name, config in INTEGRATED_SERVICES.items():
                health = check_service_health(config["url"])
                services_status[name] = {
                    "name": config["name"],
                    "url": config["url"],
                    "status": health.get("status", "unknown"),
                    "latency_ms": health.get("latency_ms", 0)
                }
            self.send_json_response({"services": services_status})
        
        elif path == "/alerts":
            # 告警列表
            conn = sqlite3.connect(INTEGRATION_DB)
            c = conn.cursor()
            c.execute('''SELECT * FROM health_alerts ORDER BY timestamp DESC LIMIT 50''')
            alerts = []
            for row in c.fetchall():
                alerts.append({
                    "id": row[0], "agent_id": row[1], "alert_type": row[2],
                    "severity": row[3], "message": row[4], "timestamp": row[5],
                    "acknowledged": bool(row[6])
                })
            conn.close()
            self.send_json_response({"alerts": alerts})
        
        elif path == "/metrics":
            # 实时指标
            metrics = fetch_agent_metrics()
            self.send_json_response(metrics)
        
        elif path == "/score":
            # 综合健康分数
            summary = get_agent_health_summary()
            alert_penalty = summary.get("alert_count", 0) * 2
            service_penalty = sum(
                20 for s in summary.get("services", []) 
                if s.get("status") != "healthy"
            )
            score = max(0, 100 - alert_penalty - service_penalty)
            self.send_json_response({
                "health_score": score,
                "status": "healthy" if score >= 80 else "warning" if score >= 60 else "critical",
                "details": {
                    "alert_count": summary.get("alert_count", 0),
                    "service_issues": service_penalty // 20
                }
            })
        
        elif path.startswith("/agent/"):
            # 单个Agent详情
            agent_id = path.split("/")[-1]
            conn = sqlite3.connect(INTEGRATION_DB)
            c = conn.cursor()
            c.execute('''SELECT * FROM agent_health 
                WHERE agent_id = ? ORDER BY timestamp DESC LIMIT 10''',
                (agent_id,))
            records = []
            for row in c.fetchall():
                records.append({
                    "health_score": row[2], "status": row[3], "timestamp": row[8]
                })
            conn.close()
            self.send_json_response({"agent_id": agent_id, "records": records})
        
        elif path == "/gateway":
            # OpenClaw Gateway状态
            gateway_status = check_gateway_status()
            self.send_json_response(gateway_status)
        
        elif path == "/resources":
            # 系统资源使用情况
            resources = get_system_resources()
            self.send_json_response(resources)
        
        elif path == "/trends":
            # 健康趋势分析
            params = parse_qs(parsed.query)
            hours = int(params.get("hours", ["24"])[0])
            trends = analyze_health_trends(hours)
            self.send_json_response({
                "trends": trends,
                "period_hours": hours,
                "timestamp": datetime.now().isoformat()
            })
        
        elif path == "/notify":
            # 测试告警通知
            params = parse_qs(parsed.query)
            message = params.get("message", ["Test alert"])[0]
            severity = params.get("severity", ["info"])[0]
            result = send_dingtalk_alert(message, severity)
            self.send_json_response(result)
        
        elif path == "/comprehensive":
            # 综合健康报告
            services = {}
            for name, config in INTEGRATED_SERVICES.items():
                health = check_service_health(config["url"])
                services[name] = {"name": config["name"], "status": health.get("status"), "latency": health.get("latency_ms")}
            
            gateway = check_gateway_status()
            resources = get_system_resources()
            summary = get_agent_health_summary()
            
            # 计算综合分数
            service_issues = sum(1 for s in services.values() if s.get("status") != "healthy")
            alert_count = summary.get("alert_count", 0)
            resource_penalty = 0
            if resources.get("cpu_percent", 0) > 80:
                resource_penalty += 10
            if resources.get("memory_percent", 0) > 80:
                resource_penalty += 10
            if resources.get("disk_percent", 0) > 90:
                resource_penalty += 15
            
            score = max(0, 100 - service_issues * 15 - alert_count * 3 - resource_penalty)
            
            self.send_json_response({
                "overall_score": score,
                "status": "healthy" if score >= 80 else "warning" if score >= 60 else "critical",
                "services": services,
                "gateway": gateway,
                "resources": resources,
                "alerts": alert_count,
                "timestamp": datetime.now().isoformat()
            })
        
        else:
            self.send_json_response({
                "service": "Agent Health Integration",
                "version": "2.0",
                "endpoints": ["/health", "/agents", "/services", "/alerts", "/metrics", "/score", 
                              "/gateway", "/resources", "/trends", "/comprehensive"]
            })

def run_background_monitor():
    """后台监控线程"""
    while True:
        try:
            # 检查所有集成服务
            conn = sqlite3.connect(INTEGRATION_DB)
            c = conn.cursor()
            
            for name, config in INTEGRATED_SERVICES.items():
                health = check_service_health(config["url"])
                c.execute('''INSERT INTO health_integrations 
                    (service_name, last_check, status, response_time) 
                    VALUES (?, ?, ?, ?)''',
                    (name, datetime.now().isoformat(), 
                     health.get("status", "unknown"),
                     health.get("latency_ms", 0)))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Monitor error: {e}")
        
        time.sleep(60)

def main():
    init_db()
    
    # 启动后台监控线程
    monitor_thread = threading.Thread(target=run_background_monitor, daemon=True)
    monitor_thread.start()
    
    server = HTTPServer(('0.0.0.0', 18210), IntegrationHandler)
    print(f"Agent Health Integration API running on port 18210")
    server.serve_forever()

if __name__ == "__main__":
    main()