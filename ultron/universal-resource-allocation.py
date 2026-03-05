#!/usr/bin/env python3
"""
宇宙资源调配系统 - Universal Resource Allocation
夙愿二十八第2世：跨宇宙协作
实现跨宇宙资源的高效调配、负载均衡和动态分配
"""

import json
import time
import random
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from collections import defaultdict
import heapq


class ResourceType(Enum):
    """资源类型"""
    ENERGY = "energy"
    MATTER = "matter"
    INFORMATION = "information"
    TIME = "time"
    SPACE = "space"
    DIMENSIONAL = "dimensional"
    QUANTUM = "quantum"
    CONSCIOUSNESS = "consciousness"


class ResourceState(Enum):
    """资源状态"""
    AVAILABLE = "available"
    ALLOCATED = "allocated"
    RESERVED = "reserved"
    DEPLETED = "depleted"
    RECYCLING = "recycling"


class AllocationStrategy(Enum):
    """分配策略"""
    EQUAL = "equal"                     # 平等分配
    PRIORITY = "priority"               # 优先级分配
    EFFICIENCY = "efficiency"           # 效率优先
    LOAD_BALANCE = "load_balance"       # 负载均衡
    ADAPTIVE = "adaptive"               # 自适应分配


@dataclass
class UniversalResource:
    """通用资源"""
    resource_id: str
    resource_type: ResourceType
    quantity: float
    quality: float
    universe_origin: str
    state: ResourceState
    allocated_to: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResourceRequest:
    """资源请求"""
    request_id: str
    requester_id: str
    target_universe: str
    resource_type: ResourceType
    quantity: float
    priority: int
    constraints: Dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    allocated_resources: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


class UniverseResourcePool:
    """宇宙资源池"""
    
    def __init__(self, universe_id: str):
        self.universe_id = universe_id
        self.resources: Dict[str, UniversalResource] = {}
        self.total_resources: Dict[ResourceType, float] = defaultdict(float)
        self.available_resources: Dict[ResourceType, float] = defaultdict(float)
        self.lock = threading.RLock()
        self._init_resources()
    
    def _init_resources(self):
        """初始化宇宙资源"""
        base_resources = {
            ResourceType.ENERGY: random.uniform(800, 1200),
            ResourceType.MATTER: random.uniform(600, 1000),
            ResourceType.INFORMATION: random.uniform(1000, 1500),
            ResourceType.TIME: random.uniform(500, 800),
            ResourceType.SPACE: random.uniform(700, 1100),
            ResourceType.DIMENSIONAL: random.uniform(300, 600),
            ResourceType.QUANTUM: random.uniform(200, 500),
            ResourceType.CONSCIOUSNESS: random.uniform(100, 300)
        }
        
        for rtype, quantity in base_resources.items():
            resource_id = f"{self.universe_id}-{rtype.value}-core"
            resource = UniversalResource(
                resource_id=resource_id,
                resource_type=rtype,
                quantity=quantity,
                quality=random.uniform(0.8, 1.0),
                universe_origin=self.universe_id,
                state=ResourceState.AVAILABLE
            )
            self.resources[resource_id] = resource
            self.total_resources[rtype] = quantity
            self.available_resources[rtype] = quantity
    
    def allocate(self, resource_type: ResourceType, quantity: float, 
                 requester_id: str) -> List[str]:
        """分配资源"""
        with self.lock:
            if self.available_resources[resource_type] < quantity:
                return []
            
            allocated = []
            remaining = quantity
            
            for res_id, resource in self.resources.items():
                if (resource.resource_type == resource_type and 
                    resource.state == ResourceState.AVAILABLE and
                    remaining > 0):
                    
                    alloc_amount = min(resource.quantity, remaining)
                    resource.quantity -= alloc_amount
                    resource.allocated_to = requester_id
                    resource.state = ResourceState.ALLOCATED
                    resource.last_access = time.time()
                    
                    allocated.append(res_id)
                    remaining -= alloc_amount
                    
                    if resource.quantity <= 0:
                        self.available_resources[resource_type] -= alloc_amount
                    
                    if remaining <= 0:
                        break
            
            return allocated
    
    def release(self, resource_ids: List[str]) -> float:
        """释放资源"""
        with self.lock:
            released = 0
            for res_id in resource_ids:
                if res_id in self.resources:
                    resource = self.resources[res_id]
                    if resource.state == ResourceState.ALLOCATED:
                        resource.state = ResourceState.AVAILABLE
                        resource.allocated_to = None
                        self.available_resources[resource.resource_type] += resource.quantity
                        released += resource.quantity
            return released
    
    def get_available(self, resource_type: ResourceType) -> float:
        """获取可用资源量"""
        return self.available_resources.get(resource_type, 0)
    
    def get_total(self, resource_type: ResourceType) -> float:
        """获取总资源量"""
        return self.total_resources.get(resource_type, 0)


class ResourceAllocator:
    """资源分配器"""
    
    def __init__(self):
        self.universe_pools: Dict[str, UniverseResourcePool] = {}
        self.requests: Dict[str, ResourceRequest] = {}
        self.allocation_history: List[Dict] = []
        self.lock = threading.RLock()
        self.request_counter = 0
        self._init_universe_pools()
    
    def _init_universe_pools(self):
        """初始化宇宙资源池"""
        universes = ["prime-0", "mirror-0", "parallel-0", "virtual-0", "dark-0"]
        for universe_id in universes:
            self.universe_pools[universe_id] = UniverseResourcePool(universe_id)
    
    def create_request(self, requester_id: str, target_universe: str,
                       resource_type: ResourceType, quantity: float,
                       priority: int = 5, constraints: Dict = None) -> str:
        """创建资源请求"""
        with self.lock:
            self.request_counter += 1
            request_id = f"req-{self.request_counter}"
            
            request = ResourceRequest(
                request_id=request_id,
                requester_id=requester_id,
                target_universe=target_universe,
                resource_type=resource_type,
                quantity=quantity,
                priority=priority,
                constraints=constraints or {}
            )
            
            self.requests[request_id] = request
            return request_id
    
    def allocate_resources(self, request_id: str, 
                           strategy: AllocationStrategy = AllocationStrategy.ADAPTIVE) -> bool:
        """分配资源"""
        with self.lock:
            if request_id not in self.requests:
                return False
            
            request = self.requests[request_id]
            
            if request.status != "pending":
                return False
            
            pool = self.universe_pools.get(request.target_universe)
            if not pool:
                return False
            
            allocated = pool.allocate(
                request.resource_type,
                request.quantity,
                request.requester_id
            )
            
            if allocated:
                request.allocated_resources = allocated
                request.status = "allocated"
                
                self.allocation_history.append({
                    "request_id": request_id,
                    "requester": request.requester_id,
                    "universe": request.target_universe,
                    "resource_type": request.resource_type.value,
                    "quantity": request.quantity,
                    "timestamp": time.time()
                })
                
                return True
            
            return False
    
    def release_resources(self, request_id: str) -> float:
        """释放资源"""
        with self.lock:
            if request_id not in self.requests:
                return 0
            
            request = self.requests[request_id]
            pool = self.universe_pools.get(request.target_universe)
            
            if pool:
                released = pool.release(request.allocated_resources)
                request.status = "released"
                return released
            
            return 0
    
    def get_resource_status(self, universe_id: str) -> Dict:
        """获取宇宙资源状态"""
        pool = self.universe_pools.get(universe_id)
        if not pool:
            return {}
        
        status = {
            "universe": universe_id,
            "total": {},
            "available": {},
            "utilization": {}
        }
        
        for rtype in ResourceType:
            total = pool.get_total(rtype)
            available = pool.get_available(rtype)
            status["total"][rtype.value] = total
            status["available"][rtype.value] = available
            status["utilization"][rtype.value] = (total - available) / total if total > 0 else 0
        
        return status
    
    def optimize_allocation(self) -> Dict:
        """优化资源分配"""
        optimizations = []
        
        for universe_id, pool in self.universe_pools.items():
            for rtype in ResourceType:
                total = pool.get_total(rtype)
                available = pool.get_available(rtype)
                utilization = (total - available) / total if total > 0 else 0
                
                if utilization < 0.3:
                    optimizations.append({
                        "universe": universe_id,
                        "resource_type": rtype.value,
                        "issue": "underutilized",
                        "suggestion": "redistribute to high-demand universes"
                    })
                elif utilization > 0.9:
                    optimizations.append({
                        "universe": universe_id,
                        "resource_type": rtype.value,
                        "issue": "overloaded",
                        "suggestion": "request resources from other universes"
                    })
        
        return {
            "optimizations": optimizations,
            "timestamp": time.time()
        }


class CrossUniverseLoadBalancer:
    """跨宇宙负载均衡器"""
    
    def __init__(self, allocator: ResourceAllocator):
        self.allocator = allocator
        self.load_history: Dict[str, List[float]] = defaultdict(list)
        self.lock = threading.Lock()
    
    def calculate_universe_load(self, universe_id: str) -> float:
        """计算宇宙负载"""
        status = self.allocator.get_resource_status(universe_id)
        if not status:
            return 0
        
        total_utilization = sum(status["utilization"].values())
        resource_types = len(status["utilization"])
        
        return total_utilization / resource_types if resource_types > 0 else 0
    
    def get_least_loaded_universe(self, resource_type: ResourceType) -> str:
        """获取负载最低的宇宙"""
        min_load = float('inf')
        best_universe = None
        
        for universe_id in self.allocator.universe_pools:
            pool = self.allocator.universe_pools[universe_id]
            available = pool.get_available(resource_type)
            total = pool.get_total(resource_type)
            
            if total > 0:
                load = 1 - (available / total)
                if load < min_load:
                    min_load = load
                    best_universe = universe_id
        
        return best_universe or "prime-0"
    
    def redistribute_resources(self) -> Dict:
        """重新分配资源"""
        redistribution_plan = []
        
        for universe_id in self.allocator.universe_pools:
            load = self.calculate_universe_load(universe_id)
            self.load_history[universe_id].append(load)
            
            if load > 0.8:
                status = self.allocator.get_resource_status(universe_id)
                for rtype_name, util in status["utilization"].items():
                    if util > 0.8:
                        target = self.get_least_loaded_universe(ResourceType[rtype_name.upper()])
                        if target != universe_id:
                            redistribution_plan.append({
                                "from": universe_id,
                                "to": target,
                                "resource_type": rtype_name,
                                "reason": "high_load"
                            })
        
        return {
            "redistribution_plan": redistribution_plan,
            "timestamp": time.time()
        }


class ResourceReservation:
    """资源预留系统"""
    
    def __init__(self, allocator: ResourceAllocator):
        self.allocator = allocator
        self.reservations: Dict[str, Dict] = {}
        self.reservation_counter = 0
        self.lock = threading.Lock()
    
    def create_reservation(self, requester_id: str, universe: str,
                          resource_type: ResourceType, quantity: float,
                          duration: float) -> str:
        """创建资源预留"""
        with self.lock:
            self.reservation_counter += 1
            reservation_id = f"res-{self.reservation_counter}"
            
            self.reservations[reservation_id] = {
                "reservation_id": reservation_id,
                "requester_id": requester_id,
                "universe": universe,
                "resource_type": resource_type,
                "quantity": quantity,
                "duration": duration,
                "created_at": time.time(),
                "expires_at": time.time() + duration,
                "status": "active"
            }
            
            return reservation_id
    
    def validate_reservation(self, reservation_id: str) -> bool:
        """验证预留是否有效"""
        if reservation_id not in self.reservations:
            return False
        
        res = self.reservations[reservation_id]
        return (res["status"] == "active" and 
                time.time() < res["expires_at"])
    
    def cancel_reservation(self, reservation_id: str) -> bool:
        """取消预留"""
        with self.lock:
            if reservation_id in self.reservations:
                self.reservations[reservation_id]["status"] = "cancelled"
                return True
            return False


def demo():
    """演示宇宙资源调配系统"""
    print("=" * 60)
    print("宇宙资源调配系统 - Universal Resource Allocation Demo")
    print("=" * 60)
    
    allocator = ResourceAllocator()
    load_balancer = CrossUniverseLoadBalancer(allocator)
    reservation = ResourceReservation(allocator)
    
    print("\n[1] 查看宇宙资源状态...")
    for universe in ["prime-0", "mirror-0", "parallel-0"]:
        status = allocator.get_resource_status(universe)
        print(f"\n  {universe}:")
        for rtype in [ResourceType.ENERGY, ResourceType.MATTER, ResourceType.INFORMATION]:
            if rtype.value in status["available"]:
                print(f"    {rtype.value}: {status['available'][rtype.value]:.1f} / {status['total'][rtype.value]:.1f}")
    
    print("\n[2] 创建资源请求...")
    req1 = allocator.create_request(
        requester_id="agent-1",
        target_universe="prime-0",
        resource_type=ResourceType.ENERGY,
        quantity=200,
        priority=8
    )
    print(f"  请求ID: {req1}")
    
    req2 = allocator.create_request(
        requester_id="agent-2",
        target_universe="mirror-0",
        resource_type=ResourceType.INFORMATION,
        quantity=300,
        priority=6
    )
    print(f"  请求ID: {req2}")
    
    print("\n[3] 分配资源...")
    result1 = allocator.allocate_resources(req1)
    result2 = allocator.allocate_resources(req2)
    print(f"  请求1: {'成功' if result1 else '失败'}")
    print(f"  请求2: {'成功' if result2 else '失败'}")
    
    print("\n[4] 创建资源预留...")
    res_id = reservation.create_reservation(
        requester_id="agent-3",
        universe="parallel-0",
        resource_type=ResourceType.DIMENSIONAL,
        quantity=100,
        duration=3600
    )
    print(f"  预留ID: {res_id}")
    print(f"  验证: {reservation.validate_reservation(res_id)}")
    
    print("\n[5] 优化资源分配...")
    optimizations = allocator.optimize_allocation()
    print(f"  优化建议数量: {len(optimizations['optimizations'])}")
    
    print("\n[6] 负载均衡...")
    for universe in ["prime-0", "mirror-0", "parallel-0"]:
        load = load_balancer.calculate_universe_load(universe)
        print(f"  {universe}: {load*100:.1f}%")
    
    redistribution = load_balancer.redistribute_resources()
    print(f"  重新分配计划: {len(redistribution['redistribution_plan'])} 项")
    
    print("\n[7] 释放资源...")
    released = allocator.release_resources(req1)
    print(f"  释放能量: {released}")
    
    print("\n" + "=" * 60)
    print("宇宙资源调配系统 - 运行完成")
    print("=" * 60)


if __name__ == "__main__":
    demo()