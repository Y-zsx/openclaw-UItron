#!/usr/bin/env python3
"""
统一编排器 - 多智能体协作网络
第4世：系统集成与测试 - 统一调度中心
"""

import json
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

# 导入各模块
from task_dispatcher import TaskDispatcher, Task, TaskPriority, AgentCapability, Agent, get_dispatcher
from conflict_resolver import ConflictResolver, Resource, get_resolver
from efficiency_analyzer import EfficiencyAnalyzer, get_analyzer

class SystemState(Enum):
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    ERROR = "error"

@dataclass
class CollaborationConfig:
    enable_conflict_resolution: bool = True
    enable_efficiency_tracking: bool = True
    task_timeout: float = 60.0
    max_retries: int = 3

class CollaborationOrchestrator:
    """多智能体协作统一编排器"""
    
    def __init__(self, config: CollaborationConfig = None):
        self.config = config or CollaborationConfig()
        self.dispatcher = get_dispatcher()
        self.resolver = get_resolver()
        self.analyzer = get_analyzer()
        self.state = SystemState.INITIALIZING
        self.start_time = None
        self.event_handlers: Dict[str, List[Callable]] = {
            "task_dispatched": [],
            "task_completed": [],
            "conflict_detected": [],
            "conflict_resolved": []
        }
        
    def initialize(self):
        """初始化系统"""
        self._register_default_resources()
        self._register_default_agents()
        self.state = SystemState.RUNNING
        self.start_time = time.time()
        print("系统初始化完成")
        
    def _register_default_resources(self):
        """注册默认资源"""
        resources = [
            Resource("db_main", "主数据库", "database"),
            Resource("api_gateway", "API网关", "api"),
            Resource("file_storage", "文件存储", "file"),
        ]
        for r in resources:
            self.resolver.register_resource(r)
            
    def _register_default_agents(self):
        """注册默认代理"""
        agents = [
            Agent("monitor_1", "监控代理-1", AgentCapability.MONITOR),
            Agent("executor_1", "执行代理-1", AgentCapability.EXECUTOR),
            Agent("learner_1", "学习代理-1", AgentCapability.LEARNER),
            Agent("messenger_1", "通信代理-1", AgentCapability.MESSENGER),
        ]
        for a in agents:
            self.dispatcher.register_agent(a)
            
    def submit_task(self, task_name: str, capability: AgentCapability, 
                   priority: TaskPriority = TaskPriority.NORMAL,
                   complexity: int = 1, payload: Dict = None) -> str:
        """提交任务"""
        task = Task(
            id=f"task_{int(time.time() * 1000)}",
            name=task_name,
            required_capability=capability,
            priority=priority,
            estimated_complexity=complexity,
            payload=payload or {}
        )
        
        task_id = self.dispatcher.add_task(task)
        
        # 记录到效率分析器
        dispatch_result = self.dispatcher.dispatch()
        if dispatch_result:
            self.analyzer.add_task(
                task.id, task_name, 
                dispatch_result["assigned_agent"],
                dispatch_result["agent_name"],
                complexity
            )
            self._trigger_event("task_dispatched", dispatch_result)
            
        return task_id
    
    def dispatch_pending_tasks(self) -> List[Dict]:
        """分发所有待处理任务"""
        results = []
        while True:
            result = self.dispatcher.dispatch()
            if result:
                results.append(result)
                self._trigger_event("task_dispatched", result)
            else:
                break
        return results
    
    def complete_task(self, agent_id: str, task_id: str, success: bool = True):
        """完成任务"""
        self.dispatcher.complete_task(agent_id, task_id, success)
        self.analyzer.record_task_complete(task_id, success)
        
        # 释放代理持有的所有资源
        for resource_id in list(self.resolver.agent_locks.get(agent_id, [])):
            self.resolver.release_lock(agent_id, resource_id)
            
        self._trigger_event("task_completed", {"task_id": task_id, "success": success})
    
    def resolve_conflict(self, conflict_id: str) -> str:
        """解决冲突"""
        result = self.resolver.resolve_resource_conflict(conflict_id)
        self._trigger_event("conflict_resolved", {"conflict_id": conflict_id, "result": result})
        return result
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        uptime = time.time() - self.start_time if self.start_time else 0
        
        return {
            "state": self.state.value,
            "uptime_seconds": round(uptime, 2),
            "dispatcher": self.dispatcher.get_stats(),
            "resolver": self.resolver.get_conflict_stats(),
            "efficiency": self.analyzer.get_collaboration_score(),
            "bottlenecks": self.analyzer.get_bottlenecks()
        }
    
    def get_full_report(self) -> Dict[str, Any]:
        """获取完整报告"""
        return {
            "system_status": self.get_system_status(),
            "efficiency_report": self.analyzer.get_report(),
            "timestamp": time.time()
        }
    
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

# 全局单例
_orchestrator = None

def get_orchestrator() -> CollaborationOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = CollaborationOrchestrator()
        _orchestrator.initialize()
    return _orchestrator

if __name__ == "__main__":
    # 测试
    orch = get_orchestrator()
    
    # 提交任务
    orch.submit_task("系统监控", AgentCapability.MONITOR, TaskPriority.HIGH, 2)
    orch.submit_task("执行部署", AgentCapability.EXECUTOR, TaskPriority.NORMAL, 3)
    orch.submit_task("数据分析", AgentCapability.LEARNER, TaskPriority.LOW, 1)
    
    # 获取状态
    print(json.dumps(orch.get_system_status(), indent=2, ensure_ascii=False))