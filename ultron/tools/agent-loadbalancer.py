#!/usr/bin/env python3
"""
Agent服务负载均衡器
提供多种负载均衡策略：轮询、最小连接数、加权轮询
"""
import http.server
import socketserver
import json
import time
import threading
from urllib.parse import urlparse, parse_qs
from datetime import datetime

PORT = 18301

# Agent后端服务配置
AGENTS = [
    {"name": "collaborate-center", "host": "localhost", "port": 18290, "weight": 10},
    {"name": "service-governance", "host": "localhost", "port": 18291, "weight": 10},
    {"name": "collaboration-api", "host": "localhost", "port": 18292, "weight": 10},
    {"name": "task-scheduler", "host": "localhost", "port": 18293, "weight": 8},
    {"name": "result-aggregator", "host": "localhost", "port": 18294, "weight": 8},
]

# 负载均衡状态
class LoadBalancer:
    def __init__(self, strategy="round_robin"):
        self.strategy = strategy
        self.agent_states = {a["name"]: {"connections": 0, "healthy": True, "last_check": None} for a in AGENTS}
        self.round_robin_index = 0
        self.health_check_interval = 30
        self.start_health_check()
    
    def start_health_check(self):
        """启动健康检查线程"""
        def check():
            while True:
                for agent in AGENTS:
                    try:
                        import urllib.request
                        url = f"http://{agent['host']}:{agent['port']}/health"
                        req = urllib.request.Request(url)
                        with urllib.request.urlopen(req, timeout=3) as resp:
                            self.agent_states[agent["name"]]["healthy"] = resp.status == 200
                    except:
                        self.agent_states[agent["name"]]["healthy"] = False
                    self.agent_states[agent["name"]]["last_check"] = datetime.now().isoformat()
                time.sleep(self.health_check_interval)
        
        thread = threading.Thread(target=check, daemon=True)
        thread.start()
    
    def get_healthy_agents(self):
        """获取健康的后端服务"""
        return [a for a in AGENTS if self.agent_states[a["name"]]["healthy"]]
    
    def select_backend(self):
        """根据策略选择后端"""
        healthy = self.get_healthy_agents()
        if not healthy:
            return None
        
        if self.strategy == "round_robin":
            # 轮询
            backend = healthy[self.round_robin_index % len(healthy)]
            self.round_robin_index += 1
            return backend
        
        elif self.strategy == "least_conn":
            # 最小连接数
            backend = min(healthy, key=lambda a: self.agent_states[a["name"]]["connections"])
            return backend
        
        elif self.strategy == "weighted":
            # 加权轮询
            total_weight = sum(a["weight"] for a in healthy)
            r = (self.round_robin_index * 7) % total_weight  # pseudo-random but deterministic
            self.round_robin_index += 1
            cumulative = 0
            for a in healthy:
                cumulative += a["weight"]
                if r < cumulative:
                    return a
            return healthy[0]
        
        return healthy[0]
    
    def register_connection(self, agent_name):
        """注册新连接"""
        if agent_name in self.agent_states:
            self.agent_states[agent_name]["connections"] += 1
    
    def unregister_connection(self, agent_name):
        """注销连接"""
        if agent_name in self.agent_states and self.agent_states[agent_name]["connections"] > 0:
            self.agent_states[agent_name]["connections"] -= 1
    
    def get_stats(self):
        """获取负载均衡统计"""
        return {
            "strategy": self.strategy,
            "total_agents": len(AGENTS),
            "healthy_agents": len(self.get_healthy_agents()),
            "agents": [
                {
                    "name": a["name"],
                    "healthy": self.agent_states[a["name"]]["healthy"],
                    "connections": self.agent_states[a["name"]]["connections"],
                    "weight": a["weight"],
                    "last_check": self.agent_states[a["name"]]["last_check"]
                }
                for a in AGENTS
            ]
        }

lb = LoadBalancer(strategy="weighted")

class LoadBalancerHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 禁用日志
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "healthy",
                "service": "loadbalancer",
                "port": PORT,
                "strategy": lb.strategy
            }).encode())
        
        elif parsed.path == "/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(lb.get_stats()).encode())
        
        elif parsed.path == "/agents":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(AGENTS).encode())
        
        elif parsed.path == "/forward":
            # 测试转发功能
            backend = lb.select_backend()
            if not backend:
                self.send_error(503, "No healthy backends")
                return
            
            lb.register_connection(backend["name"])
            try:
                import urllib.request
                url = f"http://{backend['host']}:{backend['port']}/health"
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "forwarded_to": backend["name"],
                    "response": json.loads(data.decode())
                }).encode())
            finally:
                lb.unregister_connection(backend["name"])
        
        else:
            self.send_error(404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/forward":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            
            backend = lb.select_backend()
            if not backend:
                self.send_error(503, "No healthy backends")
                return
            
            lb.register_connection(backend["name"])
            try:
                import urllib.request
                url = f"http://{backend['host']}:{backend['port']}/process"
                req = urllib.request.Request(url, data=body, method="POST")
                req.add_header("Content-Type", "application/json")
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({
                    "forwarded_to": backend["name"],
                    "backend_port": backend["port"],
                    "response": json.loads(data.decode()) if data else {}
                }).encode())
            except Exception as e:
                self.send_error(502, str(e))
            finally:
                lb.unregister_connection(backend["name"])
        
        elif parsed.path == "/strategy":
            try:
                body = json.loads(body) if (content_length := int(self.headers.get("Content-Length", 0))) > 0 else {}
                if "strategy" in body:
                    lb.strategy = body["strategy"]
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "ok", "strategy": lb.strategy}).encode())
            except:
                self.send_error(400)
        else:
            self.send_error(404)

class ReuseAddrTCPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True

if __name__ == "__main__":
    print(f"Starting Agent LoadBalancer on port {PORT}")
    print(f"Strategy: {lb.strategy}")
    print(f"Backends: {', '.join(a['name'] for a in AGENTS)}")
    
    with ReuseAddrTCPServer(("", PORT), LoadBalancerHandler) as httpd:
        httpd.serve_forever()