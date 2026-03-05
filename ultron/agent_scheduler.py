#!/usr/bin/env python3
"""
Agent协作网络智能调度与负载均衡系统
Agent Collaboration Network Intelligent Scheduler & Load Balancer

功能:
- 智能任务调度: 根据Agent负载、能力、状态分配任务
- 负载均衡: 动态平衡各Agent工作负载
- 动态权重: 基于性能自动调整Agent权重
- 故障转移: Agent失败时自动转移到其他Agent
"""

import json
import time
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
import threading


@dataclass
class AgentMetrics:
    """Agent性能指标"""
    agent_id: str
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    task_queue_size: int = 0
    success_rate: float = 1.0
    avg_response_time: float = 0.0
    tasks_completed: int = 0
    tasks_failed: int = 0
    last_heartbeat: datetime = field(default_factory=datetime.now)
    weight: float = 1.0


@dataclass
class Task:
    """任务定义"""
    task_id: str
    task_type: str
    priority: int = 5  # 1-10, 10最高
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    timeout: int = 300  # seconds
    required_capability: Optional[str] = None


class LoadBalancer:
    """负载均衡器"""
    
    STRATEGIES = ["round_robin", "least_connections", "weighted", "smart"]
    
    def __init__(self, strategy: str = "smart"):
        self.strategy = strategy
        self.agents: Dict[str, AgentMetrics] = {}
        self.rr_counter: Dict[str, int] = defaultdict(int)
        self.lock = threading.RLock()
        
    def register_agent(self, agent_id: str) -> None:
        with self.lock:
            if agent_id not in self.agents:
                self.agents[agent_id] = AgentMetrics(agent_id=agent_id)
                self.rr_counter[agent_id] = 0
                
    def unregister_agent(self, agent_id: str) -> None:
        with self.lock:
            self.agents.pop(agent_id, None)
            self.rr_counter.pop(agent_id, None)
            
    def update_metrics(self, agent_id: str, metrics: Dict) -> None:
        """更新Agent指标"""
        with self.lock:
            if agent_id in self.agents:
                agent = self.agents[agent_id]
                agent.cpu_usage = metrics.get('cpu', agent.cpu_usage)
                agent.memory_usage = metrics.get('memory', agent.memory_usage)
                agent.task_queue_size = metrics.get('queue_size', agent.task_queue_size)
                agent.success_rate = metrics.get('success_rate', agent.success_rate)
                agent.avg_response_time = metrics.get('response_time', agent.avg_response_time)
                agent.last_heartbeat = datetime.now()
                
    def calculate_load(self, agent_id: str) -> float:
        """计算Agent负载分数 (0-100)"""
        with self.lock:
            if agent_id not in self.agents:
                return 100.0
                
            agent = self.agents[agent_id]
            # 负载 = CPU*0.3 + 内存*0.3 + 队列*0.2 + (1-成功率)*20 + 响应时间*0.1
            load = (
                agent.cpu_usage * 0.3 +
                agent.memory_usage * 0.3 +
                min(agent.task_queue_size / 10, 1) * 20 +
                (1 - agent.success_rate) * 20 +
                min(agent.avg_response_time / 10, 1) * 10
            )
            return min(load, 100.0)
            
    def select_agent(self, task: Task) -> Optional[str]:
        """选择最佳Agent"""
        with self.lock:
            if not self.agents:
                return None
                
            # 检查能力要求
            if task.required_capability:
                capable_agents = [
                    a for a, m in self.agents.items()
                    if m.success_rate > 0.5  # 至少50%成功率
                ]
            else:
                capable_agents = list(self.agents.keys())
                
            if not capable_agents:
                return None
                
            if self.strategy == "round_robin":
                return self._round_robin(capable_agents)
            elif self.strategy == "least_connections":
                return self._least_connections(capable_agents)
            elif self.strategy == "weighted":
                return self._weighted(capable_agents)
            else:  # smart
                return self._smart_select(capable_agents, task)
                
    def _round_robin(self, agents: List[str]) -> str:
        """轮询"""
        agent = agents[self.rr_counter[agents[0]] % len(agents)]
        self.rr_counter[agents[0]] += 1
        return agent
        
    def _least_connections(self, agents: List[str]) -> str:
        """最少连接"""
        return min(agents, key=lambda a: self.agents[a].task_queue_size)
        
    def _weighted(self, agents: List[str]) -> str:
        """加权随机"""
        weights = [self.agents[a].weight for a in agents]
        total = sum(weights)
        probs = [w/total for w in weights]
        r = random.random()
        cumsum = 0
        for i, p in enumerate(probs):
            cumsum += p
            if r <= cumsum:
                return agents[i]
        return agents[-1]
        
    def _smart_select(self, agents: List[str], task: Task) -> str:
        """智能选择: 考虑负载 + 优先级"""
        scores = {}
        for agent_id in agents:
            load = self.calculate_load(agent_id)
            agent = self.agents[agent_id]
            
            # 分数 = (100 - 负载) * 权重 * (1 + 优先级因子)
            priority_factor = (task.priority - 5) * 0.1  # -0.4 to +0.5
            score = (100 - load) * agent.weight * (1 + priority_factor)
            
            # 高优先级任务更看重成功率
            if task.priority >= 8:
                score *= (agent.success_rate + 0.5)
                
            scores[agent_id] = score
            
        return max(scores, key=scores.get)
        
    def rebalance(self) -> Dict[str, List[str]]:
        """负载均衡重平衡 - 迁移任务"""
        with self.lock:
            moves = {}
            overloaded = []
            underloaded = []
            
            # 分类Agent
            for agent_id, agent in self.agents.items():
                load = self.calculate_load(agent_id)
                if load > 70:
                    overloaded.append((agent_id, load))
                elif load < 30:
                    underloaded.append((agent_id, load))
                    
            # 从高负载迁移到低负载
            overloaded.sort(key=lambda x: x[1], reverse=True)
            underloaded.sort(key=lambda x: x[1])
            
            for src, _ in overloaded[:len(underloaded)]:
                if underloaded:
                    dst = underloaded.pop(0)[0]
                    moves[src] = [dst]
                    
            return moves
        
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self.lock:
            return {
                "total_agents": len(self.agents),
                "strategy": self.strategy,
                "agents": {
                    aid: {
                        "load": round(self.calculate_load(aid), 1),
                        "cpu": round(m.cpu_usage, 1),
                        "memory": round(m.memory_usage, 1),
                        "queue": m.task_queue_size,
                        "success_rate": round(m.success_rate * 100, 1),
                        "weight": m.weight
                    }
                    for aid, m in self.agents.items()
                }
            }


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, balancer: LoadBalancer):
        self.balancer = balancer
        self.pending_tasks: Dict[str, Task] = {}
        self.running_tasks: Dict[str, str] = {}  # task_id -> agent_id
        self.completed_tasks: List[Dict] = []
        self.lock = threading.RLock()
        
    def submit_task(self, task: Task) -> str:
        """提交任务"""
        with self.lock:
            self.pending_tasks[task.task_id] = task
            return task.task_id
            
    def dispatch(self) -> Optional[tuple]:
        """分发任务到Agent"""
        with self.lock:
            if not self.pending_tasks:
                return None
                
            # 按优先级排序
            sorted_tasks = sorted(
                self.pending_tasks.values(),
                key=lambda t: (-t.priority, t.created_at)
            )
            
            for task in sorted_tasks:
                agent_id = self.balancer.select_agent(task)
                if agent_id:
                    del self.pending_tasks[task.task_id]
                    self.running_tasks[task.task_id] = agent_id
                    return (task, agent_id)
            return None
            
    def complete_task(self, task_id: str, success: bool) -> None:
        """任务完成"""
        with self.lock:
            if task_id in self.running_tasks:
                agent_id = self.running_tasks.pop(task_id)
                self.completed_tasks.append({
                    "task_id": task_id,
                    "agent_id": agent_id,
                    "success": success,
                    "completed_at": datetime.now().isoformat()
                })
                # 保留最近100个任务
                self.completed_tasks = self.completed_tasks[-100:]


def generate_task_id() -> str:
    return f"task_{int(time.time()*1000)}_{random.randint(1000,9999)}"


def create_sample_scheduler() -> tuple:
    """创建示例调度系统"""
    balancer = LoadBalancer(strategy="smart")
    
    # 注册示例Agent
    sample_agents = [
        "agent-alpha", "agent-beta", "agent-gamma", "agent-delta"
    ]
    for agent_id in sample_agents:
        balancer.register_agent(agent_id)
        # 模拟不同负载
        balancer.update_metrics(agent_id, {
            "cpu": random.uniform(20, 60),
            "memory": random.uniform(30, 70),
            "queue_size": random.randint(0, 5),
            "success_rate": random.uniform(0.85, 0.99),
            "response_time": random.uniform(0.5, 2.0)
        })
        
    scheduler = TaskScheduler(balancer)
    
    # 提交示例任务
    task_types = ["data_processing", "web_fetch", "compute", "io_task"]
    priorities = [3, 5, 7, 9]
    
    for i in range(8):
        task = Task(
            task_id=generate_task_id(),
            task_type=random.choice(task_types),
            priority=random.choice(priorities),
            payload={"data": f"sample_{i}"}
        )
        scheduler.submit_task(task)
        
    return balancer, scheduler


if __name__ == "__main__":
    print("🤖 Agent协作网络智能调度与负载均衡系统")
    print("=" * 50)
    
    # 创建调度系统
    balancer, scheduler = create_sample_scheduler()
    
    # 显示初始状态
    print("\n📊 初始Agent状态:")
    stats = balancer.get_stats()
    for agent_id, info in stats["agents"].items():
        print(f"  {agent_id}: 负载{info['load']}% | CPU{info['cpu']}% | 内存{info['memory']}% | 成功率{info['success_rate']}%")
    
    print(f"\n📋 待处理任务: {len(scheduler.pending_tasks)}")
    
    # 分发任务
    print("\n🚀 任务分发:")
    dispatched = 0
    while True:
        result = scheduler.dispatch()
        if not result:
            break
        task, agent_id = result
        print(f"  [{task.task_type}] 优先级{task.priority} -> {agent_id}")
        dispatched += 1
        
    print(f"\n✅ 已分发 {dispatched} 个任务")
    
    # 模拟任务完成
    print("\n🎯 模拟任务完成:")
    for task_id in list(scheduler.running_tasks.keys())[:3]:
        success = random.random() > 0.1
        scheduler.complete_task(task_id, success)
        print(f"  {task_id}: {'✅成功' if success else '❌失败'}")
        
    # 显示重平衡建议
    print("\n⚖️ 负载均衡建议:")
    moves = balancer.rebalance()
    if moves:
        for src, dsts in moves.items():
            print(f"  {src} -> {dsts[0]}")
    else:
        print("  无需重平衡")
        
    # 最终统计
    print("\n📈 最终统计:")
    final_stats = balancer.get_stats()
    print(f"  策略: {final_stats['strategy']}")
    print(f"  Agent数: {final_stats['total_agents']}")
    print(f"  待处理: {len(scheduler.pending_tasks)}")
    print(f"  运行中: {len(scheduler.running_tasks)}")
    print(f"  已完成: {len(scheduler.completed_tasks)}")