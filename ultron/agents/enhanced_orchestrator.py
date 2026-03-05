#!/usr/bin/env python3
"""
增强型多Agent协作任务编排器
支持任务依赖、并行执行、工作流调度、结果聚合
"""

import json
import os
import sys
import threading
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AGENTS_DIR)


class TaskStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


class TaskDependencyType(Enum):
    """任务依赖类型"""
    BLOCKS = "blocks"           # 当前任务阻塞依赖任务
    REQUIRES = "requires"       # 当前任务需要依赖任务先完成
    STARTS_AFTER = "starts_after"  # 当前任务在依赖任务开始后多久开始


@dataclass
class TaskDependency:
    """任务依赖定义"""
    task_id: str
    dependency_type: TaskDependencyType = TaskDependencyType.REQUIRES
    delay_seconds: float = 0  # 延迟执行时间


@dataclass
class OrchestratedTask:
    """编排任务"""
    id: str
    name: str
    agent_type: str  # monitor/executor/analyzer/communicator
    payload: Dict
    priority: int = 5  # 1-10, 10最高
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[TaskDependency] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)  # 依赖的任务ID列表
    parallel_with: List[str] = field(default_factory=list)  # 可并行执行的任务ID
    timeout: float = 60.0
    retry_count: int = 0
    max_retries: int = 3
    result: Any = None
    error: str = None
    start_time: float = None
    end_time: float = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def duration(self) -> float:
        """执行时长"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0


@dataclass 
class WorkflowDefinition:
    """工作流定义"""
    id: str
    name: str
    description: str = ""
    tasks: List[OrchestratedTask] = field(default_factory=list)
    parallel_groups: List[List[str]] = field(default_factory=list)  # 可并行执行的任务组
    on_success: str = None  # 成功后回调
    on_failure: str = None  # 失败后回调
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class WorkflowExecution:
    """工作流执行实例"""
    workflow_id: str
    execution_id: str
    status: TaskStatus
    started_at: str
    completed_at: str = None
    task_results: Dict[str, Any] = field(default_factory=dict)
    failed_tasks: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)


class EnhancedOrchestrator:
    """增强型多Agent协作任务编排器"""
    
    def __init__(self, state_file: str = None):
        self.state_file = state_file or os.path.join(AGENTS_DIR, "orchestration_state.json")
        self.tasks: Dict[str, OrchestratedTask] = {}
        self.workflows: Dict[str, WorkflowDefinition] = {}
        self.executions: Dict[str, WorkflowExecution] = {}
        self.task_queue: List[str] = []  # 待执行任务ID队列
        self.running_tasks: Dict[str, OrchestratedTask] = {}
        self.completed_tasks: Dict[str, OrchestratedTask] = {}
        
        # 事件回调
        self.event_handlers: Dict[str, List[Callable]] = {
            "task_ready": [],
            "task_started": [],
            "task_completed": [],
            "task_failed": [],
            "workflow_completed": [],
            "workflow_failed": []
        }
        
        # 任务完成回调
        self.task_completion_callbacks: Dict[str, Callable] = {}
        
        # 锁
        self._lock = threading.RLock()
        
        # 加载状态
        self._load_state()
    
    def _load_state(self):
        """加载状态"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                    # 恢复任务
                    for task_data in data.get('tasks', []):
                        # 转换状态字符串到枚举
                        if 'status' in task_data and isinstance(task_data['status'], str):
                            task_data['status'] = TaskStatus(task_data['status'])
                        task = OrchestratedTask(**task_data)
                        self.tasks[task.id] = task
                    # 恢复工作流
                    for wf_data in data.get('workflows', []):
                        # 转换任务状态
                        for task_data in wf_data.get('tasks', []):
                            if 'status' in task_data and isinstance(task_data['status'], str):
                                task_data['status'] = TaskStatus(task_data['status'])
                        wf = WorkflowDefinition(**wf_data)
                        self.workflows[wf.id] = wf
                    print(f"已加载 {len(self.tasks)} 个任务, {len(self.workflows)} 个工作流")
            except Exception as e:
                print(f"加载状态失败: {e}")
    
    def _save_state(self):
        """保存状态"""
        try:
            data = {
                'tasks': [self._task_to_dict(t) for t in self.tasks.values()],
                'workflows': [self._workflow_to_dict(w) for w in self.workflows.values()],
                'timestamp': datetime.now().isoformat()
            }
            with open(self.state_file, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存状态失败: {e}")
    
    def _task_to_dict(self, task: OrchestratedTask) -> Dict:
        return {
            'id': task.id,
            'name': task.name,
            'agent_type': task.agent_type,
            'payload': task.payload,
            'priority': task.priority,
            'status': task.status.value if hasattr(task.status, 'value') else task.status,
            'depends_on': task.depends_on,
            'parallel_with': task.parallel_with,
            'timeout': task.timeout,
            'retry_count': task.retry_count,
            'max_retries': task.max_retries,
            'result': task.result,
            'error': task.error,
            'created_at': task.created_at
        }
    
    def _workflow_to_dict(self, wf: WorkflowDefinition) -> Dict:
        return {
            'id': wf.id,
            'name': wf.name,
            'description': wf.description,
            'tasks': [self._task_to_dict(t) for t in wf.tasks],
            'parallel_groups': wf.parallel_groups,
            'on_success': wf.on_success,
            'on_failure': wf.on_failure,
            'created_at': wf.created_at
        }
    
    # ========== 任务管理 ==========
    
    def create_task(self, task_id: str, name: str, agent_type: str, 
                   payload: Dict, priority: int = 5,
                   depends_on: List[str] = None,
                   parallel_with: List[str] = None,
                   timeout: float = 60.0, max_retries: int = 3) -> OrchestratedTask:
        """创建任务"""
        with self._lock:
            task = OrchestratedTask(
                id=task_id,
                name=name,
                agent_type=agent_type,
                payload=payload,
                priority=priority,
                depends_on=depends_on or [],
                parallel_with=parallel_with or [],
                timeout=timeout,
                max_retries=max_retries
            )
            self.tasks[task_id] = task
            self._update_task_status(task)
            self._save_state()
            return task
    
    def _update_task_status(self, task: OrchestratedTask):
        """更新任务状态"""
        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            return
        
        # 检查依赖是否满足
        deps_satisfied = True
        for dep_id in task.depends_on:
            if dep_id in self.tasks:
                dep_task = self.tasks[dep_id]
                if dep_task.status != TaskStatus.COMPLETED:
                    deps_satisfied = False
                    break
        
        if deps_satisfied:
            task.status = TaskStatus.READY
            if task.id not in self.task_queue:
                self.task_queue.append(task.id)
            self._trigger_event("task_ready", task)
        else:
            task.status = TaskStatus.BLOCKED
    
    def submit_task(self, task: OrchestratedTask):
        """提交任务"""
        with self._lock:
            self.tasks[task.id] = task
            self._update_task_status(task)
            self._save_state()
    
    def get_next_task(self) -> Optional[OrchestratedTask]:
        """获取下一个可执行任务（优先级排序）"""
        with self._lock:
            # 按优先级排序
            ready_tasks = [self.tasks[tid] for tid in self.task_queue 
                          if tid in self.tasks and self.tasks[tid].status == TaskStatus.READY]
            ready_tasks.sort(key=lambda t: -t.priority)  # 高优先级优先
            
            if ready_tasks:
                task = ready_tasks[0]
                self.task_queue.remove(task.id)
                return task
            return None
    
    def start_task(self, task_id: str) -> bool:
        """开始执行任务"""
        with self._lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            if task.status != TaskStatus.READY:
                return False
            
            task.status = TaskStatus.RUNNING
            task.start_time = time.time()
            self.running_tasks[task_id] = task
            self._trigger_event("task_started", task)
            return True
    
    def complete_task(self, task_id: str, result: Any = None, error: str = None):
        """完成任务"""
        with self._lock:
            if task_id not in self.tasks:
                return
            
            task = self.tasks[task_id]
            task.end_time = time.time()
            task.result = result
            task.error = error
            
            if error:
                task.status = TaskStatus.FAILED
                self._trigger_event("task_failed", task)
                
                # 重试
                if task.retry_count < task.max_retries:
                    task.retry_count += 1
                    task.status = TaskStatus.READY
                    task.start_time = None
                    task.end_time = None
                    self.task_queue.append(task.id)
            else:
                task.status = TaskStatus.COMPLETED
                self._trigger_event("task_completed", task)
            
            # 从运行中移除
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            self.completed_tasks[task_id] = task
            
            # 检查依赖此任务的其他任务
            for other_task in self.tasks.values():
                if task_id in other_task.depends_on:
                    self._update_task_status(other_task)
            
            # 触发回调
            if task_id in self.task_completion_callbacks:
                try:
                    self.task_completion_callbacks[task_id](task)
                except Exception as e:
                    print(f"回调执行失败: {e}")
            
            self._save_state()
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            if task_id not in self.tasks:
                return False
            
            task = self.tasks[task_id]
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                return False
            
            task.status = TaskStatus.CANCELLED
            if task_id in self.task_queue:
                self.task_queue.remove(task_id)
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
            
            self._save_state()
            return True
    
    # ========== 工作流管理 ==========
    
    def create_workflow(self, workflow_id: str, name: str, 
                       description: str = "") -> WorkflowDefinition:
        """创建工作流"""
        with self._lock:
            wf = WorkflowDefinition(
                id=workflow_id,
                name=name,
                description=description
            )
            self.workflows[workflow_id] = wf
            return wf
    
    def add_task_to_workflow(self, workflow_id: str, task: OrchestratedTask):
        """添加任务到工作流"""
        with self._lock:
            if workflow_id not in self.workflows:
                return False
            self.workflows[workflow_id].tasks.append(task)
            self.tasks[task.id] = task
            return True
    
    def execute_workflow(self, workflow_id: str) -> str:
        """执行工作流"""
        with self._lock:
            if workflow_id not in self.workflows:
                return None
            
            wf = self.workflows[workflow_id]
            execution_id = f"exec_{int(time.time() * 1000)}"
            
            execution = WorkflowExecution(
                workflow_id=workflow_id,
                execution_id=execution_id,
                status=TaskStatus.RUNNING,
                started_at=datetime.now().isoformat()
            )
            self.executions[execution_id] = execution
            
            # 初始化所有任务状态
            for task in wf.tasks:
                task.status = TaskStatus.PENDING
                self._update_task_status(task)
            
            self._save_state()
            return execution_id
    
    def get_workflow_status(self, execution_id: str) -> Dict:
        """获取工作流执行状态"""
        if execution_id not in self.executions:
            return {"error": "Execution not found"}
        
        exec_info = self.executions[execution_id]
        wf = self.workflows.get(exec_info.workflow_id)
        
        if not wf:
            return {"error": "Workflow not found"}
        
        # 统计任务状态
        task_stats = defaultdict(int)
        for task in wf.tasks:
            task_stats[task.status.value] += 1
        
        # 检查是否全部完成
        all_completed = all(t.status == TaskStatus.COMPLETED for t in wf.tasks)
        any_failed = any(t.status == TaskStatus.FAILED for t in wf.tasks)
        
        if any_failed:
            exec_info.status = TaskStatus.FAILED
            exec_info.completed_at = datetime.now().isoformat()
            self._trigger_event("workflow_failed", exec_info)
        elif all_completed:
            exec_info.status = TaskStatus.COMPLETED
            exec_info.completed_at = datetime.now().isoformat()
            # 收集结果
            for task in wf.tasks:
                exec_info.task_results[task.id] = task.result
            self._trigger_event("workflow_completed", exec_info)
        
        return {
            "execution_id": execution_id,
            "workflow_id": exec_info.workflow_id,
            "workflow_name": wf.name,
            "status": exec_info.status.value,
            "task_stats": dict(task_stats),
            "started_at": exec_info.started_at,
            "completed_at": exec_info.completed_at,
            "task_results": exec_info.task_results,
            "failed_tasks": exec_info.failed_tasks
        }
    
    # ========== 批量操作 ==========
    
    def execute_parallel_tasks(self, task_ids: List[str]) -> Dict:
        """并行执行多个任务"""
        results = {}
        threads = []
        
        def run_task(task_id):
            if self.start_task(task_id):
                results[task_id] = {"status": "started"}
            else:
                results[task_id] = {"status": "failed", "error": "Task not ready"}
        
        # 创建线程
        for task_id in task_ids:
            t = threading.Thread(target=run_task, args=(task_id,))
            threads.append(t)
        
        # 启动所有线程
        for t in threads:
            t.start()
        
        # 等待完成
        for t in threads:
            t.join()
        
        return results
    
    def wait_for_completion(self, task_ids: List[str], timeout: float = 300) -> Dict:
        """等待任务完成"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            all_done = True
            pending = []
            
            for task_id in task_ids:
                if task_id in self.tasks:
                    task = self.tasks[task_id]
                    if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                        all_done = False
                        pending.append(task_id)
            
            if all_done:
                # 收集结果
                results = {}
                for task_id in task_ids:
                    if task_id in self.tasks:
                        task = self.tasks[task_id]
                        results[task_id] = {
                            "status": task.status.value,
                            "result": task.result,
                            "error": task.error,
                            "duration": task.duration()
                        }
                return {"status": "completed", "results": results}
            
            time.sleep(0.5)
        
        return {"status": "timeout", "pending": pending}
    
    # ========== 事件系统 ==========
    
    def on(self, event: str, handler: Callable):
        """注册事件处理器"""
        if event in self.event_handlers:
            self.event_handlers[event].append(handler)
    
    def _trigger_event(self, event: str, data: Any):
        """触发事件"""
        for handler in self.event_handlers.get(event, []):
            try:
                handler(data)
            except Exception as e:
                print(f"事件处理错误: {e}")
    
    # ========== 统计与报告 ==========
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            task_stats = defaultdict(int)
            for task in self.tasks.values():
                task_stats[task.status.value] += 1
            
            # 计算平均执行时间
            completed = [t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED and t.duration() > 0]
            avg_duration = sum(t.duration() for t in completed) / len(completed) if completed else 0
            
            return {
                "total_tasks": len(self.tasks),
                "task_stats": dict(task_stats),
                "pending_tasks": len(self.task_queue),
                "running_tasks": len(self.running_tasks),
                "completed_tasks": len(self.completed_tasks),
                "avg_duration_seconds": round(avg_duration, 2),
                "total_workflows": len(self.workflows),
                "active_executions": len([e for e in self.executions.values() if e.status == TaskStatus.RUNNING])
            }
    
    def get_task_details(self, task_id: str) -> Optional[Dict]:
        """获取任务详情"""
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        return {
            "id": task.id,
            "name": task.name,
            "agent_type": task.agent_type,
            "status": task.status.value,
            "priority": task.priority,
            "depends_on": task.depends_on,
            "result": task.result,
            "error": task.error,
            "duration": task.duration(),
            "created_at": task.created_at,
            "retry_count": task.retry_count
        }
    
    def get_full_report(self) -> Dict:
        """获取完整报告"""
        return {
            "stats": self.get_stats(),
            "workflows": [
                {
                    "id": wf.id,
                    "name": wf.name,
                    "task_count": len(wf.tasks)
                }
                for wf in self.workflows.values()
            ],
            "recent_tasks": [
                self.get_task_details(t.id)
                for t in sorted(self.tasks.values(), key=lambda x: x.created_at, reverse=True)[:10]
            ]
        }


# 全局单例
_orchestrator = None
_orchestrator_lock = threading.Lock()

def get_orchestrator() -> EnhancedOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        with _orchestrator_lock:
            if _orchestrator is None:
                _orchestrator = EnhancedOrchestrator()
    return _orchestrator


if __name__ == "__main__":
    # 测试
    orch = get_orchestrator()
    
    # 创建任务
    task1 = orch.create_task(
        "task_1", "数据采集", "monitor",
        {"source": "api", "interval": 60}, priority=8
    )
    task2 = orch.create_task(
        "task_2", "数据处理", "executor",
        {"input": "task_1"}, priority=7, depends_on=["task_1"]
    )
    task3 = orch.create_task(
        "task_3", "发送通知", "communicator",
        {"message": "处理完成"}, priority=5, depends_on=["task_2"]
    )
    
    # 创建工作流
    wf = orch.create_workflow("wf_test", "测试工作流")
    wf.tasks = [task1, task2, task3]
    
    # 执行工作流
    exec_id = orch.execute_workflow("wf_test")
    print(f"执行ID: {exec_id}")
    
    # 模拟任务执行
    while True:
        task = orch.get_next_task()
        if not task:
            break
        
        print(f"执行任务: {task.name}")
        orch.start_task(task.id)
        time.sleep(0.1)
        orch.complete_task(task.id, result={"success": True})
        
        # 检查工作流状态
        status = orch.get_workflow_status(exec_id)
        print(f"工作流状态: {status['status']}")
        
        if status['status'] in ['completed', 'failed']:
            break
    
    print(json.dumps(orch.get_stats(), indent=2, ensure_ascii=False))