#!/usr/bin/env python3
"""
负载均衡与故障转移增强模块
===========================
为协调Agent提供智能负载均衡和自动故障转移能力

功能:
- 多种负载均衡策略 (轮询/最少连接/性能最优/随机)
- Agent健康监控与状态跟踪
- 故障检测与自动转移
- 任务重试与排队管理
- 性能指标收集与分析
"""

import json
import time
import threading
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import statistics


class LoadBalanceStrategy(Enum):
    """负载均衡策略"""
    ROUND_ROBIN = "round_robin"          # 轮询
    LEAST_CONNECTIONS = "least_connections"  # 最少连接
    LEAST_LOAD = "least_load"            # 最低负载
    PERFORMANCE = "performance"          # 性能最优
    RANDOM = "random"                    # 随机
    WEIGHTED = "weighted"                # 加权


class AgentHealth(Enum):
    """Agent健康状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class AgentMetrics:
    """Agent性能指标"""
    agent_id: str
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    total_execution_time: float = 0.0
    avg_execution_time: float = 0.0
    min_execution_time: float = float('inf')
    max_execution_time: float = 0.0
    current_load: int = 0
    consecutive_failures: int = 0
    last_heartbeat: str = None
    success_rate: float = 100.0
    weight: int = 100  # 加权权重 (0-100)

    def update_execution_time(self, duration: float):
        """更新执行时间统计"""
        self.total_execution_time += duration
        self.completed_tasks += 1
        self.total_tasks += 1
        
        # 更新平均执行时间
        if self.completed_tasks > 0:
            self.avg_execution_time = self.total_execution_time / self.completed_tasks
        
        # 更新最小/最大执行时间
        self.min_execution_time = min(self.min_execution_time, duration)
        self.max_execution_time = max(self.max_execution_time, duration)
        
        # 重置连续失败计数
        self.consecutive_failures = 0
        
        # 更新成功率
        if self.total_tasks > 0:
            self.success_rate = (self.completed_tasks / self.total_tasks) * 100

    def record_failure(self):
        """记录失败"""
        self.failed_tasks += 1
        self.total_tasks += 1
        self.consecutive_failures += 1
        
        # 更新成功率
        if self.total_tasks > 0:
            self.success_rate = (self.completed_tasks / self.total_tasks) * 100
        
        # 连续失败3次降权
        if self.consecutive_failures >= 3:
            self.weight = max(0, self.weight - 20)

    def increment_load(self):
        """增加负载"""
        self.current_load += 1

    def decrement_load(self):
        """减少负载"""
        self.current_load = max(0, self.current_load - 1)

    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "avg_execution_time": round(self.avg_execution_time, 3),
            "success_rate": round(self.success_rate, 2),
            "current_load": self.current_load,
            "consecutive_failures": self.consecutive_failures,
            "weight": self.weight,
            "last_heartbeat": self.last_heartbeat
        }


@dataclass
class FailoverConfig:
    """故障转移配置"""
    max_retries: int = 3                    # 最大重试次数
    retry_delay: float = 2.0                # 重试延迟(秒)
    health_check_interval: float = 30.0     # 健康检查间隔(秒)
    failure_threshold: int = 3              # 失败阈值
    recovery_threshold: int = 2              # 恢复阈值 (连续成功次数)
    heartbeat_timeout: float = 60.0         # 心跳超时(秒)
    auto_failover: bool = True              # 自动故障转移


class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self, strategy: LoadBalanceStrategy = LoadBalanceStrategy.LEAST_LOAD):
        self.strategy = strategy
        self.agents: Dict[str, AgentMetrics] = {}
        self.round_robin_index: Dict[str, int] = defaultdict(int)
        self.lock = threading.RLock()
        
    def register_agent(self, agent_id: str, weight: int = 100) -> AgentMetrics:
        """注册Agent"""
        with self.lock:
            if agent_id not in self.agents:
                self.agents[agent_id] = AgentMetrics(agent_id=agent_id, weight=weight)
                self.round_robin_index[agent_id] = 0
            return self.agents[agent_id]
    
    def unregister_agent(self, agent_id: str):
        """注销Agent"""
        with self.lock:
            if agent_id in self.agents:
                del self.agents[agent_id]
    
    def select_agent(self, required_capability: str = None, 
                    exclude_agents: Set[str] = None) -> Optional[str]:
        """
        选择最佳Agent
        """
        with self.lock:
            if not self.agents:
                return None
            
            # 过滤可用Agent
            available = {
                aid: metrics for aid, metrics in self.agents.items()
                if metrics.success_rate >= 50  # 至少50%成功率
            }
            
            if exclude_agents:
                available = {k: v for k, v in available.items() if k not in exclude_agents}
            
            if not available:
                return None
            
            # 根据策略选择
            if self.strategy == LoadBalanceStrategy.ROUND_ROBIN:
                return self._round_robin(available)
            elif self.strategy == LoadBalanceStrategy.LEAST_CONNECTIONS:
                return self._least_connections(available)
            elif self.strategy == LoadBalanceStrategy.LEAST_LOAD:
                return self._least_load(available)
            elif self.strategy == LoadBalanceStrategy.PERFORMANCE:
                return self._performance_based(available)
            elif self.strategy == LoadBalanceStrategy.RANDOM:
                return self._random_select(available)
            elif self.strategy == LoadBalanceStrategy.WEIGHTED:
                return self._weighted_select(available)
            
            return self._least_load(available)
    
    def _round_robin(self, agents: Dict[str, AgentMetrics]) -> str:
        """轮询策略"""
        agent_ids = list(agents.keys())
        idx = self.round_robin_index.get(agent_ids[0], 0) % len(agent_ids)
        self.round_robin_index[agent_ids[0]] = idx + 1
        return agent_ids[idx]
    
    def _least_connections(self, agents: Dict[str, AgentMetrics]) -> str:
        """最少连接策略"""
        return min(agents.items(), key=lambda x: x[1].current_load)[0]
    
    def _least_load(self, agents: Dict[str, AgentMetrics]) -> str:
        """最低负载策略 - 综合考虑当前负载和权重"""
        def load_score(aid: str, metrics: AgentMetrics) -> float:
            # 综合评分: 负载 * (100 - 权重) / 100
            if metrics.weight == 0:
                return float('inf')
            return metrics.current_load / metrics.weight
        
        return min(agents.items(), key=lambda x: load_score(x[0], x[1]))[0]
    
    def _performance_based(self, agents: Dict[str, AgentMetrics]) -> str:
        """性能最优策略 - 基于平均执行时间和成功率"""
        def perf_score(aid: str, metrics: AgentMetrics) -> float:
            # 分数越低越好
            if metrics.avg_execution_time == 0:
                return 0
            return metrics.avg_execution_time / (metrics.success_rate / 100)
        
        return min(agents.items(), key=lambda x: perf_score(x[0], x[1]))[0]
    
    def _random_select(self, agents: Dict[str, AgentMetrics]) -> str:
        """随机选择"""
        return random.choice(list(agents.keys()))
    
    def _weighted_select(self, agents: Dict[str, AgentMetrics]) -> str:
        """加权随机选择"""
        agent_ids = list(agents.keys())
        weights = [agents[aid].weight for aid in agent_ids]
        total = sum(weights)
        if total == 0:
            return random.choice(agent_ids)
        
        r = random.uniform(0, total)
        cumulative = 0
        for i, w in enumerate(weights):
            cumulative += w
            if cumulative >= r:
                return agent_ids[i]
        return agent_ids[-1]
    
    def get_healthy_agents(self) -> List[str]:
        """获取健康Agent列表"""
        with self.lock:
            return [
                aid for aid, m in self.agents.items()
                if m.success_rate >= 70 and m.consecutive_failures < 3
            ]
    
    def get_agent_metrics(self, agent_id: str) -> Optional[Dict]:
        """获取Agent指标"""
        with self.lock:
            if agent_id in self.agents:
                return self.agents[agent_id].to_dict()
            return None
    
    def get_all_metrics(self) -> Dict:
        """获取所有Agent指标"""
        with self.lock:
            return {
                "strategy": self.strategy.value,
                "total_agents": len(self.agents),
                "healthy_agents": len(self.get_healthy_agents()),
                "agents": {aid: m.to_dict() for aid, m in self.agents.items()}
            }


class FailoverManager:
    """故障转移管理器"""
    
    def __init__(self, config: FailoverConfig = None):
        self.config = config or FailoverConfig()
        self.failed_tasks: Dict[str, Dict] = {}  # task_id -> task_info
        self.task_retry_count: Dict[str, int] = {}
        self.offline_agents: Dict[str, str] = {}  # agent_id -> last_seen
        self.lock = threading.RLock()
        
    def record_failure(self, task_id: str, agent_id: str, error: str, 
                      task_data: Dict) -> Dict:
        """
        记录任务失败
        返回: 是否需要重试/转移
        """
        with self.lock:
            retry_count = self.task_retry_count.get(task_id, 0) + 1
            self.task_retry_count[task_id] = retry_count
            
            # 记录失败
            self.failed_tasks[task_id] = {
                "task_id": task_id,
                "original_agent": agent_id,
                "error": error,
                "task_data": task_data,
                "retry_count": retry_count,
                "last_attempt": datetime.now().isoformat()
            }
            
            # 检查是否需要重试
            if retry_count < self.config.max_retries:
                return {
                    "action": "retry",
                    "task_id": task_id,
                    "retry_count": retry_count,
                    "max_retries": self.config.max_retries,
                    "delay": self.config.retry_delay * retry_count
                }
            else:
                return {
                    "action": "dead_letter",
                    "task_id": task_id,
                    "error": f"超过最大重试次数({self.config.max_retries})",
                    "original_error": error
                }
    
    def record_agent_failure(self, agent_id: str) -> Dict:
        """记录Agent故障"""
        with self.lock:
            self.offline_agents[agent_id] = datetime.now().isoformat()
            return {
                "agent_id": agent_id,
                "status": "marked_unhealthy",
                "timestamp": datetime.now().isoformat()
            }
    
    def is_agent_available(self, agent_id: str) -> bool:
        """检查Agent是否可用"""
        with self.lock:
            if agent_id in self.offline_agents:
                # 检查是否超时
                last_seen = datetime.fromisoformat(self.offline_agents[agent_id])
                elapsed = (datetime.now() - last_seen).total_seconds()
                if elapsed > self.config.heartbeat_timeout:
                    return False
            return True
    
    def mark_agent_recovered(self, agent_id: str):
        """标记Agent已恢复"""
        with self.lock:
            if agent_id in self.offline_agents:
                del self.offline_agents[agent_id]
    
    def get_failed_tasks(self) -> List[Dict]:
        """获取失败任务列表"""
        with self.lock:
            return list(self.failed_tasks.values())
    
    def clear_task(self, task_id: str):
        """清除任务记录"""
        with self.lock:
            self.failed_tasks.pop(task_id, None)
            self.task_retry_count.pop(task_id, None)
    
    def get_status(self) -> Dict:
        """获取状态"""
        with self.lock:
            return {
                "config": {
                    "max_retries": self.config.max_retries,
                    "health_check_interval": self.config.health_check_interval,
                    "failure_threshold": self.config.failure_threshold,
                    "auto_failover": self.config.auto_failover
                },
                "failed_tasks": len(self.failed_tasks),
                "offline_agents": list(self.offline_agents.keys())
            }


# 全局负载均衡器和故障转移管理器
_load_balancer = None
_failover_manager = None
_config = None

def get_load_balancer(strategy: LoadBalanceStrategy = LoadBalanceStrategy.LEAST_LOAD) -> LoadBalancer:
    global _load_balancer
    if _load_balancer is None:
        _load_balancer = LoadBalancer(strategy)
    return _load_balancer

def get_failover_manager(config: FailoverConfig = None) -> FailoverManager:
    global _failover_manager
    if _failover_manager is None:
        _failover_manager = FailoverManager(config)
    return _failover_manager


if __name__ == "__main__":
    # 测试负载均衡
    lb = LoadBalancer(LoadBalanceStrategy.WEIGHTED)
    
    # 注册测试Agent
    for i in range(5):
        lb.register_agent(f"agent-{i}", weight=100 - i * 15)
    
    print("=== 负载均衡测试 ===")
    print(f"策略: {lb.strategy.value}")
    
    # 模拟任务分配
    for _ in range(20):
        agent = lb.select_agent()
        if agent:
            print(f"选择Agent: {agent}")
    
    print("\n=== Agent指标 ===")
    metrics = lb.get_all_metrics()
    print(json.dumps(metrics, indent=2, ensure_ascii=False))