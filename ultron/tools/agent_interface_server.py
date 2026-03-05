#!/usr/bin/env python3
"""
Agent接口规范实现 - API服务器
提供符合Agent接口规范的标准API
"""

import json
import time
import uuid
import threading
from typing import Dict, Any, Optional
from dataclasses import dataclass, field, asdict
from flask import Flask, request, jsonify
from collections import defaultdict

app = Flask(__name__)

# 存储
agents: Dict[str, Dict] = {}
tasks: Dict[str, Dict] = {}
metrics_history: Dict[str, list] = defaultdict(list)


@dataclass
class Task:
    task_id: str
    task_type: str
    payload: Dict
    priority: int = 2
    timeout: int = 300
    status: str = "pending"
    result: Any = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


class AgentRegistry:
    """Agent注册中心"""
    
    @staticmethod
    def register(data: Dict) -> Dict:
        agent_id = data["agent_id"]
        if agent_id in agents:
            return {
                "success": False,
                "error_code": "E003",
                "error_message": "Agent已注册"
            }
        
        agents[agent_id] = {
            "agent_id": agent_id,
            "name": data["name"],
            "version": data["version"],
            "role": data["role"],
            "capabilities": data["capabilities"],
            "status": "ready",
            "metadata": data.get("metadata", {}),
            "registered_at": time.time(),
            "last_heartbeat": time.time()
        }
        
        return {
            "success": True,
            "agent_id": agent_id,
            "registered_at": agents[agent_id]["registered_at"],
            "config": {
                "heartbeat_interval": 30,
                "max_queue_size": 100,
                "timeout_default": 300
            }
        }
    
    @staticmethod
    def heartbeat(agent_id: str, status: str, metrics: Optional[Dict] = None) -> Dict:
        if agent_id not in agents:
            return {"success": False, "error_code": "E002", "error_message": "Agent未注册"}
        
        agents[agent_id]["status"] = status
        agents[agent_id]["last_heartbeat"] = time.time()
        
        if metrics:
            agents[agent_id]["metrics"] = metrics
        
        return {
            "success": True,
            "timestamp": time.time(),
            "commands": []
        }
    
    @staticmethod
    def get_health(agent_id: str) -> Dict:
        if agent_id not in agents:
            return {"healthy": False, "error": "Agent未注册"}
        
        agent = agents[agent_id]
        checks = {
            "registered": True,
            "heartbeat_recent": (time.time() - agent["last_heartbeat"]) < 60,
            "status_valid": agent["status"] in ["ready", "busy", "idle"]
        }
        
        return {
            "healthy": all(checks.values()),
            "checks": checks,
            "details": {
                "status": agent["status"],
                "last_heartbeat": agent["last_heartbeat"]
            },
            "timestamp": time.time()
        }
    
    @staticmethod
    def get_capabilities(agent_id: str) -> Optional[Dict]:
        if agent_id not in agents:
            return None
        agent = agents[agent_id]
        return {
            "agent_id": agent_id,
            "capabilities": agent["capabilities"],
            "version": agent["version"]
        }


class TaskManager:
    """任务管理器"""
    
    @staticmethod
    def submit(data: Dict) -> Dict:
        task_id = data.get("task_id") or f"task_{uuid.uuid4().hex[:12]}"
        
        task = Task(
            task_id=task_id,
            task_type=data["task_type"],
            payload=data["payload"],
            priority=data.get("priority", 2),
            timeout=data.get("timeout", 300)
        )
        
        tasks[task_id] = asdict(task)
        
        # 模拟异步处理
        threading.Thread(target=TaskManager._process_task, args=(task_id,)).start()
        
        return {
            "success": True,
            "task_id": task_id,
            "status": "queued",
            "queued_at": task.created_at
        }
    
    @staticmethod
    def _process_task(task_id: str):
        """模拟任务处理"""
        time.sleep(0.5)  # 模拟处理时间
        if task_id in tasks:
            tasks[task_id]["status"] = "completed"
            tasks[task_id]["completed_at"] = time.time()
            tasks[task_id]["result"] = {"message": "Task processed successfully"}
    
    @staticmethod
    def get_status(task_id: str) -> Optional[Dict]:
        return tasks.get(task_id)
    
    @staticmethod
    def cancel(task_id: str) -> Dict:
        if task_id not in tasks:
            return {"success": False, "error_code": "E004", "error_message": "任务不存在"}
        
        tasks[task_id]["status"] = "cancelled"
        tasks[task_id]["completed_at"] = time.time()
        
        return {
            "success": True,
            "task_id": task_id,
            "cancelled_at": time.time()
        }


# ========== API 路由 ==========

@app.route("/agent/register", methods=["POST"])
def register():
    """Agent注册"""
    data = request.json
    result = AgentRegistry.register(data)
    return jsonify(result)


@app.route("/agent/heartbeat", methods=["POST"])
def heartbeat():
    """Agent心跳"""
    data = request.json
    result = AgentRegistry.heartbeat(
        data.get("agent_id", ""),
        data.get("status", "ready"),
        data.get("metrics")
    )
    return jsonify(result)


@app.route("/agent/health", methods=["GET"])
def health():
    """健康检查"""
    agent_id = request.args.get("agent_id", "")
    result = AgentRegistry.get_health(agent_id)
    return jsonify(result)


@app.route("/agent/capabilities", methods=["GET"])
def capabilities():
    """获取Agent能力"""
    agent_id = request.args.get("agent_id", "")
    result = AgentRegistry.get_capabilities(agent_id)
    if result is None:
        return jsonify({"error": "Agent未注册"}), 404
    return jsonify(result)


@app.route("/task/submit", methods=["POST"])
def submit_task():
    """提交任务"""
    data = request.json
    result = TaskManager.submit(data)
    return jsonify(result)


@app.route("/task/status", methods=["GET"])
def task_status():
    """查询任务状态"""
    task_id = request.args.get("task_id", "")
    result = TaskManager.get_status(task_id)
    if result is None:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(result)


@app.route("/task/cancel", methods=["POST"])
def cancel_task():
    """取消任务"""
    data = request.json
    task_id = data.get("task_id", "")
    result = TaskManager.cancel(task_id)
    return jsonify(result)


@app.route("/spec", methods=["GET"])
def get_spec():
    """获取接口规范"""
    from agent_interface_spec import AGENT_API_SPEC
    return jsonify(AGENT_API_SPEC)


@app.route("/agents", methods=["GET"])
def list_agents():
    """列出所有Agent"""
    return jsonify({"agents": list(agents.values()), "count": len(agents)})


@app.route("/tasks", methods=["GET"])
def list_tasks():
    """列出所有任务"""
    return jsonify({"tasks": list(tasks.values()), "count": len(tasks)})


@app.route("/health", methods=["GET"])
def server_health():
    """服务器健康检查"""
    return jsonify({
        "healthy": True,
        "agents_count": len(agents),
        "tasks_count": len(tasks),
        "timestamp": time.time()
    })


if __name__ == "__main__":
    print("=" * 50)
    print("Agent接口规范服务器启动中...")
    print("端口: 8110")
    print("=" * 50)
    app.run(host="0.0.0.0", port=8110, debug=False)