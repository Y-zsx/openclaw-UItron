#!/usr/bin/env python3
"""
Agent协作网络API网关
提供RESTful API统一接口，集成注册、任务、健康检查、消息传递
"""

import json
import time
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
from flask import Flask, request, jsonify
from functools import wraps

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


class AgentStatus(Enum):
    """Agent状态枚举"""
    UNKNOWN = "unknown"
    REGISTERED = "registered"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CollabAPIGateway:
    """协作网络API网关核心类"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8089):
        self.host = host
        self.port = port
        
        # Agent注册表
        self.agents: Dict[str, Dict] = {}
        
        # 任务队列
        self.tasks: Dict[str, Dict] = {}
        self.task_queue: List[str] = []
        
        # 消息队列
        self.messages: Dict[str, List[Dict]] = {}
        
        # 指标存储
        self.metrics: Dict[str, Any] = {
            "total_requests": 0,
            "total_tasks": 0,
            "total_agents": 0,
            "api_calls": {},
            "start_time": time.time()
        }
        
        # 统计
        self.stats = {
            "requests": 0,
            "errors": 0,
            "avg_response_time": 0
        }
        
        logger.info(f"协作网络API网关初始化完成")
        
    # ========== Agent管理 ==========
    
    def register_agent(self, agent_id: str, capabilities: List[str] = None, 
                       metadata: Dict = None) -> Dict:
        """注册Agent"""
        timestamp = datetime.now().isoformat()
        
        self.agents[agent_id] = {
            "agent_id": agent_id,
            "capabilities": capabilities or [],
            "metadata": metadata or {},
            "status": AgentStatus.ACTIVE.value,
            "registered_at": timestamp,
            "last_heartbeat": timestamp,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "health_score": 100.0
        }
        
        self.metrics["total_agents"] = len(self.agents)
        logger.info(f"Agent注册: {agent_id}")
        
        return {
            "success": True,
            "agent_id": agent_id,
            "message": "Agent注册成功"
        }
    
    def unregister_agent(self, agent_id: str) -> Dict:
        """注销Agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            self.metrics["total_agents"] = len(self.agents)
            logger.info(f"Agent注销: {agent_id}")
            return {"success": True, "message": "Agent已注销"}
        return {"success": False, "error": "Agent不存在"}
    
    def heartbeat(self, agent_id: str, status: str = None, 
                  health_score: float = None) -> Dict:
        """Agent心跳"""
        if agent_id not in self.agents:
            return {"success": False, "error": "Agent未注册"}
        
        self.agents[agent_id]["last_heartbeat"] = datetime.now().isoformat()
        
        if status:
            self.agents[agent_id]["status"] = status
        if health_score is not None:
            self.agents[agent_id]["health_score"] = health_score
            
        return {"success": True, "timestamp": datetime.now().isoformat()}
    
    def list_agents(self, status: str = None, capability: str = None) -> List[Dict]:
        """列出Agent"""
        agents = list(self.agents.values())
        
        if status:
            agents = [a for a in agents if a["status"] == status]
        if capability:
            agents = [a for a in agents if capability in a["capabilities"]]
            
        return agents
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """获取Agent详情"""
        return self.agents.get(agent_id)
    
    def update_agent_status(self, agent_id: str, status: str) -> Dict:
        """更新Agent状态"""
        if agent_id not in self.agents:
            return {"success": False, "error": "Agent不存在"}
        
        valid_statuses = [s.value for s in AgentStatus]
        if status not in valid_statuses:
            return {"success": False, "error": f"无效状态: {status}"}
        
        self.agents[agent_id]["status"] = status
        return {"success": True, "status": status}
    
    # ========== 任务管理 ==========
    
    def submit_task(self, task_type: str, payload: Dict = None,
                    priority: int = 5, target_agent: str = None,
                    callback: str = None) -> Dict:
        """提交任务"""
        task_id = f"task-{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now().isoformat()
        
        task = {
            "task_id": task_id,
            "task_type": task_type,
            "payload": payload or {},
            "priority": priority,
            "status": TaskStatus.PENDING.value,
            "target_agent": target_agent,
            "callback": callback,
            "created_at": timestamp,
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "retry_count": 0
        }
        
        self.tasks[task_id] = task
        self.task_queue.append(task_id)
        self.task_queue.sort(key=lambda t: self.tasks[t].get("priority", 5), reverse=True)
        
        self.metrics["total_tasks"] += 1
        logger.info(f"任务提交: {task_id} (类型: {task_type})")
        
        return {
            "success": True,
            "task_id": task_id,
            "status": TaskStatus.PENDING.value
        }
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务详情"""
        return self.tasks.get(task_id)
    
    def update_task_status(self, task_id: str, status: str, 
                          result: Any = None, error: str = None) -> Dict:
        """更新任务状态"""
        if task_id not in self.tasks:
            return {"success": False, "error": "任务不存在"}
        
        task = self.tasks[task_id]
        task["status"] = status
        
        if status == TaskStatus.RUNNING.value and not task["started_at"]:
            task["started_at"] = datetime.now().isoformat()
        elif status in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]:
            task["completed_at"] = datetime.now().isoformat()
            if result:
                task["result"] = result
            if error:
                task["error"] = error
                
            # 更新Agent统计
            if task.get("assigned_agent"):
                agent_id = task["assigned_agent"]
                if agent_id in self.agents:
                    if status == TaskStatus.COMPLETED.value:
                        self.agents[agent_id]["tasks_completed"] += 1
                    else:
                        self.agents[agent_id]["tasks_failed"] += 1
        
        return {"success": True, "task_id": task_id, "status": status}
    
    def cancel_task(self, task_id: str) -> Dict:
        """取消任务"""
        return self.update_task_status(task_id, TaskStatus.CANCELLED.value)
    
    def list_tasks(self, status: str = None, agent_id: str = None,
                   limit: int = 50) -> List[Dict]:
        """列出任务"""
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t["status"] == status]
        if agent_id:
            tasks = [t for t in tasks if t.get("assigned_agent") == agent_id]
            
        return sorted(tasks, key=lambda t: t["created_at"], reverse=True)[:limit]
    
    def get_pending_tasks(self) -> List[Dict]:
        """获取待处理任务"""
        pending = [self.tasks[tid] for tid in self.task_queue 
                   if tid in self.tasks and self.tasks[tid]["status"] == TaskStatus.PENDING.value]
        return pending
    
    # ========== 消息传递 ==========
    
    def send_message(self, from_agent: str, to_agent: str, 
                     content: Any, message_type: str = "text") -> Dict:
        """发送消息"""
        if from_agent not in self.agents:
            return {"success": False, "error": "发送者未注册"}
        if to_agent not in self.agents:
            return {"success": False, "error": "接收者未注册"}
        
        message_id = f"msg-{uuid.uuid4().hex[:12]}"
        message = {
            "message_id": message_id,
            "from": from_agent,
            "to": to_agent,
            "type": message_type,
            "content": content,
            "timestamp": datetime.now().isoformat(),
            "read": False
        }
        
        if to_agent not in self.messages:
            self.messages[to_agent] = []
        self.messages[to_agent].append(message)
        
        logger.info(f"消息: {from_agent} -> {to_agent}")
        
        return {
            "success": True,
            "message_id": message_id
        }
    
    def get_messages(self, agent_id: str, unread_only: bool = False) -> List[Dict]:
        """获取消息"""
        messages = self.messages.get(agent_id, [])
        
        if unread_only:
            messages = [m for m in messages if not m.get("read")]
            
        return messages
    
    def mark_message_read(self, agent_id: str, message_id: str) -> Dict:
        """标记消息已读"""
        messages = self.messages.get(agent_id, [])
        for msg in messages:
            if msg["message_id"] == message_id:
                msg["read"] = True
                return {"success": True}
        return {"success": False, "error": "消息不存在"}
    
    # ========== 指标与统计 ==========
    
    def get_metrics(self) -> Dict:
        """获取系统指标"""
        uptime = time.time() - self.metrics["start_time"]
        
        # 计算Agent统计
        status_counts = {}
        for agent in self.agents.values():
            status = agent["status"]
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # 计算任务统计
        task_counts = {}
        for task in self.tasks.values():
            status = task["status"]
            task_counts[status] = task_counts.get(status, 0) + 1
        
        return {
            "uptime_seconds": uptime,
            "total_agents": len(self.agents),
            "total_tasks": len(self.tasks),
            "total_messages": sum(len(m) for m in self.messages.values()),
            "agent_status": status_counts,
            "task_status": task_counts,
            "requests": self.stats["requests"],
            "errors": self.stats["errors"]
        }
    
    def record_request(self, endpoint: str, response_time: float, 
                       success: bool = True) -> None:
        """记录请求"""
        self.stats["requests"] += 1
        
        if not success:
            self.stats["errors"] += 1
        
        # 更新平均响应时间
        n = self.stats["requests"]
        self.stats["avg_response_time"] = (
            (self.stats["avg_response_time"] * (n - 1) + response_time) / n
        )
        
        # 记录API调用
        if endpoint not in self.metrics["api_calls"]:
            self.metrics["api_calls"][endpoint] = {"calls": 0, "errors": 0}
        
        self.metrics["api_calls"][endpoint]["calls"] += 1
        if not success:
            self.metrics["api_calls"][endpoint]["errors"] += 1
    
    # ========== 健康检查 ==========
    
    def health_check(self) -> Dict:
        """系统健康检查"""
        # 检查Agent心跳
        now = datetime.now()
        stale_agents = []
        
        for agent_id, agent in self.agents.items():
            last_hb = datetime.fromisoformat(agent["last_heartbeat"])
            if (now - last_hb).total_seconds() > 300:  # 5分钟超时
                stale_agents.append(agent_id)
        
        # 更新离线Agent状态
        for agent_id in stale_agents:
            self.agents[agent_id]["status"] = AgentStatus.OFFLINE.value
        
        return {
            "healthy": len(stale_agents) < len(self.agents) * 0.5,
            "total_agents": len(self.agents),
            "stale_agents": len(stale_agents),
            "total_tasks": len(self.tasks),
            "pending_tasks": len([t for t in self.tasks.values() 
                                 if t["status"] == TaskStatus.PENDING.value]),
            "timestamp": now.isoformat()
        }


# 全局网关实例
gateway = CollabAPIGateway()


# ========== API路由 ==========

def api_response(f):
    """API响应包装器"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = f(*args, **kwargs)
            response_time = time.time() - start_time
            gateway.record_request(request.path, response_time, True)
            return jsonify(result)
        except Exception as e:
            response_time = time.time() - start_time
            gateway.record_request(request.path, response_time, False)
            logger.error(f"API错误: {e}")
            return jsonify({"success": False, "error": str(e)}), 500
    return wrapper


@app.route("/health", methods=["GET"])
@api_response
def health():
    """健康检查"""
    return gateway.health_check()


@app.route("/metrics", methods=["GET"])
@api_response
def metrics():
    """系统指标"""
    return gateway.get_metrics()


# Agent管理
@app.route("/agents", methods=["GET"])
@api_response
def list_agents():
    """列出所有Agent"""
    status = request.args.get("status")
    capability = request.args.get("capability")
    return {"agents": gateway.list_agents(status, capability)}


@app.route("/agents/<agent_id>", methods=["GET"])
@api_response
def get_agent(agent_id):
    """获取Agent详情"""
    agent = gateway.get_agent(agent_id)
    if agent:
        return {"agent": agent}
    return {"success": False, "error": "Agent不存在"}, 404


@app.route("/agents", methods=["POST"])
@api_response
def register_agent():
    """注册Agent"""
    data = request.get_json() or {}
    agent_id = data.get("agent_id") or f"agent-{uuid.uuid4().hex[:8]}"
    capabilities = data.get("capabilities", [])
    metadata = data.get("metadata", {})
    
    return gateway.register_agent(agent_id, capabilities, metadata)


@app.route("/agents/<agent_id>", methods=["DELETE"])
@api_response
def unregister_agent(agent_id):
    """注销Agent"""
    return gateway.unregister_agent(agent_id)


@app.route("/agents/<agent_id>/heartbeat", methods=["POST"])
@api_response
def agent_heartbeat(agent_id):
    """Agent心跳"""
    data = request.get_json() or {}
    return gateway.heartbeat(
        agent_id,
        data.get("status"),
        data.get("health_score")
    )


@app.route("/agents/<agent_id>/status", methods=["PUT"])
@api_response
def update_agent_status(agent_id):
    """更新Agent状态"""
    data = request.get_json() or {}
    return gateway.update_agent_status(agent_id, data.get("status"))


# 任务管理
@app.route("/tasks", methods=["GET"])
@api_response
def list_tasks():
    """列出任务"""
    status = request.args.get("status")
    agent_id = request.args.get("agent_id")
    limit = int(request.args.get("limit", 50))
    return {"tasks": gateway.list_tasks(status, agent_id, limit)}


@app.route("/tasks/<task_id>", methods=["GET"])
@api_response
def get_task(task_id):
    """获取任务详情"""
    task = gateway.get_task(task_id)
    if task:
        return {"task": task}
    return {"success": False, "error": "任务不存在"}, 404


@app.route("/tasks", methods=["POST"])
@api_response
def submit_task():
    """提交任务"""
    data = request.get_json() or {}
    return gateway.submit_task(
        data.get("task_type", "default"),
        data.get("payload"),
        data.get("priority", 5),
        data.get("target_agent"),
        data.get("callback")
    )


@app.route("/tasks/<task_id>/status", methods=["PUT"])
@api_response
def update_task_status(task_id):
    """更新任务状态"""
    data = request.get_json() or {}
    return gateway.update_task_status(
        task_id,
        data.get("status"),
        data.get("result"),
        data.get("error")
    )


@app.route("/tasks/<task_id>/cancel", methods=["POST"])
@api_response
def cancel_task(task_id):
    """取消任务"""
    return gateway.cancel_task(task_id)


@app.route("/tasks/pending", methods=["GET"])
@api_response
def get_pending_tasks():
    """获取待处理任务"""
    return {"tasks": gateway.get_pending_tasks()}


# 消息传递
@app.route("/messages/<agent_id>", methods=["GET"])
@api_response
def get_messages(agent_id):
    """获取消息"""
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    return {"messages": gateway.get_messages(agent_id, unread_only)}


@app.route("/messages", methods=["POST"])
@api_response
def send_message():
    """发送消息"""
    data = request.get_json() or {}
    return gateway.send_message(
        data.get("from"),
        data.get("to"),
        data.get("content"),
        data.get("type", "text")
    )


@app.route("/messages/<agent_id>/<message_id>/read", methods=["POST"])
@api_response
def mark_message_read(agent_id, message_id):
    """标记消息已读"""
    return gateway.mark_message_read(agent_id, message_id)


def run_server(host=None, port=None):
    """运行服务器"""
    host = host or gateway.host
    port = port or gateway.port
    
    logger.info(f"启动API网关: http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run_server()