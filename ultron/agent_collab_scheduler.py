#!/usr/bin/env python3
"""
Agent协同任务调度器 - Collaboration Task Scheduler
第50世: 实现Agent服务编排与工作流引擎

功能:
- 协同任务调度: 多Agent协作完成复杂任务
- 任务依赖管理: DAG依赖图、拓扑排序
- 工作流引擎: 串行/并行/条件执行
- 智能调度: 基于能力、负载、优先级
"""

import json
import time
import uuid
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict, deque
import threading
import heapq


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"  # 等待依赖
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 5
    HIGH = 7
    CRITICAL = 9
    URGENT = 10


class ExecutionMode(Enum):
    """执行模式"""
    SEQUENTIAL = "sequential"      # 串行
    PARALLEL = "parallel"          # 并行
    CONDITIONAL = "conditional"    # 条件
    FANOUT = "fanout"              # 扇出
    FANIN = "fanin"                # 扇入


@dataclass
class TaskNode:
    """任务节点"""
    task_id: str
    name: str
    task_type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 5
    timeout: int = 300
    retry_count: int = 0
    max_retries: int = 3
    required_capabilities: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    progress: float = 0.0  # 0-100


@dataclass
class Workflow:
    """工作流定义"""
    workflow_id: str
    name: str
    description: str = ""
    nodes: List[TaskNode] = field(default_factory=list)
    edges: Dict[str, List[str]] = field(default_factory=dict)  # task_id -> [dependent_task_ids]
    execution_mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    max_parallel: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    status: str = "pending"
    context: Dict[str, Any] = field(default_factory=dict)


class DAGScheduler:
    """DAG任务调度器 - 有向无环图"""
    
    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}
        self.node_map: Dict[str, TaskNode] = {}
        self.lock = threading.RLock()
        
    def add_workflow(self, workflow: Workflow) -> str:
        """添加工作流"""
        with self.lock:
            self.workflows[workflow.workflow_id] = workflow
            for node in workflow.nodes:
                self.node_map[node.task_id] = node
            return workflow.workflow_id
            
    def topological_sort(self, workflow_id: str) -> List[TaskNode]:
        """拓扑排序 - 获取任务执行顺序"""
        with self.lock:
            workflow = self.workflows.get(workflow_id)
            if not workflow:
                return []
                
            # 构建入度表
            in_degree = {node.task_id: 0 for node in workflow.nodes}
            for node in workflow.nodes:
                for dep in node.depends_on:
                    if dep in in_degree:
                        in_degree[node.task_id] += 1
                        
            # BFS拓扑排序
            queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
            sorted_nodes = []
            
            while queue:
                task_id = queue.popleft()
                sorted_nodes.append(self.node_map[task_id])
                
                # 更新依赖节点的入度
                for dependent_id in workflow.edges.get(task_id, []):
                    if dependent_id in in_degree:
                        in_degree[dependent_id] -= 1
                        if in_degree[dependent_id] == 0:
                            queue.append(dependent_id)
                            
            return sorted_nodes
            
    def get_ready_tasks(self, workflow_id: str) -> List[TaskNode]:
        """获取就绪任务(所有依赖已完成)"""
        with self.lock:
            workflow = self.workflows.get(workflow_id)
            if not workflow:
                return []
                
            ready = []
            completed_ids = {
                n.task_id for n in workflow.nodes 
                if n.status == TaskStatus.COMPLETED
            }
            
            for node in workflow.nodes:
                if node.status == TaskStatus.PENDING:
                    # 检查所有依赖是否完成
                    deps_met = all(dep in completed_ids for dep in node.depends_on)
                    if deps_met:
                        node.status = TaskStatus.READY
                        ready.append(node)
                        
            return ready
            
    def can_execute(self, task_id: str) -> bool:
        """检查任务是否可以执行"""
        with self.lock:
            node = self.node_map.get(task_id)
            if not node:
                return False
                
            if node.status not in [TaskStatus.PENDING, TaskStatus.READY]:
                return False
                
            # 检查依赖
            for dep_id in node.depends_on:
                dep_node = self.node_map.get(dep_id)
                if not dep_node or dep_node.status != TaskStatus.COMPLETED:
                    return False
                    
            return True


class CollaborationScheduler:
    """协同任务调度器"""
    
    def __init__(self, port: int = 8095):
        self.port = port
        self.dag = DAGScheduler()
        self.agent_registry: Dict[str, Dict] = {}
        self.task_queue: List[TaskNode] = []
        self.running_tasks: Dict[str, TaskNode] = {}
        self.completed_tasks: Dict[str, TaskNode] = {}
        self.failed_tasks: Dict[str, TaskNode] = {}
        self.lock = threading.RLock()
        
        # 调度策略
        self.strategies = {
            " fifo": self._strategy_fifo,
            "priority": self._strategy_priority,
            "capability": self._strategy_capability,
            "load_balance": self._strategy_load_balance
        }
        self.current_strategy = "priority"
        
    def register_agent(self, agent_id: str, capabilities: List[str] = None, 
                       capacity: int = 5) -> bool:
        """注册Agent"""
        with self.lock:
            self.agent_registry[agent_id] = {
                "agent_id": agent_id,
                "capabilities": capabilities or [],
                "capacity": capacity,
                "current_load": 0,
                "status": "idle",
                "last_heartbeat": datetime.now(),
                "metrics": {
                    "tasks_completed": 0,
                    "tasks_failed": 0,
                    "avg_response_time": 0
                }
            }
            return True
            
    def unregister_agent(self, agent_id: str) -> bool:
        """注销Agent"""
        with self.lock:
            self.agent_registry.pop(agent_id, None)
            return True
            
    def heartbeat(self, agent_id: str, metrics: Dict = None) -> bool:
        """Agent心跳"""
        with self.lock:
            if agent_id in self.agent_registry:
                self.agent_registry[agent_id]["last_heartbeat"] = datetime.now()
                if metrics:
                    self.agent_registry[agent_id]["metrics"].update(metrics)
                return True
            return False
            
    def submit_task(self, task: TaskNode) -> str:
        """提交单个任务"""
        with self.lock:
            task.status = TaskStatus.PENDING
            heapq.heappush(self.task_queue, (
                -task.priority, 
                task.created_at if hasattr(task, 'created_at') else datetime.now(),
                task
            ))
            return task.task_id
            
    def submit_workflow(self, workflow: Workflow) -> str:
        """提交工作流"""
        workflow_id = self.dag.add_workflow(workflow)
        
        # 将所有任务加入调度队列
        for node in workflow.nodes:
            self.submit_task(node)
            
        return workflow_id
        
    def schedule(self) -> Optional[tuple]:
        """调度任务到Agent"""
        with self.lock:
            if not self.task_queue or not self.agent_registry:
                return None
                
            # 使用当前策略选择任务
            strategy_func = self.strategies.get(self.current_strategy, self._strategy_priority)
            selected_task = strategy_func()
            
            if not selected_task:
                return None
                
            # 选择合适的Agent
            agent_id = self._select_agent(selected_task)
            if not agent_id:
                return None
                
            # 分配任务
            selected_task.status = TaskStatus.RUNNING
            selected_task.assigned_agent = agent_id
            selected_task.started_at = datetime.now()
            
            self.running_tasks[selected_task.task_id] = selected_task
            self.agent_registry[agent_id]["current_load"] += 1
            self.agent_registry[agent_id]["status"] = "busy"
            
            # 从队列移除 (queue中是tuple: (priority, datetime, task))
            self.task_queue = [t for t in self.task_queue if t[2].task_id != selected_task.task_id]
            
            return (selected_task, agent_id)
            
    def _strategy_fifo(self) -> Optional[TaskNode]:
        """FIFO策略"""
        if self.task_queue:
            return self.task_queue[0][2]
        return None
        
    def _strategy_priority(self) -> Optional[TaskNode]:
        """优先级策略"""
        if self.task_queue:
            # 堆顶是优先级最高的
            return self.task_queue[0][2]
        return None
        
    def _strategy_capability(self) -> Optional[TaskNode]:
        """能力匹配策略"""
        for _, _, task in self.task_queue:
            if task.required_capabilities:
                # 优先选择有匹配能力的任务
                for agent_id, info in self.agent_registry.items():
                    if any(cap in info["capabilities"] for cap in task.required_capabilities):
                        return task
        return self.task_queue[0][2] if self.task_queue else None
        
    def _strategy_load_balance(self) -> Optional[TaskNode]:
        """负载均衡策略 - 选择分配给最空闲Agent的任务"""
        if not self.task_queue:
            return None
            
        # 找到负载最低的Agent
        min_load_agent = min(
            self.agent_registry.items(),
            key=lambda x: x[1]["current_load"] / x[1]["capacity"]
        )
        
        # 优先选择该Agent有能力处理的任务
        for _, _, task in self.task_queue:
            agent_info = min_load_agent[1]
            if not task.required_capabilities:
                return task
            if any(cap in agent_info["capabilities"] for cap in task.required_capabilities):
                return task
                
        return self.task_queue[0][2]
        
    def _select_agent(self, task: TaskNode) -> Optional[str]:
        """为任务选择最佳Agent"""
        if not self.agent_registry:
            return None
            
        candidates = []
        
        for agent_id, info in self.agent_registry.items():
            # 检查容量
            if info["current_load"] >= info["capacity"]:
                continue
                
            # 检查能力匹配
            if task.required_capabilities:
                if not any(cap in info["capabilities"] for cap in task.required_capabilities):
                    continue
                    
            # 计算分数
            load_score = 1 - (info["current_load"] / info["capacity"])
            capability_score = 1.0 if not task.required_capabilities else 0.5
            
            score = load_score * 0.7 + capability_score * 0.3
            candidates.append((agent_id, score))
            
        if candidates:
            return max(candidates, key=lambda x: x[1])[0]
        return None
        
    def complete_task(self, task_id: str, success: bool, result: Dict = None) -> bool:
        """任务完成回调"""
        with self.lock:
            if task_id not in self.running_tasks:
                return False
                
            task = self.running_tasks.pop(task_id)
            
            if success:
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                task.result = result or {}
                task.progress = 100.0
                self.completed_tasks[task_id] = task
                
                # 更新Agent指标
                if task.assigned_agent:
                    agent = self.agent_registry.get(task.assigned_agent)
                    if agent:
                        agent["current_load"] = max(0, agent["current_load"] - 1)
                        agent["metrics"]["tasks_completed"] += 1
                        agent["status"] = "idle"
            else:
                task.status = TaskStatus.FAILED
                task.error = result.get("error") if result else "Unknown error"
                task.retry_count += 1
                
                if task.retry_count < task.max_retries:
                    # 重试
                    task.status = TaskStatus.PENDING
                    heapq.heappush(self.task_queue, (-task.priority, datetime.now(), task))
                else:
                    self.failed_tasks[task_id] = task
                    
            return True
            
    def get_stats(self) -> Dict:
        """获取调度器统计"""
        with self.lock:
            return {
                "queue_size": len(self.task_queue),
                "running": len(self.running_tasks),
                "completed": len(self.completed_tasks),
                "failed": len(self.failed_tasks),
                "agents": {
                    aid: {
                        "status": info["status"],
                        "load": f"{info['current_load']}/{info['capacity']}",
                        "capabilities": info["capabilities"]
                    }
                    for aid, info in self.agent_registry.items()
                },
                "strategy": self.current_strategy
            }
            
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        for task_list in [self.task_queue, self.running_tasks, 
                         self.completed_tasks, self.failed_tasks]:
            if task_id in task_list:
                task = task_list[task_id]
                return {
                    "task_id": task.task_id,
                    "name": task.name,
                    "status": task.status.value,
                    "assigned_agent": task.assigned_agent,
                    "progress": task.progress,
                    "result": task.result,
                    "error": task.error
                }
        return None


# 全局调度器实例
_scheduler = None

def get_scheduler() -> CollaborationScheduler:
    """获取全局调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = CollaborationScheduler(port=8095)
    return _scheduler


# ============ API服务 ============
def create_app():
    """创建API服务"""
    from flask import Flask, jsonify, request
    
    app = Flask(__name__)
    scheduler = get_scheduler()
    
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok", "service": "collaboration-scheduler"})
    
    @app.route("/stats", methods=["GET"])
    def stats():
        return jsonify(scheduler.get_stats())
    
    @app.route("/agents", methods=["POST"])
    def register_agent():
        data = request.json
        agent_id = data.get("agent_id")
        capabilities = data.get("capabilities", [])
        capacity = data.get("capacity", 5)
        
        scheduler.register_agent(agent_id, capabilities, capacity)
        return jsonify({"success": True, "agent_id": agent_id})
    
    @app.route("/agents/<agent_id>", methods=["DELETE"])
    def unregister_agent(agent_id):
        scheduler.unregister_agent(agent_id)
        return jsonify({"success": True})
    
    @app.route("/agents/<agent_id>/heartbeat", methods=["POST"])
    def agent_heartbeat(agent_id):
        metrics = request.json or {}
        scheduler.heartbeat(agent_id, metrics)
        return jsonify({"success": True})
    
    @app.route("/tasks", methods=["POST"])
    def submit_task():
        data = request.json
        task = TaskNode(
            task_id=data.get("task_id", f"task_{uuid.uuid4().hex[:8]}"),
            name=data.get("name", "unnamed"),
            task_type=data.get("type", "generic"),
            payload=data.get("payload", {}),
            priority=data.get("priority", 5),
            timeout=data.get("timeout", 300),
            required_capabilities=data.get("capabilities", [])
        )
        task_id = scheduler.submit_task(task)
        return jsonify({"success": True, "task_id": task_id})
    
    @app.route("/workflows", methods=["POST"])
    def submit_workflow():
        data = request.json
        nodes = [
            TaskNode(
                task_id=n.get("task_id", f"task_{i}"),
                name=n.get("name", f"node_{i}"),
                task_type=n.get("type", "generic"),
                payload=n.get("payload", {}),
                priority=n.get("priority", 5),
                depends_on=n.get("depends_on", []),
                required_capabilities=n.get("capabilities", [])
            )
            for i, n in enumerate(data.get("nodes", []))
        ]
        
        workflow = Workflow(
            workflow_id=data.get("workflow_id", f"wf_{uuid.uuid4().hex[:8]}"),
            name=data.get("name", "workflow"),
            description=data.get("description", ""),
            nodes=nodes,
            execution_mode=ExecutionMode(data.get("mode", "sequential"))
        )
        
        workflow_id = scheduler.submit_workflow(workflow)
        return jsonify({"success": True, "workflow_id": workflow_id})
    
    @app.route("/tasks/<task_id>/complete", methods=["POST"])
    def complete_task(task_id):
        data = request.json
        success = data.get("success", True)
        result = data.get("result")
        scheduler.complete_task(task_id, success, result)
        return jsonify({"success": True})
    
    @app.route("/tasks/<task_id>", methods=["GET"])
    def get_task(task_id):
        status = scheduler.get_task_status(task_id)
        if status:
            return jsonify(status)
        return jsonify({"error": "Task not found"}), 404
    
    @app.route("/schedule", methods=["POST"])
    def trigger_schedule():
        """手动触发调度"""
        result = scheduler.schedule()
        if result:
            task, agent_id = result
            return jsonify({
                "success": True,
                "task_id": task.task_id,
                "agent_id": agent_id
            })
        return jsonify({"success": False, "message": "No tasks to schedule"})
    
    @app.route("/strategy/<strategy_name>", methods=["PUT"])
    def set_strategy(strategy_name):
        if strategy_name in scheduler.strategies:
            scheduler.current_strategy = strategy_name
            return jsonify({"success": True, "strategy": strategy_name})
        return jsonify({"error": "Invalid strategy"}), 400
    
    return app


if __name__ == "__main__":
    print("🤖 Agent协同任务调度器")
    print("=" * 50)
    print(f"端口: 8095")
    print("功能:")
    print("  - 任务调度 (FIFO/优先级/能力匹配/负载均衡)")
    print("  - 工作流编排 (DAG依赖管理)")
    print("  - 多Agent协作")
    print("  - 任务重试与容错")
    print("=" * 50)
    
    # 测试调度器
    scheduler = get_scheduler()
    
    # 注册测试Agent
    print("\n📋 注册Agent:")
    scheduler.register_agent("agent-alpha", ["compute", "data"], 3)
    scheduler.register_agent("agent-beta", ["io", "network"], 2)
    scheduler.register_agent("agent-gamma", ["compute", "ml"], 4)
    
    for agent_id, info in scheduler.agent_registry.items():
        print(f"  ✓ {agent_id}: {info['capabilities']} (容量:{info['capacity']})")
    
    # 提交测试任务
    print("\n📝 提交任务:")
    tasks = [
        TaskNode(task_id="t1", name="数据处理", task_type="compute", 
                priority=7, required_capabilities=["compute"]),
        TaskNode(task_id="t2", name="网络请求", task_type="io", 
                priority=5, required_capabilities=["network"]),
        TaskNode(task_id="t3", name="ML推理", task_type="ml", 
                priority=9, required_capabilities=["ml", "compute"]),
        TaskNode(task_id="t4", name="文件IO", task_type="io", 
                priority=3, required_capabilities=["io"]),
    ]
    
    for task in tasks:
        scheduler.submit_task(task)
        print(f"  ✓ {task.name} (优先级:{task.priority})")
    
    # 执行调度
    print("\n🚀 调度任务:")
    scheduled = 0
    while True:
        result = scheduler.schedule()
        if not result:
            break
        task, agent_id = result
        print(f"  → {task.name} -> {agent_id}")
        scheduled += 1
        
        # 模拟任务完成
        scheduler.complete_task(task.task_id, True, {"result": "ok"})
        
    print(f"\n✅ 已调度 {scheduled} 个任务")
    
    # 显示统计
    print("\n📊 统计:")
    stats = scheduler.get_stats()
    print(f"  队列: {stats['queue_size']}")
    print(f"  运行: {stats['running']}")
    print(f"  完成: {stats['completed']}")
    print(f"  失败: {stats['failed']}")
    
    # 启动API服务
    print("\n🌐 启动API服务 (端口8095)...")
    app = create_app()
    app.run(host="0.0.0.0", port=8095, debug=False)