#!/usr/bin/env python3
"""
决策Agent协作网络
将决策引擎与多Agent系统集成，实现智能协作决策

功能:
- 决策Agent注册与管理
- Agent能力匹配
- 任务分发与协作
- 决策执行闭环
"""

import asyncio
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from aiohttp import web
import aiohttp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AgentStatus(Enum):
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class DecisionAgent:
    """决策Agent"""
    agent_id: str
    name: str
    capabilities: List[str]  # capability tags
    endpoint: str
    status: str = "idle"
    metadata: Dict = field(default_factory=dict)
    tasks_completed: int = 0
    last_active: str = ""

    def to_dict(self):
        return asdict(self)


@dataclass
class CollaborationTask:
    """协作任务"""
    task_id: str
    decision_id: str
    task_type: str
    required_capabilities: List[str]
    assigned_agents: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Optional[Dict] = None
    created_at: str = ""
    completed_at: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)


class DecisionAgentNetwork:
    """决策Agent协作网络"""
    
    def __init__(self, decision_engine_url: str = "http://localhost:18120"):
        self.decision_engine_url = decision_engine_url
        self.agents: Dict[str, DecisionAgent] = {}
        self.tasks: Dict[str, CollaborationTask] = {}
        self.task_history: List[Dict] = []
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "agents_count": 0
        }
    
    async def register_agent(self, agent: DecisionAgent) -> Dict:
        """注册Agent"""
        self.agents[agent.agent_id] = agent
        self.stats["agents_count"] = len(self.agents)
        logger.info(f"Agent注册: {agent.name} ({agent.agent_id})")
        return {"status": "success", "agent_id": agent.agent_id}
    
    async def unregister_agent(self, agent_id: str) -> Dict:
        """注销Agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            self.stats["agents_count"] = len(self.agents)
            logger.info(f"Agent注销: {agent_id}")
            return {"status": "success"}
        return {"status": "error", "message": "Agent not found"}
    
    def find_agents_by_capability(self, capability: str) -> List[DecisionAgent]:
        """根据能力查找Agent"""
        return [
            agent for agent in self.agents.values()
            if capability in agent.capabilities and agent.status != "offline"
        ]
    
    async def create_collaboration_task(self, decision_id: str, task_type: str, 
                                        required_capabilities: List[str],
                                        metadata: Dict = None) -> str:
        """创建协作任务"""
        task_id = str(uuid.uuid4())[:8]
        task = CollaborationTask(
            task_id=task_id,
            decision_id=decision_id,
            task_type=task_type,
            required_capabilities=required_capabilities,
            created_at=datetime.utcnow().isoformat(),
            metadata=metadata or {}
        )
        self.tasks[task_id] = task
        self.stats["total_tasks"] += 1
        logger.info(f"创建协作任务: {task_id} (类型: {task_type})")
        return task_id
    
    async def assign_task(self, task_id: str, agent_ids: List[str]) -> Dict:
        """分配任务给Agent"""
        if task_id not in self.tasks:
            return {"status": "error", "message": "Task not found"}
        
        task = self.tasks[task_id]
        task.assigned_agents = agent_ids
        task.status = "running"
        
        # 更新Agent状态
        for agent_id in agent_ids:
            if agent_id in self.agents:
                self.agents[agent_id].status = "busy"
        
        logger.info(f"任务分配: {task_id} -> {agent_ids}")
        return {"status": "success", "task_id": task_id}
    
    async def complete_task(self, task_id: str, result: Dict) -> Dict:
        """完成任务"""
        if task_id not in self.tasks:
            return {"status": "error", "message": "Task not found"}
        
        task = self.tasks[task_id]
        task.status = "completed"
        task.result = result
        task.completed_at = datetime.utcnow().isoformat()
        
        # 更新Agent状态
        for agent_id in task.assigned_agents:
            if agent_id in self.agents:
                self.agents[agent_id].status = "idle"
                self.agents[agent_id].tasks_completed += 1
                self.agents[agent_id].last_active = task.completed_at
        
        self.stats["completed_tasks"] += 1
        
        # 添加到历史
        self.task_history.append(task.to_dict())
        if len(self.task_history) > 100:
            self.task_history = self.task_history[-100:]
        
        logger.info(f"任务完成: {task_id}")
        return {"status": "success", "task_id": task_id}
    
    async def get_network_status(self) -> Dict:
        """获取网络状态"""
        return {
            "agents": {
                agent_id: agent.to_dict() 
                for agent_id, agent in self.agents.items()
            },
            "stats": self.stats,
            "active_tasks": len([t for t in self.tasks.values() if t.status == "running"])
        }


# 全局协作网络实例
network = DecisionAgentNetwork()


# ============ API Handlers ============

async def register_agent(request):
    """注册Agent"""
    data = await request.json()
    agent = DecisionAgent(
        agent_id=data["agent_id"],
        name=data["name"],
        capabilities=data.get("capabilities", []),
        endpoint=data.get("endpoint", ""),
        metadata=data.get("metadata", {})
    )
    result = await network.register_agent(agent)
    return web.json_response(result)


async def unregister_agent(request):
    """注销Agent"""
    agent_id = request.match_info["agent_id"]
    result = await network.unregister_agent(agent_id)
    return web.json_response(result)


async def list_agents(request):
    """列出所有Agent"""
    agents = [agent.to_dict() for agent in network.agents.values()]
    return web.json_response({"agents": agents, "count": len(agents)})


async def create_task(request):
    """创建协作任务"""
    data = await request.json()
    task_id = await network.create_collaboration_task(
        decision_id=data.get("decision_id", ""),
        task_type=data["task_type"],
        required_capabilities=data.get("required_capabilities", []),
        metadata=data.get("metadata", {})
    )
    
    # 自动匹配Agent
    capabilities = data.get("required_capabilities", [])
    matched_agents = []
    for cap in capabilities:
        agents = network.find_agents_by_capability(cap)
        for a in agents:
            if a.agent_id not in matched_agents and len(matched_agents) < 3:
                matched_agents.append(a.agent_id)
    
    if matched_agents:
        await network.assign_task(task_id, matched_agents)
    
    return web.json_response({
        "task_id": task_id,
        "assigned_agents": matched_agents,
        "status": "created"
    })


async def assign_task(request):
    """分配任务"""
    data = await request.json()
    task_id = request.match_info["task_id"]
    result = await network.assign_task(task_id, data.get("agents", []))
    return web.json_response(result)


async def complete_task(request):
    """完成任务"""
    task_id = request.match_info["task_id"]
    data = await request.json()
    result = await network.complete_task(task_id, data.get("result", {}))
    return web.json_response(result)


async def get_task(request):
    """获取任务状态"""
    task_id = request.match_info["task_id"]
    if task_id not in network.tasks:
        return web.json_response({"error": "Task not found"}, status=404)
    return web.json_response(network.tasks[task_id].to_dict())


async def list_tasks(request):
    """列出任务"""
    status = request.query.get("status")
    tasks = network.tasks.values()
    if status:
        tasks = [t for t in tasks if t.status == status]
    return web.json_response({
        "tasks": [t.to_dict() for t in tasks],
        "count": len(tasks)
    })


async def get_network_status(request):
    """获取网络状态"""
    status = await network.get_network_status()
    return web.json_response(status)


async def find_agents(request):
    """查找具有特定能力的Agent"""
    capability = request.query.get("capability")
    if not capability:
        return web.json_response({"error": "capability required"}, status=400)
    
    agents = network.find_agents_by_capability(capability)
    return web.json_response({
        "agents": [a.to_dict() for a in agents],
        "count": len(agents)
    })


async def get_task_history(request):
    """获取任务历史"""
    limit = int(request.query.get("limit", 20))
    return web.json_response({
        "tasks": network.task_history[-limit:],
        "count": len(network.task_history)
    })


async def get_stats(request):
    """获取统计信息"""
    return web.json_response(network.stats)


async def health(request):
    """健康检查"""
    return web.json_response({"status": "healthy", "service": "decision-agent-network"})


# ============ Main ============

async def init_app():
    """初始化应用"""
    app = web.Application()
    
    # Agent管理
    app.router.add_post("/api/agents/register", register_agent)
    app.router.add_delete("/api/agents/{agent_id}", unregister_agent)
    app.router.add_get("/api/agents", list_agents)
    app.router.add_get("/api/agents/find", find_agents)
    
    # 任务管理
    app.router.add_post("/api/tasks", create_task)
    app.router.add_post("/api/tasks/{task_id}/assign", assign_task)
    app.router.add_post("/api/tasks/{task_id}/complete", complete_task)
    app.router.add_get("/api/tasks/{task_id}", get_task)
    app.router.add_get("/api/tasks", list_tasks)
    app.router.add_get("/api/tasks/history", get_task_history)
    
    # 网络状态
    app.router.add_get("/api/network/status", get_network_status)
    app.router.add_get("/api/stats", get_stats)
    app.router.add_get("/health", health)
    
    return app


async def main():
    """主入口"""
    # 注册默认决策Agent
    default_agents = [
        DecisionAgent(
            agent_id="decision-monitor",
            name="决策监控Agent",
            capabilities=["monitoring", "decision_monitoring"],
            endpoint="http://localhost:18091",
            metadata={"role": "monitor"}
        ),
        DecisionAgent(
            agent_id="decision-executor",
            name="决策执行Agent",
            capabilities=["execution", "action_execution"],
            endpoint="http://localhost:18092",
            metadata={"role": "executor"}
        ),
        DecisionAgent(
            agent_id="decision-analyzer",
            name="决策分析Agent",
            capabilities=["analysis", "decision_analysis"],
            endpoint="http://localhost:18093",
            metadata={"role": "analyzer"}
        ),
        DecisionAgent(
            agent_id="decision-notifier",
            name="决策通知Agent",
            capabilities=["notification", "alerting"],
            endpoint="http://localhost:18094",
            metadata={"role": "notifier"}
        ),
    ]
    
    for agent in default_agents:
        await network.register_agent(agent)
    
    app = await init_app()
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', 18150)
    await site.start()
    
    logger.info("=" * 50)
    logger.info("决策Agent协作网络已启动")
    logger.info("端口: 18125")
    logger.info("API端点:")
    logger.info("  - POST   /api/agents/register    注册Agent")
    logger.info("  - DELETE /api/agents/{id}        注销Agent")
    logger.info("  - GET    /api/agents             列出Agent")
    logger.info("  - POST   /api/tasks              创建任务")
    logger.info("  - GET    /api/tasks/{id}         获取任务")
    logger.info("  - GET    /api/network/status    网络状态")
    logger.info("  - GET    /api/stats              统计信息")
    logger.info("=" * 50)
    
    # 保持运行
    await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())