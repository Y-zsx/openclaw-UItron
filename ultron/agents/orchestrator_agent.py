#!/usr/bin/env python3
"""
编排Agent - 多智能体协作核心
负责任务调度、agent协调、工作流编排
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AGENTS_DIR)

# 导入编排器
from orchestrator import CollaborationOrchestrator, CollaborationConfig, get_orchestrator, TaskPriority, AgentCapability


class OrchestratorAgent:
    """编排Agent - 多智能体协作调度核心"""
    
    def __init__(self):
        self.name = "orchestrator"
        self.version = "1.0"
        self.orch = None
        self.task_history = []
        
    def initialize(self):
        """初始化编排器"""
        if self.orch is None:
            config = CollaborationConfig(
                enable_conflict_resolution=True,
                enable_efficiency_tracking=True,
                task_timeout=60.0,
                max_retries=3
            )
            self.orch = CollaborationOrchestrator(config)
            self.orch.initialize()
        return {"status": "initialized", "name": self.name, "version": self.version}
    
    def orchestrate(self, task: Dict) -> Dict:
        """
        编排任务 - 核心方法
        将任务分发给合适的agent执行
        """
        if self.orch is None:
            self.initialize()
            
        task_id = task.get("id", f"task_{int(datetime.now().timestamp()*1000)}")
        task_name = task.get("name", "未命名任务")
        task_type = task.get("type", "execute")
        priority = task.get("priority", "normal")
        payload = task.get("data", {})
        
        # 映射任务类型到Agent能力
        # 注意: 使用EXECUTOR作为默认,系统会智能路由
        capability_map = {
            "execute": AgentCapability.EXECUTOR,
            "monitor": AgentCapability.MONITOR,
            "learn": AgentCapability.LEARNER,
            "send": AgentCapability.MESSENGER,
            "analyze": AgentCapability.EXECUTOR,  # 分析也通过执行器
            "orchestrate": AgentCapability.EXECUTOR  # 编排也通过执行器
        }
        
        # 映射优先级
        priority_map = {
            "low": TaskPriority.LOW,
            "normal": TaskPriority.NORMAL,
            "high": TaskPriority.HIGH,
            "critical": TaskPriority.URGENT
        }
        
        capability = capability_map.get(task_type, AgentCapability.EXECUTOR)
        task_priority = priority_map.get(priority, TaskPriority.NORMAL)
        
        # 提交任务
        submitted_id = self.orch.submit_task(
            task_name=task_name,
            capability=capability,
            priority=task_priority,
            complexity=payload.get("complexity", 1),
            payload=payload
        )
        
        result = {
            "task_id": submitted_id,
            "status": "dispatched",
            "capability": capability.value,
            "priority": task_priority.value,
            "timestamp": datetime.now().isoformat()
        }
        
        self.task_history.append(result)
        return result
    
    def execute_workflow(self, workflow: Dict) -> Dict:
        """
        执行工作流 - 按顺序执行多个任务
        """
        if self.orch is None:
            self.initialize()
            
        workflow_id = workflow.get("id", f"wf_{int(datetime.now().timestamp()*1000)}")
        tasks = workflow.get("tasks", [])
        
        results = []
        for task in tasks:
            result = self.orchestrate(task)
            results.append(result)
            
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "task_count": len(tasks),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_status(self) -> Dict:
        """获取系统状态"""
        if self.orch is None:
            return {"status": "not_initialized"}
        
        return self.orch.get_system_status()
    
    def get_report(self) -> Dict:
        """获取完整报告"""
        if self.orch is None:
            return {"status": "not_initialized"}
        
        return self.orch.get_full_report()
    
    def complete_task(self, agent_id: str, task_id: str, success: bool = True):
        """完成任务"""
        if self.orch:
            self.orch.complete_task(agent_id, task_id, success)


# 全局单例
_agent = None

def get_agent() -> OrchestratorAgent:
    global _agent
    if _agent is None:
        _agent = OrchestratorAgent()
    return _agent


# CLI接口
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="编排Agent")
    parser.add_argument("action", choices=["init", "status", "report", "orchestrate"], help="操作")
    parser.add_argument("--task", type=str, help="任务JSON字符串")
    
    args = parser.parse_args()
    
    agent = get_agent()
    
    if args.action == "init":
        result = agent.initialize()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.action == "status":
        result = agent.get_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.action == "report":
        result = agent.get_report()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.action == "orchestrate":
        if args.task:
            task = json.loads(args.task)
            result = agent.orchestrate(task)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("错误: 需要 --task 参数")