#!/usr/bin/env python3
"""
Agent Task Scheduler V2 - 任务调度与队列管理
=============================================
第51世: 实现Agent任务调度与队列管理

功能:
- 定时任务调度 (cron风格)
- 任务依赖管理 (DAG)
- 任务状态跟踪
- 任务重试与超时
- 队列优先级管理
- 任务取消与暂停
"""

import json
import time
import uuid
import heapq
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from pathlib import Path
import threading
import croniter


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"           # 等待中
    SCHEDULED = "scheduled"       # 已调度
    RUNNING = "running"           # 执行中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败
    CANCELLED = "cancelled"       # 已取消
    PAUSED = "paused"             # 已暂停
    TIMEOUT = "timeout"           # 超时


class TaskPriority(Enum):
    """任务优先级 (1=最低, 10=最高)"""
    CRITICAL = 10
    URGENT = 8
    HIGH = 7
    MEDIUM = 5
    LOW = 3
    BACKGROUND = 1


@dataclass
class ScheduledTask:
    """定时任务定义"""
    id: str
    name: str
    task_type: str
    payload: Dict
    priority: int = 5
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    run_at: Optional[str] = None      # 一次性运行时间 ISO格式
    timeout: float = 300.0            # 超时时间(秒)
    max_retries: int = 3
    retry_delay: float = 5.0          # 重试延迟(秒)
    enabled: bool = True
    depends_on: List[str] = field(default_factory=list)
    callback: Optional[str] = None    # 回调函数名
    metadata: Dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    run_count: int = 0


@dataclass
class TaskInstance:
    """任务实例 (运行时)"""
    id: str
    scheduled_task_id: str
    name: str
    task_type: str
    payload: Dict
    priority: int
    status: str = "pending"
    depends_on: List[str] = field(default_factory=list)
    timeout: float = 300.0
    max_retries: int = 3
    retry_count: int = 0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict] = None
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "scheduled_task_id": self.scheduled_task_id,
            "name": self.name,
            "task_type": self.task_type,
            "payload": self.payload,
            "priority": self.priority,
            "status": self.status,
            "depends_on": self.depends_on,
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "error": self.error,
            "result": self.result,
            "metadata": self.metadata
        }


class TaskSchedulerV2:
    """
    Agent任务调度器V2
    支持定时任务、依赖管理、优先级队列
    """
    
    def __init__(self, state_dir: str = None):
        if state_dir is None:
            state_dir = Path(__file__).parent
        
        self.state_dir = Path(state_dir)
        self.state_file = self.state_dir / "task_scheduler_state.json"
        self.tasks_file = self.state_dir / "scheduled_tasks.json"
        
        # 定时任务存储
        self.scheduled_tasks: Dict[str, ScheduledTask] = {}
        self.task_instances: Dict[str, TaskInstance] = {}
        
        # 优先级队列 (堆)
        self.priority_queue: List[TaskInstance] = []
        
        # 等待依赖的任务
        self.pending_dependency: Dict[str, List[TaskInstance]] = defaultdict(list)
        
        # 调度器状态
        self.is_running = False
        self.scheduler_thread: Optional[threading.Thread] = None
        
        # 统计
        self.stats = {
            "total_scheduled": 0,
            "total_completed": 0,
            "total_failed": 0,
            "total_cancelled": 0,
            "avg_execution_time": 0.0
        }
        
        self._load_state()
    
    def _load_state(self):
        """加载状态"""
        # 加载定时任务
        if self.tasks_file.exists():
            with open(self.tasks_file) as f:
                data = json.load(f)
                for t in data.get("scheduled_tasks", []):
                    task = ScheduledTask(**t)
                    self.scheduled_tasks[task.id] = task
        
        # 加载调度器状态
        if self.state_file.exists():
            with open(self.state_file) as f:
                data = json.load(f)
                self.stats = data.get("stats", self.stats)
    
    def _save_state(self):
        """保存状态"""
        # 保存定时任务
        tasks_data = {
            "scheduled_tasks": [asdict(t) for t in self.scheduled_tasks.values()]
        }
        with open(self.tasks_file, "w") as f:
            json.dump(tasks_data, f, indent=2)
        
        # 保存调度器状态
        state_data = {
            "stats": self.stats,
            "is_running": self.is_running,
            "saved_at": datetime.now().isoformat()
        }
        with open(self.state_file, "w") as f:
            json.dump(state_data, f, indent=2)
    
    def _calculate_next_run(self, task: ScheduledTask) -> Optional[datetime]:
        """计算下次运行时间"""
        now = datetime.now()
        
        if task.run_at:
            run_time = datetime.fromisoformat(task.run_at.replace('Z', '+00:00'))
            if task.enabled and run_time > now:
                return run_time.isoformat()
            return None
        
        if task.cron_expression:
            try:
                cron = croniter.croniter(task.cron_expression, now)
                next_dt = cron.get_next(datetime)
                return next_dt.isoformat()
            except:
                return None
        
        if task.interval_seconds:
            if task.last_run:
                last = datetime.fromisoformat(task.last_run.replace('Z', '+00:00'))
                return (last + timedelta(seconds=task.interval_seconds)).isoformat()
            return now.isoformat()
        
        return None
    
    def schedule_task(self, task: ScheduledTask) -> str:
        """添加定时任务"""
        task.next_run = self._calculate_next_run(task)
        self.scheduled_tasks[task.id] = task
        self.stats["total_scheduled"] += 1
        self._save_state()
        return task.id
    
    def create_task(
        self,
        name: str,
        task_type: str,
        payload: Dict,
        priority: int = 5,
        cron_expression: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        run_at: Optional[str] = None,
        timeout: float = 300.0,
        max_retries: int = 3,
        depends_on: List[str] = None,
        metadata: Dict = None
    ) -> str:
        """创建定时任务 (便捷方法)"""
        task = ScheduledTask(
            id=str(uuid.uuid4())[:8],
            name=name,
            task_type=task_type,
            payload=payload,
            priority=priority,
            cron_expression=cron_expression,
            interval_seconds=interval_seconds,
            run_at=run_at,
            timeout=timeout,
            max_retries=max_retries,
            depends_on=depends_on or [],
            metadata=metadata or {}
        )
        return self.schedule_task(task)
    
    def cancel_task(self, task_id: str) -> bool:
        """取消定时任务"""
        if task_id in self.scheduled_tasks:
            self.scheduled_tasks[task_id].enabled = False
            self._save_state()
            return True
        return False
    
    def pause_task(self, task_id: str) -> bool:
        """暂停任务"""
        if task_id in self.scheduled_tasks:
            self.scheduled_tasks[task_id].enabled = False
            self._save_state()
            return True
        return False
    
    def resume_task(self, task_id: str) -> bool:
        """恢复任务"""
        if task_id in self.scheduled_tasks:
            self.scheduled_tasks[task_id].enabled = True
            self.scheduled_tasks[task_id].next_run = self._calculate_next_run(
                self.scheduled_tasks[task_id]
            )
            self._save_state()
            return True
        return False
    
    def _check_dependencies(self, instance: TaskInstance) -> bool:
        """检查任务依赖是否满足"""
        for dep_id in instance.depends_on:
            dep_instance = self.task_instances.get(dep_id)
            if not dep_instance or dep_instance.status != "completed":
                return False
        return True
    
    def _enqueue_instance(self, instance: TaskInstance):
        """将任务实例加入队列"""
        if not self._check_dependencies(instance):
            # 等待依赖
            for dep_id in instance.depends_on:
                self.pending_dependency[dep_id].append(instance)
            return
        
        # 加入优先级队列
        heapq.heappush(self.priority_queue, instance)
    
    def _process_dependencies(self, completed_id: str):
        """处理依赖完成后的任务"""
        waiting = self.pending_dependency.pop(completed_id, [])
        for instance in waiting:
            if self._check_dependencies(instance):
                heapq.heappush(self.priority_queue, instance)
    
    def trigger_task(self, scheduled_task_id: str, payload: Dict = None) -> Optional[str]:
        """手动触发定时任务"""
        scheduled = self.scheduled_tasks.get(scheduled_task_id)
        if not scheduled:
            return None
        
        instance = TaskInstance(
            id=str(uuid.uuid4())[:8],
            scheduled_task_id=scheduled_task_id,
            name=scheduled.name,
            task_type=scheduled.task_type,
            payload=payload or scheduled.payload,
            priority=scheduled.priority,
            depends_on=scheduled.depends_on,
            timeout=scheduled.timeout,
            max_retries=scheduled.max_retries
        )
        
        self.task_instances[instance.id] = instance
        self._enqueue_instance(instance)
        
        return instance.id
    
    def get_next_task(self) -> Optional[TaskInstance]:
        """获取下一个待执行任务"""
        while self.priority_queue:
            instance = heapq.heappop(self.priority_queue)
            # 跳过已取消的任务
            if instance.status == "cancelled":
                continue
            return instance
        return None
    
    def start_task(self, instance_id: str) -> bool:
        """开始执行任务"""
        instance = self.task_instances.get(instance_id)
        if not instance or instance.status != "pending":
            return False
        
        instance.status = "running"
        instance.started_at = datetime.now().isoformat()
        self.task_instances[instance_id] = instance
        return True
    
    def complete_task(self, instance_id: str, result: Dict = None):
        """完成任务"""
        instance = self.task_instances.get(instance_id)
        if not instance:
            return
        
        instance.status = "completed"
        instance.completed_at = datetime.now().isoformat()
        instance.result = result
        
        # 更新统计
        self.stats["total_completed"] += 1
        if instance.started_at:
            start = datetime.fromisoformat(instance.started_at.replace('Z', '+00:00'))
            elapsed = (datetime.now() - start).total_seconds()
            # 滑动平均
            n = self.stats["total_completed"]
            self.stats["avg_execution_time"] = (
                (self.stats["avg_execution_time"] * (n-1) + elapsed) / n
            )
        
        # 处理依赖
        self._process_dependencies(instance_id)
        
        # 更新定时任务
        scheduled = self.scheduled_tasks.get(instance.scheduled_task_id)
        if scheduled:
            scheduled.last_run = instance.completed_at
            scheduled.run_count += 1
            scheduled.next_run = self._calculate_next_run(scheduled)
        
        self._save_state()
    
    def fail_task(self, instance_id: str, error: str):
        """任务失败"""
        instance = self.task_instances.get(instance_id)
        if not instance:
            return
        
        if instance.retry_count < instance.max_retries:
            # 重试
            instance.retry_count += 1
            instance.status = "pending"
            instance.error = error
            heapq.heappush(self.priority_queue, instance)
        else:
            # 最终失败
            instance.status = "failed"
            instance.completed_at = datetime.now().isoformat()
            instance.error = error
            self.stats["total_failed"] += 1
            self._process_dependencies(instance_id)
        
        self._save_state()
    
    def cancel_instance(self, instance_id: str) -> bool:
        """取消任务实例"""
        instance = self.task_instances.get(instance_id)
        if not instance or instance.status in ["completed", "failed"]:
            return False
        
        instance.status = "cancelled"
        instance.completed_at = datetime.now().isoformat()
        self.stats["total_cancelled"] += 1
        self._save_state()
        return True
    
    def get_task_status(self, instance_id: str) -> Optional[Dict]:
        """获取任务状态"""
        instance = self.task_instances.get(instance_id)
        return instance.to_dict() if instance else None
    
    def list_scheduled_tasks(self) -> List[Dict]:
        """列出所有定时任务"""
        return [
            {
                "id": t.id,
                "name": t.name,
                "task_type": t.task_type,
                "priority": t.priority,
                "enabled": t.enabled,
                "cron": t.cron_expression,
                "interval": t.interval_seconds,
                "run_at": t.run_at,
                "next_run": t.next_run,
                "last_run": t.last_run,
                "run_count": t.run_count
            }
            for t in self.scheduled_tasks.values()
        ]
    
    def list_running_tasks(self) -> List[Dict]:
        """列出运行中的任务"""
        return [
            inst.to_dict()
            for inst in self.task_instances.values()
            if inst.status == "running"
        ]
    
    def list_pending_tasks(self) -> List[Dict]:
        """列出等待中的任务"""
        return [inst.to_dict() for inst in self.priority_queue]
    
    def get_stats(self) -> Dict:
        """获取调度器统计"""
        return {
            **self.stats,
            "scheduled_tasks": len(self.scheduled_tasks),
            "running_tasks": len(self.list_running_tasks()),
            "pending_tasks": len(self.priority_queue)
        }
    
    def _scheduler_loop(self):
        """调度器主循环"""
        while self.is_running:
            try:
                now = datetime.now()
                
                # 检查并触发到期的定时任务
                for task in self.scheduled_tasks.values():
                    if not task.enabled:
                        continue
                    
                    if task.next_run:
                        next_run = datetime.fromisoformat(task.next_run.replace('Z', '+00:00'))
                        if now >= next_run:
                            self.trigger_task(task.id)
                            task.next_run = self._calculate_next_run(task)
                
                self._save_state()
                
            except Exception as e:
                print(f"Scheduler error: {e}")
            
            time.sleep(1)  # 每秒检查
    
    def start(self):
        """启动调度器"""
        if not self.is_running:
            self.is_running = True
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self.scheduler_thread.start()
            self._save_state()
    
    def stop(self):
        """停止调度器"""
        self.is_running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        self._save_state()


# 全局调度器实例
_scheduler: Optional[TaskSchedulerV2] = None


def get_scheduler() -> TaskSchedulerV2:
    """获取全局调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskSchedulerV2()
    return _scheduler


if __name__ == "__main__":
    # 测试
    scheduler = get_scheduler()
    
    # 创建定时任务
    task_id = scheduler.create_task(
        name="健康检查任务",
        task_type="health_check",
        payload={"target": "all"},
        priority=7,
        interval_seconds=60,  # 每60秒执行一次
        timeout=30.0,
        max_retries=3
    )
    
    print(f"创建定时任务: {task_id}")
    print(f"定时任务列表: {scheduler.list_scheduled_tasks()}")
    print(f"调度器统计: {scheduler.get_stats()}")
    
    # 触发任务
    instance_id = scheduler.trigger_task(task_id)
    print(f"触发任务实例: {instance_id}")
    
    # 获取任务
    task = scheduler.get_task_status(instance_id)
    print(f"任务状态: {task}")
    
    # 开始执行
    scheduler.start_task(instance_id)
    print(f"任务开始执行")
    
    # 完成
    scheduler.complete_task(instance_id, {"result": "success"})
    print(f"任务完成")
    
    print(f"最终统计: {scheduler.get_stats()}")
    print("✅ 任务调度器V2测试通过")