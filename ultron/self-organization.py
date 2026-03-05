#!/usr/bin/env python3
"""
自组织系统 - 超级有机体的自适应组织层
Self-Organization System - Adaptive organization layer for super-organism

功能：
- 动态结构形成
- 自适应层级
- 弹性组织
- 涌现组织模式
"""

import asyncio
import json
import time
import uuid
import math
import random
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("self-organization")


class OrganizationState(Enum):
    """组织状态"""
    CHAOTIC = "chaotic"
    FORMING = "forming"
    STRUCTURING = "structuring"
    STABLE = "stable"
    OPTIMIZING = "optimizing"
    EVOLVING = "evolving"


class Role(Enum):
    """角色类型"""
    LEADER = "leader"
    COORDINATOR = "coordinator"
    SPECIALIST = "specialist"
    WORKER = "worker"
    OBSERVER = "observer"
    BRIDGE = "bridge"


class LinkType(Enum):
    """连接类型"""
    HIERARCHICAL = "hierarchical"
    LATERAL = "lateral"
    TEMPORARY = "temporary"
    EMERGENT = "emergent"


@dataclass
class Agent:
    """智能体节点"""
    id: str
    capabilities: Set[str] = field(default_factory=set)
    resources: Dict[str, float] = field(default_factory=dict)
    state: str = "active"
    role: Role = Role.WORKER
    trust_score: float = 0.5
    load: float = 0.0
    
    def can_handle(self, task_type: str) -> bool:
        return task_type in self.capabilities and self.load < 0.8


@dataclass
class Link:
    """连接"""
    source: str
    target: str
    link_type: LinkType
    strength: float = 0.5
    latency: float = 0.0
    bandwidth: float = 1.0
    created_at: float = field(default_factory=time.time)
    
    def is_stable(self, threshold: float = 0.3) -> bool:
        return self.strength >= threshold


@dataclass
class Cluster:
    """集群"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    members: Set[str] = field(default_factory=set)
    leader: Optional[str] = None
    purpose: str = ""
    cohesion: float = 0.0
    formed_at: float = field(default_factory=time.time)


@dataclass
class Task:
    """任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = ""
    requirements: Set[str] = field(default_factory=set)
    priority: float = 0.5
    complexity: float = 0.5
    assigned_to: Optional[str] = None
    status: str = "pending"
    created_at: float = field(default_factory=time.time)
    
    def is_complete(self) -> bool:
        return self.status == "completed"


class SelfOrganizationSystem:
    """
    自组织系统
    
    核心能力：
    - 动态组织形成
    - 自适应层级结构
    - 负载均衡
    - 弹性与自愈
    - 涌现模式识别
    """
    
    def __init__(self, system_id: str):
        self.system_id = system_id
        self.state = OrganizationState.CHAOTIC
        
        # 节点管理
        self.agents: Dict[str, Agent] = {}
        self.links: Dict[Tuple[str, str], Link] = {}
        
        # 组织结构
        self.clusters: Dict[str, Cluster] = {}
        self.hierarchy: Dict[str, List[str]] = defaultdict(list)  # leader -> subordinates
        self.role_assignments: Dict[str, Role] = {}
        
        # 任务队列
        self.tasks: Dict[str, Task] = {}
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        
        # 动态参数
        self.parameters = {
            "cluster_threshold": 0.6,
            "leader_election_threshold": 0.7,
            "rebalance_interval": 60,
            "cohesion_threshold": 0.5,
            "link_stability_threshold": 0.3
        }
        
        # 统计
        self.stats = {
            "clusters_formed": 0,
            "role_changes": 0,
            "tasks_distributed": 0,
            "reorganizations": 0
        }
        
        logger.info(f"🔧 Self-Organization System initialized: {system_id}")
    
    # ==================== 节点管理 ====================
    
    async def register_agent(self, agent_id: str, 
                           capabilities: Optional[Set[str]] = None,
                           resources: Optional[Dict[str, float]] = None) -> Agent:
        """注册智能体"""
        agent = Agent(
            id=agent_id,
            capabilities=capabilities or set(),
            resources=resources or {"cpu": 1.0, "memory": 1.0, "storage": 1.0}
        )
        
        self.agents[agent_id] = agent
        self.state = OrganizationState.FORMING
        
        logger.info(f"📝 Agent registered: {agent_id}")
        return agent
    
    async def deregister_agent(self, agent_id: str):
        """注销智能体"""
        if agent_id in self.agents:
            del self.agents[agent_id]
            
            # 移除相关链接
            to_remove = [k for k in self.links if agent_id in k]
            for k in to_remove:
                del self.links[k]
            
            # 从集群中移除
            for cluster in self.clusters.values():
                cluster.members.discard(agent_id)
            
            logger.info(f"🗑️ Agent deregistered: {agent_id}")
    
    async def update_agent_state(self, agent_id: str, 
                                state: str = None,
                                load: float = None,
                                trust_score: float = None):
        """更新智能体状态"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            if state:
                agent.state = state
            if load is not None:
                agent.load = min(1.0, max(0.0, load))
            if trust_score is not None:
                agent.trust_score = min(1.0, max(0.0, trust_score))
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """获取智能体"""
        return self.agents.get(agent_id)
    
    def get_agents_by_capability(self, capability: str) -> List[Agent]:
        """按能力获取智能体"""
        return [a for a in self.agents.values() if capability in a.capabilities]
    
    # ==================== 连接管理 ====================
    
    async def create_link(self, source: str, target: str,
                         link_type: LinkType = LinkType.LATERAL,
                         strength: float = 0.5) -> Link:
        """创建连接"""
        if source not in self.agents or target not in self.agents:
            raise ValueError("Both agents must be registered")
        
        link = Link(
            source=source,
            target=target,
            link_type=link_type,
            strength=strength
        )
        
        self.links[(source, target)] = link
        
        # 双向链接
        reverse_link = Link(
            source=target,
            target=source,
            link_type=link_type,
            strength=strength
        )
        self.links[(target, source)] = reverse_link
        
        logger.info(f"🔗 Link created: {source} <-> {target} ({link_type.value})")
        return link
    
    async def remove_link(self, source: str, target: str):
        """移除连接"""
        self.links.pop((source, target), None)
        self.links.pop((target, source), None)
    
    async def update_link_strength(self, source: str, target: str, delta: float):
        """更新连接强度"""
        link = self.links.get((source, target))
        if link:
            link.strength = min(1.0, max(0.0, link.strength + delta))
            
            # 同步更新反向链接
            reverse = self.links.get((target, source))
            if reverse:
                reverse.strength = link.strength
    
    def get_neighbors(self, agent_id: str, min_strength: float = 0.0
                     ) -> List[Tuple[str, float]]:
        """获取邻居"""
        neighbors = []
        for (s, t), link in self.links.items():
            if s == agent_id and link.strength >= min_strength:
                neighbors.append((t, link.strength))
        return neighbors
    
    # ==================== 集群管理 ====================
    
    async def form_cluster(self, name: str, member_ids: Set[str],
                          purpose: str = "") -> Cluster:
        """形成集群"""
        if not member_ids.issubset(set(self.agents.keys())):
            raise ValueError("All members must be registered")
        
        # 选举leader
        leader = await self._elect_leader(member_ids)
        
        cluster = Cluster(
            name=name,
            members=member_ids,
            leader=leader,
            purpose=purpose
        )
        
        # 计算内聚力
        cluster.cohesion = await self._calculate_cohesion(member_ids)
        
        self.clusters[cluster.id] = cluster
        self.stats["clusters_formed"] += 1
        
        # 建立集群内部连接
        for m1 in member_ids:
            for m2 in member_ids:
                if m1 != m2 and (m1, m2) not in self.links:
                    await self.create_link(m1, m2, LinkType.LATERAL, 0.6)
        
        logger.info(f"📦 Cluster formed: {name} (leader: {leader}, members: {len(member_ids)})")
        return cluster
    
    async def _elect_leader(self, member_ids: Set[str]) -> str:
        """选举leader"""
        candidates = []
        for member_id in member_ids:
            agent = self.agents.get(member_id)
            if agent:
                score = agent.trust_score * 0.4 + (1 - agent.load) * 0.4 + 0.2
                candidates.append((member_id, score))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        leader = candidates[0][0] if candidates else list(member_ids)[0]
        
        self.role_assignments[leader] = Role.LEADER
        self.stats["role_changes"] += 1
        
        return leader
    
    async def _calculate_cohesion(self, member_ids: Set[str]) -> float:
        """计算集群内聚力"""
        if len(member_ids) < 2:
            return 1.0
        
        connections = 0
        possible = len(member_ids) * (len(member_ids) - 1)
        
        for m1 in member_ids:
            for m2 in member_ids:
                if m1 != m2 and (m1, m2) in self.links:
                    connections += 1
        
        return connections / max(1, possible)
    
    async def dissolve_cluster(self, cluster_id: str):
        """解散集群"""
        if cluster_id in self.clusters:
            cluster = self.clusters[cluster_id]
            
            # 重置角色
            if cluster.leader in self.role_assignments:
                del self.role_assignments[cluster.leader]
            
            del self.clusters[cluster_id]
            logger.info(f"📦 Cluster dissolved: {cluster_id}")
    
    async def merge_clusters(self, cluster_id1: str, cluster_id2: str) -> Cluster:
        """合并集群"""
        c1 = self.clusters.get(cluster_id1)
        c2 = self.clusters.get(cluster_id2)
        
        if not c1 or not c2:
            raise ValueError("Both clusters must exist")
        
        new_members = c1.members | c2.members
        new_name = f"{c1.name}+{c2.name}"
        
        # 解散旧集群
        await self.dissolve_cluster(cluster_id1)
        await self.dissolve_cluster(cluster_id2)
        
        # 形成新集群
        new_cluster = await self.form_cluster(new_name, new_members, 
                                              f"merged: {c1.purpose}, {c2.purpose}")
        
        return new_cluster
    
    async def split_cluster(self, cluster_id: str) -> List[Cluster]:
        """分裂集群"""
        cluster = self.clusters.get(cluster_id)
        if not cluster:
            raise ValueError("Cluster does not exist")
        
        members = list(cluster.members)
        mid = len(members) // 2
        
        group1 = set(members[:mid])
        group2 = set(members[mid:])
        
        await self.dissolve_cluster(cluster_id)
        
        c1 = await self.form_cluster(f"{cluster.name}_1", group1, cluster.purpose)
        c2 = await self.form_cluster(f"{cluster.name}_2", group2, cluster.purpose)
        
        return [c1, c2]
    
    # ==================== 动态重组织 ====================
    
    async def reorganize(self):
        """动态重组织"""
        logger.info("🔄 Starting reorganization...")
        self.state = OrganizationState.EVOLVING
        self.stats["reorganizations"] += 1
        
        # 1. 检测低负载节点
        underloaded = [a for a in self.agents.values() if a.load < 0.3]
        overloaded = [a for a in self.agents.values() if a.load > 0.7]
        
        # 2. 重新分配任务
        await self._rebalance_tasks(overloaded, underloaded)
        
        # 3. 评估集群健康
        await self._assess_cluster_health()
        
        # 4. 优化连接
        await self._optimize_links()
        
        # 5. 更新角色
        await self._update_roles()
        
        self.state = OrganizationState.OPTIMIZING
        logger.info(f"✅ Reorganization complete: {len(self.agents)} agents")
    
    async def _rebalance_tasks(self, overloaded: List[Agent],
                               underloaded: List[Agent]):
        """重平衡任务"""
        for overload in overloaded:
            # 找到可转移的任务
            for task_id, task in self.tasks.items():
                if task.assigned_to == overload.id and task.status != "completed":
                    # 尝试转移到低负载节点
                    for underload in underloaded:
                        if underload.can_handle(task.type):
                            task.assigned_to = underload.id
                            self.stats["tasks_distributed"] += 1
                            break
    
    async def _assess_cluster_health(self):
        """评估集群健康"""
        unhealthy = []
        
        for cluster in self.clusters.values():
            # 检查内聚力
            cohesion = await self._calculate_cohesion(cluster.members)
            
            # 检查leader状态
            if cluster.leader and cluster.leader in self.agents:
                leader = self.agents[cluster.leader]
                if leader.load > 0.9:
                    unhealthy.append(cluster)
        
        # 重组织不健康的集群
        for cluster in unhealthy:
            # 重新选举leader
            new_leader = await self._elect_leader(cluster.members)
            cluster.leader = new_leader
            
            # 增强连接
            for m1 in cluster.members:
                for m2 in cluster.members:
                    if m1 != m2:
                        await self.update_link_strength(m1, m2, 0.1)
    
    async def _optimize_links(self):
        """优化连接"""
        # 移除弱连接
        weak_links = []
        for (s, t), link in self.links.items():
            if link.strength < self.parameters["link_stability_threshold"]:
                weak_links.append((s, t))
        
        for s, t in weak_links:
            await self.remove_link(s, t)
        
        # 加强强连接
        strong_pairs = defaultdict(list)
        for (s, t), link in self.links.items():
            if link.strength > 0.7:
                strong_pairs[s].append(t)
        
        # 在强对之间建立更多连接
        for agent_id, neighbors in strong_pairs.items():
            for n1 in neighbors:
                for n2 in neighbors:
                    if n1 != n2 and (n1, n2) not in self.links:
                        await self.create_link(n1, n2, LinkType.EMERGENT, 0.5)
    
    async def _update_roles(self):
        """更新角色"""
        for agent_id, agent in self.agents.items():
            # 根据能力分配角色
            if "coordination" in agent.capabilities and agent.trust_score > 0.7:
                if self.role_assignments.get(agent_id) != Role.COORDINATOR:
                    self.role_assignments[agent_id] = Role.COORDINATOR
                    self.stats["role_changes"] += 1
            elif "observation" in agent.capabilities:
                if self.role_assignments.get(agent_id) != Role.OBSERVER:
                    self.role_assignments[agent_id] = Role.OBSERVER
                    self.stats["role_changes"] += 1
    
    # ==================== 任务分发 ====================
    
    async def submit_task(self, task_type: str, 
                         requirements: Optional[Set[str]] = None,
                         priority: float = 0.5,
                         complexity: float = 0.5) -> Task:
        """提交任务"""
        task = Task(
            type=task_type,
            requirements=requirements or set(),
            priority=priority,
            complexity=complexity
        )
        
        self.tasks[task.id] = task
        await self.task_queue.put((-priority, task.id))
        
        return task
    
    async def distribute_task(self, task_id: str) -> bool:
        """分发任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        # 找到最佳智能体
        candidates = []
        
        for agent_id, agent in self.agents.items():
            if agent.can_handle(task.type):
                # 计算得分
                score = (1 - agent.load) * 0.4 + agent.trust_score * 0.4
                if task.type in agent.capabilities:
                    score += 0.2
                candidates.append((agent_id, score))
        
        if not candidates:
            return False
        
        # 选择最佳
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_agent = candidates[0][0]
        
        task.assigned_to = best_agent
        task.status = "assigned"
        
        # 更新智能体负载
        if best_agent in self.agents:
            self.agents[best_agent].load += task.complexity * 0.3
        
        self.stats["tasks_distributed"] += 1
        logger.info(f"📨 Task {task_id} distributed to {best_agent}")
        
        return True
    
    async def complete_task(self, task_id: str):
        """完成任务"""
        task = self.tasks.get(task_id)
        if task and task.assigned_to:
            task.status = "completed"
            
            # 释放负载
            if task.assigned_to in self.agents:
                self.agents[task.assigned_to].load -= task.complexity * 0.3
    
    async def redistribute_tasks(self):
        """重新分配任务"""
        pending = [t for t in self.tasks.values() 
                  if t.status == "pending"]
        
        for task in pending:
            await self.distribute_task(task.id)
    
    # ==================== 涌现模式检测 ====================
    
    async def detect_emergent_patterns(self) -> List[Dict[str, Any]]:
        """检测涌现模式"""
        patterns = []
        
        # 模式1: 紧密群体
        tight_groups = await self._detect_tight_groups()
        if tight_groups:
            patterns.append({
                "type": "tight_group",
                "description": "Detected tightly connected agent groups",
                "groups": tight_groups
            })
        
        # 模式2: 中心辐射结构
        hub_structure = await self._detect_hub_structure()
        if hub_structure:
            patterns.append({
                "type": "hub_structure",
                "description": "Detected hub-and-spoke organization",
                "hubs": hub_structure
            })
        
        # 模式3: 链式结构
        chain_structure = await self._detect_chain_structure()
        if chain_structure:
            patterns.append({
                "type": "chain_structure",
                "description": "Detected linear chain organization",
                "chains": chain_structure
            })
        
        return patterns
    
    async def _detect_tight_groups(self) -> List[List[str]]:
        """检测紧密群体"""
        groups = []
        visited = set()
        
        for agent_id in self.agents:
            if agent_id in visited:
                continue
            
            # BFS找紧密连接
            group = {agent_id}
            queue = [agent_id]
            
            while queue:
                current = queue.pop(0)
                neighbors = self.get_neighbors(current, 0.7)
                
                for neighbor_id, strength in neighbors:
                    if neighbor_id not in group:
                        group.add(neighbor_id)
                        queue.append(neighbor_id)
            
            if len(group) >= 3:
                groups.append(list(group))
                visited.update(group)
        
        return groups
    
    async def _detect_hub_structure(self) -> List[str]:
        """检测中心辐射结构"""
        hubs = []
        
        for agent_id, agent in self.agents.items():
            neighbors = self.get_neighbors(agent_id, 0.4)
            if len(neighbors) >= 3:
                # 检查是否所有邻居都互不相连（纯辐射）
                non_neighbor_count = sum(1 for n, _ in neighbors 
                                        if not any(n == n2 for n2, _ in neighbors))
                if non_neighbor_count >= len(neighbors) * 0.5:
                    hubs.append(agent_id)
        
        return hubs
    
    async def _detect_chain_structure(self) -> List[List[str]]:
        """检测链式结构"""
        # 简化的链式检测
        chains = []
        
        # 找到度为1的节点作为链首
        degree = defaultdict(int)
        for (s, t), link in self.links.items():
            degree[s] += 1
        
        starts = [n for n, d in degree.items() if d == 1]
        
        for start in starts:
            chain = [start]
            visited = {start}
            current = start
            
            while True:
                neighbors = self.get_neighbors(current, 0.3)
                next_node = None
                
                for neighbor_id, _ in neighbors:
                    if neighbor_id not in visited:
                        next_node = neighbor_id
                        break
                
                if not next_node:
                    break
                
                chain.append(next_node)
                visited.add(next_node)
                current = next_node
            
            if len(chain) >= 3:
                chains.append(chain)
        
        return chains
    
    # ==================== 自愈机制 ====================
    
    async def heal(self):
        """自愈"""
        logger.info("🏥 Starting self-healing...")
        
        # 1. 检测故障节点
        failed_agents = [a for a in self.agents.values() if a.state == "failed"]
        
        # 2. 重新路由任务
        for task in self.tasks.values():
            if task.assigned_to in [a.id for a in failed_agents]:
                task.status = "pending"
                task.assigned_to = None
        
        # 3. 重建连接
        for agent in failed_agents:
            neighbors = self.get_neighbors(agent.id, 0.0)
            for neighbor_id, _ in neighbors:
                await self.update_link_strength(neighbor_id, agent.id, -0.2)
        
        # 4. 重组集群
        for cluster in self.clusters.values():
            if cluster.leader in [a.id for a in failed_agents]:
                await self._elect_leader(cluster.members)
        
        logger.info(f"✅ Self-healing complete: {len(failed_agents)} agents recovered")
    
    # ==================== 组织周期 ====================
    
    async def organization_cycle(self):
        """组织循环"""
        # 分发待处理任务
        await self.redistribute_tasks()
        
        # 检测涌现模式
        patterns = await self.detect_emergent_patterns()
        
        # 定期重组织
        if self.stats["reorganizations"] % 10 == 0:
            await self.reorganize()
        
        return {
            "state": self.state.value,
            "agents": len(self.agents),
            "clusters": len(self.clusters),
            "links": len(self.links),
            "pending_tasks": len([t for t in self.tasks.values() if t.status == "pending"]),
            "patterns": len(patterns)
        }
    
    def get_organization_report(self) -> Dict[str, Any]:
        """获取组织报告"""
        return {
            "system_id": self.system_id,
            "state": self.state.value,
            "agents": {
                "total": len(self.agents),
                "active": len([a for a in self.agents.values() if a.state == "active"]),
                "avg_load": sum(a.load for a in self.agents.values()) / max(1, len(self.agents)),
                "avg_trust": sum(a.trust_score for a in self.agents.values()) / max(1, len(self.agents))
            },
            "clusters": {
                "count": len(self.clusters),
                "avg_cohesion": sum(c.cohesion for c in self.clusters.values()) / max(1, len(self.clusters))
            },
            "tasks": {
                "total": len(self.tasks),
                "pending": len([t for t in self.tasks.values() if t.status == "pending"]),
                "distributed": self.stats["tasks_distributed"]
            },
            "stats": self.stats
        }


# ==================== 演示 ====================

async def demo():
    """演示"""
    print("=" * 60)
    print("🔧 自组织系统演示")
    print("=" * 60)
    
    # 创建系统
    system = SelfOrganizationSystem("demo-system")
    
    # 注册智能体
    agents = ["agent-A", "agent-B", "agent-C", "agent-D", "agent-E"]
    capabilities_map = {
        "agent-A": {"coordination", "analysis"},
        "agent-B": {"execution", "processing"},
        "agent-C": {"execution", "processing", "monitoring"},
        "agent-D": {"observation", "reporting"},
        "agent-E": {"execution", "specialized"}
    }
    
    for agent_id in agents:
        await system.register_agent(
            agent_id,
            capabilities=capabilities_map[agent_id],
            resources={"cpu": 1.0, "memory": 1.0}
        )
    
    # 创建连接
    await system.create_link("agent-A", "agent-B", LinkType.HIERARCHICAL, 0.8)
    await system.create_link("agent-A", "agent-C", LinkType.HIERARCHICAL, 0.7)
    await system.create_link("agent-B", "agent-D", LinkType.LATERAL, 0.6)
    await system.create_link("agent-C", "agent-E", LinkType.LATERAL, 0.5)
    
    # 形成集群
    await system.form_cluster(
        "cluster-alpha",
        {"agent-A", "agent-B", "agent-C"},
        "primary-operations"
    )
    
    # 提交任务
    task1 = await system.submit_task("execution", priority=0.8, complexity=0.6)
    task2 = await system.submit_task("analysis", priority=0.6, complexity=0.4)
    task3 = await system.submit_task("monitoring", priority=0.5, complexity=0.3)
    
    # 分发任务
    await system.distribute_task(task1.id)
    await system.distribute_task(task2.id)
    await system.distribute_task(task3.id)
    
    # 组织周期
    await system.organization_cycle()
    
    # 检测涌现模式
    patterns = await system.detect_emergent_patterns()
    print(f"\n🔍 检测到 {len(patterns)} 个涌现模式")
    
    # 报告
    print("\n" + "=" * 60)
    print("📊 组织报告")
    print("=" * 60)
    report = system.get_organization_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    print("\n✅ 演示完成")


if __name__ == "__main__":
    asyncio.run(demo())