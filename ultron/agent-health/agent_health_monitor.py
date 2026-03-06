#!/usr/bin/env python3
"""
Agent健康检查与告警系统
端口: 18299
"""
import json
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError

PORT = 18299

# Agent注册表 - 追踪实际运行的服务
AGENTS = {
    "collab-center": {
        "url": "http://localhost:18201/health",
        "interval": 30,
        "timeout": 5,
        "status": "unknown",
        "last_check": None,
        "failures": 0,
        "alert_threshold": 3
    },
    "service-governance": {
        "url": "http://localhost:18250/health",
        "interval": 30,
        "timeout": 5,
        "status": "unknown",
        "last_check": None,
        "failures": 0,
        "alert_threshold": 3
    },
    "agent-collaboration-api": {
        "url": "http://localhost:18295/health",
        "interval": 30,
        "timeout": 5,
        "status": "unknown",
        "last_check": None,
        "failures": 0,
        "alert_threshold": 3
    },
    "agent-task-scheduler": {
        "url": "http://localhost:18297/health",
        "interval": 30,
        "timeout": 5,
        "status": "unknown",
        "last_check": None,
        "failures": 0,
        "alert_threshold": 3
    },
    "agent-result-aggregator": {
        "url": "http://localhost:18298/health",
        "interval": 30,
        "timeout": 5,
        "status": "unknown",
        "last_check": None,
        "failures": 0,
        "alert_threshold": 3
    }
}

# 告警记录
ALERTS = []

def check_agent(agent_id):
    """检查单个Agent健康状态"""
    agent = AGENTS.get(agent_id)
    if not agent:
        return None
    
    url = agent["url"]
    timeout = agent["timeout"]
    
    try:
        req = Request(url)
        req.add_header('User-Agent', 'Ultron-HealthCheck/1.0')
        with urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                agent["status"] = "healthy"
                agent["failures"] = 0
                return {"status": "healthy", "code": resp.status}
            else:
                agent["status"] = "degraded"
                agent["failures"] += 1
                return {"status": "degraded", "code": resp.status}
    except URLError as e:
        agent["status"] = "down"
        agent["failures"] += 1
        return {"status": "down", "error": str(e)}
    except Exception as e:
        agent["status"] = "error"
        agent["failures"] += 1
        return {"status": "error", "error": str(e)}
    finally:
        agent["last_check"] = datetime.now().isoformat()

def check_all_agents():
    """检查所有Agent"""
    results = {}
    for agent_id in AGENTS:
        result = check_agent(agent_id)
        results[agent_id] = result
        
        # 告警逻辑
        if result and result["status"] != "healthy" and AGENTS[agent_id]["failures"] >= AGENTS[agent_id]["alert_threshold"]:
            alert = {
                "agent_id": agent_id,
                "status": result["status"],
                "failures": AGENTS[agent_id]["failures"],
                "timestamp": datetime.now().isoformat()
            }
            # 避免重复告警
            if not any(a["agent_id"] == agent_id and a["status"] == result["status"] for a in ALERTS[-5:]):
                ALERTS.append(alert)
    
    return results

def background_monitor():
    """后台监控线程"""
    while True:
        check_all_agents()
        time.sleep(30)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        path = self.path
        
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "agent-health-monitor"}).encode())
            
        elif path == "/agents" or path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            # 立即检查一次
            check_all_agents()
            
            response = {
                "timestamp": datetime.now().isoformat(),
                "agents": {
                    aid: {
                        "status": a["status"],
                        "url": a["url"],
                        "last_check": a["last_check"],
                        "failures": a["failures"]
                    }
                    for aid, a in AGENTS.items()
                },
                "summary": {
                    "total": len(AGENTS),
                    "healthy": sum(1 for a in AGENTS.values() if a["status"] == "healthy"),
                    "degraded": sum(1 for a in AGENTS.values() if a["status"] == "degraded"),
                    "down": sum(1 for a in AGENTS.values() if a["status"] == "down")
                }
            }
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        elif path == "/alerts":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"alerts": ALERTS[-20:], "count": len(ALERTS)}).encode())
            
        elif path == "/summary":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            healthy = sum(1 for a in AGENTS.values() if a["status"] == "healthy")
            total = len(AGENTS)
            health_rate = (healthy / total * 100) if total > 0 else 0
            
            response = {
                "timestamp": datetime.now().isoformat(),
                "health_rate": f"{health_rate:.1f}%",
                "total_agents": total,
                "healthy_agents": healthy,
                "status": "healthy" if health_rate == 100 else "degraded" if health_rate >= 66 else "critical"
            }
            self.wfile.write(json.dumps(response).encode())
            
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == "/register":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            
            agent_id = data.get("agent_id")
            url = data.get("url")
            
            if agent_id and url:
                AGENTS[agent_id] = {
                    "url": url,
                    "interval": data.get("interval", 30),
                    "timeout": data.get("timeout", 5),
                    "status": "unknown",
                    "last_check": None,
                    "failures": 0,
                    "alert_threshold": data.get("alert_threshold", 3)
                }
                self.send_response(201)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "registered", "agent_id": agent_id}).encode())
            else:
                self.send_response(400)
                self.end_headers()

if __name__ == "__main__":
    # 启动后台监控线程
    monitor_thread = threading.Thread(target=background_monitor, daemon=True)
    monitor_thread.start()
    
    # 启动HTTP服务
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Agent Health Monitor running on port {PORT}")
    server.serve_forever()