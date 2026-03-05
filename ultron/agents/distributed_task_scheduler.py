#!/usr/bin/env python3
"""
多智能体协作网络 - 分布式任务调度器
Distributed Task Scheduler
"""

import time
import uuid
import threading
import json
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional, Callable
from enum import Enum
import heapq

class TaskPriority(Enum):
    """任务优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SCHEDULED = "scheduled"

class Task:
    """任务"""
    
    def __init__(self, task_id: str, task_type: str, payload: dict,
                 priority: TaskPriority = TaskPriority.NORMAL,
                 scheduled_time: datetime = None, ttl: int = 3600):
        self.task_id = task_id
        self.task_type = task_type
        self.payload = payload
        self.priority = priority
        self.status = TaskStatus.PENDING
        self.scheduled_time = scheduled_time or datetime.now()
        self.start_time = None
        self.end_time = None
        self.result = None
        self.error = None
        self.retries = 0
        self.max_retries = 3
        self.ttl = ttl
        self.assigned_agent = None
        self.created_at = datetime.now()
    
    def to_dict(self) -> dict:
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'priority': self.priority.value,
            'status': self.status.value,
            'scheduled_time': self.scheduled_time.isoformat(),
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'result': self.result,
            'error': self.error,
            'retries': self.retries,
            'assigned_agent': self.assigned_agent
        }

class DistributedScheduler:
    """分布式任务调度器"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.pending_queue: List[Task] = []  # 优先级队列
        self.running_tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        
        self._lock = threading.RLock()
        self._task_handlers: Dict[str, Callable] = {}
        self._agents: Dict[str, dict] = {}
        
        self._scheduler_thread = None
        self._running = False
        
        # 统计
        self._stats = {
            'total_scheduled': 0,
            'total_completed': 0,
            'total_failed': 0
        }
    
    def register_handler(self, task_type: str, handler: Callable):
        """注册任务处理器"""
        self._task_handlers[task_type] = handler
    
    def register_agent(self, agent_id: str, agent_type: str, capabilities: List[str]):
        """注册Agent"""
        with self._lock:
            self._agents[agent_id] = {
                'type': agent_type,
                'capabilities': capabilities,
                'current_load': 0,
                'max_load': 10,
                'status': 'idle'
            }
    
    def submit_task(self, task_type: str, payload: dict,
                   priority: TaskPriority = TaskPriority.NORMAL,
                   scheduled_time: datetime = None, ttl: int = 3600) -> str:
        """提交任务"""
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        task = Task(task_id, task_type, payload, priority, scheduled_time, ttl)
        
        with self._lock:
            self.tasks[task_id] = task
            heapq.heappush(self.pending_queue, 
                          (-priority.value, task.scheduled_time, task))
            self._stats['total_scheduled'] += 1
        
        # 尝试立即调度
        self._schedule_task()
        
        return task_id
    
    def _schedule_task(self):
        """调度任务"""
        with self._lock:
            while self.pending_queue:
                _, _, task = heapq.heappop(self.pending_queue)
                
                # 检查是否超时
                if (datetime.now() - task.created_at).total_seconds() > task.ttl:
                    task.status = TaskStatus.FAILED
                    task.error = "Task TTL expired"
                    self._stats['total_failed'] += 1
                    continue
                
                # 检查是否到调度时间
                if task.scheduled_time > datetime.now():
                    heapq.heappush(self.pending_queue, 
                                  (-task.priority.value, task.scheduled_time, task))
                    break
                
                # 查找合适的Agent
                agent = self._find_available_agent(task.task_type)
                if not agent:
                    # 放回队列
                    heapq.heappush(self.pending_queue,
                                  (-task.priority.value, task.scheduled_time, task))
                    break
                
                # 分配任务
                self._assign_task(task, agent)
    
    def _find_available_agent(self, task_type: str) -> Optional[str]:
        """查找可用的Agent"""
        with self._lock:
            candidates = []
            for agent_id, agent in self._agents.items():
                if (task_type in agent['capabilities'] and 
                    agent['current_load'] < agent['max_load']):
                    candidates.append((agent_id, agent['current_load']))
            
            if candidates:
                # 选择负载最低的
                candidates.sort(key=lambda x: x[1])
                return candidates[0][0]
        return None
    
    def _assign_task(self, task: Task, agent_id: str):
        """分配任务给Agent"""
        with self._lock:
            task.status = TaskStatus.RUNNING
            task.start_time = datetime.now()
            task.assigned_agent = agent_id
            self.running_tasks[task.task_id] = task
            self._agents[agent_id]['current_load'] += 1
            self._agents[agent_id]['status'] = 'busy'
        
        # 异步执行任务
        threading.Thread(target=self._execute_task, 
                        args=(task, agent_id), daemon=True).start()
    
    def _execute_task(self, task: Task, agent_id: str):
        """执行任务"""
        try:
            handler = self._task_handlers.get(task.task_type)
            if handler:
                task.result = handler(task.payload)
            else:
                task.result = {'status': 'no_handler'}
            
            task.status = TaskStatus.COMPLETED
            task.end_time = datetime.now()
            self._stats['total_completed'] += 1
            
        except Exception as e:
            task.error = str(e)
            task.retries += 1
            
            if task.retries < task.max_retries:
                # 重试
                task.status = TaskStatus.PENDING
                heapq.heappush(self.pending_queue,
                              (-task.priority.value, task.scheduled_time, task))
            else:
                task.status = TaskStatus.FAILED
                task.end_time = datetime.now()
                self._stats['total_failed'] += 1
        
        finally:
            with self._lock:
                if task.task_id in self.running_tasks:
                    del self.running_tasks[task.task_id]
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    self.completed_tasks[task.task_id] = task
                if agent_id in self._agents:
                    self._agents[agent_id]['current_load'] = max(0, 
                        self._agents[agent_id]['current_load'] - 1)
                    if self._agents[agent_id]['current_load'] == 0:
                        self._agents[agent_id]['status'] = 'idle'
            
            # 继续调度
            self._schedule_task()
    
    def get_task_status(self, task_id: str) -> Optional[dict]:
        """获取任务状态"""
        with self._lock:
            for collection in [self.tasks, self.running_tasks, self.completed_tasks]:
                if task_id in collection:
                    return collection[task_id].to_dict()
        return None
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        with self._lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.CANCELLED
                    return True
        return False
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._lock:
            return {
                'total_scheduled': self._stats['total_scheduled'],
                'total_completed': self._stats['total_completed'],
                'total_failed': self._stats['total_failed'],
                'pending_tasks': len(self.pending_queue),
                'running_tasks': len(self.running_tasks),
                'agents': len(self._agents)
            }
    
    def get_queue_status(self) -> dict:
        """获取队列状态"""
        with self._lock:
            return {
                'pending': [t.to_dict() for t in self.pending_queue[:10]],
                'running': [t.to_dict() for t in self.running_tasks.values()],
                'recent_completed': [t.to_dict() for t in 
                                    list(self.completed_tasks.values())[-10:]]
            }


# 测试
if __name__ == '__main__':
    print("🔧 分布式任务调度器测试")
    print("="*50)
    
    scheduler = DistributedScheduler()
    
    # 注册Agent
    scheduler.register_agent('agent-001', 'executor', ['compute', 'process'])
    scheduler.register_agent('agent-002', 'analyzer', ['analyze', 'report'])
    scheduler.register_agent('agent-003', 'general', ['compute', 'analyze', 'process'])
    
    # 注册处理器
    def compute_handler(payload):
        time.sleep(0.1)
        return {'result': sum(payload.get('numbers', [1,2,3]))}
    
    def analyze_handler(payload):
        time.sleep(0.1)
        return {'result': f"Analyzed: {payload.get('data', 'N/A')}"}
    
    scheduler.register_handler('compute', compute_handler)
    scheduler.register_handler('analyze', analyze_handler)
    
    # 提交任务
    print("\n📝 提交任务:")
    for i in range(5):
        task_id = scheduler.submit_task('compute', 
                                        {'numbers': [i, i+1, i+2]},
                                        priority=TaskPriority.NORMAL)
        print(f"  任务 {i+1}: {task_id}")
    
    task_id = scheduler.submit_task('analyze', 
                                    {'data': 'test data'},
                                    priority=TaskPriority.HIGH)
    print(f"  高优先级任务: {task_id}")
    
    # 等待执行
    time.sleep(1)
    
    print("\n📊 统计:")
    stats = scheduler.get_stats()
    print(json.dumps(stats, indent=2))
    
    print("\n✅ 调度器测试完成")