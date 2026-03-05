#!/usr/bin/env python3
"""
全智能系统协同平台 - 统一调度与智能协作框架
Unified Scheduling and Intelligent Collaboration Framework
第1世：统一调度与智能协作

功能：
1. 统一调度 - 跨系统任务协调
2. 智能协作 - 多组件协同工作
"""

import json
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """任务优先级"""
    CRITICAL = 1  # 关键任务
    HIGH = 2      # 高优先级
    NORMAL = 3    # 普通任务
    LOW = 4       # 低优先级
    IDLE = 5      # 空闲任务


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ComponentType(Enum):
    """组件类型"""
    EXECUTOR = "executor"           # 执行器
    MONITOR = "monitor"             # 监控器
    ANALYZER = "analyzer"           # 分析器
    ORCHESTRATOR = "orchestrator"   # 编排器
    DECISION = "decision"           # 决策器
    COMMUNICATION = "communication" # 通信器


@dataclass
class Task:
    """任务定义"""
    id: str
    name: str
    description: str
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    handler: Optional[Callable] = None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    timeout: int = 300
    retry_count: int = 0
    max_retries: int = 3
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "timeout": self.timeout,
            "retry_count": self.retry_count,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": str(self.result)[:200] if self.result else None,
            "error": self.error,
            "metadata": self.metadata
        }


@dataclass
class Component:
    """系统组件"""
    id: str
    name: str
    type: ComponentType
    status: str = "idle"  # idle, busy, offline, error
    capacity: int = 10    # 并发处理能力
    current_load: int = 0
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    last_heartbeat: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def can_accept_task(self) -> bool:
        return self.status == "idle" and self.current_load < self.capacity
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "status": self.status,
            "capacity": self.capacity,
            "current_load": self.current_load,
            "capabilities": self.capabilities,
            "last_heartbeat": self.last_heartbeat
        }


class UnifiedScheduler:
    """
    统一调度器
    负责跨系统任务协调、智能资源分配、负载均衡
    """
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.components: Dict[str, Component] = {}
        self.task_queue: List[str] = []  # 优先级队列
        self.running_tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        self.failed_tasks: Dict[str, Task] = {}
        
        # 协作调度器
        self.collaboration_engine = None
        
        # 统计信息
        self.stats = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "active_components": 0,
            "total_execution_time": 0.0
        }
        
        # 调度配置
        self.config = {
            "max_concurrent_tasks": 50,
            "task_timeout_default": 300,
            "heartbeat_interval": 30,
            "load_balance_strategy": "adaptive",  # adaptive, round_robin, least_loaded
            "retry_strategy": "exponential",     # exponential, linear
            "priority_weight": {
                "critical": 1.0,
                "high": 0.7,
                "normal": 0.5,
                "low": 0.3,
                "idle": 0.1
            }
        }
        
        # 事件回调
        self.event_handlers = defaultdict(list)
        
        # 调度锁
        self._lock = threading.RLock()
        
        logger.info("🧠 统一调度器初始化完成")
    
    def register_component(self, component: Component) -> bool:
        """注册系统组件"""
        with self._lock:
            self.components[component.id] = component
            self.stats["active_components"] = len(self.components)
            self._emit_event("component_registered", component.to_dict())
            logger.info(f"✅ 组件注册: {component.name} ({component.type.value})")
            return True
    
    def unregister_component(self, component_id: str) -> bool:
        """注销组件"""
        with self._lock:
            if component_id in self.components:
                component = self.components.pop(component_id)
                self.stats["active_components"] = len(self.components)
                self._emit_event("component_unregistered", {"id": component_id})
                logger.info(f"🗑️ 组件注销: {component_id}")
                return True
            return False
    
    def submit_task(self, task: Task) -> str:
        """提交任务到调度器"""
        with self._lock:
            self.tasks[task.id] = task
            self.task_queue.append(task.id)
            self.stats["total_tasks"] += 1
            
            # 根据优先级排序
            self._sort_queue()
            
            self._emit_event("task_submitted", task.to_dict())
            logger.info(f"📝 任务提交: {task.name} (优先级: {task.priority.name})")
            
            return task.id
    
    def _sort_queue(self):
        """根据优先级排序任务队列"""
        def get_priority(task_id: str) -> float:
            task = self.tasks.get(task_id)
            if not task:
                return 0.5
            weight = self.config["priority_weight"].get(task.priority.name.lower(), 0.5)
            # 等待时间加成
            wait_time = (datetime.now() - datetime.fromisoformat(task.created_at)).total_seconds()
            return weight + (wait_time / 1000)  # 等待越久，优先级略高
        
        self.task_queue.sort(key=get_priority, reverse=True)
    
    def _get_ready_tasks(self) -> List[Task]:
        """获取就绪任务（所有依赖已满足）"""
        ready = []
        for task_id in self.task_queue:
            task = self.tasks.get(task_id)
            if not task or task.status != TaskStatus.PENDING:
                continue
            
            # 检查依赖
            deps_ready = all(
                dep_id in self.completed_tasks 
                for dep_id in task.dependencies
            )
            
            if deps_ready:
                ready.append(task)
        
        return ready
    
    def _select_best_component(self, task: Task) -> Optional[Component]:
        """选择最佳执行组件"""
        strategy = self.config["load_balance_strategy"]
        
        # 筛选可用的组件
        available = [
            c for c in self.components.values() 
            if c.can_accept_task()
        ]
        
        if not available:
            return None
        
        if strategy == "least_loaded":
            # 选择负载最低的
            return min(available, key=lambda c: c.current_load / c.capacity)
        elif strategy == "round_robin":
            # 轮询选择
            idx = self.stats["completed_tasks"] % len(available)
            return available[idx]
        else:
            # 自适应选择 - 考虑任务类型和组件能力
            return self._adaptive_select(available, task)
    
    def _adaptive_select(self, components: List[Component], task: Task) -> Component:
        """自适应组件选择"""
        # 简单实现：优先选择匹配任务类型的组件
        task_capabilities = task.metadata.get("required_capabilities", [])
        
        if task_capabilities:
            for comp in components:
                if any(cap in comp.capabilities for cap in task_capabilities):
                    return comp
        
        # 默认选择负载最低的
        return min(components, key=lambda c: c.current_load / c.capacity)
    
    def dispatch_task(self, task_id: str) -> bool:
        """分发任务到指定组件"""
        with self._lock:
            task = self.tasks.get(task_id)
            if not task or task.status != TaskStatus.PENDING:
                return False
            
            component = self._select_best_component(task)
            if not component:
                logger.warning(f"⚠️ 无可用组件: {task.name}")
                return False
            
            # 更新状态
            task.status = TaskStatus.READY
            component.current_load += 1
            component.status = "busy"
            self.running_tasks[task_id] = task
            
            # 异步执行
            threading.Thread(
                target=self._execute_task,
                args=(task_id, component.id),
                daemon=True
            ).start()
            
            self._emit_event("task_dispatched", {
                "task": task.to_dict(),
                "component": component.to_dict()
            })
            
            logger.info(f"🚀 任务分发: {task.name} -> {component.name}")
            return True
    
    def _execute_task(self, task_id: str, component_id: str):
        """执行任务"""
        task = self.tasks.get(task_id)
        component = self.components.get(component_id)
        
        if not task or not component:
            return
        
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.now().isoformat()
            
            logger.info(f"▶️ 执行任务: {task.name}")
            
            # 执行任务
            if task.handler:
                result = task.handler(*task.args, **task.kwargs)
                task.result = result
            else:
                # 默认模拟执行
                time.sleep(min(task.timeout / 10, 1))
                task.result = "completed"
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            
            # 移动到完成队列
            self.completed_tasks[task_id] = task
            self.stats["completed_tasks"] += 1
            
            self._emit_event("task_completed", task.to_dict())
            logger.info(f"✅ 任务完成: {task.name}")
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.now().isoformat()
            self.failed_tasks[task_id] = task
            self.stats["failed_tasks"] += 1
            
            self._emit_event("task_failed", task.to_dict())
            logger.error(f"❌ 任务失败: {task.name} - {e}")
            
        finally:
            # 清理
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            if task_id in self.task_queue:
                self.task_queue.remove(task_id)
            
            if component:
                component.current_load = max(0, component.current_load - 1)
                component.status = "idle"
                component.last_heartbeat = datetime.now().isoformat()
    
    def start_dispatch_loop(self):
        """启动任务分发循环"""
        def loop():
            while True:
                try:
                    ready_tasks = self._get_ready_tasks()
                    for task in ready_tasks:
                        self.dispatch_task(task.id)
                    
                    time.sleep(1)
                except Exception as e:
                    logger.error(f"调度循环错误: {e}")
        
        threading.Thread(target=loop, daemon=True).start()
        logger.info("🔄 任务分发循环已启动")
    
    def _emit_event(self, event_type: str, data: Dict):
        """触发事件"""
        for handler in self.event_handlers[event_type]:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"事件处理错误: {e}")
    
    def on(self, event_type: str, handler: Callable):
        """注册事件处理"""
        self.event_handlers[event_type].append(handler)
    
    def get_status(self) -> Dict:
        """获取调度器状态"""
        return {
            "total_tasks": self.stats["total_tasks"],
            "pending_tasks": len(self.task_queue),
            "running_tasks": len(self.running_tasks),
            "completed_tasks": self.stats["completed_tasks"],
            "failed_tasks": self.stats["failed_tasks"],
            "active_components": len(self.components),
            "components": [c.to_dict() for c in self.components.values()]
        }
    
    def get_task_info(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        task = self.tasks.get(task_id)
        if task:
            return task.to_dict()
        return None
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            task = self.tasks.get(task_id)
            if task and task.status in [TaskStatus.PENDING, TaskStatus.READY]:
                task.status = TaskStatus.CANCELLED
                if task_id in self.task_queue:
                    self.task_queue.remove(task_id)
                self._emit_event("task_cancelled", task.to_dict())
                logger.info(f"🚫 任务已取消: {task.name}")
                return True
            return False
    
    def retry_failed_task(self, task_id: str) -> bool:
        """重试失败任务"""
        with self._lock:
            task = self.failed_tasks.get(task_id)
            if not task:
                return False
            
            if task.retry_count >= task.max_retries:
                logger.warning(f"任务重试次数超限: {task.name}")
                return False
            
            # 重置任务
            task.status = TaskStatus.PENDING
            task.retry_count += 1
            task.error = None
            task.completed_at = None
            self.task_queue.append(task.id)
            del self.failed_tasks[task_id]
            
            self._emit_event("task_retried", task.to_dict())
            logger.info(f"🔄 任务重试: {task.name} (第{task.retry_count}次)")
            return True


class IntelligentCollaboration:
    """
    智能协作引擎
    负责多组件协同工作、消息传递、状态同步
    """
    
    def __init__(self, scheduler: UnifiedScheduler):
        self.scheduler = scheduler
        self.message_bus: Dict[str, List[Dict]] = defaultdict(list)
        self.collaboration_sessions: Dict[str, Dict] = {}
        self.component_relations: Dict[str, List[str]] = defaultdict(list)
        self.shared_state: Dict[str, Any] = {}
        
        # 协作模式
        self.collaboration_modes = {
            "pipeline": self._pipeline_collaborate,
            "parallel": self._parallel_collaborate,
            "hierarchical": self._hierarchical_collaborate,
            "dynamic": self._dynamic_collaborate
        }
        
        # 状态同步间隔
        self.sync_interval = 2
        
        logger.info("🤝 智能协作引擎初始化完成")
    
    def create_session(self, session_id: str, participants: List[str], mode: str = "dynamic") -> bool:
        """创建协作会话"""
        with self.scheduler._lock:
            self.collaboration_sessions[session_id] = {
                "id": session_id,
                "participants": participants,
                "mode": mode,
                "created_at": datetime.now().isoformat(),
                "status": "active",
                "message_count": 0,
                "shared_data": {}
            }
            
            # 建立组件关联
            for i, comp_id in enumerate(participants):
                if i > 0:
                    self.component_relations[comp_id].append(participants[i-1])
            
            logger.info(f"🎯 协作会话创建: {session_id} (模式: {mode})")
            return True
    
    def send_message(self, session_id: str, sender: str, content: Any, msg_type: str = "data") -> bool:
        """发送协作消息"""
        session = self.collaboration_sessions.get(session_id)
        if not session:
            logger.warning(f"会话不存在: {session_id}")
            return False
        
        message = {
            "id": f"msg_{len(self.message_bus[session_id])}_{int(time.time())}",
            "sender": sender,
            "content": content,
            "type": msg_type,
            "timestamp": datetime.now().isoformat()
        }
        
        self.message_bus[session_id].append(message)
        session["message_count"] += 1
        
        # 更新共享状态
        if isinstance(content, dict) and content.get("type") == "state_update":
            self.shared_state.update(content.get("data", {}))
        
        # 触发消息处理
        self._process_message(session_id, message)
        
        logger.debug(f"📨 消息: {sender} -> {session_id}")
        return True
    
    def _process_message(self, session_id: str, message: Dict):
        """处理协作消息"""
        content = message.get("content", {})
        
        # 根据消息类型处理
        if isinstance(content, dict):
            msg_type = content.get("type", "data")
            
            if msg_type == "task_request":
                # 任务请求
                self._handle_task_request(session_id, content)
            elif msg_type == "state_sync":
                # 状态同步
                self._handle_state_sync(session_id, content)
            elif msg_type == "result_share":
                # 结果共享
                self._handle_result_share(session_id, content)
    
    def _handle_task_request(self, session_id: str, content: Dict):
        """处理任务请求"""
        session = self.collaboration_sessions.get(session_id)
        if not session:
            return
        
        # 创建新任务
        task = Task(
            id=content.get("task_id", f"task_{int(time.time())}"),
            name=content.get("name", "协作任务"),
            description=content.get("description", ""),
            priority=TaskPriority[content.get("priority", "NORMAL")],
            metadata=content.get("metadata", {})
        )
        
        self.scheduler.submit_task(task)
    
    def _handle_state_sync(self, session_id: str, content: Dict):
        """处理状态同步"""
        self.shared_state.update(content.get("data", {}))
    
    def _handle_result_share(self, session_id: str, content: Dict):
        """处理结果共享"""
        session = self.collaboration_sessions.get(session_id)
        if session:
            session["shared_data"].update(content.get("data", {}))
    
    def broadcast_state(self, component_id: str, state: Dict):
        """广播组件状态"""
        for session_id, session in self.collaboration_sessions.items():
            if component_id in session["participants"]:
                self.send_message(
                    session_id,
                    component_id,
                    {"type": "state_update", "data": state},
                    "state"
                )
    
    def _pipeline_collaborate(self, session: Dict) -> List[Task]:
        """管道协作模式：顺序执行"""
        tasks = []
        for i, participant in enumerate(session["participants"]):
            task = Task(
                id=f"pipeline_{session['id']}_{i}",
                name=f"管道任务-{i+1}",
                description=f"管道阶段 {i+1}",
                dependencies=[tasks[-1].id] if tasks else [],
                metadata={"session_id": session["id"], "stage": i}
            )
            tasks.append(task)
        return tasks
    
    def _parallel_collaborate(self, session: Dict) -> List[Task]:
        """并行协作模式：同时执行"""
        tasks = []
        for i, participant in enumerate(session["participants"]):
            task = Task(
                id=f"parallel_{session['id']}_{i}",
                name=f"并行任务-{i+1}",
                description=f"并行执行 {i+1}",
                metadata={"session_id": session["id"], "parallel": True}
            )
            tasks.append(task)
        return tasks
    
    def _hierarchical_collaborate(self, session: Dict) -> List[Task]:
        """层级协作模式：主从执行"""
        tasks = []
        participants = session["participants"]
        
        # 第一个是协调者
        coordinator = Task(
            id=f"hierarchical_{session['id']}_coordinator",
            name="协调者任务",
            description="层级协调",
            metadata={"session_id": session["id"], "role": "coordinator"}
        )
        tasks.append(coordinator)
        
        # 其他是执行者
        for i in range(1, len(participants)):
            task = Task(
                id=f"hierarchical_{session['id']}_{i}",
                name=f"执行者任务-{i}",
                description="层级执行",
                dependencies=[coordinator.id],
                metadata={"session_id": session["id"], "role": "executor"}
            )
            tasks.append(task)
        
        return tasks
    
    def _dynamic_collaborate(self, session: Dict) -> List[Task]:
        """动态协作模式：自适应执行"""
        # 根据当前系统状态动态决定
        tasks = []
        status = self.scheduler.get_status()
        
        # 如果负载低，使用并行
        if status["running_tasks"] < 10:
            return self._parallel_collaborate(session)
        # 如果负载高，使用管道
        else:
            return self._pipeline_collaborate(session)
    
    def start_collaboration(self, session_id: str) -> bool:
        """启动协作会话"""
        session = self.collaboration_sessions.get(session_id)
        if not session:
            return False
        
        mode = session["mode"]
        collaborate_func = self.collaboration_modes.get(mode, self._dynamic_collaborate)
        
        tasks = collaborate_func(session)
        
        for task in tasks:
            self.scheduler.submit_task(task)
        
        logger.info(f"🚀 协作会话启动: {session_id} (生成{len(tasks)}个任务)")
        return True
    
    def get_session_status(self, session_id: str) -> Optional[Dict]:
        """获取会话状态"""
        session = self.collaboration_sessions.get(session_id)
        if not session:
            return None
        
        messages = self.message_bus.get(session_id, [])
        
        return {
            "id": session["id"],
            "participants": session["participants"],
            "mode": session["mode"],
            "status": session["status"],
            "message_count": len(messages),
            "shared_data": session["shared_data"]
        }
    
    def close_session(self, session_id: str) -> bool:
        """关闭协作会话"""
        if session_id in self.collaboration_sessions:
            session = self.collaboration_sessions.pop(session_id)
            logger.info(f"👋 协作会话关闭: {session_id}")
            return True
        return False


class CollaborationOrchestrator:
    """
    协作编排器
    协调多个组件完成复杂任务
    """
    
    def __init__(self):
        self.scheduler = UnifiedScheduler()
        self.collaboration = IntelligentCollaboration(self.scheduler)
        self.task_templates: Dict[str, Task] = {}
        
        # 启动分发循环
        self.scheduler.start_dispatch_loop()
        
        logger.info("🎼 协作编排器初始化完成")
    
    def register_system_components(self):
        """注册系统组件"""
        components = [
            Component("exec-1", "执行器1", ComponentType.EXECUTOR, capacity=20, 
                     capabilities=["execute", "run", "process"]),
            Component("exec-2", "执行器2", ComponentType.EXECUTOR, capacity=15,
                     capabilities=["execute", "run"]),
            Component("monitor-1", "监控器", ComponentType.MONITOR, capacity=30,
                     capabilities=["monitor", "watch", "alert"]),
            Component("analyzer-1", "分析器", ComponentType.ANALYZER, capacity=10,
                     capabilities=["analyze", "evaluate", "predict"]),
            Component("orch-1", "编排器", ComponentType.ORCHESTRATOR, capacity=50,
                     capabilities=["orchestrate", "coordinate", "schedule"]),
        ]
        
        for comp in components:
            self.scheduler.register_component(comp)
        
        return len(components)
    
    def create_workflow(self, name: str, steps: List[Dict]) -> str:
        """创建工作流"""
        workflow_id = f"workflow_{int(time.time())}"
        
        # 注册组件
        self.register_system_components()
        
        # 创建协作会话
        session_id = f"session_{workflow_id}"
        participants = [step["component"] for step in steps]
        
        self.collaboration.create_session(
            session_id,
            participants,
            mode="dynamic"
        )
        
        # 提交工作流任务
        for i, step in enumerate(steps):
            task = Task(
                id=f"{workflow_id}_step_{i}",
                name=step.get("name", f"步骤{i+1}"),
                description=step.get("description", ""),
                priority=TaskPriority[step.get("priority", "NORMAL")],
                metadata={
                    "workflow_id": workflow_id,
                    "session_id": session_id,
                    "step": i
                }
            )
            self.scheduler.submit_task(task)
        
        logger.info(f"📋 工作流创建: {name} ({len(steps)}步骤)")
        return workflow_id
    
    def get_full_status(self) -> Dict:
        """获取完整状态"""
        return {
            "scheduler": self.scheduler.get_status(),
            "collaboration": {
                "sessions": len(self.collaboration.collaboration_sessions),
                "messages": sum(len(m) for m in self.collaboration.message_bus.values())
            },
            "timestamp": datetime.now().isoformat()
        }


# ========== 主程序 ==========
if __name__ == "__main__":
    print("=" * 50)
    print("🦞 奥创 - 统一调度与智能协作框架")
    print("第1世：统一调度与智能协作")
    print("=" * 50)
    
    # 创建协作编排器
    orchestrator = CollaborationOrchestrator()
    
    # 注册组件
    comp_count = orchestrator.register_system_components()
    print(f"✅ 已注册 {comp_count} 个系统组件")
    
    # 创建示例工作流
    workflow_id = orchestrator.create_workflow("智能协作工作流", [
        {"name": "数据采集", "component": "monitor-1", "priority": "HIGH"},
        {"name": "数据分析", "component": "analyzer-1", "priority": "NORMAL"},
        {"name": "任务执行", "component": "exec-1", "priority": "HIGH"},
        {"name": "结果处理", "component": "orch-1", "priority": "NORMAL"},
    ])
    
    print(f"✅ 工作流已创建: {workflow_id}")
    
    # 等待执行
    time.sleep(5)
    
    # 获取状态
    status = orchestrator.get_full_status()
    print("\n📊 系统状态:")
    print(f"  活跃组件: {status['scheduler']['active_components']}")
    print(f"  总任务数: {status['scheduler']['total_tasks']}")
    print(f"  完成任务: {status['scheduler']['completed_tasks']}")
    print(f"  失败任务: {status['scheduler']['failed_tasks']}")
    print(f"  协作会话: {status['collaboration']['sessions']}")
    
    print("\n🦞 第1世完成：统一调度与智能协作框架")