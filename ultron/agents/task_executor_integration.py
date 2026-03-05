#!/usr/bin/env python3
"""
任务执行器集成层
将AgentExecutor与TaskDispatcher集成
"""

import asyncio
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime

# 导入执行器
from agent_executor import (
    AgentExecutor, ExecutionTask, ExecutionType, 
    ExecutionStatus, ExecutionResult, get_executor
)
from task_dispatcher import TaskDispatcher, Task, TaskPriority, AgentCapability, Agent, get_dispatcher


class TaskExecutor集成:
    """任务执行器集成 - 调度+执行一体化"""
    
    def __init__(self):
        self.dispatcher = get_dispatcher()
        self.executor = get_executor()
        self.execution_tasks: Dict[str, ExecutionTask] = {}
        self.results: Dict[str, ExecutionResult] = {}
        
    async def submit_and_execute(self, task: Task) -> ExecutionResult:
        """提交任务并立即执行"""
        # 转换为执行任务
        exec_task = self._task_to_execution(task)
        
        # 注册到分发器 (但不等待调度,直接执行)
        self.dispatcher.add_task(task)
        
        # 执行
        result = await self.executor.execute(exec_task)
        
        # 记录结果
        self.results[task.id] = result
        
        return result
    
    def _task_to_execution(self, task: Task) -> ExecutionTask:
        """将Task转换为ExecutionTask"""
        # 根据能力映射执行类型
        type_map = {
            AgentCapability.MONITOR: ExecutionType.FUNCTION,
            AgentCapability.EXECUTOR: ExecutionType.SHELL,
            AgentCapability.LEARNER: ExecutionType.PYTHON,
            AgentCapability.MESSENGER: ExecutionType.API
        }
        
        exec_type = type_map.get(task.required_capability, ExecutionType.SHELL)
        
        # 从payload提取执行信息
        payload = task.payload or {}
        
        return ExecutionTask(
            task_id=task.id,
            execution_type=exec_type,
            command=payload.get("command", ""),
            func_name=payload.get("function", ""),
            func_args=payload.get("args", []),
            api_config=payload.get("api", {}),
            timeout=payload.get("timeout", 30.0),
            env=payload.get("env", {}),
            cwd=payload.get("cwd", ""),
            max_retry=payload.get("max_retry", 2)
        )
    
    async def execute_pending_tasks(self) -> List[ExecutionResult]:
        """执行所有待处理任务"""
        results = []
        
        # 分发任务
        while True:
            dispatch_result = self.dispatcher.dispatch()
            if not dispatch_result:
                break
                
            task_id = dispatch_result["task_id"]
            
            # 查找对应的原始任务
            # 这里简化处理 - 实际需要更好的映射
            task = Task(
                id=task_id,
                name=dispatch_result["task_name"],
                required_capability=AgentCapability.EXECUTOR,
                priority=TaskPriority.NORMAL,
                payload={}
            )
            
            exec_task = self._task_to_execution(task)
            result = await self.executor.execute(exec_task)
            results.append(result)
            self.results[task_id] = result
            
        return results
    
    def get_task_result(self, task_id: str) -> Optional[Dict]:
        """获取任务结果"""
        if task_id in self.results:
            return self.results[task_id].to_dict()
        return None
    
    def get_combined_stats(self) -> Dict:
        """获取组合统计"""
        return {
            "dispatcher": self.dispatcher.get_stats(),
            "executor": self.executor.get_stats()
        }


# 全局实例
_integration = None

def get_integration() -> TaskExecutor集成:
    global _integration
    if _integration is None:
        _integration = TaskExecutor集成()
    return _integration


if __name__ == "__main__":
    # 测试集成
    integration = get_integration()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # 提交一个任务
    task = Task(
        id="test_task_1",
        name="测试系统状态",
        required_capability=AgentCapability.MONITOR,
        priority=TaskPriority.HIGH,
        payload={
            "function": "get_system_status"
        },
        estimated_complexity=1
    )
    
    result = loop.run_until_complete(integration.submit_and_execute(task))
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    
    print("\n组合统计:")
    print(json.dumps(integration.get_combined_stats(), indent=2))
    
    loop.close()