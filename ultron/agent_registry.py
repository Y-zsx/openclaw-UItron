"""
Agent服务注册与发现机制
提供Agent的注册、注销、发现、状态管理功能
"""

import asyncio
import json
import time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum
import heapq


class AgentStatus(Enum):
    """Agent状态枚举"""
    REGISTERING = "registering"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


@dataclass
class AgentInfo:
    """Agent信息"""
    agent_id: str
    name: str
    capabilities: List[str]
    endpoint: str
    status: str
    load: float = 0.0
    metadata: dict = None
    registered_at: float = 0.0
    last_heartbeat: float = 0.0
    health_score: float = 1.0
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.registered_at == 0.0:
            self.registered_at = time.time()
        if self.last_heartbeat == 0.0:
            self.last_heartbeat = time.time()
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'AgentInfo':
        return cls(**data)


class ServiceRegistry:
    """服务注册中心"""
    
    def __init__(self, heartbeat_timeout: float = 30.0):
        self.agents: Dict[str, AgentInfo] = {}
        self.capability_index: Dict[str, Set[str]] = {}  # capability -> agent_ids
        self.heartbeat_timeout = heartbeat_timeout
        self._lock = asyncio.Lock()
        self._health_check_task = None
    
    async def register(self, agent: AgentInfo) -> bool:
        """注册Agent"""
        async with self._lock:
            agent_id = agent.agent_id
            
            # 更新能力索引
            for cap in agent.capabilities:
                if cap not in self.capability_index:
                    self.capability_index[cap] = set()
                self.capability_index[cap].add(agent_id)
            
            agent.status = AgentStatus.ACTIVE.value
            agent.last_heartbeat = time.time()
            self.agents[agent_id] = agent
            
            print(f"✅ Agent注册: {agent_id} - 能力: {agent.capabilities}")
            return True
    
    async def unregister(self, agent_id: str) -> bool:
        """注销Agent"""
        async with self._lock:
            if agent_id not in self.agents:
                return False
            
            agent = self.agents[agent_id]
            
            # 移除能力索引
            for cap in agent.capabilities:
                if cap in self.capability_index:
                    self.capability_index[cap].discard(agent_id)
            
            del self.agents[agent_id]
            print(f"✅ Agent注销: {agent_id}")
            return True
    
    async def heartbeat(self, agent_id: str, load: float = 0.0) -> bool:
        """Agent心跳"""
        async with self._lock:
            if agent_id not in self.agents:
                return False
            
            agent = self.agents[agent_id]
            agent.last_heartbeat = time.time()
            agent.load = load
            
            # 根据负载更新状态
            if load < 0.3:
                agent.status = AgentStatus.IDLE.value
            elif load < 0.7:
                agent.status = AgentStatus.ACTIVE.value
            else:
                agent.status = AgentStatus.BUSY.value
            
            return True
    
    async def discover_by_capability(self, capability: str) -> List[AgentInfo]:
        """按能力发现Agent"""
        async with self._lock:
            agent_ids = self.capability_index.get(capability, set())
            return [
                self.agents[aid]
                for aid in agent_ids
                if aid in self.agents
            ]
    
    async def discover_all(self, status_filter: Optional[str] = None) -> List[AgentInfo]:
        """发现所有Agent"""
        async with self._lock:
            agents = list(self.agents.values())
            if status_filter:
                agents = [a for a in agents if a.status == status_filter]
            return agents
    
    async def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """获取指定Agent"""
        async with self._lock:
            return self.agents.get(agent_id)
    
    async def health_check(self) -> Dict[str, List[str]]:
        """健康检查 - 返回不健康的Agent"""
        async with self._lock:
            now = time.time()
            unhealthy = {"timeout": [], "low_health": []}
            
            for agent_id, agent in list(self.agents.items()):
                # 检查心跳超时
                if now - agent.last_heartbeat > self.heartbeat_timeout:
                    agent.status = AgentStatus.OFFLINE.value
                    unhealthy["timeout"].append(agent_id)
                
                # 检查健康分数
                elif agent.health_score < 0.5:
                    agent.status = AgentStatus.UNHEALTHY.value
                    unhealthy["low_health"].append(agent_id)
            
            if unhealthy["timeout"] or unhealthy["low_health"]:
                print(f"⚠️ 健康检查: 超时 {len(unhealthy['timeout'])}, 低健康 {len(unhealthy['low_health'])}")
            
            return unhealthy
    
    async def update_capabilities(self, agent_id: str, capabilities: List[str]) -> bool:
        """更新Agent能力"""
        async with self._lock:
            if agent_id not in self.agents:
                return False
            
            agent = self.agents[agent_id]
            old_caps = set(agent.capabilities)
            new_caps = set(capabilities)
            
            # 移除旧能力索引
            for cap in old_caps - new_caps:
                if cap in self.capability_index:
                    self.capability_index[cap].discard(agent_id)
            
            # 添加新能力索引
            for cap in new_caps - old_caps:
                if cap not in self.capability_index:
                    self.capability_index[cap] = set()
                self.capability_index[cap].add(agent_id)
            
            agent.capabilities = capabilities
            return True
    
    def get_stats(self) -> dict:
        """获取注册中心统计"""
        status_counts = {}
        for agent in self.agents.values():
            status_counts[agent.status] = status_counts.get(agent.status, 0) + 1
        
        return {
            "total_agents": len(self.agents),
            "capabilities": list(self.capability_index.keys()),
            "status_breakdown": status_counts
        }


class ServiceDiscovery:
    """服务发现客户端 - 智能选择最佳Agent"""
    
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
    
    async def find_best_agent(self, capabilities: List[str], 
                               prefer_idle: bool = True) -> Optional[AgentInfo]:
        """找到最佳Agent（综合考虑能力和负载）"""
        async with self.registry._lock:
            # 找到具备所有所需能力的Agent
            candidate_ids = None
            for cap in capabilities:
                cap_agents = self.registry.capability_index.get(cap, set())
                if candidate_ids is None:
                    candidate_ids = cap_agents
                else:
                    candidate_ids &= cap_agents
            
            if not candidate_ids:
                return None
            
            # 过滤活跃Agent
            candidates = [
                self.registry.agents[aid]
                for aid in candidate_ids
                if aid in self.registry.agents
                and self.registry.agents[aid].status in [AgentStatus.ACTIVE.value, AgentStatus.IDLE.value]
            ]
            
            if not candidates:
                return None
            
            # 按负载排序选择
            if prefer_idle:
                # 优先选择负载低的
                candidates.sort(key=lambda a: a.load)
            else:
                # 随机选择（负载均衡）
                import random
                return random.choice(candidates)
            
            return candidates[0] if candidates else None
    
    async def find_by_load(self, max_load: float = 0.8) -> List[AgentInfo]:
        """找到负载低于阈值的Agent"""
        async with self.registry._lock:
            return [
                a for a in self.registry.agents.values()
                if a.load < max_load and a.status != AgentStatus.OFFLINE.value
            ]


# 演示
async def demo():
    print("=" * 50)
    print("Agent服务注册与发现机制 - 演示")
    print("=" * 50)
    
    registry = ServiceRegistry(heartbeat_timeout=10.0)
    discovery = ServiceDiscovery(registry)
    
    # 注册Agents
    agents = [
        AgentInfo("agent-1", "Worker-A", ["web_scraping", "data_processing"], 
                  "http://worker-a:8001", AgentStatus.ACTIVE.value, load=0.2),
        AgentInfo("agent-2", "Worker-B", ["data_processing", "ml_inference"], 
                  "http://worker-b:8002", AgentStatus.ACTIVE.value, load=0.5),
        AgentInfo("agent-3", "Worker-C", ["web_scraping", "ml_inference"], 
                  "http://worker-c:8003", AgentStatus.IDLE.value, load=0.1),
    ]
    
    for agent in agents:
        await registry.register(agent)
    
    print(f"\n📊 注册统计: {registry.get_stats()}")
    
    # 心跳
    await registry.heartbeat("agent-1", load=0.3)
    await registry.heartbeat("agent-2", load=0.6)
    
    # 发现
    print("\n🔍 发现具备 web_scraping 能力的Agent:")
    found = await registry.discover_by_capability("web_scraping")
    for a in found:
        print(f"  - {a.name} (负载: {a.load})")
    
    # 智能选择最佳Agent
    print("\n🎯 智能选择最佳Agent (需要 web_scraping + data_processing):")
    best = await discovery.find_best_agent(["web_scraping", "data_processing"])
    if best:
        print(f"  → {best.name} (负载: {best.load})")
    
    # 健康检查
    print("\n🏥 健康检查:")
    unhealthy = await registry.health_check()
    print(f"  → {unhealthy}")
    
    print("\n✅ 演示完成")


if __name__ == "__main__":
    asyncio.run(demo())