#!/usr/bin/env python3
"""
星际虫洞网络 - Interstellar Wormhole Network
第3世：银河级智能 - 星际虫洞网络

实现跨星际即时通信与物质传输的虫洞网络系统
"""

import asyncio
import json
import time
import uuid
import hashlib
import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import numpy as np

class WormholeStatus(Enum):
    """虫洞状态"""
    STABLE = "stable"
    UNSTABLE = "unstable"
    COLLAPSING = "collapsing"
    EXPANDING = "expanding"
    ACTIVE = "active"
    DORMANT = "dormant"

class WormholeType(Enum):
    """虫洞类型"""
    MICRO = "micro"              # 微观虫洞（量子通信）
    MESO = "meso"                # 中型虫洞（信息传输）
    MACRO = "macro"              # 大型虫洞（物质传输）
    GALACTIC = "galactic"        # 银河级虫洞（时空隧道）

class EnergyType(Enum):
    """能量类型"""
    EXOTIC = "exotic"            # 奇异物质
    DARK = "dark"                # 暗能量
    VACUUM = "vacuum"            # 真空能
    STELLAR = "stellar"          # 恒星能
    HAWKING = "hawking"          # 霍金辐射

@dataclass
class WormholeEndpoint:
    """虫洞端点"""
    endpoint_id: str
    coordinates: Tuple[float, float, float]  # 银河系坐标 (x, y, z) 单位：光年
    system_name: str
    stability: float              # 稳定性 0-1
    capacity: float               # 容量 (TB/s 或 物质吨位)
    energy_requirement: float     # 能量需求 (GW)
    last_maintenance: float

@dataclass
class Wormhole:
    """虫洞"""
    wormhole_id: str
    wormhole_type: WormholeType
    endpoint_a: WormholeEndpoint
    endpoint_b: WormholeEndpoint
    status: WormholeStatus
    created: float
    stability: float
    bandwidth: float              # 带宽 (TB/s)
    latency: float                # 延迟 (秒)
    energy_cost: float            # 能量消耗 (GW)
    traversal_count: int = 0
    energy_reserve: float = 1.0   # 能量储备 0-1
    theoretical_distance: float = 0.0  # 理论上的物理距离（光年）

class WormholeNetwork:
    """虫洞网络主类"""
    
    def __init__(self):
        self.wormholes: Dict[str, Wormhole] = {}
        self.endpoints: Dict[str, WormholeEndpoint] = {}
        self.routing_table: Dict[str, Dict[str, Any]] = {}
        
        # 网络参数
        self.max_wormholes = 10000
        self.stability_threshold = 0.6
        self.energy_efficiency = 0.85
        self.quantum_entanglement_range = 1000  # 光年
        
        # 能量管理
        self.energy_pools: Dict[str, float] = defaultdict(lambda: 1e12)  # GW
        self.energy_transfers: List[Dict] = []
        
        # 虫洞生成参数
        self.exotic_matter_required = {
            WormholeType.MICRO: 1e-10,      # 克
            WormholeType.MESO: 1e-6,        # 克
            WormholeType.MACRO: 1e3,        # 公斤
            WormholeType.GALACTIC: 1e9      # 吨
        }
    
    async def create_wormhole(
        self, 
        coord_a: Tuple[float, float, float], 
        coord_b: Tuple[float, float, float],
        wormhole_type: WormholeType = WormholeType.MESO,
        system_a: str = "Unknown",
        system_b: str = "Unknown"
    ) -> str:
        """创建虫洞"""
        if len(self.wormholes) >= self.max_wormholes:
            raise Exception("Maximum wormholes reached")
        
        wormhole_id = f"WH-{uuid.uuid4().hex[:12]}"
        
        # 计算实际距离
        actual_distance = self._calculate_distance(coord_a, coord_b)
        
        # 创建端点
        endpoint_a = WormholeEndpoint(
            endpoint_id=f"EP-{uuid.uuid4().hex[:8]}",
            coordinates=coord_a,
            system_name=system_a,
            stability=0.9,
            capacity=self._get_capacity(wormhole_type),
            energy_requirement=self._get_energy_requirement(wormhole_type, actual_distance),
            last_maintenance=time.time()
        )
        
        endpoint_b = WormholeEndpoint(
            endpoint_id=f"EP-{uuid.uuid4().hex[:8]}",
            coordinates=coord_b,
            system_name=system_b,
            stability=0.9,
            capacity=self._get_capacity(wormhole_type),
            energy_requirement=self._get_energy_requirement(wormhole_type, actual_distance),
            last_maintenance=time.time()
        )
        
        # 计算虫洞属性
        if wormhole_type == WormholeType.GALACTIC:
            # 银河级虫洞：几乎瞬时
            latency = 0.001  # 毫秒级
            stability = 0.95
        elif actual_distance > 10000:
            # 远距离：显著缩短
            latency = max(0.1, actual_distance / 299792.0 * 0.0001)  # 光年的万分之一
            stability = 0.8
        else:
            latency = actual_distance / 299792.0  # 光速时间
            stability = 0.85
        
        wormhole = Wormhole(
            wormhole_id=wormhole_id,
            wormhole_type=wormhole_type,
            endpoint_a=endpoint_a,
            endpoint_b=endpoint_b,
            status=WormholeStatus.ACTIVE,
            created=time.time(),
            stability=stability,
            bandwidth=self._calculate_bandwidth(wormhole_type, stability),
            latency=latency,
            energy_cost=self._calculate_energy_cost(wormhole_type, actual_distance),
            theoretical_distance=actual_distance
        )
        
        self.wormholes[wormhole_id] = wormhole
        self.endpoints[endpoint_a.endpoint_id] = endpoint_a
        self.endpoints[endpoint_b.endpoint_id] = endpoint_b
        
        # 更新路由表
        await self._update_routing_table(wormhole_id)
        
        return wormhole_id
    
    def _calculate_distance(self, coord_a: Tuple, coord_b: Tuple) -> float:
        """计算两点之间的欧氏距离（光年）"""
        return math.sqrt(
            (coord_b[0] - coord_a[0])**2 + 
            (coord_b[1] - coord_a[1])**2 + 
            (coord_b[2] - coord_a[2])**2
        )
    
    def _get_capacity(self, wormhole_type: WormholeType) -> float:
        """获取虫洞容量"""
        capacities = {
            WormholeType.MICRO: 1e12,       # 1 TB/s
            WormholeType.MESO: 1e15,        # 1 PB/s
            WormholeType.MACRO: 1e9,        # 1 百万吨
            WormholeType.GALACTIC: 1e18     # 1 EB/s 或 10亿吨
        }
        return capacities[wormhole_type]
    
    def _get_energy_requirement(self, wormhole_type: WormholeType, distance: float) -> float:
        """计算能量需求"""
        base_energy = {
            WormholeType.MICRO: 1e6,        # 1 GW
            WormholeType.MESO: 1e9,         # 1 TW
            WormholeType.MACRO: 1e12,       # 1 PW
            WormholeType.GALACTIC: 1e15     # 1 EW
        }
        
        # 能量需求与距离成正比
        return base_energy[wormhole_type] * (1 + distance / 100000)
    
    def _calculate_bandwidth(self, wormhole_type: WormholeType, stability: float) -> float:
        """计算带宽"""
        base_bandwidth = {
            WormholeType.MICRO: 1e12,       # TB/s
            WormholeType.MESO: 1e15,        # PB/s
            WormholeType.MACRO: 1e6,        # 吨/秒
            WormholeType.GALACTIC: 1e18     # EB/s
        }
        return base_bandwidth[wormhole_type] * stability
    
    def _calculate_energy_cost(self, wormhole_type: WormholeType, distance: float) -> float:
        """计算能量消耗"""
        base_cost = {
            WormholeType.MICRO: 1e6,        # GW
            WormholeType.MESO: 1e9,         # TW
            WormholeType.MACRO: 1e12,       # PW
            WormholeType.GALACTIC: 1e15     # EW
        }
        
        # 能量消耗与距离成对数关系
        return base_cost[wormhole_type] * math.log2(1 + distance / 1000)
    
    async def _update_routing_table(self, wormhole_id: str):
        """更新路由表"""
        wormhole = self.wormholes[wormhole_id]
        
        # 获取所有可达端点
        all_endpoints = list(self.endpoints.keys())
        
        for ep_a in all_endpoints:
            if ep_a not in self.routing_table:
                self.routing_table[ep_a] = {}
            
            for ep_b in all_endpoints:
                if ep_a != ep_b:
                    path = self._find_shortest_path(ep_a, ep_b)
                    if path:
                        self.routing_table[ep_a][ep_b] = path
    
    def _find_shortest_path(self, from_endpoint: str, to_endpoint: str) -> Optional[Dict]:
        """使用Dijkstra算法寻找最短路径"""
        if from_endpoint == to_endpoint:
            return {"hops": 0, "total_latency": 0, "route": [from_endpoint]}
        
        # 简化的路由计算
        for wh in self.wormholes.values():
            if wh.status != WormholeStatus.ACTIVE:
                continue
            
            route_a_to_b = None
            route_b_to_a = None
            
            if wh.endpoint_a.endpoint_id == from_endpoint and wh.endpoint_b.endpoint_id == to_endpoint:
                route_a_to_b = {"hops": 1, "total_latency": wh.latency, "route": [from_endpoint, to_endpoint], "wormhole": wh.wormhole_id}
            
            if wh.endpoint_b.endpoint_id == from_endpoint and wh.endpoint_a.endpoint_id == to_endpoint:
                route_b_to_a = {"hops": 1, "total_latency": wh.latency, "route": [from_endpoint, to_endpoint], "wormhole": wh.wormhole_id}
            
            if route_a_to_b:
                return route_a_to_b
            if route_b_to_a:
                return route_b_to_a
        
        return None
    
    async def transmit_data(
        self, 
        wormhole_id: str, 
        data_size: float,  # TB
        priority: int = 1
    ) -> Dict[str, Any]:
        """通过虫洞传输数据"""
        if wormhole_id not in self.wormholes:
            raise Exception("Wormhole not found")
        
        wormhole = self.wormholes[wormhole_id]
        
        if wormhole.status != WormholeStatus.ACTIVE:
            return {"success": False, "reason": "Wormhole not active"}
        
        # 检查带宽
        transmission_time = data_size / wormhole.bandwidth
        
        if transmission_time > 3600:  # 超过1小时
            return {"success": False, "reason": "Data too large"}
        
        # 检查能量
        required_energy = wormhole.energy_cost * (transmission_time / 3600)
        
        if wormhole.energy_reserve < required_energy / 1e12:  # 转换单位
            # 尝试从能量池获取
            await self._recharge_wormhole(wormhole_id)
        
        # 执行传输
        await asyncio.sleep(min(transmission_time, 0.1))  # 模拟
        
        wormhole.traversal_count += 1
        wormhole.energy_reserve -= required_energy / 1e12
        
        return {
            "success": True,
            "transmission_time": transmission_time,
            "wormhole_id": wormhole_id,
            "from": wormhole.endpoint_a.system_name,
            "to": wormhole.endpoint_b.system_name
        }
    
    async def transmit_matter(
        self,
        wormhole_id: str,
        mass: float,  # 吨
        priority: int = 1
    ) -> Dict[str, Any]:
        """通过虫洞传输物质"""
        if wormhole_id not in self.wormholes:
            raise Exception("Wormhole not found")
        
        wormhole = self.wormholes[wormhole_id]
        
        if wormhole.wormhole_type not in [WormholeType.MACRO, WormholeType.GALACTIC]:
            return {"success": False, "reason": "Wormhole type cannot transport matter"}
        
        # 检查容量
        if mass > wormhole.bandwidth:  # 这里的bandwidth用于物质传输
            return {"success": False, "reason": "Mass exceeds capacity"}
        
        # 计算传输时间（物质需要更长时间）
        base_time = wormhole.latency
        mass_penalty = mass / 1000  # 每吨增加延迟
        transmission_time = base_time + mass_penalty
        
        # 执行传输
        await asyncio.sleep(min(transmission_time, 0.1))
        
        wormhole.traversal_count += 1
        
        return {
            "success": True,
            "transmission_time": transmission_time,
            "wormhole_id": wormhole_id,
            "mass_transferred": mass,
            "from": wormhole.endpoint_a.system_name,
            "to": wormhole.endpoint_b.system_name
        }
    
    async def _recharge_wormhole(self, wormhole_id: str):
        """为虫洞充能"""
        wormhole = self.wormholes[wormhole_id]
        
        # 从最近恒星获取能量
        energy_transfer = wormhole.energy_cost * 0.5
        wormhole.energy_reserve = min(1.0, wormhole.energy_reserve + 0.3)
        
        self.energy_transfers.append({
            "wormhole_id": wormhole_id,
            "energy": energy_transfer,
            "timestamp": time.time()
        })
    
    async def stabilize_wormhole(self, wormhole_id: str) -> bool:
        """稳定虫洞"""
        if wormhole_id not in self.wormholes:
            return False
        
        wormhole = self.wormholes[wormhole_id]
        
        # 增加稳定性
        wormhole.stability = min(1.0, wormhole.stability + 0.1)
        wormhole.status = WormholeStatus.STABLE
        
        # 更新端点稳定性
        wormhole.endpoint_a.stability = wormhole.stability
        wormhole.endpoint_b.stability = wormhole.stability
        
        return True
    
    async def collapse_wormhole(self, wormhole_id: str) -> bool:
        """坍塌虫洞"""
        if wormhole_id not in self.wormholes:
            return False
        
        wormhole = self.wormholes[wormhole_id]
        
        # 逐渐坍塌
        for _ in range(5):
            wormhole.stability -= 0.2
            wormhole.status = WormholeStatus.COLLAPSING
            await asyncio.sleep(0.1)
        
        # 移除虫洞
        del self.wormholes[wormhole_id]
        del self.endpoints[wormhole.endpoint_a.endpoint_id]
        del self.endpoints[wormhole.endpoint_b.endpoint_id]
        
        return True
    
    async def analyze_stability(self) -> Dict[str, Any]:
        """分析网络稳定性"""
        if not self.wormholes:
            return {"status": "no_wormholes"}
        
        total_stability = 0.0
        stable_count = 0
        unstable_count = 0
        
        for wh in self.wormholes.values():
            total_stability += wh.stability
            if wh.stability >= self.stability_threshold:
                stable_count += 1
            else:
                unstable_count += 1
        
        avg_stability = total_stability / len(self.wormholes)
        
        return {
            "total_wormholes": len(self.wormholes),
            "stable_count": stable_count,
            "unstable_count": unstable_count,
            "average_stability": avg_stability,
            "network_health": "healthy" if avg_stability > 0.8 else "degraded",
            "total_traversals": sum(wh.traversal_count for wh in self.wormholes.values())
        }
    
    def get_wormhole_info(self, wormhole_id: str) -> Optional[Dict]:
        """获取虫洞信息"""
        if wormhole_id not in self.wormholes:
            return None
        
        wh = self.wormholes[wormhole_id]
        
        return {
            "wormhole_id": wh.wormhole_id,
            "type": wh.wormhole_type.name,
            "status": wh.status.name,
            "endpoint_a": {
                "system": wh.endpoint_a.system_name,
                "coordinates": wh.endpoint_a.coordinates,
                "stability": wh.endpoint_a.stability
            },
            "endpoint_b": {
                "system": wh.endpoint_b.system_name,
                "coordinates": wh.endpoint_b.coordinates,
                "stability": wh.endpoint_b.stability
            },
            "theoretical_distance": f"{wh.theoretical_distance:.1f} light-years",
            "actual_latency": f"{wh.latency:.6f} seconds",
            "bandwidth": f"{wh.bandwidth:.2e}",
            "traversals": wh.traversal_count,
            "energy_reserve": f"{wh.energy_reserve:.1%}"
        }
    
    def find_route(self, from_system: str, to_system: str) -> Optional[Dict]:
        """查找路由"""
        from_ep = None
        to_ep = None
        
        for ep in self.endpoints.values():
            if ep.system_name == from_system:
                from_ep = ep.endpoint_id
            if ep.system_name == to_system:
                to_ep = ep.endpoint_id
        
        if not from_ep or not to_ep:
            return None
        
        return self._find_shortest_path(from_ep, to_ep)
    
    async def expand_network(self, target_systems: List[Tuple[str, Tuple[float, float, float]]]):
        """扩展网络到新系统"""
        new_wormholes = []
        
        # 找到最近的可连接点
        for system_name, coords in target_systems:
            # 寻找最近的现有端点
            nearest = None
            min_distance = float('inf')
            
            for ep in self.endpoints.values():
                dist = self._calculate_distance(coords, ep.coordinates)
                if dist < min_distance:
                    min_distance = dist
                    nearest = ep
            
            if nearest:
                # 确定虫洞类型
                if min_distance > 50000:
                    wh_type = WormholeType.GALACTIC
                elif min_distance > 10000:
                    wh_type = WormholeType.MACRO
                elif min_distance > 1000:
                    wh_type = WormholeType.MESO
                else:
                    wh_type = WormholeType.MICRO
                
                # 创建虫洞
                try:
                    wh_id = await self.create_wormhole(
                        nearest.coordinates,
                        coords,
                        wh_type,
                        nearest.system_name,
                        system_name
                    )
                    new_wormholes.append(wh_id)
                except Exception as e:
                    print(f"Failed to create wormhole to {system_name}: {e}")
        
        return new_wormholes
    
    def get_network_topology(self) -> Dict[str, Any]:
        """获取网络拓扑"""
        connections = []
        
        for wh in self.wormholes.values():
            connections.append({
                "from": wh.endpoint_a.system_name,
                "to": wh.endpoint_b.system_name,
                "type": wh.wormhole_type.name,
                "distance": wh.theoretical_distance,
                "latency": wh.latency,
                "stability": wh.stability
            })
        
        return {
            "total_wormholes": len(self.wormholes),
            "total_endpoints": len(self.endpoints),
            "connections": connections,
            "type_distribution": self._get_type_distribution()
        }
    
    def _get_type_distribution(self) -> Dict[str, int]:
        """获取虫洞类型分布"""
        dist = defaultdict(int)
        for wh in self.wormholes.values():
            dist[wh.wormhole_type.name] += 1
        return dict(dist)


class WormholeEnergyManager:
    """虫洞能量管理器"""
    
    def __init__(self, network: WormholeNetwork):
        self.network = network
        self.energy_sources = {}
    
    async def add_energy_source(
        self, 
        source_type: EnergyType, 
        location: Tuple[float, float, float],
        power_output: float  # GW
    ):
        """添加能量源"""
        source_id = f"ES-{uuid.uuid4().hex[:8]}"
        
        self.energy_sources[source_id] = {
            "type": source_type,
            "location": location,
            "power_output": power_output,
            "efficiency": 0.9,
            "last_update": time.time()
        }
        
        return source_id
    
    async def distribute_energy(self):
        """分配能量"""
        total_power = sum(s["power_output"] * s["efficiency"] 
                        for s in self.energy_sources.values())
        
        # 按需分配
        needed = sum(wh.energy_cost for wh in self.network.wormholes.values() 
                    if wh.status == WormholeStatus.ACTIVE)
        
        if total_power > needed:
            for wh in self.network.wormholes.values():
                if wh.status == WormholeStatus.ACTIVE and wh.energy_reserve < 0.5:
                    # 充能
                    wh.energy_reserve = min(1.0, wh.energy_reserve + 0.3)
    
    def calculate_energy_efficiency(self) -> float:
        """计算能量效率"""
        if not self.energy_sources:
            return 0.0
        
        total_output = sum(s["power_output"] * s["efficiency"] 
                         for s in self.energy_sources.values())
        total_cost = sum(wh.energy_cost for wh in self.network.wormholes.values())
        
        if total_cost == 0:
            return 1.0
        
        return min(1.0, total_output / total_cost)


class QuantumEntanglementLink:
    """量子纠缠链接 - 用于虫洞间的即时通信"""
    
    def __init__(self):
        self.entangled_pairs: Dict[str, str] = {}
        self.entanglement_states: Dict[str, Dict] = {}
    
    def create_entanglement(self, endpoint_a: str, endpoint_b: str) -> str:
        """创建量子纠缠"""
        pair_id = f"QE-{uuid.uuid4().hex[:12]}"
        
        self.entangled_pairs[endpoint_a] = endpoint_b
        self.entangled_pairs[endpoint_b] = endpoint_a
        
        self.entanglement_states[pair_id] = {
            "a": endpoint_a,
            "b": endpoint_b,
            "created": time.time(),
            "coherence": 1.0,
            "measurements": 0
        }
        
        return pair_id
    
    def measure(self, pair_id: str, endpoint: str) -> Any:
        """测量量子态"""
        if pair_id not in self.entanglement_states:
            return None
        
        state = self.entanglement_states[pair_id]
        
        # 模拟量子测量
        result = random.choice([0, 1])
        state["measurements"] += 1
        
        # 每次测量都会降低相干性
        state["coherence"] *= 0.99
        
        # 检查是否需要重新纠缠
        if state["coherence"] < 0.5:
            return {"result": result, "need_refresh": True}
        
        return {"result": result, "need_refresh": False}
    
    def teleport_state(self, pair_id: str, state: Any) -> bool:
        """量子态隐形传态"""
        if pair_id not in self.entanglement_states:
            return False
        
        entanglement = self.entanglement_states[pair_id]
        
        if entanglement["coherence"] < 0.3:
            return False
        
        # 模拟量子态传态
        return True


# 全局实例
_wormhole_network = None

def get_wormhole_network() -> WormholeNetwork:
    """获取虫洞网络实例"""
    global _wormhole_network
    if _wormhole_network is None:
        _wormhole_network = WormholeNetwork()
    return _wormhole_network


async def create_galactic_network():
    """创建银河级虫洞网络"""
    network = get_wormhole_network()
    
    # 主要恒星系统坐标（简化的银道坐标系）
    systems = [
        ("Sol", (0, 0, 0)),
        ("Sirius", (8.6, 0, 0)),
        ("Alpha Centauri", (4.37, 0, 0)),
        ("Vega", (25, 0, 0)),
        ("Betelgeuse", (700, 0, 0)),
        ("Galactic Core", (27000, 0, 0)),
        ("Kepler-442", (112, 0, 0)),
        ("Trappist-1", (39, 0, 0)),
        ("Proxima Centauri", (4.24, 0, 0)),
        ("Wolf 359", (7.78, 0, 0)),
    ]
    
    # 创建主要连接
    for i in range(len(systems) - 1):
        coord_a = systems[i][1]
        coord_b = systems[i + 1][1]
        
        # 远距离使用银河级虫洞
        dist = network._calculate_distance(coord_a, coord_b)
        wh_type = WormholeType.GALACTIC if dist > 100 else WormholeType.MESO
        
        try:
            await network.create_wormhole(
                coord_a, coord_b, wh_type,
                systems[i][0], systems[i + 1][0]
            )
        except Exception as e:
            print(f"Failed: {e}")
    
    return network


async def main():
    """主函数 - 演示虫洞网络"""
    print("🌌 星际虫洞网络初始化...")
    
    network = await create_galactic_network()
    print(f"✓ 已创建 {len(network.wormholes)} 个虫洞")
    
    # 网络分析
    analysis = await network.analyze_stability()
    print(f"✓ 网络健康度: {analysis['network_health']}")
    print(f"✓ 稳定虫洞: {analysis['stable_count']}")
    print(f"✓ 总穿越次数: {analysis['total_traversals']}")
    
    # 传输测试
    if network.wormholes:
        wh_id = list(network.wormholes.keys())[0]
        
        # 数据传输
        result = await network.transmit_data(wh_id, 1.0)
        print(f"✓ 数据传输: {result}")
        
        # 物质传输
        if network.wormholes[wh_id].wormhole_type in [WormholeType.MACRO, WormholeType.GALACTIC]:
            result = await network.transmit_matter(wh_id, 1.0)
            print(f"✓ 物质传输: {result}")
    
    # 获取拓扑
    topology = network.get_network_topology()
    print(f"\n🕸️ 网络拓扑:")
    print(f"  虫洞数: {topology['total_wormholes']}")
    print(f"  端点数: {topology['total_endpoints']}")
    print(f"  类型分布: {topology['type_distribution']}")
    
    # 路由测试
    route = network.find_route("Sol", "Alpha Centauri")
    if route:
        print(f"\n🛤️ Sol -> Alpha Centauri 路由:")
        print(f"  跳数: {route['hops']}")
        print(f"  延迟: {route['total_latency']:.6f}s")
    
    # 能量管理
    energy_mgr = WormholeEnergyManager(network)
    
    # 添加恒星能量源
    await energy_mgr.add_energy_source(EnergyType.STELLAR, (0, 0, 0), 3.846e14)  # 太阳
    print(f"\n⚡ 能量效率: {energy_mgr.calculate_energy_efficiency():.2%}")
    
    # 显示虫洞信息
    if network.wormholes:
        wh_id = list(network.wormholes.keys())[0]
        info = network.get_wormhole_info(wh_id)
        print(f"\n🔮 虫洞详情 ({wh_id}):")
        print(f"  类型: {info['type']}")
        print(f"  状态: {info['status']}")
        print(f"  距离: {info['theoretical_distance']}")
        print(f"  延迟: {info['actual_latency']}")
    
    return network


if __name__ == "__main__":
    asyncio.run(main())