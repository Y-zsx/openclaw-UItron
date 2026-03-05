#!/usr/bin/env python3
"""
Agent Task Queue & Load Balancer
=================================
第39世: 实现Agent任务队列与负载均衡

功能:
- 优先级任务队列
- 多种负载均衡算法
- Agent能力评估
- 智能任务分配
"""

import json
import time
import uuid
import heapq
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict


class LoadBalancingAlgorithm(Enum):
    """负载均衡算法"""
    ROUND_ROBIN = "round_robin"           # 轮询
    LEAST_LOADED = "least_loaded"         # 最小负载
    LEAST_CONNECTIONS = "least_connections"  # 最少连接数
    WEIGHTED = "weighted"                  # 加权轮询
    CAPABILITY_MATCH = "capability_match"  # 能力匹配优先
    HYBRID = "hybrid"                      # 混合策略


class TaskPriority(Enum):
    """任务优先级 (1=最低, 10=最高)"""
    CRITICAL = 10
    HIGH = 8
    MEDIUM = 5
    LOW = 3
    BACKGROUND = 1


@dataclass
class AgentCapability:
    """Agent能力定义"""
    agent_id: str
    agent_type: str
    skills: List[str] = field(default_factory=list)
    max_concurrent_tasks: int = 3
    current_load: int = 0
    avg_task_duration: float = 1.0  # 平均任务执行时间(秒)
    success_rate: float = 0.95      # 成功率
    cpu_usage: float = 0.0          # CPU使用率
    memory_usage: float = 0.0       # 内存使用率
    metadata: Dict = field(default_factory=dict)
    
    @property
    def load_factor(self) -> float:
        """计算负载因子 (0-1, 越小越空闲)"""
        return self.current_load / max(self.max_concurrent_tasks, 1)
    
    @property
    def is_available(self) -> bool:
        """是否可接受新任务"""
        return self.current_load < self.max_concurrent_tasks


@dataclass 
class QueuedTask:
    """队列任务"""
    id: str
    name: str
    agent_type: str
    payload: Dict
    priority: int = 5
    depends_on: List[str] = field(default_factory=list)
    timeout: float = 60.0
    max_retries: int = 3
    retry_count: int = 0
    required_skills: List[str] = field(default_factory=list)
    weight: float = 1.0  # 任务权重(影响负载计算)
    metadata: Dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def __lt__(self, other):
        """用于堆排序: 优先级高的在前"""
        return self.priority > other.priority


class TaskQueueManager:
    """
    Agent任务队列与负载均衡管理器
    """
    
    def __init__(self, state_file: str = "task_queue_state.json"):
        self.state_file = state_file
        self.tasks: Dict[str, QueuedTask] = {}
        self.pending_queue: List[QueuedTask] = []  # 优先级堆
        self.agents: Dict[str, AgentCapability] = {}
        self.assignments: Dict[str, str] = {}  # task_id -> agent_id
        self.completed_tasks: List[Dict] = []
        
        # 算法状态
        self.round_robin_index: Dict[str, int] = defaultdict(int)
        self.task_counts: Dict[str, int] = defaultdict(int)  # agent_id -> 已完成任务数
        
        # 负载均衡配置
        self.algorithm = LoadBalancingAlgorithm.CAPABILITY_MATCH
        
        # 回调函数
        self.on_task_assigned: Optional[Callable] = None
        self.on_task_completed: Optional[Callable] = None
        
        self._load_state()
    
    def _load_state(self):
        """加载状态"""
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                # 恢复agents
                for agent_data in state.get('agents', []):
                    agent = AgentCapability(**agent_data)
                    self.agents[agent.agent_id] = agent
        except FileNotFoundError:
            pass
    
    def _save_state(self):
        """保存状态"""
        state = {
            'agents': [vars(a) for a in self.agents.values()],
            'completed_tasks': self.completed_tasks[-100:],  # 保留最近100个
            'timestamp': datetime.now().isoformat()
        }
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    # ========== Agent管理 ==========
    
    def register_agent(self, agent_id: str, agent_type: str, 
                       skills: List[str] = None, max_concurrent: int = 3,
                       weight: float = 1.0) -> AgentCapability:
        """注册Agent"""
        capability = AgentCapability(
            agent_id=agent_id,
            agent_type=agent_type,
            skills=skills or [agent_type],
            max_concurrent_tasks=max_concurrent,
            metadata={'weight': weight, 'registered_at': datetime.now().isoformat()}
        )
        self.agents[agent_id] = capability
        self._save_state()
        return capability
    
    def update_agent_load(self, agent_id: str, current_load: int = None,
                          cpu_usage: float = None, memory_usage: float = None):
        """更新Agent负载信息"""
        if agent_id not in self.agents:
            return False
        
        agent = self.agents[agent_id]
        if current_load is not None:
            agent.current_load = current_load
        if cpu_usage is not None:
            agent.cpu_usage = cpu_usage
        if memory_usage is not None:
            agent.memory_usage = memory_usage
        
        self._save_state()
        return True
    
    def get_available_agents(self, agent_type: str = None) -> List[AgentCapability]:
        """获取可用的Agent列表"""
        available = []
        for agent in self.agents.values():
            if not agent.is_available:
                continue
            if agent_type and agent.agent_type != agent_type:
                continue
            available.append(agent)
        return available
    
    # ========== 任务队列 ==========
    
    def enqueue(self, name: str, agent_type: str, payload: Dict,
                priority: int = 5, depends_on: List[str] = None,
                timeout: float = 60.0, required_skills: List[str] = None,
                weight: float = 1.0) -> str:
        """入队任务"""
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        
        task = QueuedTask(
            id=task_id,
            name=name,
            agent_type=agent_type,
            payload=payload,
            priority=priority,
            depends_on=depends_on or [],
            timeout=timeout,
            required_skills=required_skills or [],
            weight=weight
        )
        
        self.tasks[task_id] = task
        heapq.heappush(self.pending_queue, task)
        
        return task_id
    
    def dequeue(self) -> Optional[QueuedTask]:
        """出队优先级最高的任务"""
        while self.pending_queue:
            task = heapq.heappop(self.pending_queue)
            # 检查依赖是否满足
            if self._dependencies_met(task):
                return task
            # 依赖未满足,重新检查
        return None
    
    def _dependencies_met(self, task: QueuedTask) -> bool:
        """检查任务依赖是否满足"""
        for dep_id in task.depends_on:
            if dep_id not in self.completed_task_ids():
                return False
        return True
    
    def completed_task_ids(self) -> set:
        """获取已完成任务ID集合"""
        return {t['id'] for t in self.completed_tasks if t.get('status') == 'completed'}
    
    def get_queue_status(self) -> Dict:
        """获取队列状态"""
        return {
            'pending': len(self.pending_queue),
            'total_tasks': len(self.tasks),
            'agents': len(self.agents),
            'available_agents': len(self.get_available_agents())
        }
    
    # ========== 负载均衡算法 ==========
    
    def set_algorithm(self, algorithm: LoadBalancingAlgorithm):
        """设置负载均衡算法"""
        self.algorithm = algorithm
    
    def select_agent(self, task: QueuedTask) -> Optional[str]:
        """根据负载均衡算法选择最佳Agent"""
        available = self.get_available_agents(task.agent_type)
        
        if not available:
            return None
        
        if self.algorithm == LoadBalancingAlgorithm.ROUND_ROBIN:
            return self._round_robin_select(available, task.agent_type)
        elif self.algorithm == LoadBalancingAlgorithm.LEAST_LOADED:
            return self._least_loaded_select(available)
        elif self.algorithm == LoadBalancingAlgorithm.LEAST_CONNECTIONS:
            return self._least_connections_select(available)
        elif self.algorithm == LoadBalancingAlgorithm.WEIGHTED:
            return self._weighted_select(available)
        elif self.algorithm == LoadBalancingAlgorithm.CAPABILITY_MATCH:
            return self._capability_match_select(available, task)
        elif self.algorithm == LoadBalancingAlgorithm.HYBRID:
            return self._hybrid_select(available, task)
        
        return available[0].agent_id
    
    def _round_robin_select(self, available: List[AgentCapability], 
                            agent_type: str) -> str:
        """轮询选择"""
        index = self.round_robin_index[agent_type]
        self.round_robin_index[agent_type] = (index + 1) % len(available)
        return available[index].agent_id
    
    def _least_loaded_select(self, available: List[AgentCapability]) -> str:
        """最小负载选择"""
        return min(available, key=lambda a: a.load_factor).agent_id
    
    def _least_connections_select(self, available: List[AgentCapability]) -> str:
        """最少连接数选择"""
        return min(available, key=lambda a: a.current_load).agent_id
    
    def _weighted_select(self, available: List[AgentCapability]) -> str:
        """加权选择"""
        # 基于weight和当前负载计算权重
        weights = []
        for agent in available:
            w = agent.metadata.get('weight', 1.0)
            # 负载越高,权重越低
            adjusted = w / (1 + agent.load_factor)
            weights.append(adjusted)
        
        total = sum(weights)
        r = total * (time.time() % 1)  # 伪随机
        cumulative = 0
        for i, w in enumerate(weights):
            cumulative += w
            if cumulative >= r:
                return available[i].agent_id
        return available[-1].agent_id
    
    def _capability_match_select(self, available: List[AgentCapability],
                                  task: QueuedTask) -> str:
        """能力匹配优先选择"""
        # 首先筛选满足技能要求的
        if task.required_skills:
            candidates = [a for a in available 
                         if any(s in a.skills for s in task.required_skills)]
            if candidates:
                available = candidates
        
        # 然后选择负载最低的
        if not available:
            return None
        return min(available, key=lambda a: a.load_factor).agent_id
    
    def _hybrid_select(self, available: List[AgentCapability],
                       task: QueuedTask) -> str:
        """混合策略: 能力匹配 + 负载均衡"""
        # 第一优先: 技能匹配
        if task.required_skills:
            skilled = [a for a in available 
                      if any(s in a.skills for s in task.required_skills)]
            if skilled:
                available = skilled
        
        # 第二优先: 低负载
        # 第三优先: 高成功率
        # 第四优先: 低平均执行时间
        return min(available, 
                  key=lambda a: (a.load_factor, -a.success_rate, a.avg_task_duration)
                  ).agent_id
    
    # ========== 任务分配 ==========
    
    def assign_task(self, task_id: str, agent_id: str = None) -> bool:
        """分配任务给Agent"""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        
        # 如果没有指定agent,自动选择
        if not agent_id:
            agent_id = self.select_agent(task)
            if not agent_id:
                return False  # 没有可用Agent
        
        # 更新状态
        self.assignments[task_id] = agent_id
        self.agents[agent_id].current_load += 1
        self.task_counts[agent_id] += 1
        
        # 触发回调
        if self.on_task_assigned:
            self.on_task_assigned(task, self.agents[agent_id])
        
        self._save_state()
        return True
    
    def complete_task(self, task_id: str, result: Any = None, 
                     success: bool = True):
        """标记任务完成"""
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        agent_id = self.assignments.get(task_id)
        
        # 更新Agent负载
        if agent_id and agent_id in self.agents:
            agent = self.agents[agent_id]
            agent.current_load = max(0, agent.current_load - 1)
            # 更新平均执行时间
            duration = task.metadata.get('duration', 1.0)
            agent.avg_task_duration = (agent.avg_task_duration * 0.8 + duration * 0.2)
        
        # 记录完成
        completed = {
            'id': task.id,
            'name': task.name,
            'agent_type': task.agent_type,
            'priority': task.priority,
            'agent_id': agent_id,
            'result': result,
            'success': success,
            'completed_at': datetime.now().isoformat()
        }
        self.completed_tasks.append(completed)
        
        # 触发回调
        if self.on_task_completed:
            self.on_task_completed(task, result, success)
        
        # 清理
        del self.tasks[task_id]
    
    def get_load_balancing_stats(self) -> Dict:
        """获取负载均衡统计"""
        stats = {
            'algorithm': self.algorithm.value,
            'total_agents': len(self.agents),
            'available_agents': len(self.get_available_agents()),
            'queue_status': self.get_queue_status(),
            'agent_loads': []
        }
        
        for agent in self.agents.values():
            stats['agent_loads'].append({
                'agent_id': agent.agent_id,
                'agent_type': agent.agent_type,
                'current_load': agent.current_load,
                'max_concurrent': agent.max_concurrent_tasks,
                'load_factor': round(agent.load_factor, 2),
                'is_available': agent.is_available,
                'tasks_completed': self.task_counts.get(agent.agent_id, 0),
                'success_rate': round(agent.success_rate, 2),
                'avg_duration': round(agent.avg_task_duration, 2)
            })
        
        return stats


# ========== CLI工具 ==========

def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Agent Task Queue & Load Balancer')
    parser.add_argument('command', choices=['enqueue', 'list', 'assign', 'complete', 'stats'],
                       help='命令')
    parser.add_argument('--name', help='任务名称')
    parser.add_argument('--type', '--agent-type', dest='agent_type', help='Agent类型')
    parser.add_argument('--payload', help='任务数据(JSON)')
    parser.add_argument('--priority', type=int, default=5, help='优先级(1-10)')
    parser.add_argument('--task-id', help='任务ID')
    parser.add_argument('--agent-id', help='Agent ID')
    parser.add_argument('--algorithm', choices=['rr', 'll', 'lc', 'w', 'cm', 'hy'],
                       default='cm', help='负载均衡算法')
    
    args = parser.parse_args()
    
    # 算法映射
    algo_map = {
        'rr': LoadBalancingAlgorithm.ROUND_ROBIN,
        'll': LoadBalancingAlgorithm.LEAST_LOADED,
        'lc': LoadBalancingAlgorithm.LEAST_CONNECTIONS,
        'w': LoadBalancingAlgorithm.WEIGHTED,
        'cm': LoadBalancingAlgorithm.CAPABILITY_MATCH,
        'hy': LoadBalancingAlgorithm.HYBRID
    }
    
    manager = TaskQueueManager()
    manager.set_algorithm(algo_map[args.algorithm])
    
    if args.command == 'enqueue':
        if not args.name or not args.agent_type:
            print("错误: --name 和 --type 必须指定")
            return
        
        payload = json.loads(args.payload) if args.payload else {}
        task_id = manager.enqueue(args.name, args.agent_type, payload, args.priority)
        print(f"任务已入队: {task_id}")
    
    elif args.command == 'list':
        status = manager.get_queue_status()
        print(f"队列状态: {json.dumps(status, indent=2, ensure_ascii=False)}")
    
    elif args.command == 'assign':
        if not args.task_id:
            print("错误: --task-id 必须指定")
            return
        
        success = manager.assign_task(args.task_id, args.agent_id)
        print(f"任务分配: {'成功' if success else '失败'}")
    
    elif args.command == 'complete':
        if not args.task_id:
            print("错误: --task-id 必须指定")
            return
        
        manager.complete_task(args.task_id)
        print(f"任务完成: {args.task_id}")
    
    elif args.command == 'stats':
        stats = manager.get_load_balancing_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()