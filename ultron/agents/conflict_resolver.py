#!/usr/bin/env python3
"""
冲突解决器 - 多智能体协作网络
第3世：协作优化 - 冲突解决机制
"""

import json
import time
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

class ConflictType(Enum):
    RESOURCE_CONFLICT = "resource"      # 资源冲突（同时访问同一资源）
    TASK_OVERLAP = "task_overlap"        # 任务重叠（多个代理处理同一任务）
    PRIORITY_CONFLICT = "priority"       # 优先级冲突（高优先级任务被抢占）
    DEADLOCK = "deadlock"                # 死锁（循环等待）

class ConflictSeverity(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class Conflict:
    id: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    involved_agents: List[str]
    involved_tasks: List[str]
    resource_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    resolved: bool = False
    resolution: Optional[str] = None

@dataclass
class Resource:
    id: str
    name: str
    type: str  # file, api, database, device
    locked_by: Optional[str] = None
    lock_time: Optional[float] = None
    lock_timeout: float = 30.0  # 默认30秒超时

class ConflictResolver:
    """冲突解决器"""
    
    def __init__(self):
        self.conflicts: Dict[str, Conflict] = {}
        self.resources: Dict[str, Resource] = {}
        self.agent_locks: Dict[str, Set[str]] = defaultdict(set)  # agent -> set of resources
        self.conflict_history: List[Conflict] = []
        self._conflict_counter = 0
        
    def register_resource(self, resource: Resource) -> bool:
        """注册资源"""
        if resource.id in self.resources:
            return False
        self.resources[resource.id] = resource
        return True
    
    def acquire_lock(self, agent_id: str, resource_id: str) -> bool:
        """请求资源锁"""
        if resource_id not in self.resources:
            return False
            
        resource = self.resources[resource_id]
        
        # 资源未被锁定，直接获取
        if resource.locked_by is None:
            resource.locked_by = agent_id
            resource.lock_time = time.time()
            self.agent_locks[agent_id].add(resource_id)
            return True
        
        # 资源被自己锁定
        if resource.locked_by == agent_id:
            return True
            
        # 资源被其他代理锁定，检查是否超时
        if time.time() - resource.lock_time > resource.lock_timeout:
            # 超时，强制释放并获取
            self._release_lock(resource.locked_by, resource_id)
            resource.locked_by = agent_id
            resource.lock_time = time.time()
            self.agent_locks[agent_id].add(resource_id)
            return True
            
        return False
    
    def _release_lock(self, agent_id: str, resource_id: str):
        """释放资源锁"""
        if resource_id in self.resources:
            resource = self.resources[resource_id]
            if resource.locked_by == agent_id:
                resource.locked_by = None
                resource.lock_time = None
                if resource_id in self.agent_locks[agent_id]:
                    self.agent_locks[agent_id].remove(resource_id)
    
    def release_lock(self, agent_id: str, resource_id: str) -> bool:
        """释放资源锁（公开接口）"""
        self._release_lock(agent_id, resource_id)
        return True
    
    def check_resource_conflict(self, agent_id: str, resource_id: str) -> Optional[Conflict]:
        """检查资源冲突"""
        if resource_id not in self.resources:
            return None
            
        resource = self.resources[resource_id]
        if resource.locked_by and resource.locked_by != agent_id:
            # 检测到冲突
            conflict = Conflict(
                id=f"conflict_{self._conflict_counter}",
                conflict_type=ConflictType.RESOURCE_CONFLICT,
                severity=ConflictSeverity.MEDIUM,
                involved_agents=[agent_id, resource.locked_by],
                involved_tasks=[],
                resource_id=resource_id
            )
            self._conflict_counter += 1
            self.conflicts[conflict.id] = conflict
            return conflict
        return None
    
    def resolve_resource_conflict(self, conflict_id: str) -> str:
        """解决资源冲突 - 采用优先级和等待时间策略"""
        if conflict_id not in self.conflicts:
            return "Conflict not found"
            
        conflict = self.conflicts[conflict_id]
        if conflict.resolved:
            return "Already resolved"
            
        resource_id = conflict.resource_id
        if resource_id not in self.resources:
            return "Resource not found"
            
        resource = self.resources[resource_id]
        current_holder = conflict.involved_agents[1]  # 持有者
        
        # 释放当前持有者的锁
        self._release_lock(current_holder, resource_id)
        
        # 授予请求者
        requester = conflict.involved_agents[0]
        resource.locked_by = requester
        resource.lock_time = time.time()
        self.agent_locks[requester].add(resource_id)
        
        conflict.resolved = True
        conflict.resolution = f"Resource transferred from {current_holder} to {requester}"
        self.conflict_history.append(conflict)
        
        return conflict.resolution
    
    def detect_deadlock(self, agents: List[str]) -> Optional[List[str]]:
        """检测死锁（简单的循环等待检测）"""
        # 构建等待图
        wait_graph: Dict[str, Set[str]] = {a: set() for a in agents}
        
        for agent_id in agents:
            for resource_id in self.agent_locks[agent_id]:
                resource = self.resources.get(resource_id)
                if resource and resource.locked_by:
                    wait_graph[agent_id].add(resource.locked_by)
        
        # 简单检测：是否有循环等待
        def has_cycle(agent: str, visited: Set[str], path: List[str]) -> Optional[List[str]]:
            if agent in visited:
                return path[path.index(agent):] if agent in path else None
            visited.add(agent)
            path.append(agent)
            
            for next_agent in wait_graph.get(agent, set()):
                cycle = has_cycle(next_agent, visited.copy(), path.copy())
                if cycle:
                    return cycle
            return None
        
        for agent in agents:
            cycle = has_cycle(agent, set(), [])
            if cycle:
                return cycle
        return None
    
    def resolve_deadlock(self, cycle: List[str]) -> str:
        """解决死锁 - 强制释放 youngest 持有者的资源"""
        if len(cycle) < 2:
            return "Invalid cycle"
            
        # 找到最年轻的持有者（最后加锁的）
        youngest = None
        youngest_time = float('inf')
        
        for i in range(len(cycle) - 1):
            holder = cycle[i]
            resource_id = list(self.agent_locks[holder])[0] if self.agent_locks[holder] else None
            if resource_id:
                resource = self.resources[resource_id]
                if resource.lock_time and resource.lock_time < youngest_time:
                    youngest = holder
                    youngest_time = resource.lock_time
        
        if youngest:
            # 释放其所有锁
            for resource_id in list(self.agent_locks[youngest]):
                self._release_lock(youngest, resource_id)
            return f"Released locks from {youngest} to break deadlock"
        
        return "Could not resolve"
    
    def get_conflict_stats(self) -> Dict[str, Any]:
        """获取冲突统计"""
        resolved = sum(1 for c in self.conflicts.values() if c.resolved)
        by_type = defaultdict(int)
        by_severity = defaultdict(int)
        
        for c in self.conflicts.values():
            by_type[c.conflict_type.value] += 1
            by_severity[c.severity.name] += 1
            
        return {
            "total_conflicts": len(self.conflicts),
            "resolved": resolved,
            "unresolved": len(self.conflicts) - resolved,
            "by_type": dict(by_type),
            "by_severity": dict(by_severity),
            "active_locks": sum(1 for r in self.resources.values() if r.locked_by)
        }

# 单例
_resolver = None

def get_resolver() -> ConflictResolver:
    global _resolver
    if _resolver is None:
        _resolver = ConflictResolver()
    return _resolver

if __name__ == "__main__":
    resolver = get_resolver()
    
    # 注册资源
    resolver.register_resource(Resource("r1", "数据库", "database"))
    resolver.register_resource(Resource("r2", "API", "api"))
    
    # 模拟冲突
    resolver.acquire_lock("agent1", "r1")
    print("Agent1 locked r1")
    
    conflict = resolver.check_resource_conflict("agent2", "r1")
    if conflict:
        print(f"Conflict detected: {conflict.conflict_type}")
        resolution = resolver.resolve_resource_conflict(conflict.id)
        print(f"Resolved: {resolution}")
    
    print("Stats:", json.dumps(resolver.get_conflict_stats(), indent=2))