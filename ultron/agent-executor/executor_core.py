#!/usr/bin/env python3
"""
Agent执行器 - 多智能体协作网络核心组件
功能: 任务分发、Agent管理、执行调度
"""
import json
import time
import uuid
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict

@dataclass
class Agent:
    id: str
    name: str
    capabilities: List[str]
    status: str = "idle"
    tasks_completed: int = 0
    current_task: Optional[str] = None

@dataclass
class Task:
    id: str
    type: str
    payload: Dict[str, Any]
    status: str = "pending"
    assigned_agent: Optional[str] = None
    result: Optional[Dict] = None
    created_at: float = 0
    completed_at: Optional[float] = None

class AgentExecutor:
    """Agent执行器核心类"""
    
    CAPABILITIES = ["browser", "exec", "data", "analysis", "communication"]
    
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.tasks: Dict[str, Task] = {}
        self._task_counter = 0
        
    def register_agent(self, name: str, capabilities: List[str]) -> str:
        """注册新Agent"""
        valid_caps = [c for c in capabilities if c in self.CAPABILITIES]
        agent = Agent(
            id=f"agent_{uuid.uuid4().hex[:8]}",
            name=name,
            capabilities=valid_caps
        )
        self.agents[agent.id] = agent
        return agent.id
    
    def submit_task(self, task_type: str, payload: Dict[str, Any]) -> str:
        """提交新任务"""
        task = Task(
            id=f"task_{uuid.uuid4().hex[:8]}",
            type=task_type,
            payload=payload,
            created_at=time.time()
        )
        self.tasks[task.id] = task
        self._task_counter += 1
        return task.id
    
    def get_idle_agent(self, required_capability: str = None) -> Optional[Agent]:
        """获取空闲Agent，优先匹配能力"""
        idle = [a for a in self.agents.values() if a.status == "idle"]
        if not idle:
            return None
        if required_capability:
            for agent in idle:
                if required_capability in agent.capabilities:
                    return agent
        return idle[0]
    
    def execute_task(self, task_id: str) -> Dict[str, Any]:
        """执行任务"""
        task = self.tasks.get(task_id)
        if not task:
            return {"status": "error", "message": "Task not found"}
        
        if task.status != "pending":
            return {"status": "error", "message": f"Task already {task.status}"}
        
        # 分配Agent
        required_cap = task.payload.get("capability")
        agent = self.get_idle_agent(required_cap)
        
        if not agent:
            return {"status": "error", "message": "No idle agent available"}
        
        # 执行
        task.status = "running"
        task.assigned_agent = agent.id
        agent.status = "busy"
        agent.current_task = task.id
        
        try:
            # 模拟执行（实际可接入真实执行环境）
            result = self._run_task(task, agent)
            task.result = result
            task.status = "completed"
            task.completed_at = time.time()
            agent.tasks_completed += 1
        except Exception as e:
            task.status = "failed"
            task.result = {"error": str(e)}
        finally:
            agent.status = "idle"
            agent.current_task = None
            
        return {"status": task.status, "agent": agent.name, "result": task.result}
    
    def _run_task(self, task: Task, agent: Agent) -> Dict:
        """实际运行任务"""
        task_type = task.type
        
        if task_type == "exec":
            return {"executed": True, "output": f"Executed by {agent.name}"}
        elif task_type == "data":
            return {"processed": True, "records": len(str(task.payload))}
        elif task_type == "analysis":
            return {"analyzed": True, "confidence": 0.85}
        else:
            return {"result": "completed"}
    
    def get_status(self) -> Dict:
        """获取执行器状态"""
        return {
            "agents": {aid: asdict(a) for aid, a in self.agents.items()},
            "tasks": {
                "total": len(self.tasks),
                "pending": len([t for t in self.tasks.values() if t.status == "pending"]),
                "running": len([t for t in self.tasks.values() if t.status == "running"]),
                "completed": len([t for t in self.tasks.values() if t.status == "completed"]),
                "failed": len([t for t in self.tasks.values() if t.status == "failed"])
            },
            "capabilities": self.CAPABILITIES
        }

# CLI工具
if __name__ == "__main__":
    executor = AgentExecutor()
    
    # 注册默认Agent
    executor.register_agent("Worker-1", ["exec", "data"])
    executor.register_agent("Worker-2", ["browser", "analysis"])
    executor.register_agent("Worker-3", ["communication", "data"])
    
    print("🤖 Agent执行器初始化完成")
    print(json.dumps(executor.get_status(), indent=2))
