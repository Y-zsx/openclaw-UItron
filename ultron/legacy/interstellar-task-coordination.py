#!/usr/bin/env python3
"""
星际任务协调系统 (Interstellar Task Coordination)
奥创夙愿二十七第2世 - 跨星际协作核心组件

功能：
- 跨星际任务分发与调度
- 多智能体任务协调
- 任务依赖管理
- 任务状态跟踪与同步
- 故障恢复与重试机制
- 任务完成度评估
"""

import asyncio
import json
import time
import uuid
import random
import hashlib
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable, Tuple
from enum import Enum, auto
from collections import defaultdict, deque
from heapq import heappush, heappop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InterstellarTaskCoordination")


class TaskStatus(Enum):
    """任务状态"""
    PENDING = auto()         # 待处理
    DISPATCHED = auto()      # 已分发
    RUNNING = auto()         # 运行中
    WAITING = auto()         # 等待中（依赖未满足）
    COMPLETED = auto()       # 已完成
    FAILED = auto()          # 失败
    CANCELLED = auto()       # 已取消
    PAUSED = auto()          # 已暂停
    RECOVERING = auto()      # 恢复中


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 0    # 紧急
    URGENT = 1      # 紧急
    HIGH = 2        # 高
    NORMAL = 3      # 正常
    LOW = 4         # 低
    BACKGROUND = 5  # 后台


class CoordinationMode(Enum):
    """协调模式"""
    CENTRALIZED = auto()     # 集中式
    DISTRIBUTED = auto()     # 分布式
    FEDERATED = auto()       # 联邦式
    HIERARCHICAL = auto()    # 层级式


@dataclass
class TaskDependency:
    """任务依赖"""
    dependency_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    depends_on_task_id: str = ""
    dependency_type: str = "finish_to_start"  # finish_to_start, start_to_start, etc.
    satisfied: bool = False


@dataclass
class TaskExecution:
    """任务执行记录"""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str = ""
    agent_id: str = ""
    start_time: float = 0
    end_time: float = 0
    progress: float = 0  # 0-100
    status: TaskStatus = TaskStatus.PENDING
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    output: Any = None
    error: str = ""


@dataclass
class SubTask:
    """子任务"""
    subtask_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: str = ""
    progress: float = 0
    dependencies: List[str] = field(default_factory=list)
    resources_needed: Dict[str, float] = field(default_factory=dict)


@dataclass
class InterstellarCoordinationTask:
    """星际协调任务"""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    
    # 任务定义
    task_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    required_capabilities: Dict[str, float] = field(default_factory=dict)
    
    # 位置信息
    source_position: Tuple[float, float, float] = (0, 0, 0)
    target_position: Tuple[float, float, float] = (0, 0, 0)
    source_system: str = ""
    target_system: str = ""
    
    # 时间约束
    created_at: float = field(default_factory=time.time)
    scheduled_start: float = 0
    deadline: float = 0
    estimated_duration: float = 0
    actual_duration: float = 0
    
    # 依赖关系
    dependencies: List[TaskDependency] = field(default_factory=list)
    depends_on_tasks: List[str] = field(default_factory=list)
    
    # 子任务
    subtasks: List[SubTask] = field(default_factory=list)
    
    # 执行信息
    assigned_agents: List[str] = field(default_factory=list)
    execution_history: List[TaskExecution] = field(default_factory=list)
    current_execution: Optional[TaskExecution] = None
    
    # 结果
    result: Any = None
    success: bool = False
    error_message: str = ""
    
    # 约束
    max_retries: int = 3
    retry_count: int = 0
    timeout: float = 0
    
    def can_start(self, completed_tasks: Set[str]) -> bool:
        """检查是否可以开始（依赖是否满足）"""
        for dep in self.dependencies:
            if not dep.satisfied and dep.depends_on_task_id not in completed_tasks:
                return False
        return True
    
    def get_progress(self) -> float:
        """获取任务进度"""
        if not self.subtasks:
            return 100.0 if self.status == TaskStatus.COMPLETED else 0.0
        
        total_progress = sum(st.progress for st in self.subtasks)
        return total_progress / len(self.subtasks)


class TaskGraph:
    """任务依赖图"""
    
    def __init__(self):
        self.tasks: Dict[str, InterstellarCoordinationTask] = {}
        self.adjacency: Dict[str, Set[str]] = defaultdict(set)  # task -> depends on
        self.reverse_adjacency: Dict[str, Set[str]] = defaultdict(set)  # task -> dependent tasks
        
        self.lock = threading.RLock()
    
    def add_task(self, task: InterstellarCoordinationTask):
        """添加任务到图中"""
        with self.lock:
            self.tasks[task.task_id] = task
            
            # 添加依赖边
            for dep in task.dependencies:
                self.adjacency[task.task_id].add(dep.depends_on_task_id)
                self.reverse_adjacency[dep.depends_on_task_id].add(task.task_id)
    
    def remove_task(self, task_id: str):
        """移除任务"""
        with self.lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
            
            # 清理依赖边
            if task_id in self.adjacency:
                del self.adjacency[task_id]
            
            for deps in self.adjacency.values():
                deps.discard(task_id)
            
            if task_id in self.reverse_adjacency:
                del self.reverse_adjacency[task_id]
    
    def get_ready_tasks(self, completed_tasks: Set[str]) -> List[InterstellarCoordinationTask]:
        """获取就绪的任务（所有依赖都已满足）"""
        with self.lock:
            ready = []
            for task in self.tasks.values():
                if task.status != TaskStatus.PENDING:
                    continue
                
                if task.can_start(completed_tasks):
                    ready.append(task)
            
            # 按优先级排序
            ready.sort(key=lambda t: t.priority.value)
            return ready
    
    def topological_sort(self) -> List[str]:
        """拓扑排序（返回任务ID列表）"""
        with self.lock:
            in_degree = {tid: len(deps) for tid, deps in self.adjacency.items()}
            queue = [tid for tid, deg in in_degree.items() if deg == 0]
            result = []
            
            while queue:
                current = queue.pop(0)
                result.append(current)
                
                for dependent in self.reverse_adjacency.get(current, set()):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
            
            return result
    
    def find_critical_path(self, completed_tasks: Set[str]) -> List[str]:
        """查找关键路径"""
        with self.lock:
            # 简化版本：找到从就绪任务到终点的最长路径
            ready = self.get_ready_tasks(completed_tasks)
            
            if not ready:
                return []
            
            # 使用DFS找最长路径
            def dfs(task_id: str, visited: Set[str]) -> List[str]:
                if task_id in visited:
                    return []
                
                visited.add(task_id)
                dependents = self.reverse_adjacency.get(task_id, set())
                
                if not dependents:
                    return [task_id]
                
                longest = []
                for dep in dependents:
                    path = dfs(dep, visited.copy())
                    if len(path) > len(longest):
                        longest = path
                
                return [task_id] + longest
            
            critical_paths = []
            for task in ready:
                path = dfs(task.task_id, set())
                if path:
                    critical_paths.append(path)
            
            return max(critical_paths, key=len) if critical_paths else []


class TaskCoordinator:
    """任务协调器"""
    
    def __init__(self, coordinator_id: str = "main"):
        self.id = coordinator_id
        self.task_graph = TaskGraph()
        self.execution_queue: deque = deque()
        
        # 执行器接口（这里模拟）
        self.executor_registry: Dict[str, Any] = {}
        
        # 监控
        self.task_metrics: Dict[str, Dict[str, Any]] = defaultdict(dict)
        
        self.lock = threading.RLock()
    
    def create_task(self, name: str, description: str,
                   task_type: str = "generic",
                   priority: TaskPriority = TaskPriority.NORMAL,
                   deadline: float = 0,
                   source_position: Tuple[float, float, float] = (0, 0, 0),
                   target_position: Tuple[float, float, float] = (0, 0, 0),
                   payload: Dict[str, Any] = None) -> InterstellarCoordinationTask:
        """创建任务"""
        task = InterstellarCoordinationTask(
            name=name,
            description=description,
            task_type=task_type,
            priority=priority,
            deadline=deadline,
            source_position=source_position,
            target_position=target_position,
            payload=payload or {}
        )
        
        with self.lock:
            self.task_graph.add_task(task)
            self._initialize_metrics(task.task_id)
        
        logger.info(f"任务已创建: {name} (ID: {task.task_id})")
        return task
    
    def _initialize_metrics(self, task_id: str):
        """初始化任务指标"""
        self.task_metrics[task_id] = {
            "created_at": time.time(),
            "dispatched_at": 0,
            "started_at": 0,
            "completed_at": 0,
            "retries": 0,
            "status_changes": []
        }
    
    def add_dependency(self, task_id: str, depends_on_task_id: str,
                       dependency_type: str = "finish_to_start"):
        """添加任务依赖"""
        with self.lock:
            task = self.task_graph.tasks.get(task_id)
            if not task:
                logger.warning(f"任务 {task_id} 不存在")
                return False
            
            dep = TaskDependency(
                task_id=task_id,
                depends_on_task_id=depends_on_task_id,
                dependency_type=dependency_type
            )
            
            task.dependencies.append(dep)
            task.depends_on_tasks.append(depends_on_task_id)
            
            # 更新图
            self.task_graph.adjacency[task_id].add(depends_on_task_id)
            self.task_graph.reverse_adjacency[depends_on_task_id].add(task_id)
            
            return True
    
    def add_subtask(self, parent_task_id: str, name: str, description: str = "") -> Optional[SubTask]:
        """添加子任务"""
        with self.lock:
            parent = self.task_graph.tasks.get(parent_task_id)
            if not parent:
                return None
            
            subtask = SubTask(
                name=name,
                description=description
            )
            
            parent.subtasks.append(subtask)
            return subtask
    
    def dispatch_task(self, task_id: str, agent_id: str) -> bool:
        """分发任务"""
        with self.lock:
            task = self.task_graph.tasks.get(task_id)
            if not task:
                logger.warning(f"任务 {task_id} 不存在")
                return False
            
            if task.status != TaskStatus.PENDING:
                logger.warning(f"任务 {task_id} 状态不允许分发: {task.status}")
                return False
            
            # 检查依赖
            completed = set(
                tid for tid, t in self.task_graph.tasks.items()
                if t.status == TaskStatus.COMPLETED
            )
            
            if not task.can_start(completed):
                task.status = TaskStatus.WAITING
                logger.info(f"任务 {task_id} 等待依赖满足")
                return False
            
            # 分发任务
            task.status = TaskStatus.DISPATCHED
            task.assigned_agents.append(agent_id)
            
            # 创建执行记录
            execution = TaskExecution(
                task_id=task_id,
                agent_id=agent_id,
                start_time=time.time(),
                status=TaskStatus.RUNNING
            )
            task.current_execution = execution
            task.execution_history.append(execution)
            
            # 更新指标
            self.task_metrics[task_id]["dispatched_at"] = time.time()
            self.task_metrics[task_id]["status_changes"].append({
                "time": time.time(),
                "from": TaskStatus.PENDING.name,
                "to": TaskStatus.DISPATCHED.name
            })
            
            logger.info(f"任务 {task_id} 已分发到 agent {agent_id}")
            return True
    
    def update_task_progress(self, task_id: str, progress: float):
        """更新任务进度"""
        with self.lock:
            task = self.task_graph.tasks.get(task_id)
            if not task:
                return
            
            if task.current_execution:
                task.current_execution.progress = min(100, max(0, progress))
            
            # 子任务进度
            if task.subtasks:
                # 简化：所有子任务平均分配进度
                per_subtask = progress / len(task.subtasks)
                for subtask in task.subtasks:
                    subtask.progress = per_subtask
    
    def complete_task(self, task_id: str, success: bool = True, 
                     result: Any = None, error: str = ""):
        """完成任务"""
        with self.lock:
            task = self.task_graph.tasks.get(task_id)
            if not task:
                return
            
            if success:
                task.status = TaskStatus.COMPLETED
                task.success = True
                task.result = result
                task.actual_duration = time.time() - task.created_at
                
                # 更新依赖状态
                for dep in task.dependencies:
                    dep.satisfied = True
                
                # 触发依赖任务
                self._check_dependent_tasks(task_id)
                
                logger.info(f"任务 {task_id} 已完成")
            else:
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.status = TaskStatus.PENDING
                    logger.info(f"任务 {task_id} 将在 {task.retry_count} 秒后重试")
                    # 简化：立即重试
                    self.dispatch_task(task_id, task.assigned_agents[0] if task.assigned_agents else "default")
                else:
                    task.status = TaskStatus.FAILED
                    task.success = False
                    task.error_message = error
                    logger.error(f"任务 {task_id} 失败: {error}")
            
            # 更新执行记录
            if task.current_execution:
                task.current_execution.end_time = time.time()
                task.current_execution.status = task.status
                task.current_execution.progress = 100 if success else task.current_execution.progress
            
            # 更新指标
            self.task_metrics[task_id]["completed_at"] = time.time()
            self.task_metrics[task_id]["status_changes"].append({
                "time": time.time(),
                "from": "RUNNING",
                "to": task.status.name
            })
    
    def _check_dependent_tasks(self, completed_task_id: str):
        """检查依赖此任务的其他任务"""
        with self.lock:
            dependent_task_ids = self.task_graph.reverse_adjacency.get(completed_task_id, set())
            
            completed = set(
                tid for tid, t in self.task_graph.tasks.items()
                if t.status == TaskStatus.COMPLETED
            )
            
            for task_id in dependent_task_ids:
                task = self.task_graph.tasks.get(task_id)
                if task and task.status == TaskStatus.WAITING:
                    if task.can_start(completed):
                        task.status = TaskStatus.PENDING
                        logger.info(f"任务 {task_id} 现在可以执行")
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self.lock:
            task = self.task_graph.tasks.get(task_id)
            if not task:
                return False
            
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                return False
            
            task.status = TaskStatus.CANCELLED
            
            # 取消子任务
            for subtask in task.subtasks:
                subtask.status = TaskStatus.CANCELLED
            
            logger.info(f"任务 {task_id} 已取消")
            return True
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        with self.lock:
            task = self.task_graph.tasks.get(task_id)
            if not task or task.status != TaskStatus.RUNNING:
                return False
            
            task.status = TaskStatus.PAUSED
            
            if task.current_execution:
                task.current_execution.status = TaskStatus.PAUSED
            
            logger.info(f"任务 {task_id} 已暂停")
            return True
    
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        with self.lock:
            task = self.task_graph.tasks.get(task_id)
            if not task or task.status != TaskStatus.PAUSED:
                return False
            
            task.status = TaskStatus.RUNNING
            
            if task.current_execution:
                task.current_execution.status = TaskStatus.RUNNING
            
            logger.info(f"任务 {task_id} 已恢复")
            return True
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态"""
        with self.lock:
            task = self.task_graph.tasks.get(task_id)
            if not task:
                return None
            
            return {
                "task_id": task.task_id,
                "name": task.name,
                "status": task.status.name,
                "priority": task.priority.name,
                "progress": task.get_progress(),
                "assigned_agents": task.assigned_agents,
                "dependencies_satisfied": all(dep.satisfied for dep in task.dependencies),
                "subtasks_count": len(task.subtasks),
                "subtasks_completed": sum(1 for st in task.subtasks if st.status == TaskStatus.COMPLETED),
                "created_at": task.created_at,
                "actual_duration": task.actual_duration,
                "success": task.success,
                "error_message": task.error_message
            }
    
    def get_coordinator_status(self) -> Dict[str, Any]:
        """获取协调器状态"""
        with self.lock:
            tasks = list(self.task_graph.tasks.values())
            
            status_counts = defaultdict(int)
            for task in tasks:
                status_counts[task.status.name] += 1
            
            return {
                "coordinator_id": self.id,
                "total_tasks": len(tasks),
                "status_breakdown": dict(status_counts),
                "pending_tasks": status_counts[TaskStatus.PENDING.name],
                "running_tasks": status_counts[TaskStatus.RUNNING.name],
                "completed_tasks": status_counts[TaskStatus.COMPLETED.name],
                "failed_tasks": status_counts[TaskStatus.FAILED.name],
                "critical_path": self.task_graph.find_critical_path(
                    set(tid for tid, t in self.task_graph.tasks.items() if t.status == TaskStatus.COMPLETED)
                )
            }


class DistributedTaskScheduler:
    """分布式任务调度器"""
    
    def __init__(self, coordinator: TaskCoordinator):
        self.coordinator = coordinator
        self.schedule_interval = 1.0  # 秒
        self.scheduler_task: Optional[asyncio.Task] = None
        
        # 调度策略
        self.scheduling_policy = "priority"  # priority, deadline, resource, hybrid
        self.load_balancing = True
        
        self.lock = threading.RLock()
    
    async def start(self):
        """启动调度器"""
        self.scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("分布式任务调度器已启动")
    
    async def stop(self):
        """停止调度器"""
        if self.scheduler_task:
            self.scheduler_task.cancel()
            logger.info("分布式任务调度器已停止")
    
    async def _scheduler_loop(self):
        """调度循环"""
        while True:
            await asyncio.sleep(self.schedule_interval)
            await self._schedule_tasks()
    
    async def _schedule_tasks(self):
        """调度任务"""
        with self.lock:
            completed = set(
                tid for tid, t in self.coordinator.task_graph.tasks.items()
                if t.status == TaskStatus.COMPLETED
            )
            
            ready_tasks = self.coordinator.task_graph.get_ready_tasks(completed)
            
            if not ready_tasks:
                return
            
            # 根据策略排序
            if self.scheduling_policy == "priority":
                ready_tasks.sort(key=lambda t: t.priority.value)
            elif self.scheduling_policy == "deadline":
                ready_tasks.sort(key=lambda t: t.deadline if t.deadline > 0 else float('inf'))
            elif self.scheduling_policy == "resource":
                ready_tasks.sort(key=lambda t: sum(t.required_capabilities.values()), reverse=True)
            elif self.scheduling_policy == "hybrid":
                ready_tasks.sort(key=lambda t: self._hybrid_score(t))
            
            # 分发任务
            for task in ready_tasks[:5]:  # 每次最多分发5个
                if not task.assigned_agents:
                    # 模拟分配agent
                    agent_id = f"agent-{random.randint(1, 10)}"
                    self.coordinator.dispatch_task(task.task_id, agent_id)
    
    def _hybrid_score(self, task: InterstellarCoordinationTask) -> float:
        """混合评分"""
        score = task.priority.value * 10
        
        if task.deadline > 0:
            time_left = task.deadline - time.time()
            if time_left < 0:
                score += 100  # 已过期
            elif time_left < 3600:
                score += 50
        
        score += sum(task.required_capabilities.values()) * 0.1
        
        return -score  # 负数使得分数高的排在前面
    
    def set_scheduling_policy(self, policy: str):
        """设置调度策略"""
        self.scheduling_policy = policy
        logger.info(f"调度策略已设置为: {policy}")


class TaskRecoveryManager:
    """任务恢复管理器"""
    
    def __init__(self, coordinator: TaskCoordinator):
        self.coordinator = coordinator
        self.recovery_points: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.checkpoint_interval = 60  # 秒
        
        self.lock = threading.RLock()
    
    def create_checkpoint(self, task_id: str):
        """创建检查点"""
        with self.lock:
            task = self.coordinator.task_graph.tasks.get(task_id)
            if not task:
                return
            
            checkpoint = {
                "timestamp": time.time(),
                "task_id": task_id,
                "status": task.status.name,
                "progress": task.get_progress(),
                "assigned_agents": list(task.assigned_agents),
                "result": task.result,
                "current_execution": None
            }
            
            if task.current_execution:
                checkpoint["current_execution"] = {
                    "progress": task.current_execution.progress,
                    "checkpoints": list(task.current_execution.checkpoints)
                }
            
            self.recovery_points[task_id].append(checkpoint)
            
            # 限制检查点数量
            if len(self.recovery_points[task_id]) > 10:
                self.recovery_points[task_id].pop(0)
            
            logger.info(f"任务 {task_id} 检查点已创建")
    
    def recover_from_checkpoint(self, task_id: str, checkpoint_index: int = -1) -> bool:
        """从检查点恢复"""
        with self.lock:
            if task_id not in self.recovery_points:
                logger.warning(f"任务 {task_id} 没有检查点")
                return False
            
            checkpoints = self.recovery_points[task_id]
            if not checkpoints:
                return False
            
            checkpoint = checkpoints[checkpoint_index]
            
            task = self.coordinator.task_graph.tasks.get(task_id)
            if not task:
                return False
            
            # 恢复任务状态
            task.status = TaskStatus.RECOVERING
            task.assigned_agents = checkpoint["assigned_agents"]
            task.result = checkpoint.get("result")
            
            # 恢复执行进度
            if checkpoint.get("current_execution"):
                if task.current_execution:
                    task.current_execution.progress = checkpoint["current_execution"]["progress"]
                    task.current_execution.checkpoints = checkpoint["current_execution"]["checkpoints"]
            
            # 重新分发任务
            if task.assigned_agents:
                agent_id = task.assigned_agents[0]
                self.coordinator.dispatch_task(task_id, agent_id)
            
            task.status = TaskStatus.RUNNING
            
            logger.info(f"任务 {task_id} 已从检查点恢复")
            return True
    
    def auto_recover_failed_tasks(self):
        """自动恢复失败任务"""
        with self.lock:
            failed_tasks = [
                t for t in self.coordinator.task_graph.tasks.values()
                if t.status == TaskStatus.FAILED and t.retry_count < t.max_retries
            ]
            
            for task in failed_tasks:
                logger.info(f"自动恢复任务: {task.task_id}")
                task.status = TaskStatus.PENDING
                task.retry_count += 1


class CrossSystemCoordination:
    """跨系统任务协调"""
    
    def __init__(self, coordinator: TaskCoordinator):
        self.coordinator = coordinator
        self.remote_systems: Dict[str, Any] = {}
        
        self.lock = threading.RLock()
    
    def register_remote_system(self, system_id: str, endpoint: str):
        """注册远程系统"""
        with self.lock:
            self.remote_systems[system_id] = {
                "endpoint": endpoint,
                "registered_at": time.time(),
                "status": "active"
            }
            logger.info(f"远程系统 {system_id} 已注册")
    
    def delegate_task(self, task_id: str, target_system: str) -> bool:
        """委托任务到远程系统"""
        with self.lock:
            task = self.coordinator.task_graph.tasks.get(task_id)
            if not task:
                return False
            
            if target_system not in self.remote_systems:
                logger.warning(f"远程系统 {target_system} 不存在")
                return False
            
            # 模拟任务委托
            logger.info(f"任务 {task_id} 已委托到远程系统 {target_system}")
            
            # 远程系统会处理任务完成回调
            return True
    
    def sync_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """同步任务状态"""
        with self.lock:
            task = self.coordinator.task_graph.tasks.get(task_id)
            if not task:
                return None
            
            # 简化：返回本地状态
            return self.coordinator.get_task_status(task_id)


# 演示代码
def demo():
    """演示星际任务协调系统"""
    logger.info("=" * 60)
    logger.info("星际任务协调系统演示")
    logger.info("=" * 60)
    
    # 创建任务协调器
    coordinator = TaskCoordinator("alpha-centauri-coordinator")
    scheduler = DistributedTaskScheduler(coordinator)
    recovery = TaskRecoveryManager(coordinator)
    cross_system = CrossSystemCoordination(coordinator)
    
    # 创建任务
    task1 = coordinator.create_task(
        name="星际探测",
        description="探测未知星域",
        task_type="exploration",
        priority=TaskPriority.HIGH,
        deadline=time.time() + 86400,
        source_position=(0, 0, 0),
        target_position=(10, 10, 5),
        payload={"target": "unknown-region", "sensors": ["spectrometer", "imager"]}
    )
    
    task2 = coordinator.create_task(
        name="数据分析",
        description="分析探测数据",
        task_type="analysis",
        priority=TaskPriority.NORMAL,
        source_position=(10, 10, 5),
        payload={"data_source": "task-1", "algorithms": ["ML", "statistical"]}
    )
    
    task3 = coordinator.create_task(
        name="资源采集",
        description="采集星际资源",
        task_type="resource_gathering",
        priority=TaskPriority.LOW,
        target_position=(8, 8, 4),
        payload={"resource_type": "hydrogen", "amount": 1000}
    )
    
    # 添加依赖关系
    coordinator.add_dependency(task2.task_id, task1.task_id)
    
    # 添加子任务
    coordinator.add_subtask(task1.task_id, "扫描星域", "执行全面扫描")
    coordinator.add_subtask(task1.task_id, "收集数据", "收集传感器数据")
    coordinator.add_subtask(task1.task_id, "分析结果", "初步分析数据")
    
    # 分发任务
    coordinator.dispatch_task(task1.task_id, "agent-001")
    coordinator.dispatch_task(task3.task_id, "agent-002")
    
    # 模拟任务执行和进度
    coordinator.update_task_progress(task1.task_id, 50.0)
    
    # 创建检查点
    recovery.create_checkpoint(task1.task_id)
    
    # 完成子任务
    if task1.subtasks:
        task1.subtasks[0].status = TaskStatus.COMPLETED
        task1.subtasks[0].progress = 100
        task1.subtasks[1].status = TaskStatus.COMPLETED
        task1.subtasks[1].progress = 100
    
    # 完成主任务
    coordinator.update_task_progress(task1.task_id, 100.0)
    coordinator.complete_task(task1.task_id, success=True, result={"data_size": "1TB"})
    
    # 依赖任务现在应该可以执行
    logger.info("\n等待执行的任务:")
    completed = {task1.task_id}
    ready_tasks = coordinator.task_graph.get_ready_tasks(completed)
    for rt in ready_tasks:
        logger.info(f"  - {rt.name} (ID: {rt.task_id})")
    
    # 分发就绪任务
    for rt in ready_tasks:
        coordinator.dispatch_task(rt.task_id, "agent-003")
        coordinator.complete_task(rt.task_id, success=True)
    
    # 跨系统协调演示
    cross_system.register_remote_system("proxima", "grpc://proxima:50051")
    cross_system.register_remote_system("sirius", "grpc://sirius:50051")
    
    # 状态报告
    status = coordinator.get_coordinator_status()
    logger.info(f"\n协调器状态: {json.dumps(status, indent=2, default=str)}")
    
    logger.info("=" * 60)
    logger.info("演示完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    demo()