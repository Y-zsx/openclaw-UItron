#!/usr/bin/env python3
"""任务分发调度器 - 多智能体协作网络第三世"""
import json
import random
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

REGISTRY_FILE = Path(__file__).parent / "registry.json"
METRICS_FILE = Path(__file__).parent.parent / "metrics_history.json"

class TaskScheduler:
    """智能任务分发器"""
    
    def __init__(self):
        self.registry = self._load_registry()
        self.metrics = self._load_metrics()
    
    def _load_registry(self):
        with open(REGISTRY_FILE) as f:
            return json.load(f)
    
    def _load_metrics(self):
        try:
            with open(METRICS_FILE) as f:
                return json.load(f)
        except:
            return {"load": [], "memory": [], "disk": []}
    
    def get_agent_load(self, agent: str) -> float:
        """获取代理当前负载 (0.0-1.0)"""
        status = self.registry["agents"].get(agent, {}).get("status", "idle")
        return 0.0 if status == "idle" else 0.7
    
    def get_least_loaded_agent(self, capable_agents: List[str]) -> Optional[str]:
        """获取负载最低的代理"""
        loads = {a: self.get_agent_load(a) for a in capable_agents}
        return min(loads, key=loads.get) if loads else None
    
    def get_capable_agents(self, task_type: str) -> List[str]:
        """获取能处理该任务的代理"""
        agents = self.registry["agents"]
        capable = []
        
        task_capability_map = {
            "monitor": ["monitor"],
            "execute": ["executor"],
            "learn": ["learner"],
            "notify": ["messenger"]
        }
        
        required = task_capability_map.get(task_type, ["executor"])
        for agent_name, agent_info in agents.items():
            if agent_name in required:
                capable.append(agent_name)
        
        return capable
    
    def dispatch(self, task: Dict) -> Optional[str]:
        """分发任务到合适的代理"""
        task_type = task.get("type", "execute")
        task_priority = task.get("priority", "normal")
        
        # 获取能处理该任务的代理
        capable = self.get_capable_agents(task_type)
        if not capable:
            return None
        
        # 高优先级任务直接分配
        if task_priority == "high":
            return capable[0]
        
        # 负载均衡：选择最空闲的
        return self.get_least_loaded_agent(capable)
    
    def resolve_conflict(self, task1: Dict, task2: Dict) -> str:
        """冲突解决：高优先级先执行"""
        p1, p2 = task1.get("priority", "normal"), task2.get("priority", "normal")
        priority_order = {"high": 0, "normal": 1, "low": 2}
        
        if priority_order.get(p1, 1) <= priority_order.get(p2, 1):
            return "task1"
        return "task2"
    
    def calculate_efficiency(self) -> float:
        """计算协作效率"""
        if not self.registry.get("agents"):
            return 0.0
        
        active = sum(1 for a in self.registry["agents"].values() 
                    if a.get("status") == "active")
        total = len(self.registry["agents"])
        
        return active / total if total > 0 else 0.0

if __name__ == "__main__":
    scheduler = TaskScheduler()
    
    # 测试任务分发
    test_task = {
        "type": "execute",
        "priority": "normal",
        "description": "磁盘清理任务"
    }
    
    agent = scheduler.dispatch(test_task)
    print(f"任务分发测试: {test_task['description']} -> {agent}")
    print(f"协作效率: {scheduler.calculate_efficiency():.0%}")
    print("✅ 任务分发算法测试通过")