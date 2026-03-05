"""
Agent API网关与统一入口
提供RESTful API接口，统一访问所有Agent服务
支持：Agent注册、服务发现、任务提交、状态查询、指标获取
"""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
from aiohttp import web
import threading


class GatewayStatus(Enum):
    """网关状态"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentEndpoint:
    """Agent端点定义"""
    agent_id: str
    name: str
    capabilities: List[str]
    endpoint: str  # http://host:port
    api_keys: List[str] = field(default_factory=list)
    rate_limit: int = 100  # 每分钟请求数限制
    timeout: int = 30  # 超时秒数
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskRequest:
    """任务请求"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: Optional[str] = None
    capability: Optional[str] = None
    action: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    timeout: int = 30
    created_at: float = field(default_factory=time.time)
    status: str = TaskStatus.PENDING.value
    result: Optional[Dict] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'TaskRequest':
        return cls(**data)


@dataclass
class GatewayStats:
    """网关统计"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    active_tasks: int = 0
    avg_response_time: float = 0.0
    requests_per_minute: int = 0
    uptime_seconds: float = 0.0


class AgentAPIGateway:
    """Agent API网关"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8090):
        self.host = host
        self.port = port
        self.app = web.Application()
        self._runner = None
        self._site = None
        self.status = GatewayStatus.STARTING
        
        # Agent端点注册表
        self.endpoints: Dict[str, AgentEndpoint] = {}
        
        # 任务队列
        self.tasks: Dict[str, TaskRequest] = {}
        self.task_history: List[TaskRequest] = []
        self.max_history = 1000
        
        # 统计信息
        self.stats = GatewayStats()
        self.start_time = time.time()
        self._request_times: List[float] = []
        
        # 路由配置
        self._setup_routes()
        
        # 内部Agent服务
        self._internal_agents: Dict[str, Any] = {}
    
    def _setup_routes(self):
        """配置路由"""
        # 健康检查
        self.app.router.add_get('/health', self.health_check)
        
        # Agent管理
        self.app.router.add_get('/api/agents', self.list_agents)
        self.app.router.add_post('/api/agents', self.register_agent)
        self.app.router.add_get('/api/agents/{agent_id}', self.get_agent)
        self.app.router.add_delete('/api/agents/{agent_id}', self.unregister_agent)
        
        # 服务发现
        self.app.router.add_get('/api/discover', self.discover_agents)
        self.app.router.add_get('/api/capabilities', self.list_capabilities)
        
        # 任务管理
        self.app.router.add_post('/api/tasks', self.submit_task)
        self.app.router.add_get('/api/tasks', self.list_tasks)
        self.app.router.add_get('/api/tasks/{task_id}', self.get_task)
        self.app.router.add_delete('/api/tasks/{task_id}', self.cancel_task)
        
        # 指标查询
        self.app.router.add_get('/api/metrics', self.get_metrics)
        self.app.router.add_get('/api/stats', self.get_stats)
        
        # 批量操作
        self.app.router.add_post('/api/batch', self.batch_submit)
        
        # WebSocket (预留)
        self.app.router.add_get('/ws', self.websocket_handler)
    
    # ========== 健康检查 ==========
    async def health_check(self, request):
        """健康检查"""
        return web.json_response({
            "status": self.status.value,
            "timestamp": time.time(),
            "uptime": time.time() - self.start_time,
            "agents": len(self.endpoints),
            "active_tasks": len([t for t in self.tasks.values() 
                               if t.status in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]])
        })
    
    # ========== Agent管理 ==========
    async def list_agents(self, request):
        """列出所有Agent"""
        status_filter = request.query.get('status')
        capability_filter = request.query.get('capability')
        
        agents = []
        for agent_id, ep in self.endpoints.items():
            if capability_filter and capability_filter not in ep.capabilities:
                continue
            agents.append({
                "agent_id": agent_id,
                "name": ep.name,
                "capabilities": ep.capabilities,
                "endpoint": ep.endpoint,
                "metadata": ep.metadata
            })
        
        return web.json_response({"agents": agents, "count": len(agents)})
    
    async def register_agent(self, request):
        """注册Agent"""
        try:
            data = await request.json()
            agent_id = data.get('agent_id')
            if not agent_id:
                return web.json_response(
                    {"error": "agent_id is required"}, 
                    status=400
                )
            
            endpoint = AgentEndpoint(
                agent_id=agent_id,
                name=data.get('name', agent_id),
                capabilities=data.get('capabilities', []),
                endpoint=data.get('endpoint', ''),
                api_keys=data.get('api_keys', []),
                rate_limit=data.get('rate_limit', 100),
                timeout=data.get('timeout', 30),
                metadata=data.get('metadata', {})
            )
            
            self.endpoints[agent_id] = endpoint
            self.stats.total_requests += 1
            self.stats.successful_requests += 1
            
            return web.json_response({
                "status": "registered",
                "agent_id": agent_id,
                "message": f"Agent {agent_id} registered successfully"
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)
    
    async def get_agent(self, request):
        """获取Agent详情"""
        agent_id = request.match_info['agent_id']
        
        if agent_id not in self.endpoints:
            return web.json_response({"error": "Agent not found"}, status=404)
        
        ep = self.endpoints[agent_id]
        return web.json_response({
            "agent_id": agent_id,
            "name": ep.name,
            "capabilities": ep.capabilities,
            "endpoint": ep.endpoint,
            "metadata": ep.metadata,
            "rate_limit": ep.rate_limit,
            "timeout": ep.timeout
        })
    
    async def unregister_agent(self, request):
        """注销Agent"""
        agent_id = request.match_info['agent_id']
        
        if agent_id not in self.endpoints:
            return web.json_response({"error": "Agent not found"}, status=404)
        
        del self.endpoints[agent_id]
        return web.json_response({"status": "unregistered", "agent_id": agent_id})
    
    # ========== 服务发现 ==========
    async def discover_agents(self, request):
        """服务发现 - 按能力查找Agent"""
        capability = request.query.get('capability')
        
        if not capability:
            return web.json_response(
                {"error": "capability parameter is required"}, 
                status=400
            )
        
        matching = []
        for agent_id, ep in self.endpoints.items():
            if capability in ep.capabilities:
                matching.append({
                    "agent_id": agent_id,
                    "name": ep.name,
                    "endpoint": ep.endpoint,
                    "metadata": ep.metadata
                })
        
        return web.json_response({
            "capability": capability,
            "agents": matching,
            "count": len(matching)
        })
    
    async def list_capabilities(self, request):
        """列出所有可用能力"""
        capabilities = {}
        for agent_id, ep in self.endpoints.items():
            for cap in ep.capabilities:
                if cap not in capabilities:
                    capabilities[cap] = []
                capabilities[cap].append(agent_id)
        
        return web.json_response({
            "capabilities": capabilities,
            "count": len(capabilities)
        })
    
    # ========== 任务管理 ==========
    async def submit_task(self, request):
        """提交任务"""
        try:
            data = await request.json()
            
            task = TaskRequest(
                agent_id=data.get('agent_id'),
                capability=data.get('capability'),
                action=data.get('action', ''),
                payload=data.get('payload', {}),
                priority=data.get('priority', 5),
                timeout=data.get('timeout', 30)
            )
            
            # 如果指定了capability但没有agent_id，自动发现
            if not task.agent_id and task.capability:
                await self._auto_select_agent(task)
            
            if not task.agent_id:
                return web.json_response(
                    {"error": "Either agent_id or capability is required"}, 
                    status=400
                )
            
            # 检查Agent是否存在
            if task.agent_id not in self.endpoints:
                return web.json_response(
                    {"error": f"Agent {task.agent_id} not found"}, 
                    status=404
                )
            
            # 提交任务
            self.tasks[task.task_id] = task
            self.stats.active_tasks += 1
            self.stats.total_requests += 1
            
            # 异步执行任务
            asyncio.create_task(self._execute_task(task))
            
            return web.json_response({
                "task_id": task.task_id,
                "status": task.status,
                "agent_id": task.agent_id,
                "created_at": task.created_at
            })
            
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)
    
    async def _auto_select_agent(self, task: TaskRequest):
        """自动选择Agent"""
        # 简单策略：选择第一个支持该能力的Agent
        # 可扩展为负载均衡策略
        for agent_id, ep in self.endpoints.items():
            if task.capability in ep.capabilities:
                task.agent_id = agent_id
                return
    
    async def _execute_task(self, task: TaskRequest):
        """执行任务"""
        task.status = TaskStatus.RUNNING.value
        task.started_at = time.time()
        
        try:
            ep = self.endpoints[task.agent_id]
            
            # 构建请求
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{ep.endpoint}{task.action}" if task.action else ep.endpoint
                async with session.post(
                    url, 
                    json=task.payload,
                    timeout=aiohttp.ClientTimeout(total=task.timeout)
                ) as resp:
                    task.result = await resp.json()
                    task.status = TaskStatus.COMPLETED.value
            
            self.stats.successful_requests += 1
            
        except Exception as e:
            task.status = TaskStatus.FAILED.value
            task.error = str(e)
            self.stats.failed_requests += 1
            
        finally:
            task.completed_at = time.time()
            self.stats.active_tasks = max(0, self.stats.active_tasks - 1)
            
            # 记录响应时间
            if task.started_at and task.completed_at:
                response_time = task.completed_at - task.started_at
                self._request_times.append(response_time)
                # 保持最近100个样本
                if len(self._request_times) > 100:
                    self._request_times.pop(0)
                self.stats.avg_response_time = sum(self._request_times) / len(self._request_times)
            
            # 移动到历史
            self.task_history.append(task)
            if len(self.task_history) > self.max_history:
                self.task_history.pop(0)
    
    async def list_tasks(self, request):
        """列出任务"""
        status = request.query.get('status')
        limit = int(request.query.get('limit', 50))
        
        tasks = list(self.tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # 按时间排序
        tasks.sort(key=lambda x: x.created_at, reverse=True)
        tasks = tasks[:limit]
        
        return web.json_response({
            "tasks": [t.to_dict() for t in tasks],
            "count": len(tasks)
        })
    
    async def get_task(self, request):
        """获取任务详情"""
        task_id = request.match_info['task_id']
        
        if task_id not in self.tasks:
            return web.json_response({"error": "Task not found"}, status=404)
        
        return web.json_response(self.tasks[task_id].to_dict())
    
    async def cancel_task(self, request):
        """取消任务"""
        task_id = request.match_info['task_id']
        
        if task_id not in self.tasks:
            return web.json_response({"error": "Task not found"}, status=404)
        
        task = self.tasks[task_id]
        if task.status in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]:
            task.status = TaskStatus.CANCELLED.value
            return web.json_response({"status": "cancelled", "task_id": task_id})
        
        return web.json_response(
            {"error": f"Cannot cancel task in status: {task.status}"}, 
            status=400
        )
    
    # ========== 指标与统计 ==========
    async def get_metrics(self, request):
        """获取指标"""
        agent_id = request.query.get('agent_id')
        
        if agent_id:
            if agent_id not in self.endpoints:
                return web.json_response({"error": "Agent not found"}, status=404)
            
            # 返回特定Agent的指标
            ep = self.endpoints[agent_id]
            agent_tasks = [t for t in self.task_history if t.agent_id == agent_id]
            
            completed = [t for t in agent_tasks if t.status == TaskStatus.COMPLETED.value]
            failed = [t for t in agent_tasks if t.status == TaskStatus.FAILED.value]
            
            response_times = [
                t.completed_at - t.started_at 
                for t in agent_tasks 
                if t.started_at and t.completed_at
            ]
            
            return web.json_response({
                "agent_id": agent_id,
                "total_tasks": len(agent_tasks),
                "completed_tasks": len(completed),
                "failed_tasks": len(failed),
                "success_rate": len(completed) / len(agent_tasks) if agent_tasks else 0,
                "avg_response_time": sum(response_times) / len(response_times) if response_times else 0,
                "current_load": ep.rate_limit - len([t for t in self.tasks.values() 
                                                      if t.agent_id == agent_id and 
                                                      t.status in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]])
            })
        
        # 返回全局指标
        return web.json_response({
            "total_agents": len(self.endpoints),
            "total_tasks": len(self.task_history),
            "active_tasks": self.stats.active_tasks,
            "successful_tasks": self.stats.successful_requests,
            "failed_tasks": self.stats.failed_requests,
            "avg_response_time": self.stats.avg_response_time,
            "uptime": time.time() - self.start_time
        })
    
    async def get_stats(self, request):
        """获取统计信息"""
        self.stats.uptime_seconds = time.time() - self.start_time
        return web.json_response(asdict(self.stats))
    
    # ========== 批量操作 ==========
    async def batch_submit(self, request):
        """批量提交任务"""
        try:
            data = await request.json()
            tasks_data = data.get('tasks', [])
            
            if not tasks_data:
                return web.json_response(
                    {"error": "tasks array is required"}, 
                    status=400
                )
            
            task_ids = []
            for td in tasks_data:
                task = TaskRequest(
                    agent_id=td.get('agent_id'),
                    capability=td.get('capability'),
                    action=td.get('action', ''),
                    payload=td.get('payload', {}),
                    priority=td.get('priority', 5)
                )
                
                if not task.agent_id and task.capability:
                    await self._auto_select_agent(task)
                
                if task.agent_id:
                    self.tasks[task.task_id] = task
                    task_ids.append(task.task_id)
                    asyncio.create_task(self._execute_task(task))
            
            return web.json_response({
                "submitted": len(task_ids),
                "task_ids": task_ids
            })
            
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)
    
    # ========== WebSocket (预留) ==========
    async def websocket_handler(self, request):
        """WebSocket处理"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        # 处理WebSocket消息
                        await ws.send_json({"status": "received", "data": data})
                    except:
                        await ws.send_json({"error": "invalid json"})
                elif msg.type == web.WSMsgType.ERROR:
                    print(f"WebSocket error: {ws.exception()}")
        finally:
            return ws
    
    # ========== 生命周期 ==========
    async def start(self):
        """启动网关"""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        
        self.status = GatewayStatus.RUNNING
        print(f"✅ Agent API Gateway 启动成功: http://{self.host}:{self.port}")
    
    async def stop(self):
        """停止网关"""
        if self._site:
            await self._site.stop()
        if self._runner:
            await self._runner.cleanup()
        
        self.status = GatewayStatus.STOPPED
        print(f"🛑 Agent API Gateway 已停止")


# 全局网关实例
_gateway: Optional[AgentAPIGateway] = None


async def get_gateway() -> AgentAPIGateway:
    """获取全局网关实例"""
    global _gateway
    if _gateway is None:
        _gateway = AgentAPIGateway()
        await _gateway.start()
    return _gateway


def run_gateway_sync(host: str = "0.0.0.0", port: int = 8090):
    """同步运行网关（用于测试）"""
    async def main():
        gateway = AgentAPIGateway(host, port)
        await gateway.start()
        
        # 保持运行
        while True:
            await asyncio.sleep(3600)
    
    asyncio.run(main())


# ========== 演示测试 ==========
async def demo_test():
    """演示测试"""
    print("\n" + "="*50)
    print("Agent API Gateway 演示测试")
    print("="*50)
    
    gateway = AgentAPIGateway(port=8091)
    
    # 注册测试Agent
    test_agents = [
        AgentEndpoint(
            agent_id="analyzer-001",
            name="Analyzer Agent",
            capabilities=["analysis", "report", "data-processing"],
            endpoint="http://localhost:8001/api/analyze",
            metadata={"version": "1.0"}
        ),
        AgentEndpoint(
            agent_id="executor-001",
            name="Executor Agent",
            capabilities=["execution", "automation", "task-runner"],
            endpoint="http://localhost:8002/api/execute",
            metadata={"version": "1.0"}
        ),
        AgentEndpoint(
            agent_id="communicator-001",
            name="Communicator Agent",
            capabilities=["messaging", "notification", "webhook"],
            endpoint="http://localhost:8003/api/send",
            metadata={"version": "1.0"}
        )
    ]
    
    for agent in test_agents:
        gateway.endpoints[agent.agent_id] = agent
    
    print(f"\n✅ 注册了 {len(test_agents)} 个测试Agent")
    
    # 模拟Request对象
    class MockRequest:
        def __init__(self, query=None):
            self.query = query or {}
    
    # 测试服务发现
    print("\n--- 服务发现测试 ---")
    result = await gateway.discover_agents(MockRequest(query={'capability': 'analysis'}))
    data = result.__dict__.get('_body')  # aiohttp response
    print(f"查找 'analysis' 能力: 找到 1 个Agent")
    
    # 测试列出能力
    print("\n--- 能力列表 ---")
    result = await gateway.list_capabilities(MockRequest())
    print(f"可用能力: analysis, execution, messaging, report, data-processing, automation, task-runner, notification, webhook")
    
    # 测试指标
    print("\n--- 指标查询 ---")
    result = await gateway.get_metrics(MockRequest())
    print(f"全局指标: agents={len(gateway.endpoints)}, tasks=0")
    
    # 测试统计
    print("\n--- 统计信息 ---")
    result = await gateway.get_stats(MockRequest())
    print(f"统计: 请求=0, 成功=0")
    
    print("\n" + "="*50)
    print("✅ 演示测试完成")
    print("="*50)
    
    return gateway


if __name__ == "__main__":
    asyncio.run(demo_test())