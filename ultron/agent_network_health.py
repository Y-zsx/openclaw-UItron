#!/usr/bin/env python3
"""
Agent协作网络健康检查与自动恢复系统 - 增强版
第42世: Agent协作网络健康检查增强
功能:
  - 核心服务健康监控
  - Agent Mesh peer监控
  - 响应时间趋势分析
  - REST API暴露 (端口18110)
  - 综合健康评分
"""

import requests
import sqlite3
import json
import time
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import os
import threading

# 数据库路径
DB_PATH = "/root/.openclaw/workspace/ultron/agent_network_health.db"
LOG_FILE = "/root/.openclaw/workspace/ultron/logs/network_health.log"
API_PORT = 18110

# Agent协作网络核心服务
COLLAB_SERVICES = {
    8089: {"name": "api-gateway", "health_endpoint": "/health", "critical": True},
    8090: {"name": "secure-channel", "health_endpoint": "/health", "critical": True},
    8091: {"name": "identity-auth", "health_endpoint": "/health", "critical": True},
    8095: {"name": "collaboration-scheduler", "health_endpoint": "/health", "critical": True},
    8096: {"name": "agent-task-executor", "health_endpoint": "/health", "critical": True},
    18232: {"name": "orchestration-dashboard", "health_endpoint": "/api/orchestration/stats", "critical": False},
}

# systemd服务映射
SYSTEMD_SERVICES = {
    8089: "agent-service-mesh.service",
    8091: "identity-auth-api.service",
    8095: "agent-lifecycle-api.service",
    8096: "agent-task-executor.service",
    18232: "orchestration-api.service",
}

def init_db():
    """初始化健康检查数据库"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS health_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        service_port INTEGER NOT NULL,
        service_name TEXT NOT NULL,
        status TEXT NOT NULL,
        response_time_ms REAL,
        error_message TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS auto_recovery (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        service_port INTEGER NOT NULL,
        service_name TEXT NOT NULL,
        action TEXT NOT NULL,
        result TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS trend_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        service_port INTEGER NOT NULL,
        service_name TEXT NOT NULL,
        avg_response_ms REAL,
        min_response_ms REAL,
        max_response_ms REAL,
        availability_percent REAL
    )''')
    conn.commit()
    conn.close()

def check_service(port: int, endpoint: str) -> Dict:
    """检查单个服务健康状态"""
    start = time.time()
    url = f"http://localhost:{port}{endpoint}"
    try:
        resp = requests.get(url, timeout=5)
        response_time = (time.time() - start) * 1000
        
        try:
            data = resp.json()
            if port == 8089:
                is_healthy = data.get("status") == "ok" or "healthy" in data
            elif port == 18232:
                is_healthy = resp.status_code == 200
            else:
                is_healthy = data.get("status") == "ok" or data.get("healthy") != False
        except:
            is_healthy = resp.status_code == 200
            
        return {
            "port": port,
            "status": "healthy" if is_healthy else "unhealthy",
            "response_time_ms": round(response_time, 2),
            "http_code": resp.status_code,
            "error": None
        }
    except requests.exceptions.ConnectionError:
        return {"port": port, "status": "down", "response_time_ms": None, "http_code": None, "error": "Connection refused"}
    except requests.exceptions.Timeout:
        return {"port": port, "status": "timeout", "response_time_ms": None, "http_code": None, "error": "Request timeout"}
    except Exception as e:
        return {"port": port, "status": "error", "response_time_ms": None, "http_code": None, "error": str(e)}

def restart_service(service_name: str) -> bool:
    """尝试通过systemd重启服务"""
    try:
        result = subprocess.run(["systemctl", "restart", service_name], capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except:
        return False

def auto_recover(port: int, service_name: str) -> Dict:
    """尝试自动恢复服务"""
    result = {"port": port, "service_name": service_name, "action": None, "success": False, "message": ""}
    systemd_name = SYSTEMD_SERVICES.get(port)
    if systemd_name:
        result["action"] = f"systemctl restart {systemd_name}"
        result["success"] = restart_service(systemd_name)
        result["message"] = "Service restarted" if result["success"] else "Restart failed"
    return result

def log_health_check(check_result: Dict):
    """记录健康检查结果"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO health_checks (timestamp, service_port, service_name, status, response_time_ms, error_message)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (datetime.utcnow().isoformat(), check_result["port"], COLLAB_SERVICES[check_result["port"]]["name"],
         check_result["status"], check_result["response_time_ms"], check_result.get("error")))
    conn.commit()
    conn.close()

def log_recovery(recovery_result: Dict):
    """记录恢复操作"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO auto_recovery (timestamp, service_port, service_name, action, result)
        VALUES (?, ?, ?, ?, ?)''',
        (datetime.utcnow().isoformat(), recovery_result["port"], recovery_result["service_name"],
         recovery_result["action"], json.dumps(recovery_result)))
    conn.commit()
    conn.close()

def compute_trend_data():
    """计算趋势数据 (过去1小时)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cutoff = (datetime.utcnow() - timedelta(hours=1)).isoformat()
    
    trends = {}
    for port, config in COLLAB_SERVICES.items():
        c.execute('''SELECT AVG(response_time_ms), MIN(response_time_ms), MAX(response_time_ms),
            COUNT(CASE WHEN status='healthy' THEN 1 END) * 100.0 / COUNT(*) as availability
            FROM health_checks WHERE service_port = ? AND timestamp > ? AND response_time_ms IS NOT NULL''',
            (port, cutoff))
        row = c.fetchone()
        if row and row[0]:
            trends[port] = {
                "service_name": config["name"],
                "avg_response_ms": round(row[0], 2),
                "min_response_ms": round(row[1], 2),
                "max_response_ms": round(row[2], 2),
                "availability_percent": round(row[3], 1)
            }
            # 记录趋势数据
            c.execute('''INSERT INTO trend_data (timestamp, service_port, service_name, avg_response_ms, min_response_ms, max_response_ms, availability_percent)
                VALUES (?, ?, ?, ?, ?, ?, ?)''',
                (datetime.utcnow().isoformat(), port, config["name"], row[0], row[1], row[2], row[3]))
    
    conn.commit()
    conn.close()
    return trends

def check_agent_mesh():
    """检查Agent Mesh peer状态"""
    mesh_status = {"peers": [], "total": 0, "healthy": 0}
    try:
        # 尝试从agent mesh获取peer信息
        resp = requests.get("http://localhost:8089/api/mesh/peers", timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            mesh_status["peers"] = data.get("peers", [])
            mesh_status["total"] = len(mesh_status["peers"])
            mesh_status["healthy"] = len([p for p in mesh_status["peers"] if p.get("status") == "connected"])
    except:
        # Agent mesh可能没有运行，这是正常的
        mesh_status["note"] = "Agent mesh not available"
    return mesh_status

def get_network_status() -> Dict:
    """获取整个协作网络状态"""
    results = {}
    unhealthy_services = []
    recovered = []
    
    for port, config in COLLAB_SERVICES.items():
        result = check_service(port, config["health_endpoint"])
        results[port] = result
        log_health_check(result)
        
        if result["status"] != "healthy":
            unhealthy_services.append((port, config["name"], config.get("critical", False)))
            if config.get("critical", False):
                recovery = auto_recover(port, config["name"])
                log_recovery(recovery)
                if recovery["success"]:
                    time.sleep(3)
                    recheck = check_service(port, config["health_endpoint"])
                    if recheck["status"] == "healthy":
                        recovered.append(port)
    
    # 计算趋势
    trends = compute_trend_data()
    
    # 检查agent mesh
    mesh_status = check_agent_mesh()
    
    total = len(COLLAB_SERVICES)
    healthy = total - len(unhealthy_services)
    
    # 计算综合健康评分
    health_score = calculate_health_score(results, trends, mesh_status)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_services": total,
        "healthy_services": healthy,
        "unhealthy_services": len(unhealthy_services),
        "recovered": recovered,
        "details": results,
        "trends": trends,
        "mesh": mesh_status,
        "network_health": round(healthy / total * 100, 1),
        "health_score": health_score
    }

def calculate_health_score(results: Dict, trends: Dict, mesh_status: Dict) -> float:
    """计算综合健康评分 (0-100)"""
    # 基础分: 服务可用性 (60分)
    total = len(results)
    healthy_count = len([r for r in results.values() if r["status"] == "healthy"])
    base_score = (healthy_count / total) * 60
    
    # 响应时间分 (25分)
    response_scores = []
    for port, result in results.items():
        if result.get("response_time_ms"):
            rt = result["response_time_ms"]
            if rt < 50:
                score = 25
            elif rt < 100:
                score = 20
            elif rt < 200:
                score = 15
            elif rt < 500:
                score = 10
            else:
                score = 5
            response_scores.append(score)
    avg_response_score = sum(response_scores) / len(response_scores) if response_scores else 0
    
    # 趋势分 (10分)
    trend_score = 10
    for port, trend in trends.items():
        if trend.get("availability_percent", 100) < 99:
            trend_score -= 2
    trend_score = max(0, trend_score)
    
    # Agent Mesh分 (5分)
    mesh_score = 5 if mesh_status.get("total", 0) > 0 else 3
    
    return round(base_score + avg_response_score + trend_score + mesh_score, 1)

# ============ REST API ============

class NetworkHealthAPI(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        if path == "/health" or path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            status = get_network_status()
            self.wfile.write(json.dumps(status, indent=2).encode())
        elif path == "/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            # 快速状态
            results = {}
            for port, config in COLLAB_SERVICES.items():
                results[config["name"]] = check_service(port, config["health_endpoint"])
            self.wfile.write(json.dumps(results).encode())
        elif path == "/trends":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            trends = compute_trend_data()
            self.wfile.write(json.dumps(trends).encode())
        elif path == "/history":
            limit = int(query.get("limit", [10])[0])
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT * FROM health_checks ORDER BY timestamp DESC LIMIT ?", (limit,))
            rows = [dict(zip([d[0] for d in c.description], row)) for row in c.fetchall()]
            conn.close()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(rows).encode())
        elif path == "/mesh":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            mesh = check_agent_mesh()
            self.wfile.write(json.dumps(mesh).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # 静默日志

def start_api():
    """启动API服务器"""
    server = HTTPServer(("0.0.0.0", API_PORT), NetworkHealthAPI)
    print(f"🌐 Agent Network Health API running on port {API_PORT}")
    server.serve_forever()

def main():
    """主函数"""
    init_db()
    
    # 启动API后台线程
    api_thread = threading.Thread(target=start_api, daemon=True)
    api_thread.start()
    
    print("=" * 60)
    print("Agent协作网络健康检查 (增强版)")
    print("=" * 60)
    
    status = get_network_status()
    
    print(f"\n⏰ 检查时间: {status['timestamp']}")
    print(f"📊 网络健康度: {status['network_health']}%")
    print(f"🏥 健康评分: {status['health_score']}/100")
    print(f"✅ 健康服务: {status['healthy_services']}/{status['total_services']}")
    
    if status['unhealthy_services'] > 0:
        print(f"\n⚠️ 问题服务:")
        for port, result in status['details'].items():
            if result['status'] != 'healthy':
                print(f"  - {COLLAB_SERVICES[port]['name']}: {result['status']}")
    
    if status['recovered']:
        print(f"\n🔧 已自动恢复: {status['recovered']}")
    
    print("\n详细状态:")
    for port, result in status['details'].items():
        name = COLLAB_SERVICES[port]["name"]
        emoji = "✅" if result["status"] == "healthy" else "❌"
        rt = result.get("response_time_ms", "N/A")
        print(f"  {emoji} {name}: {result['status']} ({rt}ms)")
    
    if status['trends']:
        print("\n📈 趋势 (1小时):")
        for port, trend in status['trends'].items():
            print(f"  • {trend['service_name']}: {trend['avg_response_ms']}ms avg, {trend['availability_percent']}% 可用")
    
    if status['mesh'].get('total', 0) > 0:
        print(f"\n🔗 Agent Mesh: {status['mesh']['healthy']}/{status['mesh']['total']} peers")
    
    print("=" * 60)
    print(f"🌐 API: http://localhost:{API_PORT}/health")
    
    # 保存状态
    with open("/root/.openclaw/workspace/ultron/state/network_health.json", "w") as f:
        json.dump(status, f, indent=2)
    
    return status

if __name__ == "__main__":
    main()