#!/usr/bin/env python3
"""
奥创跨系统工作流编排器 v2 - 跨系统工作流编排
Cross-System Workflow Orchestrator v2

功能:
- 工作流模板引擎
- 跨系统任务调度
- 状态同步机制
"""

import json
import asyncio
import time
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    WAITING = "waiting"


class TaskType(Enum):
    """任务类型"""
    SYSTEM_CHECK = "system_check"
    DATA_COLLECT = "data_collect"
    ALERT = "alert"
    AUTO_FIX = "auto_fix"
    REPORT = "report"
    CUSTOM = "custom"


@dataclass
class Task:
    """任务定义"""
    id: str
    name: str
    task_type: TaskType
    target_system: str
    command: str
    params: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 60
    retry: int = 0
    max_retries: int = 3
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    depends_on: List[str] = field(default_factory=list)


@dataclass
class Workflow:
    """工作流定义"""
    id: str
    name: str
    description: str
    tasks: List[Task]
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict] = None


@dataclass
class WorkflowTemplate:
    """工作流模板"""
    id: str
    name: str
    description: str
    category: str
    tasks: List[Dict[str, Any]]
    parameters: Dict[str, Any] = field(default_factory=dict)


class TaskExecutor:
    """任务执行器"""
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._lock = threading.Lock()
    
    async def execute(self, task: Task) -> Task:
        """执行任务"""
        async with self.semaphore:
            task.status = TaskStatus.RUNNING
            task.started_at = time.time()
            
            try:
                # 模拟任务执行
                result = await self._run_command(task)
                task.status = TaskStatus.SUCCESS
                task.result = result
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                
                # 重试逻辑
                if task.retry < task.max_retries:
                    task.retry += 1
                    task.status = TaskStatus.PENDING
                    return await self.execute(task)
            finally:
                task.completed_at = time.time()
            
            return task
    
    async def _run_command(self, task: Task) -> Any:
        """运行命令"""
        # 模拟不同类型任务的执行
        if task.task_type == TaskType.SYSTEM_CHECK:
            await asyncio.sleep(0.5)
            return {
                "status": "healthy",
                "cpu": 20.5,
                "memory": 45.2,
                "disk": 35.8
            }
        elif task.task_type == TaskType.DATA_COLLECT:
            await asyncio.sleep(0.3)
            return {
                "collected": True,
                "records": 100,
                "timestamp": datetime.now().isoformat()
            }
        elif task.task_type == TaskType.ALERT:
            await asyncio.sleep(0.1)
            return {"sent": True, "channel": "dingtalk"}
        elif task.task_type == TaskType.AUTO_FIX:
            await asyncio.sleep(1.0)
            return {"fixed": True, "actions": ["restart_service", "clear_cache"]}
        else:
            await asyncio.sleep(0.5)
            return {"completed": True}


class WorkflowEngine:
    """工作流引擎"""
    
    def __init__(self, max_concurrent: int = 3):
        self.executor = TaskExecutor(max_concurrent=max_concurrent * 2)
        self.workflows: Dict[str, Workflow] = {}
        self.task_results: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._running = False
    
    def create_workflow(self, name: str, description: str, tasks: List[Task]) -> Workflow:
        """创建工作流"""
        workflow = Workflow(
            id=str(uuid.uuid4())[:8],
            name=name,
            description=description,
            tasks=tasks
        )
        with self._lock:
            self.workflows[workflow.id] = workflow
        return workflow
    
    async def run_workflow(self, workflow_id: str) -> Workflow:
        """运行工作流"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow.status = "running"
        workflow.started_at = time.time()
        
        # 构建依赖图
        task_map = {task.id: task for task in workflow.tasks}
        completed = set()
        
        while len(completed) < len(workflow.tasks):
            # 找到所有可执行的任务（依赖都已完成）
            ready_tasks = [
                task for task in workflow.tasks
                if task.id not in completed
                and all(dep in completed for dep in task.depends_on)
                and task.status in [TaskStatus.PENDING, TaskStatus.WAITING]
            ]
            
            if not ready_tasks:
                # 检查是否有失败的任务
                failed = [t for t in workflow.tasks if t.status == TaskStatus.FAILED]
                if failed:
                    workflow.status = "failed"
                    break
                await asyncio.sleep(0.1)
                continue
            
            # 并行执行准备好的任务
            results = await asyncio.gather(
                *[self.executor.execute(task) for task in ready_tasks],
                return_exceptions=True
            )
            
            # 记录结果
            for task, result in zip(ready_tasks, results):
                if isinstance(result, Exception):
                    task.status = TaskStatus.FAILED
                    task.error = str(result)
                else:
                    self.task_results[task.id] = task.result
                    completed.add(task.id)
        
        # 工作流完成
        workflow.completed_at = time.time()
        if all(t.status == TaskStatus.SUCCESS for t in workflow.tasks):
            workflow.status = "success"
            workflow.result = {
                "total_tasks": len(workflow.tasks),
                "successful": sum(1 for t in workflow.tasks if t.status == TaskStatus.SUCCESS),
                "failed": sum(1 for t in workflow.tasks if t.status == TaskStatus.FAILED),
                "duration": workflow.completed_at - workflow.started_at
            }
        else:
            workflow.status = "failed"
        
        return workflow
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict]:
        """获取工作流状态"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return None
        
        return {
            "id": workflow.id,
            "name": workflow.name,
            "status": workflow.status,
            "tasks": [
                {
                    "id": t.id,
                    "name": t.name,
                    "status": t.status.value,
                    "result": t.result,
                    "error": t.error
                }
                for t in workflow.tasks
            ],
            "created_at": workflow.created_at,
            "started_at": workflow.started_at,
            "completed_at": workflow.completed_at,
            "duration": workflow.completed_at - workflow.started_at if workflow.completed_at and workflow.started_at else None
        }


class WorkflowTemplateEngine:
    """工作流模板引擎"""
    
    def __init__(self):
        self.templates: Dict[str, WorkflowTemplate] = {}
        self._register_default_templates()
    
    def _register_default_templates(self):
        """注册默认模板"""
        # 系统健康检查工作流
        self.register_template(WorkflowTemplate(
            id="sys-health-check",
            name="系统健康检查",
            description="执行全面的系统健康检查",
            category="monitoring",
            tasks=[
                {"id": "check1", "name": "CPU检查", "type": TaskType.SYSTEM_CHECK, "target": "server", "command": "check_cpu"},
                {"id": "check2", "name": "内存检查", "type": TaskType.SYSTEM_CHECK, "target": "server", "command": "check_memory"},
                {"id": "check3", "name": "磁盘检查", "type": TaskType.SYSTEM_CHECK, "target": "server", "command": "check_disk"},
            ]
        ))
        
        # 数据采集工作流
        self.register_template(WorkflowTemplate(
            id="data-collect",
            name="数据采集",
            description="从多个系统采集数据",
            category="data",
            tasks=[
                {"id": "collect1", "name": "采集OpenClaw数据", "type": TaskType.DATA_COLLECT, "target": "openclaw", "command": "collect_metrics"},
                {"id": "collect2", "name": "采集服务器数据", "type": TaskType.DATA_COLLECT, "target": "server", "command": "collect_metrics"},
                {"id": "collect3", "name": "采集Docker数据", "type": TaskType.DATA_COLLECT, "target": "docker", "command": "collect_metrics"},
            ]
        ))
        
        # 告警响应工作流
        self.register_template(WorkflowTemplate(
            id="alert-response",
            name="告警响应",
            description="处理告警并执行自动修复",
            category="alerting",
            tasks=[
                {"id": "alert1", "name": "发送告警", "type": TaskType.ALERT, "target": "dingtalk", "command": "send_alert"},
                {"id": "fix1", "name": "自动修复", "type": TaskType.AUTO_FIX, "target": "server", "command": "auto_fix"},
                {"id": "verify1", "name": "验证修复", "type": TaskType.SYSTEM_CHECK, "target": "server", "command": "verify"},
            ]
        ))
        
        # 日报生成工作流
        self.register_template(WorkflowTemplate(
            id="daily-report",
            name="日报生成",
            description="生成每日报告",
            category="reporting",
            tasks=[
                {"id": "report1", "name": "收集数据", "type": TaskType.DATA_COLLECT, "target": "all", "command": "collect"},
                {"id": "report2", "name": "生成报告", "type": TaskType.REPORT, "target": "system", "command": "generate_report"},
                {"id": "report3", "name": "发送报告", "type": TaskType.ALERT, "target": "dingtalk", "command": "send_report"},
            ]
        ))
    
    def register_template(self, template: WorkflowTemplate):
        """注册模板"""
        self.templates[template.id] = template
    
    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """获取模板"""
        return self.templates.get(template_id)
    
    def list_templates(self, category: Optional[str] = None) -> List[WorkflowTemplate]:
        """列出模板"""
        if category:
            return [t for t in self.templates.values() if t.category == category]
        return list(self.templates.values())
    
    def create_workflow_from_template(self, template_id: str, params: Dict = None) -> Optional[Workflow]:
        """从模板创建工作流"""
        template = self.get_template(template_id)
        if not template:
            return None
        
        params = params or {}
        tasks = []
        
        for task_def in template.tasks:
            task = Task(
                id=task_def["id"],
                name=task_def["name"],
                task_type=TaskType(task_def["type"]),
                target_system=task_def["target"],
                command=task_def["command"],
                params=params.get(task_def["id"], {}),
                timeout=task_def.get("timeout", 60)
            )
            tasks.append(task)
        
        return Workflow(
            id=str(uuid.uuid4())[:8],
            name=template.name,
            description=template.description,
            tasks=tasks
        )


class CrossSystemScheduler:
    """跨系统任务调度器"""
    
    def __init__(self, engine: WorkflowEngine):
        self.engine = engine
        self.scheduled_tasks: Dict[str, dict] = {}
        self._running = False
        self._scheduler_task: Optional[asyncio.Task] = None
    
    def schedule_workflow(self, workflow_id: str, interval: int = 3600, immediate: bool = False):
        """调度工作流"""
        self.scheduled_tasks[workflow_id] = {
            "interval": interval,
            "last_run": time.time() if not immediate else 0,
            "next_run": time.time() if immediate else time.time() + interval
        }
    
    async def start(self):
        """启动调度器"""
        self._running = True
        self._scheduler_task = asyncio.create_task(self._schedule_loop())
    
    async def stop(self):
        """停止调度器"""
        self._running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
    
    async def _schedule_loop(self):
        """调度循环"""
        while self._running:
            try:
                now = time.time()
                for workflow_id, schedule in self.scheduled_tasks.items():
                    if now >= schedule["next_run"]:
                        # 执行工作流
                        asyncio.create_task(self.engine.run_workflow(workflow_id))
                        
                        # 更新下次运行时间
                        schedule["last_run"] = now
                        schedule["next_run"] = now + schedule["interval"]
                
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Scheduler error: {e}")
                await asyncio.sleep(5)


class StateSynchronizer:
    """状态同步机制"""
    
    def __init__(self):
        self.states: Dict[str, Any] = {}
        self.listeners: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.Lock()
    
    def update_state(self, key: str, value: Any):
        """更新状态"""
        with self._lock:
            old_value = self.states.get(key)
            self.states[key] = value
            
            # 触发监听器
            for listener in self.listeners[key]:
                try:
                    listener(key, old_value, value)
                except Exception as e:
                    print(f"Listener error: {e}")
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """获取状态"""
        return self.states.get(key, default)
    
    def register_listener(self, key: str, callback: Callable):
        """注册监听器"""
        self.listeners[key].append(callback)
    
    def get_all_states(self) -> Dict[str, Any]:
        """获取所有状态"""
        with self._lock:
            return dict(self.states)


async def demo():
    """演示"""
    print("=== 跨系统工作流编排器 v2 演示 ===\n")
    
    # 创建引擎
    engine = WorkflowEngine(max_concurrent=3)
    
    # 创建模板引擎
    template_engine = WorkflowTemplateEngine()
    
    # 列出模板
    print("可用模板:")
    for t in template_engine.list_templates():
        print(f"  - {t.id}: {t.name} ({t.category})")
    print()
    
    # 从模板创建工作流
    workflow = template_engine.create_workflow_from_template("sys-health-check")
    if workflow:
        print(f"创建工作流: {workflow.name} (ID: {workflow.id})")
        print(f"任务数: {len(workflow.tasks)}")
        for task in workflow.tasks:
            print(f"  - {task.name} [{task.task_type.value}]")
        
        # 添加到引擎并运行
        engine.workflows[workflow.id] = workflow
        result = await engine.run_workflow(workflow.id)
        
        print(f"\n工作流状态: {result.status}")
        if result.result:
            print(f"  总任务: {result.result['total_tasks']}")
            print(f"  成功: {result.result['successful']}")
            print(f"  失败: {result.result['failed']}")
            print(f"  耗时: {result.result['duration']:.2f}s")
    
    # 创建自定义工作流
    print("\n--- 创建自定义工作流 ---")
    tasks = [
        Task(id="t1", name="检查服务器", task_type=TaskType.SYSTEM_CHECK, 
             target_system="server", command="check"),
        Task(id="t2", name="采集数据", task_type=TaskType.DATA_COLLECT,
             target_system="openclaw", command="collect", depends_on=["t1"]),
        Task(id="t3", name="发送告警", task_type=TaskType.ALERT,
             target_system="dingtalk", command="alert", depends_on=["t2"]),
    ]
    
    custom_wf = engine.create_workflow(
        name="自定义测试工作流",
        description="测试自定义工作流",
        tasks=tasks
    )
    
    print(f"创建自定义工作流: {custom_wf.name} (ID: {custom_wf.id})")
    result = await engine.run_workflow(custom_wf.id)
    print(f"工作流状态: {result.status}")
    
    # 状态同步演示
    print("\n--- 状态同步演示 ---")
    synchronizer = StateSynchronizer()
    
    def state_listener(key, old, new):
        print(f"状态变更: {key} -> {new}")
    
    synchronizer.register_listener("workflow_status", state_listener)
    synchronizer.update_state("workflow_status", "running")
    synchronizer.update_state("workflow_status", "completed")
    
    print(f"当前状态: {synchronizer.get_all_states()}")
    
    # 获取工作流状态
    status = engine.get_workflow_status(custom_wf.id)
    print(f"\n工作流最终状态: {json.dumps(status, indent=2, default=str)[:500]}...")
    
    return status


if __name__ == "__main__":
    asyncio.run(demo())