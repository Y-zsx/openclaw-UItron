#!/usr/bin/env python3
"""
Agent健康监控集成 - 端口18210
整合多个健康检查源，提供统一的Agent健康状态管理
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

# 集成端点配置 - 每个服务配置正确的健康检查端点
INTEGRATED_SERVICES = {
    "health_api": {"url": "http://localhost:18196/", "name": "健康检查API"},
    "task_monitor": {"url": "http://localhost:18195/", "name": "任务监控API"},
    "collab_center": {"url": "http://localhost:18201/health", "name": "协作中心"},
    "task_retry": {"url": "http://localhost:18197/", "name": "任务重试管理器"},
    "system_summary": {"url": "http://localhost:18199/health", "name": "系统总结API"},
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
        
        else:
            self.send_json_response({
                "service": "Agent Health Integration",
                "version": "1.0",
                "endpoints": ["/health", "/agents", "/services", "/alerts", "/metrics", "/score"]
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