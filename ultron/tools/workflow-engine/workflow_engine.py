#!/usr/bin/env python3
"""
Agent服务编排与工作流引擎
支持：工作流定义、任务编排、状态管理、失败重试、并行执行
"""

import json
import time
import uuid
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import threading

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class WorkflowStatus(Enum):
    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Task:
    id: str
    name: str
    command: str
    depends_on: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    retries: int = 0
    max_retries: int = 3

@dataclass
class Workflow:
    id: str
    name: str
    description: str
    tasks: List[Task]
    status: WorkflowStatus = WorkflowStatus.CREATED
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    result: Optional[Any] = None
    current_task_idx: int = 0

class WorkflowEngine:
    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}
        self.task_handlers: Dict[str, Callable] = {}
        self.lock = threading.Lock()
        
        # 注册默认任务处理器
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """注册默认任务处理器"""
        import subprocess
        
        def shell_handler(command: str) -> Dict:
            try:
                result = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=300
                )
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        self.task_handlers["shell"] = shell_handler
        self.task_handlers["http"] = self._http_handler
    
    def _http_handler(self, command: str) -> Dict:
        """HTTP请求处理器"""
        try:
            import urllib.request
            import urllib.parse
            
            parts = command.split("|")
            method = "GET"
            url = command
            
            if len(parts) >= 2:
                method = parts[0].strip().upper()
                url = parts[1].strip()
            
            req = urllib.request.Request(url, method=method)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return {
                    "success": True,
                    "status": resp.status,
                    "body": resp.read().decode("utf-8")
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def register_handler(self, task_type: str, handler: Callable):
        """注册自定义任务处理器"""
        self.task_handlers[task_type] = handler
    
    def create_workflow(self, name: str, description: str, tasks: List[Dict]) -> str:
        """创建工作流"""
        workflow_id = f"wf_{uuid.uuid4().hex[:8]}"
        
        task_objects = []
        for t in tasks:
            task = Task(
                id=f"task_{uuid.uuid4().hex[:6]}",
                name=t["name"],
                command=t["command"],
                depends_on=t.get("depends_on", []),
                max_retries=t.get("max_retries", 3)
            )
            task_objects.append(task)
        
        workflow = Workflow(
            id=workflow_id,
            name=name,
            description=description,
            tasks=task_objects
        )
        
        with self.lock:
            self.workflows[workflow_id] = workflow
        
        return workflow_id
    
    def get_ready_tasks(self, workflow: Workflow) -> List[Task]:
        """获取就绪任务（依赖都已完成）"""
        ready = []
        completed_ids = {t.id for t in workflow.tasks if t.status == TaskStatus.COMPLETED}
        
        for task in workflow.tasks:
            if task.status == TaskStatus.PENDING:
                deps_met = all(dep in completed_ids for dep in task.depends_on)
                if deps_met:
                    ready.append(task)
        
        return ready
    
    def execute_task(self, task: Task) -> Dict:
        """执行单个任务"""
        task.status = TaskStatus.RUNNING
        task.start_time = datetime.now().isoformat()
        
        # 解析任务类型和命令
        parts = task.command.split(":", 1)
        task_type = parts[0] if len(parts) > 1 else "shell"
        cmd = parts[1] if len(parts) > 1 else task.command
        
        handler = self.task_handlers.get(task_type, self.task_handlers["shell"])
        
        try:
            result = handler(cmd)
            if result.get("success", False):
                task.status = TaskStatus.COMPLETED
                task.result = result
            else:
                if task.retries < task.max_retries:
                    task.status = TaskStatus.PENDING
                    task.retries += 1
                else:
                    task.status = TaskStatus.FAILED
                    task.error = result.get("error", "Unknown error")
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
        
        task.end_time = datetime.now().isoformat()
        return asdict(task)
    
    def run_workflow(self, workflow_id: str) -> Dict:
        """运行工作流"""
        with self.lock:
            workflow = self.workflows.get(workflow_id)
            if not workflow:
                return {"success": False, "error": "Workflow not found"}
            
            if workflow.status != WorkflowStatus.CREATED:
                return {"success": False, "error": f"Workflow already {workflow.status.value}"}
        
        workflow.status = WorkflowStatus.RUNNING
        workflow.started_at = datetime.now().isoformat()
        
        while True:
            ready_tasks = self.get_ready_tasks(workflow)
            
            if not ready_tasks:
                # 检查是否有失败
                failed = [t for t in workflow.tasks if t.status == TaskStatus.FAILED]
                if failed:
                    workflow.status = WorkflowStatus.FAILED
                    workflow.ended_at = datetime.now().isoformat()
                    return {"success": False, "failed_tasks": [t.name for t in failed]}
                
                # 检查是否全部完成
                completed = all(t.status == TaskStatus.COMPLETED for t in workflow.tasks)
                if completed:
                    workflow.status = WorkflowStatus.COMPLETED
                    workflow.ended_at = datetime.now().isoformat()
                    workflow.result = {
                        "tasks_completed": len(workflow.tasks),
                        "total_time": (
                            datetime.fromisoformat(workflow.ended_at) - 
                            datetime.fromisoformat(workflow.started_at)
                        ).total_seconds()
                    }
                    return {"success": True, "result": workflow.result}
                
                break
            
            # 并行执行就绪任务
            for task in ready_tasks:
                self.execute_task(task)
        
        return {"success": False, "error": "Workflow deadlocked"}
    
    def get_workflow_status(self, workflow_id: str) -> Optional[Dict]:
        """获取工作流状态"""
        with self.lock:
            wf = self.workflows.get(workflow_id)
            if not wf:
                return None
            
            return {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "status": wf.status.value,
                "created_at": wf.created_at,
                "started_at": wf.started_at,
                "ended_at": wf.ended_at,
                "tasks": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "status": t.status.value,
                        "depends_on": t.depends_on,
                        "result": t.result,
                        "error": t.error,
                        "retries": t.retries
                    }
                    for t in wf.tasks
                ],
                "result": wf.result
            }
    
    def list_workflows(self) -> List[Dict]:
        """列出所有工作流"""
        with self.lock:
            return [
                {
                    "id": wf.id,
                    "name": wf.name,
                    "status": wf.status.value,
                    "created_at": wf.created_at,
                    "tasks_count": len(wf.tasks),
                    "completed": sum(1 for t in wf.tasks if t.status == TaskStatus.COMPLETED)
                }
                for wf in self.workflows.values()
            ]
    
    def cancel_workflow(self, workflow_id: str) -> bool:
        """取消工作流"""
        with self.lock:
            wf = self.workflows.get(workflow_id)
            if wf and wf.status == WorkflowStatus.RUNNING:
                wf.status = WorkflowStatus.CANCELLED
                wf.ended_at = datetime.now().isoformat()
                for task in wf.tasks:
                    if task.status == TaskStatus.PENDING:
                        task.status = TaskStatus.CANCELLED
                return True
        return False
    
    def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流"""
        with self.lock:
            if workflow_id in self.workflows:
                del self.workflows[workflow_id]
                return True
        return False


# 全局引擎实例
_engine = None
_lock = threading.Lock()

def get_engine() -> WorkflowEngine:
    global _engine
    with _lock:
        if _engine is None:
            _engine = WorkflowEngine()
        return _engine