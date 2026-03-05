#!/usr/bin/env python3
"""
编排引擎 API 服务
端口: 18102
"""

import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time
import os

# 确保路径正确
sys.path.insert(0, "/root/.openclaw/workspace/ultron/tools/orchestrator")
from orchestrator import (
    OrchestrationEngine, get_engine, AgentSpec, 
    AgentCapability, OrchestrationStatus
)

PORT = 18102

class OrchestratorAPIHandler(BaseHTTPRequestHandler):
    engine: OrchestrationEngine = get_engine()
    
    def log_message(self, format, *args):
        pass
    
    def send_json(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        # 健康检查
        if path == "/health" or path == "/api/health":
            self.send_json(200, {
                "status": "ok", 
                "service": "orchestrator",
                "port": PORT,
                "version": "1.0.0"
            })
        
        # Agent注册表
        elif path == "/api/agents" or path == "/agents":
            agents = self.engine.registry.list_all()
            self.send_json(200, {
                "agents": [
                    {
                        "id": a.id,
                        "name": a.name,
                        "capabilities": a.capabilities,
                        "endpoint": a.endpoint,
                        "status": a.status,
                        "metadata": a.metadata
                    }
                    for a in agents
                ],
                "count": len(agents)
            })
        
        # Agent发现
        elif path == "/api/agents/discover" or path == "/agents/discover":
            discovered = self.engine.discover_agents()
            self.send_json(200, {
                "discovered": [
                    {
                        "id": a.id,
                        "name": a.name,
                        "capabilities": a.capabilities,
                        "endpoint": a.endpoint,
                        "status": a.status
                    }
                    for a in discovered
                ],
                "count": len(discovered)
            })
        
        # 按能力查找Agent
        elif path.startswith("/api/agents/capability/"):
            capability = path.split("/")[-1]
            agents = self.engine.registry.find_by_capability(capability)
            self.send_json(200, {
                "capability": capability,
                "agents": [a.id for a in agents],
                "count": len(agents)
            })
        
        # 单个Agent信息
        elif path.startswith("/api/agents/"):
            agent_id = path.split("/")[-1]
            agent = self.engine.registry.get(agent_id)
            if agent:
                self.send_json(200, {
                    "id": agent.id,
                    "name": agent.name,
                    "capabilities": agent.capabilities,
                    "endpoint": agent.endpoint,
                    "status": agent.status,
                    "metadata": agent.metadata
                })
            else:
                self.send_json(404, {"error": "Agent not found"})
        
        # 编排列表
        elif path == "/api/orchestrations" or path == "/orchestrations":
            orchestrations = self.engine.list_orchestrations()
            self.send_json(200, {
                "orchestrations": orchestrations,
                "count": len(orchestrations)
            })
        
        # 单个编排状态
        elif path.startswith("/api/orchestrations/") and path != "/api/orchestrations":
            parts = path.split("/")
            if len(parts) >= 3:
                orch_id = parts[-1]
                status = self.engine.get_status(orch_id)
                if status:
                    self.send_json(200, status)
                else:
                    self.send_json(404, {"error": "Orchestration not found"})
        
        # 编排类型信息
        elif path == "/api/types":
            self.send_json(200, {
                "capabilities": [c.value for c in AgentCapability],
                "statuses": {
                    "orchestration": [s.value for s in OrchestrationStatus]
                }
            })
        
        # 仪表盘
        elif path == "/api/dashboard" or path == "/dashboard":
            agents = self.engine.registry.list_all()
            orchestrations = self.engine.list_orchestrations()
            
            active_orch = [o for o in orchestrations if o["status"] == "running"]
            
            self.send_json(200, {
                "agents": {
                    "total": len(agents),
                    "online": sum(1 for a in agents if a.status == "online"),
                    "offline": sum(1 for a in agents if a.status == "offline")
                },
                "orchestrations": {
                    "total": len(orchestrations),
                    "running": len(active_orch),
                    "completed": sum(1 for o in orchestrations if o["status"] == "completed"),
                    "failed": sum(1 for o in orchestrations if o["status"] == "failed")
                }
            })
        
        else:
            self.send_json(404, {"error": "Not found"})
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        # 注册Agent
        if path == "/api/agents/register" or path == "/agents/register":
            agent = AgentSpec(
                id=data.get("id", ""),
                name=data.get("name", ""),
                capabilities=data.get("capabilities", []),
                endpoint=data.get("endpoint", ""),
                status=data.get("status", "online"),
                metadata=data.get("metadata", {})
            )
            
            if not agent.id or not agent.name:
                self.send_json(400, {"error": "id and name required"})
                return
            
            self.engine.register_agent(agent)
            self.send_json(201, {"success": True, "agent_id": agent.id})
        
        # 注销Agent
        elif path == "/api/agents/unregister":
            agent_id = data.get("agent_id")
            if not agent_id:
                self.send_json(400, {"error": "agent_id required"})
                return
            
            if self.engine.registry.unregister(agent_id):
                self.send_json(200, {"success": True})
            else:
                self.send_json(404, {"error": "Agent not found"})
        
        # 创建编排
        elif path == "/api/orchestrations/create" or path == "/orchestrations/create":
            name = data.get("name", "Untitled")
            description = data.get("description", "")
            agents = data.get("agents", [])
            tasks = data.get("tasks", [])
            
            if not tasks:
                self.send_json(400, {"error": "Tasks required"})
                return
            
            orch_id = self.engine.create_orchestration(name, description, agents, tasks)
            self.send_json(201, {"success": True, "orchestration_id": orch_id})
        
        # 运行编排
        elif path == "/api/orchestrations/run" or path == "/orchestrations/run":
            orch_id = data.get("orchestration_id")
            if not orch_id:
                self.send_json(400, {"error": "orchestration_id required"})
                return
            
            result = self.engine.run_orchestration(orch_id)
            if result.get("success"):
                self.send_json(200, result)
            else:
                self.send_json(400, result)
        
        else:
            self.send_json(404, {"error": "Not found"})
    
    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path.startswith("/api/orchestrations/"):
            orch_id = path.split("/")[-1]
            # 暂时不支持删除
            self.send_json(501, {"error": "Not implemented"})
        else:
            self.send_json(404, {"error": "Not found"})


def run_server():
    # 确保目录存在
    os.makedirs("/root/.openclaw/workspace/ultron/tools/orchestrator", exist_ok=True)
    
    server = HTTPServer(("0.0.0.0", PORT), OrchestratorAPIHandler)
    print(f"[Orchestrator API] Started on port {PORT}")
    sys.stdout.flush()
    server.serve_forever()


if __name__ == "__main__":
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(1)
    
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass