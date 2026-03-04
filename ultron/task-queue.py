#!/usr/bin/env python3
"""
奥创任务队列系统 - 第2世：任务分发与执行
功能：任务队列、远程执行引擎、执行结果回传
"""

import json
import os
import datetime
import uuid
import socket
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from queue import Queue, Empty
import threading
import subprocess


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4


@dataclass
class Task:
    """任务定义"""
    task_id: str
    name: str
    command: str
    target_device: str  # device_id 或 "local" 或 "broadcast"
    priority: int
    status: str
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    result: Optional[Dict]
    error: Optional[str]
    metadata: Dict[str, Any]


class TaskQueue:
    """任务队列管理器"""
    
    def __init__(self, queue_path: str = None):
        self.queue_path = queue_path or "/root/.openclaw/workspace/ultron/logs/task_queue.json"
        self.tasks: Dict[str, Task] = {}
        self.pending_queue: List[str] = []  # 任务ID列表
        self._lock = threading.Lock()
        self._load_queue()
    
    def _load_queue(self):
        """加载任务队列"""
        if os.path.exists(self.queue_path):
            try:
                with open(self.queue_path, 'r') as f:
                    data = json.load(f)
                    for t in data.get("tasks", []):
                        self.tasks[t["task_id"]] = Task(**t)
                    self.pending_queue = data.get("pending", [])
            except Exception as e:
                print(f"加载任务队列失败: {e}")
    
    def _save_queue(self):
        """保存任务队列"""
        Path(self.queue_path).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "tasks": [asdict(t) for t in self.tasks.values()],
            "pending": self.pending_queue,
            "last_updated": datetime.datetime.now().isoformat()
        }
        with open(self.queue_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def create_task(self, name: str, command: str, target_device: str = "local",
                   priority: TaskPriority = TaskPriority.NORMAL, 
                   metadata: Dict = None) -> str:
        """创建新任务"""
        task_id = str(uuid.uuid4())[:8]
        
        task = Task(
            task_id=task_id,
            name=name,
            command=command,
            target_device=target_device,
            priority=priority.value,
            status=TaskStatus.PENDING.value,
            created_at=datetime.datetime.now().isoformat(),
            started_at=None,
            completed_at=None,
            result=None,
            error=None,
            metadata=metadata or {}
        )
        
        with self._lock:
            self.tasks[task_id] = task
            self._add_to_pending(task_id, priority)
            self._save_queue()
        
        return task_id
    
    def _add_to_pending(self, task_id: str, priority: TaskPriority):
        """按优先级添加到待执行队列"""
        # 按优先级插入：越高越靠前
        inserted = False
        for i, tid in enumerate(self.pending_queue):
            if self.tasks[tid].priority < priority.value:
                self.pending_queue.insert(i, task_id)
                inserted = True
                break
        
        if not inserted:
            self.pending_queue.append(task_id)
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务"""
        return self.tasks.get(task_id)
    
    def get_next_task(self) -> Optional[Task]:
        """获取下一个待执行任务"""
        with self._lock:
            while self.pending_queue:
                task_id = self.pending_queue.pop(0)
                task = self.tasks.get(task_id)
                if task and task.status == TaskStatus.PENDING.value:
                    return task
            return None
    
    def start_task(self, task_id: str) -> bool:
        """开始执行任务"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status != TaskStatus.PENDING.value:
            return False
        
        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.datetime.now().isoformat()
        self._save_queue()
        return True
    
    def complete_task(self, task_id: str, result: Dict = None, error: str = None) -> bool:
        """完成任务"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        task.status = TaskStatus.COMPLETED.value if not error else TaskStatus.FAILED.value
        task.completed_at = datetime.datetime.now().isoformat()
        task.result = result
        task.error = error
        self._save_queue()
        return True
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        if task.status in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]:
            return False
        
        task.status = TaskStatus.CANCELLED.value
        task.completed_at = datetime.datetime.now().isoformat()
        self._save_queue()
        return True
    
    def list_tasks(self, status: str = None, limit: int = 50) -> List[Task]:
        """列出任务"""
        tasks = list(self.tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # 按创建时间倒序
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        return tasks[:limit]
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        total = len(self.tasks)
        by_status = {}
        
        for t in self.tasks.values():
            by_status[t.status] = by_status.get(t.status, 0) + 1
        
        return {
            "total_tasks": total,
            "pending": len(self.pending_queue),
            "by_status": by_status,
            "last_updated": datetime.datetime.now().isoformat()
        }


class RemoteExecutor:
    """远程执行引擎"""
    
    def __init__(self, task_queue: TaskQueue, device_registry=None):
        self.task_queue = task_queue
        self.device_registry = device_registry
        self.executing: Dict[str, Task] = {}
        self._running = False
        self._thread: Optional[threading.Thread] = None
    
    def start(self):
        """启动执行引擎"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print("执行引擎已启动")
    
    def stop(self):
        """停止执行引擎"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("执行引擎已停止")
    
    def _run_loop(self):
        """主执行循环"""
        while self._running:
            task = self.task_queue.get_next_task()
            
            if task:
                self._execute_task(task)
            else:
                # 没有任务时休眠
                threading.Event().wait(1)
    
    def _execute_task(self, task: Task):
        """执行单个任务"""
        print(f"执行任务: {task.name} ({task.task_id})")
        
        self.task_queue.start_task(task.task_id)
        self.executing[task.task_id] = task
        
        try:
            # 根据目标设备执行
            if task.target_device == "local" or task.target_device == "localhost":
                result = self._execute_local(task)
            elif task.target_device == "broadcast":
                # 广播到所有设备（这里简化为本机）
                result = self._execute_local(task)
            else:
                # 远程执行（需要设备注册表）
                result = self._execute_remote(task)
            
            self.task_queue.complete_task(task.task_id, result=result)
            print(f"任务完成: {task.name}")
            
        except Exception as e:
            self.task_queue.complete_task(task.task_id, error=str(e))
            print(f"任务失败: {task.name} - {e}")
        
        finally:
            if task.task_id in self.executing:
                del self.executing[task.task_id]
    
    def _execute_local(self, task: Task) -> Dict:
        """本地执行"""
        start_time = datetime.datetime.now()
        
        # 执行命令
        result = subprocess.run(
            task.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=300  # 5分钟超时
        )
        
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "duration_seconds": duration,
            "executed_at": start_time.isoformat(),
            "device": "local"
        }
    
    def _execute_remote(self, task: Task) -> Dict:
        """远程执行（预留接口）"""
        # 实际远程执行需要通过 OpenClaw 的 nodes 工具
        # 这里返回模拟结果
        return {
            "status": "remote_execution_pending",
            "target": task.target_device,
            "command": task.command
        }
    
    def get_executing(self) -> List[Task]:
        """获取正在执行的任务"""
        return list(self.executing.values())


# 全局实例
_task_queue: Optional[TaskQueue] = None
_executor: Optional[RemoteExecutor] = None

def get_task_queue() -> TaskQueue:
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue

def get_executor() -> RemoteExecutor:
    global _executor
    if _executor is None:
        _executor = RemoteExecutor(get_task_queue())
    return _executor


if __name__ == "__main__":
    import sys
    
    queue = get_task_queue()
    executor = get_executor()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "create":
            if len(sys.argv) > 3:
                task_id = queue.create_task(
                    name=sys.argv[2],
                    command=sys.argv[3],
                    target_device=sys.argv[4] if len(sys.argv) > 4 else "local"
                )
                print(f"任务已创建: {task_id}")
            else:
                print("用法: create <name> <command> [target]")
        
        elif cmd == "list":
            tasks = queue.list_tasks()
            print(f"任务数: {len(tasks)}")
            for t in tasks[:10]:
                print(f"  [{t.status}] {t.name} - {t.command[:40]}")
        
        elif cmd == "status":
            stats = queue.get_statistics()
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        
        elif cmd == "start":
            executor.start()
        
        elif cmd == "stop":
            executor.stop()
        
        elif cmd == "executing":
            exec_tasks = executor.get_executing()
            print(f"正在执行: {len(exec_tasks)}")
            for t in exec_tasks:
                print(f"  - {t.name}: {t.command[:40]}")
        
        elif cmd == "run":
            # 创建并立即执行一个任务
            if len(sys.argv) > 2:
                task_id = queue.create_task(
                    name=f"cli-{sys.argv[2]}",
                    command=" ".join(sys.argv[2:]),
                    target_device="local"
                )
                executor.start()
                # 执行一个任务
                task = queue.get_next_task()
                if task:
                    executor._execute_task(task)
            else:
                print("用法: run <command>")
        
        else:
            print("用法: task-queue.py [create|list|status|start|stop|executing|run]")
    else:
        stats = queue.get_statistics()
        exec_tasks = executor.get_executing()
        print("=" * 40)
        print("  奥创任务队列系统 v1.0")
        print("=" * 40)
        print(f"总任务: {stats['total_tasks']}")
        print(f"待执行: {stats['pending']}")
        print(f"执行中: {len(exec_tasks)}")
        print(f"已完成: {stats['by_status'].get('completed', 0)}")
        print("=" * 40)