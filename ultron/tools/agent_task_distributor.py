#!/usr/bin/env python3
"""
Agent Task Distributor - 智能任务分发器
根据Agent能力、负载和历史表现自动分发任务
"""
import json
import time
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import argparse

STATS_FILE = Path("/root/.openclaw/workspace/ultron/data/agent_stats.json")
AGENT_REGISTRY = Path("/root/.openclaw/workspace/ultron/data/agent_registry.json")

class AgentTaskDistributor:
    """智能任务分发器"""
    
    def __init__(self):
        self.stats = self._load_stats()
        self.registry = self._load_registry()
        
    def _load_stats(self) -> Dict:
        """加载统计数据"""
        if STATS_FILE.exists():
            with open(STATS_FILE) as f:
                return json.load(f)
        return {}
    
    def _save_stats(self):
        """保存统计数据"""
        STATS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATS_FILE, 'w') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)
    
    def _load_registry(self) -> Dict:
        """加载Agent注册表"""
        if AGENT_REGISTRY.exists():
            with open(AGENT_REGISTRY) as f:
                return json.load(f)
        return {"agents": {}}
    
    def _save_registry(self):
        """保存注册表"""
        AGENT_REGISTRY.parent.mkdir(parents=True, exist_ok=True)
        with open(AGENT_REGISTRY, 'w') as f:
            json.dump(self.registry, f, indent=2, ensure_ascii=False)
    
    def register_agent(self, agent_id: str, capabilities: List[str], 
                       capacity: int = 5) -> Dict:
        """注册Agent"""
        if "agents" not in self.registry:
            self.registry["agents"] = {}
            
        self.registry["agents"][agent_id] = {
            "capabilities": capabilities,
            "capacity": capacity,
            "current_load": 0,
            "status": "active",
            "registered_at": datetime.now().isoformat()
        }
        
        # 初始化统计
        if agent_id not in self.stats:
            self.stats[agent_id] = {
                "tasks_completed": 0,
                "tasks_failed": 0,
                "avg_completion_time": 0,
                "success_rate": 100.0,
                "last_task": None
            }
        
        self._save_registry()
        self._save_stats()
        
        return {"status": "registered", "agent_id": agent_id}
    
    def update_load(self, agent_id: str, load_delta: int):
        """更新Agent负载"""
        if agent_id in self.registry.get("agents", {}):
            self.registry["agents"][agent_id]["current_load"] += load_delta
            self._save_registry()
    
    def record_task(self, agent_id: str, success: bool, duration: float):
        """记录任务执行结果"""
        if agent_id not in self.stats:
            self.stats[agent_id] = {
                "tasks_completed": 0,
                "tasks_failed": 0,
                "avg_completion_time": 0,
                "success_rate": 100.0,
                "last_task": None
            }
        
        stats = self.stats[agent_id]
        
        if success:
            stats["tasks_completed"] += 1
        else:
            stats["tasks_failed"] += 1
        
        # 更新平均完成时间
        n = stats["tasks_completed"] + stats["tasks_failed"]
        stats["avg_completion_time"] = (
            (stats["avg_completion_time"] * (n - 1) + duration) / n
        )
        
        # 更新成功率
        stats["success_rate"] = (stats["tasks_completed"] / n) * 100
        stats["last_task"] = datetime.now().isoformat()
        
        self._save_stats()
    
    def find_best_agent(self, required_capabilities: List[str]) -> Optional[str]:
        """找到最佳Agent"""
        best_agent = None
        best_score = -1
        
        for agent_id, agent in self.registry.get("agents", {}).items():
            if agent["status"] != "active":
                continue
            
            # 检查能力匹配
            agent_caps = set(agent.get("capabilities", []))
            required = set(required_capabilities)
            
            if not required.issubset(agent_caps):
                continue
            
            # 检查容量
            if agent["current_load"] >= agent.get("capacity", 5):
                continue
            
            # 计算得分
            stats = self.stats.get(agent_id, {})
            success_rate = stats.get("success_rate", 100)
            avg_time = stats.get("avg_completion_time", 60)
            current_load = agent["current_load"]
            capacity = agent.get("capacity", 5)
            
            # 得分 = 成功率 + 负载得分 - 时间惩罚
            load_factor = 1 - (current_load / capacity)
            time_factor = max(0, 60 - avg_time) / 60
            
            score = (success_rate * 0.5) + (load_factor * 30) + (time_factor * 20)
            
            if score > best_score:
                best_score = score
                best_agent = agent_id
        
        return best_agent
    
    def distribute_task(self, task: Dict) -> Dict:
        """分发任务"""
        required = task.get("required_capabilities", [])
        task_id = task.get("id", f"task_{int(time.time())}")
        
        # 查找最佳Agent
        agent_id = self.find_best_agent(required)
        
        if not agent_id:
            return {
                "status": "failed",
                "reason": "No suitable agent found",
                "task_id": task_id
            }
        
        # 更新负载
        self.update_load(agent_id, 1)
        
        return {
            "status": "distributed",
            "task_id": task_id,
            "agent_id": agent_id,
            "estimated_completion": self.stats.get(agent_id, {}).get("avg_completion_time", 60)
        }
    
    def get_status(self) -> Dict:
        """获取分发器状态"""
        agents = []
        for agent_id, agent in self.registry.get("agents", {}).items():
            stats = self.stats.get(agent_id, {})
            agents.append({
                "id": agent_id,
                "capabilities": agent.get("capabilities", []),
                "load": agent.get("current_load", 0),
                "capacity": agent.get("capacity", 5),
                "status": agent.get("status", "unknown"),
                "success_rate": stats.get("success_rate", 0),
                "avg_time": stats.get("avg_completion_time", 0)
            })
        
        return {
            "total_agents": len(agents),
            "active_agents": len([a for a in agents if a["status"] == "active"]),
            "agents": agents
        }

def main():
    parser = argparse.ArgumentParser(description="Agent Task Distributor")
    parser.add_argument("command", choices=["register", "distribute", "status", "complete"],
                       help="Command to execute")
    parser.add_argument("--agent", help="Agent ID")
    parser.add_argument("--capabilities", nargs="+", help="Agent capabilities")
    parser.add_argument("--capacity", type=int, default=5, help="Agent capacity")
    parser.add_argument("--task", type=json.loads, help="Task JSON")
    parser.add_argument("--success", type=lambda x: x.lower() == "true", default=True,
                       help="Task success")
    parser.add_argument("--duration", type=float, default=1.0, help="Task duration")
    
    args = parser.parse_args()
    distributor = AgentTaskDistributor()
    
    if args.command == "register":
        if not args.agent or not args.capabilities:
            print("Error: --agent and --capabilities required")
            return
        result = distributor.register_agent(args.agent, args.capabilities, args.capacity)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == "distribute":
        if not args.task:
            print("Error: --task JSON required")
            return
        result = distributor.distribute_task(args.task)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == "complete":
        if not args.agent:
            print("Error: --agent required")
            return
        distributor.update_load(args.agent, -1)
        distributor.record_task(args.agent, args.success, args.duration)
        print(json.dumps({"status": "recorded"}, indent=2))
    
    elif args.command == "status":
        result = distributor.get_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()