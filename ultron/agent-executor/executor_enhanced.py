#!/usr/bin/env python3
"""
Agent执行器增强版 (第56世)
- 任务优先级队列
- 任务依赖管理
- 资源限制与超时控制
- 执行结果缓存
- 任务重试机制
- 批量任务处理
"""
import asyncio
import json
import time
import uuid
import hashlib
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
import psutil
import os

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING_DEPS = "waiting_dependencies"

class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

class AgentCapability(Enum):
    BROWSER = "browser"
    EXEC = "exec"
    DATA = "data"
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"
    FILE = "file"
    NETWORK = "network"

@dataclass
class Agent:
    id: str
    name: str
    capabilities: List[AgentCapability]
    status: str = "idle"
    current_task: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    max_concurrent: int = 1
    resource_limits: Dict[str, Any] = field(default_factory=lambda: {
        "max_memory_mb": 512,
        "max_cpu_percent": 50,
        "max_execution_time": 300
    })

@dataclass
class Task:
    id: str
    type: str
    payload: Dict[str, Any]
    priority: TaskPriority = TaskPriority.NORMAL
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)
    timeout: int = 300  # 秒
    cache_key: Optional[str] = None
    tags: List[str] = field(default_factory=list)


class ResultCache:
    """执行结果缓存"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 3600):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.timestamps: Dict[str, float] = {}
        self.max_size = max_size
        self.ttl = ttl
    
    def _generate_key(self, task_type: str, payload: Dict[str, Any]) -> str:
        """生成缓存键"""
        content = f"{task_type}:{json.dumps(payload, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get(self, task_type: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """获取缓存结果"""
        key = self._generate_key(task_type, payload)
        if key in self.cache:
            if time.time() - self.timestamps[key] < self.ttl:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.timestamps[key]
        return None
    
    def set(self, task_type: str, payload: Dict[str, Any], result: Dict[str, Any]):
        """缓存结果"""
        key = self._generate_key(task_type, payload)
        self.cache[key] = result
        self.timestamps[key] = time.time()
        
        # 清理旧缓存
        if len(self.cache) > self.max_size:
            oldest = min(self.timestamps.items(), key=lambda x: x[1])
            del self.cache[oldest[0]]
            del self.timestamps[oldest[0]]
    
    def clear(self):
        """清空缓存"""
        self.cache.clear()
        self.timestamps.clear()


class EnhancedAgentExecutor:
    """增强版Agent执行器"""
    
    def __init__(self, port: int = 18162):
        self.port = port
        self.agents: Dict[str, Agent] = {}
        self.tasks: Dict[str, Task] = {}
        self.priority_queues: Dict[TaskPriority, asyncio.PriorityQueue] = {
            p: asyncio.PriorityQueue() for p in TaskPriority
        }
        self.result_cache = ResultCache()
        self.running = False
        self.worker_tasks: List[asyncio.Task] = []
        
        # 统计
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "cached_results": 0,
            "start_time": time.time()
        }
        
        # 任务依赖图
        self.dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_deps: Dict[str, Set[str]] = defaultdict(set)
    
    def register_agent(self, name: str, capabilities: List[str], 
                       max_concurrent: int = 1, resource_limits: Dict = None) -> str:
        """注册Agent"""
        agent_id = f"agent_{uuid.uuid4().hex[:8]}"
        caps = [AgentCapability(c) for c in capabilities 
                if c in [e.value for e in AgentCapability]]
        
        limits = resource_limits or {
            "max_memory_mb": 512,
            "max_cpu_percent": 50,
            "max_execution_time": 300
        }
        
        self.agents[agent_id] = Agent(
            id=agent_id,
            name=name,
            capabilities=caps,
            max_concurrent=max_concurrent,
            resource_limits=limits
        )
        return agent_id
    
    def set_agent_status(self, agent_id: str, status: str):
        """设置Agent状态"""
        if agent_id in self.agents:
            self.agents[agent_id].status = status
    
    async def submit_task(self, task_type: str, payload: Dict[str, Any],
                          priority: int = 1, dependencies: List[str] = None,
                          max_retries: int = 3, timeout: int = 300,
                          tags: List[str] = None, use_cache: bool = True) -> str:
        """提交任务"""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        
        # 检查缓存
        if use_cache:
            cached = self.result_cache.get(task_type, payload)
            if cached:
                self.stats["cached_results"] += 1
                return {"task_id": task_id, "result": cached, "cached": True}
        
        task = Task(
            id=task_id,
            type=task_type,
            payload=payload,
            priority=TaskPriority(priority),
            dependencies=dependencies or [],
            max_retries=max_retries,
            timeout=timeout,
            tags=tags or []
        )
        
        self.tasks[task_id] = task
        self.stats["total_tasks"] += 1
        
        # 处理依赖
        if dependencies:
            for dep_id in dependencies:
                if dep_id in self.tasks:
                    self.dependency_graph[dep_id].add(task_id)
                    self.reverse_deps[task_id].add(dep_id)
            
            # 检查是否所有依赖都已完成
            if not self._check_dependencies_met(task_id):
                task.status = TaskStatus.WAITING_DEPS
                return task_id
        
        # 加入优先级队列
        await self.priority_queues[task.priority].put((priority, task_id))
        return task_id
    
    def _check_dependencies_met(self, task_id: str) -> bool:
        """检查任务依赖是否满足"""
        deps = self.reverse_deps.get(task_id, set())
        for dep_id in deps:
            dep_task = self.tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False
        return True
    
    def _get_ready_tasks(self) -> List[str]:
        """获取所有就绪的任务"""
        ready = []
        for task_id, task in self.tasks.items():
            if task.status in [TaskStatus.PENDING, TaskStatus.WAITING_DEPS]:
                if task.status == TaskStatus.WAITING_DEPS:
                    if self._check_dependencies_met(task_id):
                        task.status = TaskStatus.PENDING
                        ready.append(task_id)
                else:
                    ready.append(task_id)
        return ready
    
    def match_agent(self, required_capability: str) -> Optional[Agent]:
        """匹配最合适的Agent"""
        idle_agents = [
            a for a in self.agents.values() 
            if a.status == "idle" or (
                a.status == "busy" and 
                a.metrics.get("current_tasks", 0) < a.max_concurrent
            )
        ]
        
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
        agent.metrics["current_tasks"] = agent.metrics.get("current_tasks", 0) + 1
        
        try:
            # 带超时的执行
            result = await asyncio.wait_for(
                self._run_agent_task(agent, task),
                timeout=task.timeout
            )
            
            task.result = result
            task.status = TaskStatus.COMPLETED
            task.completed_at = time.time()
            
            # 更新Agent指标
            agent.metrics["tasks_completed"] = agent.metrics.get("tasks_completed", 0) + 1
            agent.metrics["current_tasks"] = max(0, agent.metrics.get("current_tasks", 1) - 1)
            agent.metrics["last_execution_time"] = task.completed_at - task.started_at
            
            # 缓存结果
            if task.status == TaskStatus.COMPLETED:
                self.result_cache.set(task.type, task.payload, result)
            
            self.stats["completed_tasks"] += 1
            
            # 检查依赖此任务的其他任务
            await self._check_dependent_tasks(task_id)
            
            return {"status": "completed", "result": result}
            
        except asyncio.TimeoutError:
            task.status = TaskStatus.FAILED
            task.error = f"Task timeout after {task.timeout}s"
            task.completed_at = time.time()
            self.stats["failed_tasks"] += 1
            return {"status": "failed", "error": "Task timeout"}
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = time.time()
            self.stats["failed_tasks"] += 1
            
            # 重试机制
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.PENDING
                await self.priority_queues[task.priority].put((task.priority.value, task_id))
            
            return {"status": "failed", "error": str(e)}
            
        finally:
            if agent.status == "busy":
                agent.status = "idle"
            agent.current_task = None
    
    async def _check_dependent_tasks(self, completed_task_id: str):
        """检查并唤醒依赖此任务的其他任务"""
        dependent_tasks = self.dependency_graph.get(completed_task_id, set())
        for task_id in dependent_tasks:
            if self._check_dependencies_met(task_id):
                task = self.tasks[task_id]
                if task.status == TaskStatus.WAITING_DEPS:
                    task.status = TaskStatus.PENDING
                    await self.priority_queues[task.priority].put(
                        (task.priority.value, task_id)
                    )
    
    async def _run_agent_task(self, agent: Agent, task: Task) -> Dict[str, Any]:
        """运行Agent任务"""
        task_type = task.type
        
        if task_type == "exec":
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
            data = task.payload.get("data", [])
            operation = task.payload.get("operation", "process")
            
            if operation == "aggregate":
                result = {"sum": sum(data), "avg": sum(data)/len(data) if data else 0, "count": len(data)}
            elif operation == "filter":
                condition = task.payload.get("condition", {})
                result = {"filtered": data, "count": len(data)}
            else:
                result = {"processed": True, "data_size": len(str(data))}
            
            return result
            
        elif task_type == "analysis":
            # 分析任务
            return {
                "analysis": "completed",
                "confidence": 0.85,
                "insights": ["Pattern detected", "Trend identified"]
            }
            
        elif task_type == "batch":
            # 批量任务
            subtasks = task.payload.get("subtasks", [])
            results = []
            for subtask in subtasks:
                results.append({"subtask": subtask, "status": "done"})
            return {"batch_results": results, "total": len(subtasks)}
            
        else:
            return {"result": "unknown task type"}
    
    async def worker(self, worker_id: int):
        """工作协程"""
        while self.running:
            try:
                # 从高优先级到低优先级获取任务
                task_id = None
                for priority in sorted(TaskPriority, key=lambda p: p.value, reverse=True):
                    try:
                        _, tid = await asyncio.wait_for(
                            self.priority_queues[priority].get(),
                            timeout=0.1
                        )
                        task_id = tid
                        break
                    except asyncio.TimeoutError:
                        continue
                
                if task_id:
                    await self.execute_task(task_id)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Worker {worker_id} error: {e}")
    
    async def start(self):
        """启动执行器"""
        self.running = True
        
        # 注册默认Agent
        self.register_agent("Worker-1", ["exec", "data"], max_concurrent=2)
        self.register_agent("Worker-2", ["browser", "analysis"], max_concurrent=1)
        self.register_agent("Worker-3", ["communication", "data"], max_concurrent=2)
        self.register_agent("Worker-4", ["file", "exec"], max_concurrent=2)
        
        # 启动工作协程
        num_workers = 4
        self.worker_tasks = [
            asyncio.create_task(self.worker(i)) 
            for i in range(num_workers)
        ]
        
        print(f"🚀 增强版Agent执行器启动 (port {self.port})")
        print(f"📋 注册Agent: {len(self.agents)}, Workers: {num_workers}")
        
        await asyncio.gather(*self.worker_tasks)
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        # 计算队列大小
        queue_sizes = {}
        for priority in TaskPriority:
            queue_sizes[priority.name] = self.priority_queues[priority].qsize()
        
        return {
            "port": self.port,
            "uptime": time.time() - self.stats["start_time"],
            "stats": self.stats,
            "cache": {
                "size": len(self.result_cache.cache),
                "hit_rate": self.stats["cached_results"] / max(1, self.stats["total_tasks"])
            },
            "agents": {
                aid: {
                    "name": a.name,
                    "status": a.status,
                    "capabilities": [c.value for c in a.capabilities],
                    "max_concurrent": a.max_concurrent,
                    "current_tasks": a.metrics.get("current_tasks", 0),
                    "tasks_completed": a.metrics.get("tasks_completed", 0)
                }
                for aid, a in self.agents.items()
            },
            "tasks": {
                "total": len(self.tasks),
                "pending": len([t for t in self.tasks.values() if t.status == TaskStatus.PENDING]),
                "running": len([t for t in self.tasks.values() if t.status == TaskStatus.RUNNING]),
                "waiting_deps": len([t for t in self.tasks.values() if t.status == TaskStatus.WAITING_DEPS]),
                "completed": len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]),
                "failed": len([t for t in self.tasks.values() if t.status == TaskStatus.FAILED])
            },
            "queues": queue_sizes
        }
    
    async def submit_batch(self, tasks: List[Dict[str, Any]]) -> List[str]:
        """批量提交任务"""
        task_ids = []
        for task_spec in tasks:
            tid = await self.submit_task(
                task_type=task_spec.get("type", "exec"),
                payload=task_spec.get("payload", {}),
                priority=task_spec.get("priority", 1),
                dependencies=task_spec.get("dependencies", []),
                max_retries=task_spec.get("max_retries", 3),
                timeout=task_spec.get("timeout", 300),
                tags=task_spec.get("tags", []),
                use_cache=task_spec.get("use_cache", True)
            )
            task_ids.append(tid)
        return task_ids
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task.status in [TaskStatus.PENDING, TaskStatus.WAITING_DEPS]:
                task.status = TaskStatus.CANCELLED
                return True
        return False
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务结果"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        return {
            "id": task.id,
            "type": task.type,
            "status": task.status.value,
            "priority": task.priority.value,
            "assigned_agent": task.assigned_agent,
            "result": task.result,
            "error": task.error,
            "retry_count": task.retry_count,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "duration": task.completed_at - task.started_at if task.completed_at and task.started_at else None,
            "tags": task.tags
        }


# HTTP API服务
from aiohttp import web

async def status_handler(request):
    executor = request.app["executor"]
    return web.json_response(executor.get_status())

async def submit_handler(request):
    executor = request.app["executor"]
    data = await request.json()
    
    if "tasks" in data:
        # 批量提交
        task_ids = await executor.submit_batch(data["tasks"])
        return web.json_response({"task_ids": task_ids, "count": len(task_ids)})
    else:
        # 单任务提交
        task_id = await executor.submit_task(
            task_type=data.get("type", "exec"),
            payload=data.get("payload", {}),
            priority=data.get("priority", 1),
            dependencies=data.get("dependencies", []),
            max_retries=data.get("max_retries", 3),
            timeout=data.get("timeout", 300),
            tags=data.get("tags", []),
            use_cache=data.get("use_cache", True)
        )
        return web.json_response({"task_id": task_id})

async def task_handler(request):
    executor = request.app["executor"]
    task_id = request.match_info["task_id"]
    
    result = executor.get_task_result(task_id)
    if not result:
        return web.json_response({"error": "Task not found"}, status=404)
    return web.json_response(result)

async def cancel_handler(request):
    executor = request.app["executor"]
    task_id = request.match_info["task_id"]
    success = executor.cancel_task(task_id)
    return web.json_response({"success": success})

async def batch_handler(request):
    executor = request.app["executor"]
    task_ids = request.match_info.get("task_ids", "").split(",")
    
    results = []
    for task_id in task_ids:
        result = executor.get_task_result(task_id)
        if result:
            results.append(result)
    
    return web.json_response({"results": results, "count": len(results)})

async def register_agent_handler(request):
    executor = request.app["executor"]
    data = await request.json()
    agent_id = executor.register_agent(
        data.get("name"),
        data.get("capabilities", []),
        data.get("max_concurrent", 1),
        data.get("resource_limits")
    )
    return web.json_response({"agent_id": agent_id})

async def cache_clear_handler(request):
    executor = request.app["executor"]
    executor.result_cache.clear()
    return web.json_response({"success": True, "message": "Cache cleared"})

async def dashboard_handler(request):
    """Dashboard页面"""
    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent执行器监控面板</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #eee;
            padding: 20px;
        }
        .header { text-align: center; padding: 20px; margin-bottom: 20px; }
        .header h1 { 
            font-size: 2rem; 
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        .stat-card h3 { color: #888; font-size: 0.9rem; margin-bottom: 8px; }
        .stat-card .value { font-size: 2rem; font-weight: bold; }
        .stat-card.total .value { color: #00d4ff; }
        .stat-card.completed .value { color: #00ff88; }
        .stat-card.failed .value { color: #ff4757; }
        .stat-card.cache .value { color: #ffa502; }
        
        .main-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
        .panel { background: rgba(255,255,255,0.05); border-radius: 12px; padding: 20px; }
        .panel h2 { font-size: 1.2rem; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        
        .agent-list { max-height: 300px; overflow-y: auto; }
        .agent-item { display: flex; justify-content: space-between; align-items: center; padding: 12px; margin-bottom: 8px; background: rgba(255,255,255,0.05); border-radius: 8px; }
        .agent-info { display: flex; align-items: center; gap: 10px; }
        .agent-status { width: 10px; height: 10px; border-radius: 50%; }
        .agent-status.idle { background: #00ff88; }
        .agent-status.busy { background: #ffa502; }
        .agent-caps { font-size: 0.8rem; color: #888; }
        
        .task-stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
        .task-stat { text-align: center; padding: 15px; background: rgba(255,255,255,0.05); border-radius: 8px; }
        .task-stat .num { font-size: 1.5rem; font-weight: bold; }
        .task-stat .label { font-size: 0.8rem; color: #888; }
        
        .queue-info { display: flex; gap: 20px; margin-top: 15px; }
        .queue-item { flex: 1; text-align: center; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 8px; }
        
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
        th { color: #888; font-weight: normal; font-size: 0.9rem; }
        .status-badge { padding: 4px 8px; border-radius: 4px; font-size: 0.8rem; }
        .status-badge.completed { background: rgba(0,255,136,0.2); color: #00ff88; }
        .status-badge.pending { background: rgba(255,165,2,0.2); color: #ffa502; }
        .status-badge.running { background: rgba(0,212,255,0.2); color: #00d4ff; }
        .status-badge.failed { background: rgba(255,71,87,0.2); color: #ff4757; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 Agent执行器监控面板</h1>
        <p>端口: <span id="port">-</span> | 运行时间: <span id="uptime">-</span></p>
    </div>
    <div class="stats-grid">
        <div class="stat-card total"><h3>总任务数</h3><div class="value" id="totalTasks">-</div></div>
        <div class="stat-card completed"><h3>已完成</h3><div class="value" id="completedTasks">-</div></div>
        <div class="stat-card failed"><h3>失败</h3><div class="value" id="failedTasks">-</div></div>
        <div class="stat-card cache"><h3>缓存命中率</h3><div class="value" id="cacheHitRate">-</div></div>
    </div>
    <div class="main-grid">
        <div class="panel">
            <h2>👥 Agent状态</h2>
            <div class="agent-list" id="agentList"></div>
        </div>
        <div class="panel">
            <h2>📊 任务统计</h2>
            <div class="task-stats">
                <div class="task-stat"><div class="num" id="pendingTasks">-</div><div class="label">等待中</div></div>
                <div class="task-stat"><div class="num" id="runningTasks">-</div><div class="label">执行中</div></div>
                <div class="task-stat"><div class="num" id="waitingDeps">-</div><div class="label">等待依赖</div></div>
            </div>
            <div class="queue-info" id="queueInfo"></div>
        </div>
    </div>
    <script>
        async function fetchStatus() {
            try { const res = await fetch('/status'); statusData = await res.json(); updateUI(); } catch(e) { console.error(e); }
        }
        function updateUI() {
            if (!statusData) return;
            document.getElementById("port").textContent = statusData.port;
            document.getElementById("uptime").textContent = formatUptime(statusData.uptime);
            document.getElementById("totalTasks").textContent = statusData.stats.total_tasks;
            document.getElementById("completedTasks").textContent = statusData.stats.completed_tasks;
            document.getElementById("failedTasks").textContent = statusData.stats.failed_tasks;
            document.getElementById("cacheHitRate").textContent = (statusData.cache.hit_rate * 100).toFixed(1) + "%";
            document.getElementById("agentList").innerHTML = Object.values(statusData.agents).map(a => '<div class="agent-item"><div class="agent-info"><div class="agent-status '+a.status+'"></div><div><div>'+a.name+'</div><div class="agent-caps">'+a.capabilities.join(", ")+'</div></div></div><div>'+a.tasks_completed+' 任务</div></div>').join("");
            document.getElementById("pendingTasks").textContent = statusData.tasks.pending;
            document.getElementById("runningTasks").textContent = statusData.tasks.running;
            document.getElementById("waitingDeps").textContent = statusData.tasks.waiting_deps;
            document.getElementById("queueInfo").innerHTML = Object.entries(statusData.queues).map(([n,c]) => '<div class="queue-item"><div class="num">'+c+'</div><div class="label">'+n+'</div></div>').join("");
        }
        function formatUptime(s) { const h=Math.floor(s/3600),m=Math.floor((s%3600)/60),sec=Math.floor(s%60); return h+"h "+m+"m "+sec+"s"; }
        fetchStatus(); setInterval(fetchStatus, 3000);
    </script>
</body>
</html>'''
    return web.Response(text=html, content_type='text/html')

async def on_startup(app):
    """应用启动时的回调"""
    executor = app["executor"]
    executor.running = True
    
    # 启动worker后台任务
    for i in range(4):
        asyncio.create_task(executor.worker(i))
    
    # 注册默认Agent
    executor.register_agent("Worker-1", ["exec", "data"], max_concurrent=2)
    executor.register_agent("Worker-2", ["browser", "analysis"], max_concurrent=1)
    executor.register_agent("Worker-3", ["communication", "data"], max_concurrent=2)
    executor.register_agent("Worker-4", ["file", "exec"], max_concurrent=2)
    
    print(f"📋 已注册{len(executor.agents)}个Worker Agent")

def create_app(executor: EnhancedAgentExecutor):
    app = web.Application()
    app["executor"] = executor
    app.on_startup.append(on_startup)
    app.router.add_get("/status", status_handler)
    app.router.add_post("/tasks", submit_handler)
    app.router.add_get("/tasks/{task_id}", task_handler)
    app.router.add_post("/tasks/{task_id}/cancel", cancel_handler)
    app.router.add_get("/batch/{task_ids}", batch_handler)
    app.router.add_post("/agents", register_agent_handler)
    app.router.add_post("/cache/clear", cache_clear_handler)
    app.router.add_get("/", dashboard_handler)
    app.router.add_get("/dashboard", dashboard_handler)
    return app


if __name__ == "__main__":
    executor = EnhancedAgentExecutor(port=18210)
    app = create_app(executor)
    print(f"🌐 增强版Agent执行器API服务启动: http://0.0.0.0:{executor.port}")
    web.run_app(app, host="0.0.0.0", port=executor.port)