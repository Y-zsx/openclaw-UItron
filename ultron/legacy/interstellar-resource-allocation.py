#!/usr/bin/env python3
"""
星际资源分配系统 (Interstellar Resource Allocation)
奥创夙愿二十七第2世 - 跨星际协作核心组件

功能：
- 跨星际资源发现与注册
- 动态资源调度与分配
- 资源公平分配算法
- 资源优先级管理
- 跨光年距离的资源共享
- 资源负载均衡
"""

import asyncio
import json
import time
import uuid
import random
import hashlib
import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable, Tuple
from enum import Enum, auto
from collections import defaultdict, deque
from heapq import heappush, heappop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InterstellarResourceAllocation")


class ResourceType(Enum):
    """资源类型"""
    ENERGY = auto()          # 能量
    COMPUTATION = auto()     # 计算资源
    STORAGE = auto()         # 存储资源
    BANDWIDTH = auto()       # 带宽
    MEMORY = auto()          # 内存
    PROCESSING = auto()      # 处理能力
    SENSORS = auto()         # 传感器
    ACTUATORS = auto()       # 执行器
    QUANTUM = auto()         # 量子计算资源
    SPECIALIZED = auto()     # 专业设备


class ResourceState(Enum):
    """资源状态"""
    AVAILABLE = auto()       # 可用
    ALLOCATED = auto()       # 已分配
    RESERVED = auto()        # 预留
    MAINTENANCE = auto()     # 维护中
    OFFLINE = auto()         # 离线
    DEGRADED = auto()        # 降级


class AllocationStrategy(Enum):
    """分配策略"""
    FIFO = auto()            # 先进先出
    PRIORITY = auto()        # 优先级
    FAIR_SHARE = auto()      # 公平分享
    EFFICIENCY = auto()      # 效率优先
    LOAD_BALANCED = auto()   # 负载均衡
    DISTANCE_AWARE = auto()  # 距离感知


class ResourcePriority(Enum):
    """资源请求优先级"""
    CRITICAL = 1    # 关键任务
    HIGH = 2        # 高优先级
    NORMAL = 3      # 正常
    LOW = 4         # 低优先级
    BEST_EFFORT = 5 # 尽力而为


@dataclass
class ResourceCapacity:
    """资源容量"""
    energy: float = 0            # 能量 (单位: TW)
    computation: float = 0       # 计算能力 (TFLOPS)
    storage: float = 0           # 存储 (TB)
    bandwidth: float = 0         # 带宽 (Gbps)
    memory: float = 0            # 内存 (TB)
    processing: float = 0        # 处理能力 (核心数)
    quantum: float = 0           # 量子比特数
    sensors: int = 0             # 传感器数量
    actuators: int = 0           # 执行器数量
    specialized: Dict[str, float] = field(default_factory=dict)
    
    def get(self, resource_type: ResourceType) -> float:
        """获取指定类型资源的数量"""
        return getattr(self, resource_type.name.lower(), 0)
    
    def can_allocate(self, resource_type: ResourceType, amount: float) -> bool:
        """检查是否可以分配指定数量的资源"""
        available = self.get(resource_type)
        return available >= amount
    
    def allocate(self, resource_type: ResourceType, amount: float) -> bool:
        """尝试分配资源"""
        if self.can_allocate(resource_type, amount):
            current = self.get(resource_type)
            setattr(self, resource_type.name.lower(), current - amount)
            return True
        return False
    
    def release(self, resource_type: ResourceType, amount: float):
        """释放资源"""
        current = self.get(resource_type)
        setattr(self, resource_type.name.lower(), current + amount)


@dataclass
class ResourceMetrics:
    """资源指标"""
    utilization: float = 0       # 利用率 0-1
    efficiency: float = 0        # 效率 0-1
    reliability: float = 1.0     # 可靠性 0-1
    latency: float = 0           # 延迟 (ms)
    throughput: float = 0        # 吞吐量
    error_rate: float = 0        # 错误率
    last_updated: float = field(default_factory=time.time)
    
    def update(self, **kwargs):
        """更新指标"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.last_updated = time.time()


@dataclass
class StarSystem:
    """恒星系统资源池"""
    system_id: str = ""
    name: str = ""
    position: Tuple[float, float, float] = (0, 0, 0)
    resources: ResourceCapacity = field(default_factory=ResourceCapacity)
    metrics: ResourceMetrics = field(default_factory=ResourceMetrics)
    state: ResourceState = ResourceState.AVAILABLE
    connected_systems: Set[str] = field(default_factory=set)
    resource_price: Dict[ResourceType, float] = field(default_factory=dict)
    
    def distance_to(self, other: 'StarSystem') -> float:
        """计算到另一个恒星系统的距离（光年）"""
        dx = self.position[0] - other.position[0]
        dy = self.position[1] - other.position[1]
        dz = self.position[2] - other.position[2]
        return (dx*dx + dy*dy + dz*dz) ** 0.5
    
    def light_years_to(self, other: 'StarSystem') -> float:
        """光年距离"""
        return self.distance_to(other)


@dataclass
class ResourceRequest:
    """资源请求"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    requester_id: str = ""
    resource_type: ResourceType = ResourceType.COMPUTATION
    amount: float = 0
    priority: ResourcePriority = ResourcePriority.NORMAL
    duration: float = 0      # 持续时间 (秒)
    deadline: float = 0      # 截止时间
    quality_of_service: float = 1.0  # QoS要求 0-1
    source_position: Tuple[float, float, float] = (0, 0, 0)
    target_system_id: str = ""
    constraints: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    allocated: bool = False
    allocated_system: str = ""
    
    def calculate_priority_score(self, current_time: float) -> float:
        """计算优先级分数"""
        score = (6 - self.priority.value) * 20
        
        # 紧急程度
        if self.deadline > 0:
            time_left = self.deadline - current_time
            if time_left <= 0:
                score += 100
            elif time_left < 3600:
                score += 50
            elif time_left < 86400:
                score += 20
        
        # 资源量需求
        score += min(self.amount / 100, 20)
        
        return score


@dataclass
class ResourceAllocation:
    """资源分配记录"""
    allocation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    request_id: str = ""
    system_id: str = ""
    resource_type: ResourceType = ResourceType.COMPUTATION
    amount: float = 0
    start_time: float = 0
    end_time: float = 0
    active: bool = True
    preempted: bool = False


class InterstellarResourceRegistry:
    """星际资源注册中心"""
    
    def __init__(self, registry_id: str = "main"):
        self.id = registry_id
        self.systems: Dict[str, StarSystem] = {}
        self.resource_requests: Dict[str, ResourceRequest] = {}
        self.allocations: Dict[str, ResourceAllocation] = {}
        
        # 资源索引
        self.system_by_resource: Dict[ResourceType, List[str]] = defaultdict(list)
        
        self.lock = threading.RLock()
        self._setup_default_systems()
    
    def _setup_default_systems(self):
        """设置默认恒星系统"""
        default_systems = [
            ("sol", "Sol", (0, 0, 0), ResourceCapacity(
                energy=10000, computation=5000, storage=100000,
                bandwidth=1000, memory=500, processing=1000
            )),
            ("alpha-centauri", "Alpha-Centauri", (4.37, 0, 0), ResourceCapacity(
                energy=8000, computation=4000, storage=80000,
                bandwidth=800, memory=400, processing=800
            )),
            ("barnard", "Barnard's Star", (5.96, 0, 0), ResourceCapacity(
                energy=6000, computation=3000, storage=60000,
                bandwidth=600, memory=300, processing=600
            )),
            ("sirius", "Sirius", (8.6, 0, 0), ResourceCapacity(
                energy=12000, computation=6000, storage=120000,
                bandwidth=1200, memory=600, processing=1200
            )),
            ("epsilon-eridani", "Epsilon Eridani", (10.5, 0, 0), ResourceCapacity(
                energy=5000, computation=2500, storage=50000,
                bandwidth=500, memory=250, processing=500
            )),
            ("proxima", "Proxima Centauri", (4.24, 0, 0), ResourceCapacity(
                energy=4000, computation=2000, storage=40000,
                bandwidth=400, memory=200, processing=400
            )),
        ]
        
        for sys_id, name, pos, resources in default_systems:
            system = StarSystem(
                system_id=sys_id,
                name=name,
                position=pos,
                resources=resources
            )
            self.register_system(system)
    
    def register_system(self, system: StarSystem):
        """注册恒星系统"""
        with self.lock:
            self.systems[system.system_id] = system
            
            # 更新资源索引
            for res_type in ResourceType:
                if system.resources.get(res_type) > 0:
                    self.system_by_resource[res_type].append(system.system_id)
            
            # 建立连接
            self._update_connections(system)
            
            logger.info(f"恒星系统 {system.name} 已注册")
    
    def _update_connections(self, system: StarSystem):
        """更新系统连接"""
        max_connection_distance = 20  # 光年
        
        for other_id, other in self.systems.items():
            if other_id != system.system_id:
                distance = system.distance_to(other)
                if distance < max_connection_distance:
                    system.connected_systems.add(other_id)
                    other.connected_systems.add(system.system_id)
    
    def find_systems_with_resource(self, resource_type: ResourceType,
                                   min_amount: float = 0) -> List[StarSystem]:
        """查找具有指定资源的系统"""
        with self.lock:
            candidates = []
            for sys_id in self.system_by_resource.get(resource_type, []):
                if sys_id in self.systems:
                    system = self.systems[sys_id]
                    if system.resources.get(resource_type) >= min_amount:
                        if system.state == ResourceState.AVAILABLE:
                            candidates.append(system)
            return candidates
    
    def find_nearest_system(self, position: Tuple[float, float, float],
                           resource_type: ResourceType = None,
                           min_amount: float = 0) -> Optional[StarSystem]:
        """查找最近的系统"""
        candidates = []
        
        if resource_type:
            systems = self.find_systems_with_resource(resource_type, min_amount)
        else:
            systems = list(self.systems.values())
        
        for system in systems:
            if system.state != ResourceState.AVAILABLE:
                continue
            
            distance = (
                (system.position[0] - position[0])**2 +
                (system.position[1] - position[1])**2 +
                (system.position[2] - position[2])**2
            ) ** 0.5
            
            candidates.append((distance, system))
        
        if not candidates:
            return None
        
        candidates.sort()
        return candidates[0][1]
    
    def submit_request(self, request: ResourceRequest) -> bool:
        """提交资源请求"""
        with self.lock:
            self.resource_requests[request.id] = request
            logger.info(f"资源请求已提交: {request.id} - {request.resource_type.name}: {request.amount}")
            return True
    
    def get_pending_requests(self, resource_type: ResourceType = None) -> List[ResourceRequest]:
        """获取待处理的请求"""
        with self.lock:
            requests = []
            for req in self.resource_requests.values():
                if req.allocated:
                    continue
                if resource_type and req.resource_type != resource_type:
                    continue
                requests.append(req)
            
            # 按优先级排序
            current_time = time.time()
            requests.sort(
                key=lambda r: r.calculate_priority_score(current_time),
                reverse=True
            )
            return requests


class ResourceAllocator:
    """资源分配器"""
    
    def __init__(self, registry: InterstellarResourceRegistry):
        self.registry = registry
        self.strategy = AllocationStrategy.FAIR_SHARE
        self.allocation_history: deque = deque(maxlen=1000)
        
        # 调度器
        self.scheduler_task: Optional[asyncio.Task] = None
        
        self.lock = threading.RLock()
    
    def set_strategy(self, strategy: AllocationStrategy):
        """设置分配策略"""
        self.strategy = strategy
        logger.info(f"分配策略已设置为: {strategy.name}")
    
    def allocate(self, request: ResourceRequest) -> Optional[ResourceAllocation]:
        """分配资源"""
        with self.lock:
            # 根据策略选择目标系统
            target_system = self._select_target_system(request)
            
            if not target_system:
                logger.warning(f"无法为请求 {request.id} 找到合适的系统")
                return None
            
            # 尝试分配
            if not target_system.resources.allocate(request.resource_type, request.amount):
                logger.warning(f"系统 {target_system.name} 资源不足")
                return None
            
            # 创建分配记录
            allocation = ResourceAllocation(
                request_id=request.id,
                system_id=target_system.system_id,
                resource_type=request.resource_type,
                amount=request.amount,
                start_time=time.time(),
                end_time=time.time() + request.duration if request.duration > 0 else 0
            )
            
            self.registry.allocations[allocation.allocation_id] = allocation
            request.allocated = True
            request.allocated_system = target_system.system_id
            
            self.allocation_history.append(allocation)
            
            logger.info(f"资源已分配: {request.id} -> {target_system.name}")
            return allocation
    
    def _select_target_system(self, request: ResourceRequest) -> Optional[StarSystem]:
        """根据策略选择目标系统"""
        candidates = self.registry.find_systems_with_resource(
            request.resource_type,
            request.amount
        )
        
        if not candidates:
            return None
        
        if self.strategy == AllocationStrategy.FIFO:
            return candidates[0]
        
        elif self.strategy == AllocationStrategy.PRIORITY:
            # 优先级策略：选择资源最充裕的
            return max(candidates, key=lambda s: s.resources.get(request.resource_type))
        
        elif self.strategy == AllocationStrategy.FAIR_SHARE:
            # 公平分享：选择负载最低的
            def load_score(system):
                total = 0
                for rt in ResourceType:
                    total += system.metrics.utilization
                return total / len(ResourceType)
            return min(candidates, key=load_score)
        
        elif self.strategy == AllocationStrategy.EFFICIENCY:
            # 效率优先：选择效率最高的
            return max(candidates, key=lambda s: s.metrics.efficiency)
        
        elif self.strategy == AllocationStrategy.LOAD_BALANCED:
            # 负载均衡：选择最接近平均负载的
            avg_load = sum(s.metrics.utilization for s in candidates) / len(candidates)
            return min(candidates, key=lambda s: abs(s.metrics.utilization - avg_load))
        
        elif self.strategy == AllocationStrategy.DISTANCE_AWARE:
            # 距离感知：选择最近的
            def distance_score(system):
                distance = (
                    (system.position[0] - request.source_position[0])**2 +
                    (system.position[1] - request.source_position[1])**2 +
                    (system.position[2] - request.source_position[2])**2
                ) ** 0.5
                # 考虑资源充足性
                resource_factor = system.resources.get(request.resource_type) / request.amount
                return distance / max(resource_factor, 0.1)
            
            return min(candidates, key=distance_score)
        
        return candidates[0]
    
    def release_allocation(self, allocation_id: str) -> bool:
        """释放分配"""
        with self.lock:
            if allocation_id not in self.registry.allocations:
                return False
            
            allocation = self.registry.allocations[allocation_id]
            
            if not allocation.active:
                return False
            
            # 释放资源
            system = self.registry.systems.get(allocation.system_id)
            if system:
                system.resources.release(allocation.resource_type, allocation.amount)
            
            allocation.active = False
            allocation.end_time = time.time()
            
            logger.info(f"资源分配已释放: {allocation_id}")
            return True
    
    def preempt_allocation(self, allocation_id: str) -> bool:
        """抢占分配（高优先级请求可抢占低优先级）"""
        with self.lock:
            if allocation_id not in self.registry.allocations:
                return False
            
            allocation = self.registry.allocations[allocation_id]
            allocation.preempted = True
            allocation.active = False
            allocation.end_time = time.time()
            
            # 释放资源
            system = self.registry.systems.get(allocation.system_id)
            if system:
                system.resources.release(allocation.resource_type, allocation.amount)
            
            logger.info(f"资源分配已被抢占: {allocation_id}")
            return True
    
    def rebalance(self):
        """重新平衡资源分配"""
        with self.lock:
            logger.info("开始资源重新平衡...")
            
            # 查找负载不均衡的系统
            loads = []
            for system in self.registry.systems.values():
                if system.state == ResourceState.AVAILABLE:
                    loads.append((system.metrics.utilization, system))
            
            if len(loads) < 2:
                return
            
            loads.sort()
            min_load = loads[0][1]
            max_load = loads[-1][1]
            
            # 从高负载系统向低负载系统转移资源
            logger.info(f"负载均衡: {min_load.name} ({min_load.metrics.utilization:.2f}) <-> {max_load.name} ({max_load.metrics.utilization:.2f})")
    
    def get_allocation_stats(self) -> Dict[str, Any]:
        """获取分配统计"""
        with self.lock:
            total_allocations = len(self.registry.allocations)
            active_allocations = sum(1 for a in self.registry.allocations.values() if a.active)
            preempted = sum(1 for a in self.registry.allocations.values() if a.preempted)
            
            return {
                "total_allocations": total_allocations,
                "active_allocations": active_allocations,
                "preempted": preempted,
                "strategy": self.strategy.name,
                "history_size": len(self.allocation_history)
            }


class FederatedResourceManager:
    """联邦资源管理器 - 跨星际资源协调"""
    
    def __init__(self):
        self.registries: Dict[str, InterstellarResourceRegistry] = {}
        self.federation_policy = {
            "resource_sharing": "enabled",
            "cost_sharing": "proportional",
            "priority_boost": 0,
            "max_latency": 100  # 年
        }
        
        self.lock = threading.RLock()
    
    def register_registry(self, registry: InterstellarResourceRegistry):
        """注册资源注册中心"""
        with self.lock:
            self.registries[registry.id] = registry
            logger.info(f"资源注册中心 {registry.id} 已加入联邦")
    
    def federated_allocate(self, request: ResourceRequest) -> Optional[ResourceAllocation]:
        """联邦资源分配"""
        with self.lock:
            # 首先尝试本地分配
            for registry in self.registries.values():
                allocator = ResourceAllocator(registry)
                allocation = allocator.allocate(request)
                if allocation:
                    return allocation
            
            # 尝试跨联邦分配
            return self._cross_federation_allocate(request)
    
    def _cross_federation_allocate(self, request: ResourceRequest) -> Optional[ResourceAllocation]:
        """跨联邦分配"""
        # 查找最近的注册中心
        best_registry = None
        best_distance = float('inf')
        
        for registry in self.registries.values():
            for system in registry.systems.values():
                distance = (
                    (system.position[0] - request.source_position[0])**2 +
                    (system.position[1] - request.source_position[1])**2 +
                    (system.position[2] - request.source_position[2])**2
                ) ** 0.5
                
                if distance < best_distance:
                    best_distance = distance
                    best_registry = registry
        
        if best_registry:
            allocator = ResourceAllocator(best_registry)
            return allocator.allocate(request)
        
        return None
    
    def optimize_federation_resources(self):
        """优化联邦资源分配"""
        with self.lock:
            logger.info("优化联邦资源分配...")
            
            # 收集所有系统的资源使用情况
            resource_map: Dict[ResourceType, List[Tuple[float, StarSystem]]] = defaultdict(list)
            
            for registry in self.registries.values():
                for system in registry.systems.values():
                    for res_type in ResourceType:
                        amount = system.resources.get(res_type)
                        if amount > 0:
                            utilization = system.metrics.utilization
                            resource_map[res_type].append((utilization, system))
            
            # 重新分配负载
            for res_type, systems in resource_map.items():
                if len(systems) < 2:
                    continue
                
                systems.sort(key=lambda x: x[0])
                low_util = systems[0]
                high_util = systems[-1]
                
                # 从高负载系统转移资源
                logger.info(f"优化 {res_type.name}: {low_util[1].name} < {high_util[1].name}")


class ResourceAuction:
    """资源拍卖系统"""
    
    def __init__(self, allocator: ResourceAllocator):
        self.allocator = allocator
        self.active_auctions: Dict[str, Dict[str, Any]] = {}
        self.auction_history: List[Dict[str, Any]] = []
        
        self.lock = threading.RLock()
    
    def create_auction(self, resource_type: ResourceType, amount: float,
                      starting_price: float, duration: float) -> str:
        """创建拍卖"""
        auction_id = str(uuid.uuid4())
        
        auction = {
            "id": auction_id,
            "resource_type": resource_type,
            "amount": amount,
            "starting_price": starting_price,
            "current_price": starting_price,
            "duration": duration,
            "start_time": time.time(),
            "bids": [],
            "active": True
        }
        
        with self.lock:
            self.active_auctions[auction_id] = auction
        
        logger.info(f"拍卖创建: {resource_type.name} x {amount}, 起价: {starting_price}")
        return auction_id
    
    def place_bid(self, auction_id: str, bidder_id: str, amount: float) -> bool:
        """出价"""
        with self.lock:
            if auction_id not in self.active_auctions:
                return False
            
            auction = self.active_auctions[auction_id]
            
            if not auction["active"]:
                return False
            
            if amount <= auction["current_price"]:
                return False
            
            # 验证出价者有足够资源
            # (简化版本)
            
            auction["bids"].append({
                "bidder_id": bidder_id,
                "amount": amount,
                "timestamp": time.time()
            })
            auction["current_price"] = amount
            
            logger.info(f"新出价: {bidder_id} 出价 {amount}")
            return True
    
    def close_auction(self, auction_id: str) -> Optional[Dict[str, Any]]:
        """关闭拍卖"""
        with self.lock:
            if auction_id not in self.active_auctions:
                return None
            
            auction = self.active_auctions[auction_id]
            auction["active"] = False
            auction["end_time"] = time.time()
            
            # 确定获胜者
            if auction["bids"]:
                winning_bid = max(auction["bids"], key=lambda b: b["amount"])
                auction["winner"] = winning_bid["bidder_id"]
                auction["final_price"] = winning_bid["amount"]
            else:
                auction["winner"] = None
                auction["final_price"] = auction["starting_price"]
            
            self.auction_history.append(auction)
            
            logger.info(f"拍卖结束: 获胜者 {auction.get('winner')}, 价格 {auction['final_price']}")
            return auction


class AdaptiveResourceScheduler:
    """自适应资源调度器"""
    
    def __init__(self, allocator: ResourceAllocator):
        self.allocator = allocator
        self.scheduling_history: List[Dict[str, Any]] = []
        self.prediction_model: Dict[str, Any] = {}
        
        self.lock = threading.RLock()
    
    def schedule(self, requests: List[ResourceRequest]) -> List[ResourceAllocation]:
        """调度资源请求"""
        with self.lock:
            allocations = []
            
            # 预测资源需求
            predicted_demand = self._predict_demand(requests)
            
            # 动态调整策略
            self._adapt_strategy(predicted_demand)
            
            # 按批次处理
            for request in requests:
                allocation = self.allocator.allocate(request)
                if allocation:
                    allocations.append(allocation)
            
            # 记录调度历史
            self.scheduling_history.append({
                "timestamp": time.time(),
                "requests_count": len(requests),
                "allocations_count": len(allocations),
                "strategy": self.allocator.strategy.name,
                "predicted_demand": predicted_demand
            })
            
            return allocations
    
    def _predict_demand(self, requests: List[ResourceRequest]) -> Dict[ResourceType, float]:
        """预测资源需求"""
        demand = defaultdict(float)
        
        for request in requests:
            demand[request.resource_type] += request.amount
        
        return dict(demand)
    
    def _adapt_strategy(self, predicted_demand: Dict[ResourceType, float]):
        """根据预测自适应调整策略"""
        total_demand = sum(predicted_demand.values())
        
        if total_demand > 10000:
            # 高需求时使用负载均衡
            self.allocator.set_strategy(AllocationStrategy.LOAD_BALANCED)
        elif total_demand < 1000:
            # 低需求时使用效率优先
            self.allocator.set_strategy(AllocationStrategy.EFFICIENCY)
        else:
            # 正常需求使用公平分享
            self.allocator.set_strategy(AllocationStrategy.FAIR_SHARE)


# 演示代码
def demo():
    """演示星际资源分配系统"""
    logger.info("=" * 60)
    logger.info("星际资源分配系统演示")
    logger.info("=" * 60)
    
    # 创建资源注册中心
    registry = InterstellarResourceRegistry("milky-way")
    
    # 创建资源分配器
    allocator = ResourceAllocator(registry)
    allocator.set_strategy(AllocationStrategy.DISTANCE_AWARE)
    
    # 创建资源请求
    requests = [
        ResourceRequest(
            requester_id="task-001",
            resource_type=ResourceType.COMPUTATION,
            amount=500,
            priority=ResourcePriority.HIGH,
            duration=3600,
            source_position=(0, 0, 0)
        ),
        ResourceRequest(
            requester_id="task-002",
            resource_type=ResourceType.STORAGE,
            amount=1000,
            priority=ResourcePriority.NORMAL,
            duration=86400,
            source_position=(4, 0, 0)
        ),
        ResourceRequest(
            requester_id="task-003",
            resource_type=ResourceType.BANDWIDTH,
            amount=100,
            priority=ResourcePriority.LOW,
            duration=7200,
            source_position=(8, 0, 0)
        ),
    ]
    
    # 提交请求并分配
    for req in requests:
        registry.submit_request(req)
        allocation = allocator.allocate(req)
        
        if allocation:
            logger.info(f"分配成功: {allocation.allocation_id} -> 系统 {allocation.system_id}")
    
    # 显示系统状态
    logger.info("\n恒星系统资源状态:")
    for system in registry.systems.values():
        logger.info(f"  {system.name}: 计算={system.resources.computation}, "
                   f"存储={system.resources.storage}, 带宽={system.resources.bandwidth}")
    
    # 测试资源释放
    if registry.allocations:
        first_allocation = list(registry.allocations.keys())[0]
        allocator.release_allocation(first_allocation)
        logger.info(f"\n释放分配: {first_allocation}")
    
    # 联邦资源管理演示
    federation = FederatedResourceManager()
    federation.register_registry(registry)
    federation.optimize_federation_resources()
    
    # 拍卖演示
    auction = ResourceAuction(allocator)
    auction_id = auction.create_auction(
        ResourceType.QUANTUM,
        amount=100,
        starting_price=1000,
        duration=300
    )
    
    auction.place_bid(auction_id, "bidder-1", 1500)
    auction.place_bid(auction_id, "bidder-2", 2000)
    auction.close_auction(auction_id)
    
    # 统计信息
    stats = allocator.get_allocation_stats()
    logger.info(f"\n分配统计: {json.dumps(stats, indent=2)}")
    
    logger.info("=" * 60)
    logger.info("演示完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    demo()