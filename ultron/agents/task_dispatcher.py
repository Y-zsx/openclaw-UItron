#!/usr/bin/env python3
"""
任务分发器 - 多智能体协作网络
第3世：协作优化 - 任务分发算法
"""

import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4

class AgentCapability(Enum):
    MONITOR = "monitor"
    EXECUTOR = "executor"
    LEARNER = "learner"
    MESSENGER = "messenger"

@dataclass
class Agent:
    id: str
    name: str
    capability: AgentCapability
    workload: int = 0
    max_load: int = 10
    available: bool = True
    success_rate: float = 1.0

@dataclass
class Task:
    id: str
    name: str
    required_capability: AgentCapability
    priority: TaskPriority = TaskPriority.NORMAL
    estimated_complexity: int = 1  # 1-5
    payload: Dict[str, Any] = None
    created_at: float = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.payload is None:
            self.payload = {}

class TaskDispatcher:
    """智能任务分发器"""
    
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.task_queue: List[Task] = []
        self.completed_tasks: List[Task] = []
        self.load_history: List[Dict] = []
        
    def register_agent(self, agent: Agent) -> bool:
        """注册代理"""
        if agent.id in self.agents:
            return False
        self.agents[agent.id] = agent
        return True
    
    def unregister_agent(self, agent_id: str) -> bool:
        """注销代理"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            return True
        return False
    
    def add_task(self, task: Task) -> str:
        """添加任务到队列"""
        self.task_queue.append(task)
        self._sort_by_priority()
        return task.id
    
    def _sort_by_priority(self):
        """按优先级排序"""
        priority_weights = {
            TaskPriority.URGENT: 4,
            TaskPriority.HIGH: 3,
            TaskPriority.NORMAL: 2,
            TaskPriority.LOW: 1
        }
        self.task_queue.sort(
            key=lambda t: (priority_weights[t.priority], -t.created_at),
            reverse=True
        )
    
    def dispatch(self) -> Optional[Dict[str, Any]]:
        """分发任务给最合适的代理"""
        if not self.task_queue:
            return None
            
        task = self.task_queue.pop(0)
        
        # 筛选可用代理
        suitable_agents = [
            a for a in self.agents.values()
            if a.capability == task.required_capability
            and a.available
            and a.workload < a.max_load
        ]
        
        if not suitable_agents:
            # 没有合适代理，任务放回队列
            self.task_queue.insert(0, task)
            return None
        
        # 选择最优代理（负载最低 + 成功率最高）
        best_agent = min(
            suitable_agents,
            key=lambda a: (a.workload / a.max_load, -a.success_rate)
        )
        
        # 更新代理负载
        best_agent.workload += task.estimated_complexity
        
        return {
            "task_id": task.id,
            "task_name": task.name,
            "assigned_agent": best_agent.id,
            "agent_name": best_agent.name,
            "dispatch_time": time.time()
        }
    
    def complete_task(self, agent_id: str, task_id: str, success: bool = True):
        """完成任务，释放代理负载"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            # 查找任务复杂度
            for task in self.completed_tasks:
                if task.id == task_id:
                    agent.workload -= task.estimated_complexity
                    break
    
    def get_load_balance(self) -> Dict[str, Any]:
        """获取负载均衡状态"""
        total_load = sum(a.workload for a in self.agents.values())
        avg_load = total_load / len(self.agents) if self.agents else 0
        
        return {
            "total_agents": len(self.agents),
            "total_load": total_load,
            "average_load": avg_load,
            "agent_loads": {
                a.id: {
                    "name": a.name,
                    "workload": a.workload,
                    "max_load": a.max_load,
                    "utilization": a.workload / a.max_load if a.max_load > 0 else 0,
                    "available": a.available
                }
                for a in self.agents.values()
            }
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "queue_length": len(self.task_queue),
            "completed_count": len(self.completed_tasks),
            "active_agents": sum(1 for a in self.agents.values() if a.available),
            "load_balance": self.get_load_balance()
        }

# 单例实例
_dispatcher = None

def get_dispatcher() -> TaskDispatcher:
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = TaskDispatcher()
    return _dispatcher

if __name__ == "__main__":
    # 测试
    dispatcher = get_dispatcher()
    
    # 注册代理
    dispatcher.register_agent(Agent("a1", "Monitor-1", AgentCapability.MONITOR))
    dispatcher.register_agent(Agent("a2", "Executor-1", AgentCapability.EXECUTOR))
    dispatcher.register_agent(Agent("a3", "Learner-1", AgentCapability.LEARNER))
    
    # 添加任务
    dispatcher.add_task(Task("t1", "监控任务", AgentCapability.MONITOR, TaskPriority.HIGH, 3))
    dispatcher.add_task(Task("t2", "执行任务", AgentCapability.EXECUTOR, TaskPriority.NORMAL, 2))
    dispatcher.add_task(Task("t3", "学习任务", AgentCapability.LEARNER, TaskPriority.LOW, 1))
    
    print("Stats:", json.dumps(dispatcher.get_stats(), indent=2))
    print("Dispatch:", dispatcher.dispatch())
    print("Load:", json.dumps(dispatcher.get_load_balance(), indent=2))