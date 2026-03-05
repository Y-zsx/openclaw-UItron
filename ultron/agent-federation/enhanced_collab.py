#!/usr/bin/env python3
"""
增强的多智能体协作网络
- 智能任务分配
- 动态负载均衡
- 跨Agent协同决策
- 性能优化
"""

import asyncio
import json
import time
import random
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import hashlib

class CollabMetrics:
    def __init__(self):
        self.task_counts = defaultdict(int)
        self.response_times = defaultdict(list)
        self.success_rates = defaultdict(float)
        self.load_scores = defaultdict(float)
        self.last_update = {}
    
    def record_task(self, agent_id: str, duration: float, success: bool):
        self.task_counts[agent_id] += 1
        self.response_times[agent_id].append(duration)
        if len(self.response_times[agent_id]) > 100:
            self.response_times[agent_id] = self.response_times[agent_id][-100:]
        
        # 更新成功率
        total = self.task_counts[agent_id]
        successes = sum(1 for s in self.success_rates if s)
        if total > 0:
            self.success_rates[agent_id] = successes / total
        
        self.last_update[agent_id] = time.time()
    
    def get_load_score(self, agent_id: str) -> float:
        """计算Agent负载分数 (0-100)"""
        task_count = self.task_counts.get(agent_id, 0)
        avg_response = sum(self.response_times.get(agent_id, [1])) / max(len(self.response_times.get(agent_id, [1])), 1)
        
        # 负载分数 = 任务数 * 0.3 + 平均响应时间 * 0.7
        score = min(100, task_count * 2 + avg_response * 0.5)
        self.load_scores[agent_id] = score
        return score
    
    def get_best_agent(self, agents: List[str], task_type: str = "general") -> str:
        """选择最佳Agent进行任务分配"""
        if not agents:
            return ""
        
        best_agent = None
        best_score = float('inf')
        
        for agent_id in agents:
            load = self.get_load_score(agent_id)
            success = self.success_rates.get(agent_id, 1.0)
            
            # 综合分数: 负载越低越好, 成功率越高越好
            composite_score = load * 0.7 + (1 - success) * 30
            
            if composite_score < best_score:
                best_score = composite_score
                best_agent = agent_id
        
        return best_agent or agents[0]

class TaskCoordinator:
    def __init__(self):
        self.pending_tasks = []
        self.active_tasks = {}
        self.completed_tasks = []
        self.task_dependencies = defaultdict(list)
        self.metrics = CollabMetrics()
    
    def create_task(self, task_id: str, agent_ids: List[str], task_type: str = "general", priority: int = 5) -> Dict:
        """创建新任务"""
        task = {
            "id": task_id,
            "agents": agent_ids,
            "type": task_type,
            "priority": priority,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "assigned_agent": None,
            "result": None
        }
        
        # 智能选择最佳Agent
        if agent_ids:
            best_agent = self.metrics.get_best_agent(agent_ids, task_type)
            task["assigned_agent"] = best_agent
        
        self.pending_tasks.append(task)
        return task
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """分配任务给Agent"""
        for task in self.pending_tasks:
            if task["id"] == task_id:
                task["status"] = "assigned"
                task["assigned_agent"] = agent_id
                task["assigned_at"] = datetime.now().isoformat()
                self.active_tasks[task_id] = task
                self.pending_tasks.remove(task)
                return True
        return False
    
    def complete_task(self, task_id: str, result: Any, success: bool = True):
        """完成任务"""
        if task_id in self.active_tasks:
            task = self.active_tasks[task_id]
            task["status"] = "completed"
            task["result"] = result
            task["success"] = success
            task["completed_at"] = datetime.now().isoformat()
            
            # 记录指标
            if "assigned_at" in task:
                duration = (datetime.fromisoformat(task["completed_at"]) - 
                           datetime.fromisoformat(task["assigned_at"])).total_seconds()
                self.metrics.record_task(task["assigned_agent"], duration, success)
            
            self.completed_tasks.append(task)
            del self.active_tasks[task_id]
            
            # 检查依赖任务
            self._check_dependencies(task_id)
    
    def _check_dependencies(self, completed_task_id: str):
        """检查并激活依赖任务"""
        for task in self.pending_tasks:
            if completed_task_id in task.get("dependencies", []):
                task["dependencies"].remove(completed_task_id)
                if not task["dependencies"]:
                    # 所有依赖满足，可以执行
                    if task["agents"]:
                        best = self.metrics.get_best_agent(task["agents"], task["type"])
                        self.assign_task(task["id"], best)
    
    def get_status(self) -> Dict:
        """获取协作状态"""
        return {
            "pending": len(self.pending_tasks),
            "active": len(self.active_tasks),
            "completed": len(self.completed_tasks),
            "agents": {
                agent: {
                    "load_score": self.metrics.get_load_score(agent),
                    "task_count": self.metrics.task_counts.get(agent, 0),
                    "success_rate": self.metrics.success_rates.get(agent, 1.0)
                }
                for agent in set(self.metrics.task_counts.keys())
            }
        }

class CollabEnhancer:
    def __init__(self):
        self.coordinator = TaskCoordinator()
        self.agent_registry = {}
        self.collab_patterns = defaultdict(list)
    
    def register_agent(self, agent_id: str, capabilities: List[str], endpoint: str):
        """注册Agent"""
        self.agent_registry[agent_id] = {
            "id": agent_id,
            "capabilities": capabilities,
            "endpoint": endpoint,
            "registered_at": datetime.now().isoformat(),
            "status": "active"
        }
    
    def find_agents_by_capability(self, capability: str) -> List[str]:
        """根据能力查找Agent"""
        return [
            agent_id for agent_id, info in self.agent_registry.items()
            if capability in info["capabilities"] and info["status"] == "active"
        ]
    
    def optimize_task_distribution(self, tasks: List[Dict]) -> List[Dict]:
        """优化任务分配"""
        optimized = []
        
        for task in tasks:
            task_type = task.get("type", "general")
            required_capability = task.get("capability", task_type)
            
            # 找到具有所需能力的Agent
            capable_agents = self.find_agents_by_capability(required_capability)
            
            if capable_agents:
                # 选择最佳Agent
                best_agent = self.coordinator.metrics.get_best_agent(capable_agents, task_type)
                task["assigned_agent"] = best_agent
                
                # 更新负载
                task["estimated_load"] = self.coordinator.metrics.get_load_score(best_agent)
            
            optimized.append(task)
        
        return optimized
    
    def get_collab_analytics(self) -> Dict:
        """获取协作分析数据"""
        status = self.coordinator.get_status()
        
        # 计算整体健康度
        total_tasks = status["completed"] + status["active"] + status["pending"]
        success_count = sum(1 for t in self.coordinator.completed_tasks if t.get("success", False))
        success_rate = success_count / max(status["completed"], 1)
        
        # 平均响应时间
        all_response_times = []
        for times in self.coordinator.metrics.response_times.values():
            all_response_times.extend(times)
        avg_response = sum(all_response_times) / max(len(all_response_times), 1)
        
        return {
            "status": status,
            "health_score": success_rate * 100 * 0.7 + (100 - avg_response) * 0.3,
            "success_rate": success_rate,
            "avg_response_time": avg_response,
            "total_agents": len(self.agent_registry),
            "active_agents": sum(1 for a in self.agent_registry.values() if a["status"] == "active")
        }

# 全局实例
enhancer = CollabEnhancer()

if __name__ == "__main__":
    # 测试增强功能
    print("=== 多智能体协作网络增强 ===")
    
    # 注册测试Agent
    enhancer.register_agent("agent-1", ["compute", "execute"], "http://localhost:8001")
    enhancer.register_agent("agent-2", ["compute", "analyze"], "http://localhost:8002")
    enhancer.register_agent("agent-3", ["notify", "execute"], "http://localhost:8003")
    
    # 创建测试任务
    task1 = enhancer.coordinator.create_task(
        "task-1", 
        ["agent-1", "agent-2"],
        "compute",
        priority=8
    )
    print(f"创建任务: {task1}")
    
    # 分析
    analytics = enhancer.get_collab_analytics()
    print(f"协作分析: {json.dumps(analytics, indent=2)}")