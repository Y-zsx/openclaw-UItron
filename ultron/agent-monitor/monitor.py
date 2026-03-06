#!/usr/bin/env python3
"""
Agent服务统一监控系统
监控多个Agent服务的健康状态、指标和性能
"""

import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from urllib.request import urlopen, Request
from urllib.error import URLError
import ssl

# ==================== 配置 ====================
MONITOR_PORT = 18304

# Agent监控配置
AGENT_CONFIGS = {
    "collaborate-center": {
        "name": "协作中心",
        "port": 18201,
        "health_endpoint": "/health",
        "check_interval": 30,
        "timeout": 5,
        "enabled": True
    },
    "service-governance": {
        "name": "服务治理",
        "port": 18202,
        "health_endpoint": "/health",
        "check_interval": 30,
        "timeout": 5,
        "enabled": True
    },
    "collaboration-api": {
        "name": "协作API",
        "port": 18203,
        "health_endpoint": "/health",
        "check_interval": 30,
        "timeout": 5,
        "enabled": True
    },
    "task-scheduler": {
        "name": "任务调度器",
        "port": 18204,
        "health_endpoint": "/health",
        "check_interval": 30,
        "timeout": 5,
        "enabled": True
    },
    "result-aggregator": {
        "name": "结果聚合器",
        "port": 18205,
        "health_endpoint": "/health",
        "check_interval": 30,
        "timeout": 5,
        "enabled": True
    }
}

# ==================== 监控状态 ====================
class AgentMonitor:
    def __init__(self):
        self.agents = {}
        self.metrics = {}
        self.alerts = []
        self.lock = threading.Lock()
        self.start_time = datetime.now()
        
        # 初始化Agent状态
        for agent_id, config in AGENT_CONFIGS.items():
            self.agents[agent_id] = {
                "id": agent_id,
                "name": config["name"],
                "port": config["port"],
                "status": "unknown",
                "last_check": None,
                "last_success": None,
                "consecutive_failures": 0,
                "total_checks": 0,
                "total_successes": 0,
                "total_failures": 0,
                "avg_response_time": 0,
                "response_times": [],
                "enabled": config["enabled"]
            }
            self.metrics[agent_id] = {
                "cpu_percent": 0,
                "memory_percent": 0,
                "requests_per_minute": 0,
                "error_rate": 0,
                "uptime_seconds": 0
            }
    
    def check_agent(self, agent_id: str) -> dict:
        """检查单个Agent的健康状态"""
        config = AGENT_CONFIGS.get(agent_id)
        if not config or not config["enabled"]:
            return {"status": "disabled", "error": "Agent disabled"}
        
        agent = self.agents[agent_id]
        start_time = time.time()
        
        try:
            url = f"http://localhost:{config['port']}{config['health_endpoint']}"
            req = Request(url, method='GET')
            req.timeout = config.get("timeout", 5)
            
            with urlopen(req, context=ssl._create_unverified_context()) as response:
                response_time = (time.time() - start_time) * 1000  # ms
                status_code = response.getcode()
                
                try:
                    data = json.loads(response.read().decode())
                except:
                    data = {}
                
                result = {
                    "status": "healthy" if status_code == 200 else "unhealthy",
                    "response_time": round(response_time, 2),
                    "status_code": status_code,
                    "data": data
                }
                
                # 更新统计
                agent["total_checks"] += 1
                agent["total_successes"] += 1
                agent["consecutive_failures"] = 0
                agent["last_success"] = datetime.now().isoformat()
                agent["response_times"].append(response_time)
                
                # 保留最近100次响应时间
                if len(agent["response_times"]) > 100:
                    agent["response_times"] = agent["response_times"][-100:]
                
                agent["avg_response_time"] = sum(agent["response_times"]) / len(agent["response_times"])
                
                return result
                
        except URLError as e:
            return self._handle_error(agent, str(e), start_time)
        except Exception as e:
            return self._handle_error(agent, str(e), start_time)
    
    def _handle_error(self, agent: dict, error: str, start_time: float) -> dict:
        """处理检查错误"""
        response_time = (time.time() - start_time) * 1000
        
        agent["total_checks"] += 1
        agent["total_failures"] += 1
        agent["consecutive_failures"] += 1
        
        # 根据连续失败次数判断状态
        if agent["consecutive_failures"] >= 3:
            status = "critical"
        elif agent["consecutive_failures"] >= 1:
            status = "degraded"
        else:
            status = "unhealthy"
        
        # 生成告警
        if agent["consecutive_failures"] == 3:
            self.alerts.append({
                "agent_id": agent["id"],
                "level": "critical",
                "message": f"{agent['name']} 连续3次检查失败",
                "timestamp": datetime.now().isoformat()
            })
        
        return {
            "status": status,
            "response_time": round(response_time, 2),
            "error": error
        }
    
    def check_all_agents(self) -> dict:
        """检查所有Agent"""
        results = {}
        for agent_id in AGENT_CONFIGS:
            agent = self.agents[agent_id]
            result = self.check_agent(agent_id)
            agent["status"] = result.get("status", "unknown")
            agent["last_check"] = datetime.now().isoformat()
            results[agent_id] = result
        
        return results
    
    def get_status(self) -> dict:
        """获取整体状态"""
        healthy_count = sum(1 for a in self.agents.values() if a["status"] == "healthy")
        total_enabled = sum(1 for a in self.agents.values() if a["enabled"])
        
        # 告警清理 (保留最近10条)
        if len(self.alerts) > 10:
            self.alerts = self.alerts[-10:]
        
        return {
            "status": "healthy" if healthy_count == total_enabled else "degraded",
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": int((datetime.now() - self.start_time).total_seconds()),
            "agents": {
                agent_id: {
                    "name": agent["name"],
                    "status": agent["status"],
                    "last_check": agent["last_check"],
                    "last_success": agent["last_success"],
                    "avg_response_time": round(agent["avg_response_time"], 2),
                    "total_checks": agent["total_checks"],
                    "success_rate": round(agent["total_successes"] / max(agent["total_checks"], 1) * 100, 2)
                }
                for agent_id, agent in self.agents.items()
                if agent["enabled"]
            },
            "alerts": self.alerts[-5:],  # 最近5条告警
            "summary": {
                "total_agents": total_enabled,
                "healthy": healthy_count,
                "degraded": sum(1 for a in self.agents.values() if a["status"] == "degraded"),
                "critical": sum(1 for a in self.agents.values() if a["status"] == "critical"),
                "unhealthy": sum(1 for a in self.agents.values() if a["status"] == "unhealthy")
            }
        }
    
    def get_agent_detail(self, agent_id: str) -> dict:
        """获取单个Agent详情"""
        agent = self.agents.get(agent_id)
        if not agent:
            return {"error": "Agent not found"}
        
        return {
            "id": agent["id"],
            "name": agent["name"],
            "port": agent["port"],
            "status": agent["status"],
            "enabled": agent["enabled"],
            "last_check": agent["last_check"],
            "last_success": agent["last_success"],
            "consecutive_failures": agent["consecutive_failures"],
            "statistics": {
                "total_checks": agent["total_checks"],
                "total_successes": agent["total_successes"],
                "total_failures": agent["total_failures"],
                "success_rate": round(agent["total_successes"] / max(agent["total_checks"], 1) * 100, 2),
                "avg_response_time": round(agent["avg_response_time"], 2)
            },
            "recent_response_times": agent["response_times"][-10:]
        }
    
    def reset_agent(self, agent_id: str) -> dict:
        """重置Agent状态"""
        if agent_id not in self.agents:
            return {"error": "Agent not found"}
        
        with self.lock:
            self.agents[agent_id]["consecutive_failures"] = 0
            self.agents[agent_id]["status"] = "unknown"
        
        return {"message": f"Agent {agent_id} 已重置", "status": "reset"}
    
    def clear_alerts(self) -> dict:
        """清除告警"""
        self.alerts = []
        return {"message": "告警已清除", "count": 0}


# ==================== HTTP处理器 ====================
monitor = AgentMonitor()

class MonitorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.rstrip('/')
        
        if path == '' or path == '/':
            self.send_json_response(monitor.get_status())
        
        elif path == '/health':
            self.send_json_response({"status": "ok", "service": "agent-monitor"})
        
        elif path == '/agents':
            self.send_json_response(monitor.get_status()["agents"])
        
        elif path == '/summary':
            self.send_json_response(monitor.get_status()["summary"])
        
        elif path == '/alerts':
            self.send_json_response({"alerts": monitor.alerts})
        
        elif path == '/check':
            # 立即检查所有Agent
            results = monitor.check_all_agents()
            self.send_json_response({
                "message": "检查完成",
                "results": results,
                "timestamp": datetime.now().isoformat()
            })
        
        elif path.startswith('/agent/'):
            agent_id = path[7:]
            self.send_json_response(monitor.get_agent_detail(agent_id))
        
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        path = self.path.rstrip('/')
        
        if path == '/reset':
            # 重置指定agent
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"
            
            try:
                data = json.loads(body) if body else {}
                agent_id = data.get("agent_id")
                
                if agent_id:
                    result = monitor.reset_agent(agent_id)
                else:
                    # 重置所有
                    for aid in monitor.agents:
                        monitor.reset_agent(aid)
                    result = {"message": "所有Agent已重置"}
                
                self.send_json_response(result)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
        
        elif path == '/clear-alerts':
            result = monitor.clear_alerts()
            self.send_json_response(result)
        
        elif path == '/check':
            # 手动触发检查
            results = monitor.check_all_agents()
            self.send_json_response({
                "message": "检查完成",
                "results": results,
                "timestamp": datetime.now().isoformat()
            })
        
        else:
            self.send_error(404, "Not Found")
    
    def send_json_response(self, data: dict, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode())
    
    def log_message(self, format, *args):
        pass  # 禁用默认日志


def run_server():
    """运行监控服务器"""
    server = HTTPServer(('0.0.0.0', MONITOR_PORT), MonitorHandler)
    print(f"Agent统一监控系统运行在端口 {MONITOR_PORT}")
    print(f"访问 http://localhost:{MONITOR_PORT} 查看状态")
    
    # 启动时检查一次
    monitor.check_all_agents()
    
    server.serve_forever()


if __name__ == '__main__':
    run_server()