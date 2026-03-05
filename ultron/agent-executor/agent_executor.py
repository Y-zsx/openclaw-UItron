#!/usr/bin/env python3
"""
Agent执行器 - 多智能体协作网络核心组件
负责任务分发、执行、监控与结果汇总
"""
import asyncio
import json
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
import psutil
import os

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AgentCapability(Enum):
    BROWSER = "browser"
    EXEC = "exec"
    DATA = "data"
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"

@dataclass
class Agent:
    id: str
    name: str
    capabilities: List[AgentCapability]
    status: str = "idle"
    current_task: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Task:
    id: str
    type: str
    payload: Dict[str, Any]
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None

class AgentExecutor:
    """Agent执行器核心类"""
    
    def __init__(self, port: int = 18160):
        self.port = port
        self.agents: Dict[str, Agent] = {}
        self.tasks: Dict[str, Task] = {}
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.running = False
        
    def register_agent(self, name: str, capabilities: List[str]) -> str:
        """注册Agent"""
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        caps = [AgentCapability(c) for c in capabilities if c in [e.value for e in AgentCapability]]
        self.agents[agent_id] = Agent(
            id=agent_id,
            name=name,
            capabilities=caps
        )
        return agent_id
    
    async def submit_task(self, task_type: str, payload: Dict[str, Any]) -> str:
        """提交任务"""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        task = Task(id=task_id, type=task_type, payload=payload)
        self.tasks[task_id] = task
        await self.task_queue.put(task_id)
        return task_id
    
    def match_agent(self, required_capability: str) -> Optional[Agent]:
        """匹配最合适的Agent"""
        idle_agents = [a for a in self.agents.values() if a.status == "idle"]
        for agent in idle_agents:
            if any(c.value == required_capability for c in agent.capabilities):
                return agent
        return idle_agents[0] if idle_agents else None
    
    async def execute_task(self, task_id: str) -> Dict[str, Any]:
        """执行单个任务"""
        task = self.tasks[task_id]
        task.status = TaskStatus.RUNNING
        task.started_at = time.time()
        
        # 匹配Agent
        required_cap = task.payload.get("capability", "exec")
        agent = self.match_agent(required_cap)
        
        if not agent:
            task.status = TaskStatus.FAILED
            task.error = "No available agent"
            return {"status": "failed", "error": "No available agent"}
        
        # 分配任务
        task.assigned_agent = agent.id
        agent.status = "busy"
        agent.current_task = task_id
        
        try:
            # 模拟执行
            result = await self._run_agent_task(agent, task)
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            
            # 更新Agent指标
            agent.metrics["tasks_completed"] = agent.metrics.get("tasks_completed", 0) + 1
            agent.metrics["last_execution_time"] = task.completed_at - task.started_at
            
            return {"status": "completed", "result": result}
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            return {"status": "failed", "error": str(e)}
        finally:
            agent.status = "idle"
            agent.current_task = None
    
    async def _run_agent_task(self, agent: Agent, task: Task) -> Dict[str, Any]:
        """运行Agent任务"""
        task_type = task.type
        
        if task_type == "exec":
            # 执行命令
            cmd = task.payload.get("command", "echo 'hello'")
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return {
                "stdout": stdout.decode(),
                "stderr": stderr.decode(),
                "returncode": proc.returncode
            }
        elif task_type == "data":
            # 数据处理任务
            return {"processed": True, "data_size": len(str(task.payload))}
        elif task_type == "analysis":
            # 分析任务
            return {"analysis": "completed", "confidence": 0.85}
        else:
            return {"result": "unknown task type"}
    
    async def worker(self):
        """工作协程"""
        while self.running:
            try:
                task_id = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                await self.execute_task(task_id)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Worker error: {e}")
    
    async def start(self):
        """启动执行器"""
        self.running = True
        # 注册默认Agent
        self.register_agent("Worker-1", ["exec", "data"])
        self.register_agent("Worker-2", ["browser", "analysis"])
        self.register_agent("Worker-3", ["communication", "data"])
        
        # 启动工作协程
        workers = [asyncio.create_task(self.worker()) for _ in range(3)]
        print(f"🚀 Agent执行器启动 (port {self.port})")
        print(f"📋 注册Agent: {len(self.agents)}")
        
        await asyncio.gather(*workers)
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "port": self.port,
            "agents": {
                aid: {
                    "name": a.name,
                    "status": a.status,
                    "capabilities": [c.value for c in a.capabilities],
                    "metrics": a.metrics
                }
                for aid, a in self.agents.items()
            },
            "tasks": {
                "total": len(self.tasks),
                "pending": len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING]),
                "running": len([t for t in self.tasks.values() if t.status == TaskStatus.RUNNING]),
                "completed": len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]),
                "failed": len([t for t in self.tasks.values() if t.status == TaskStatus.FAILED])
            },
            "queue_size": self.task_queue.qsize()
        }

# HTTP API服务
from aiohttp import web

async def status_handler(request):
    executor = request.app["executor"]
    return web.json_response(executor.get_status())

async def submit_handler(request):
    executor = request.app["executor"]
    data = await request.json()
    task_id = await executor.submit_task(data.get("type", "exec"), data.get("payload", {}))
    return web.json_response({"task_id": task_id})

async def task_handler(request):
    executor = request.app["executor"]
    task_id = request.match_info["task_id"]
    task = executor.tasks.get(task_id)
    if not task:
        return web.json_response({"error": "Task not found"}, status=404)
    return web.json_response({
        "id": task.id,
        "type": task.type,
        "status": task.status.value,
        "assigned_agent": task.assigned_agent,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at,
        "started_at": task.started_at,
        "completed_at": task.completed_at
    })

async def register_agent_handler(request):
    executor = request.app["executor"]
    data = await request.json()
    agent_id = executor.register_agent(data.get("name"), data.get("capabilities", []))
    return web.json_response({"agent_id": agent_id})

def create_app(executor: AgentExecutor):
    app = web.Application()
    app["executor"] = executor
    app.router.add_get("/status", status_handler)
    app.router.add_post("/tasks", submit_handler)
    app.router.add_get("/tasks/{task_id}", task_handler)
    app.router.add_post("/agents", register_agent_handler)
    return app

if __name__ == "__main__":
    executor = AgentExecutor(port=18160)
    app = create_app(executor)
    print(f"🌐 Agent执行器API服务启动: http://0.0.0.0:{executor.port}")
    web.run_app(app, host="0.0.0.0", port=executor.port)
