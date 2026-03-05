#!/usr/bin/env python3
"""
星际路由器 (Interstellar Router)
处理星际网络中的智能路由

功能:
- 多路径路由
- 负载均衡
- 故障转移
- 成本优化路由
- 动态路径发现
"""

import time
import heapq
import random
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import math


class RouteMetric(Enum):
    """路由度量类型"""
    HOP_COUNT = "hop"        # 跳数
    LATENCY = "latency"      # 延迟
    BANDWIDTH = "bandwidth"  # 带宽
    COST = "cost"            # 成本
    RELIABILITY = "reliability"  # 可靠性
    COMPOSITE = "composite"  # 复合度量


@dataclass
class Node:
    """星际网络节点"""
    node_id: str
    position: Tuple[float, float, float]  # 3D坐标 (光年)
    bandwidth: float = 100  # Mbps
    latency_base: float = 0  # 基础延迟 (秒)
    reliability: float = 0.99  # 可靠性 0-1
    cost_per_mb: float = 0.01  # 每MB成本
    load: float = 0.0  # 当前负载 0-1
    neighbors: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    
    @property
    def available_bandwidth(self) -> float:
        return self.bandwidth * (1 - self.load)
    
    @property
    def effective_reliability(self) -> float:
        return self.reliability * (1 - self.load)


@dataclass
class Link:
    """星际网络链路"""
    link_id: str
    source: str
    destination: str
    distance: float  # 光年
    bandwidth: float = 100  # Mbps
    latency: float = 0  # 秒
    reliability: float = 0.99
    cost_per_mb: float = 0.01
    active: bool = True
    
    def __post_init__(self):
        if self.latency == 0:
            # 光年转光秒
            light_seconds_per_year = 365.25 * 24 * 3600
            self.latency = self.distance * light_seconds_per_year


@dataclass
class Route:
    """路由路径"""
    source: str
    destination: str
    path: List[str]
    metric: RouteMetric
    value: float
    hops: int
    total_latency: float
    total_bandwidth: float
    total_cost: float
    reliability: float
    
    @property
    def is_valid(self) -> bool:
        return len(self.path) > 0 and self.hops > 0


class InterstellarRouter:
    """星际路由器"""
    
    # 光秒/光年
    LIGHT_SECONDS_PER_YEAR = 365.25 * 24 * 3600
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.nodes: Dict[str, Node] = {}
        self.links: Dict[str, Link] = {}
        self.routing_table: Dict[str, Dict[str, Route]] = {}  # dest -> {metric -> route}
        self.route_cache: Dict[str, Route] = {}
        self.cache_ttl = 300  # 缓存5分钟
        
    def add_node(self, node: Node) -> None:
        """添加节点"""
        self.nodes[node.node_id] = node
        
        # 初始化路由表条目
        if node.node_id not in self.routing_table:
            self.routing_table[node.node_id] = {}
    
    def add_link(self, link: Link) -> None:
        """添加链路"""
        self.links[link.link_id] = link
        
        # 更新节点的邻居列表
        if link.source in self.nodes:
            if link.destination not in self.nodes[link.source].neighbors:
                self.nodes[link.source].neighbors.append(link.destination)
        if link.destination in self.nodes:
            if link.source not in self.nodes[link.destination].neighbors:
                self.nodes[link.destination].neighbors.append(link.source)
    
    def calculate_distance(self, pos1: Tuple[float, float, float],
                          pos2: Tuple[float, float, float]) -> float:
        """计算两点间距离"""
        dx = pos2[0] - pos1[0]
        dy = pos2[1] - pos1[1]
        dz = pos2[2] - pos2[2]
        return math.sqrt(dx**2 + dy**2 + dz**2)
    
    def find_route(self, source: str, destination: str,
                   metric: RouteMetric = RouteMetric.COMPOSITE,
                   k_paths: int = 1) -> List[Route]:
        """查找路由路径"""
        
        if source == destination:
            return [Route(source, destination, [source], metric, 0, 0, 0, 0, 0, 1.0)]
        
        if source not in self.nodes or destination not in self.nodes:
            return []
        
        # 使用Dijkstra算法找k条最短路径
        routes = self._dijkstra(source, destination, metric, k_paths)
        
        return routes
    
    def _dijkstra(self, source: str, destination: str,
                  metric: RouteMetric, k: int) -> List[Route]:
        """Dijkstra算法实现"""
        
        # 优先队列: (cost, node, path, metrics)
        pq = [(0, source, [source], {
            'latency': 0.0,
            'bandwidth': float('inf'),
            'cost': 0.0,
            'reliability': 1.0,
            'hops': 0
        })]
        
        visited: Set[str] = set()
        found_routes: List[Route] = []
        
        while pq and len(found_routes) < k:
            cost, current, path, metrics = heapq.heappop(pq)
            
            if current in visited:
                continue
            visited.add(current)
            
            if current == destination:
                route = self._create_route(source, destination, path, metric, metrics)
                if route:
                    found_routes.append(route)
                continue
            
            # 探索邻居
            current_node = self.nodes.get(current)
            if not current_node:
                continue
            
            for neighbor_id in current_node.neighbors:
                if neighbor_id in visited:
                    continue
                
                # 找到连接两节点的链路
                link = self._find_link(current, neighbor_id)
                if not link or not link.active:
                    continue
                
                # 计算扩展成本
                new_metrics = self._calculate_link_cost(metrics, link, metric)
                new_cost = self._get_composite_cost(new_metrics, metric)
                
                heapq.heappush(pq, (
                    new_cost,
                    neighbor_id,
                    path + [neighbor_id],
                    new_metrics
                ))
        
        return found_routes
    
    def _find_link(self, node1: str, node2: str) -> Optional[Link]:
        """查找两节点间的链路"""
        for link in self.links.values():
            if (link.source == node1 and link.destination == node2) or \
               (link.source == node2 and link.destination == node1):
                return link
        return None
    
    def _calculate_link_cost(self, current_metrics: Dict,
                            link: Link, metric: RouteMetric) -> Dict:
        """计算链路成本"""
        
        # 计算扩展的度量
        new_latency = current_metrics['latency'] + link.latency
        new_bandwidth = min(current_metrics['bandwidth'], link.bandwidth)
        new_cost = current_metrics['cost'] + link.cost_per_mb * 1  # 假设1MB
        new_reliability = current_metrics['reliability'] * link.reliability
        new_hops = current_metrics['hops'] + 1
        
        return {
            'latency': new_latency,
            'bandwidth': new_bandwidth,
            'cost': new_cost,
            'reliability': new_reliability,
            'hops': new_hops
        }
    
    def _get_composite_cost(self, metrics: Dict, metric: RouteMetric) -> float:
        """获取复合成本"""
        
        if metric == RouteMetric.HOP_COUNT:
            return metrics['hops']
        
        elif metric == RouteMetric.LATENCY:
            return metrics['latency']
        
        elif metric == RouteMetric.BANDWIDTH:
            return -metrics['bandwidth']  # 负值，因为越小越好
        
        elif metric == RouteMetric.COST:
            return metrics['cost']
        
        elif metric == RouteMetric.RELIABILITY:
            return -metrics['reliability']  # 负值
        
        elif metric == RouteMetric.COMPOSITE:
            # 复合度量：延迟 + 成本 - 可靠性
            latency_cost = metrics['latency'] / 3600 / 24  # 转换为天
            reliability_bonus = metrics['reliability'] * 100
            return latency_cost + metrics['cost'] - reliability_bonus
        
        return 0
    
    def _create_route(self, source: str, destination: str,
                     path: List[str], metric: RouteMetric,
                     metrics: Dict) -> Optional[Route]:
        """创建路由对象"""
        
        if len(path) < 2:
            return None
        
        return Route(
            source=source,
            destination=destination,
            path=path,
            metric=metric,
            value=self._get_composite_cost(metrics, metric),
            hops=metrics['hops'],
            total_latency=metrics['latency'],
            total_bandwidth=metrics['bandwidth'],
            total_cost=metrics['cost'],
            reliability=metrics['reliability']
        )
    
    def update_routing_table(self) -> None:
        """更新整个路由表"""
        self.routing_table.clear()
        
        for source in self.nodes:
            for dest in self.nodes:
                if source != dest:
                    routes = self.find_route(source, dest, RouteMetric.COMPOSITE, 1)
                    if routes:
                        self.routing_table[source] = {
                            RouteMetric.COMPOSITE: routes[0]
                        }
    
    def get_next_hop(self, destination: str,
                    metric: RouteMetric = RouteMetric.COMPOSITE) -> Optional[str]:
        """获取到目的地的下一跳"""
        
        if destination not in self.routing_table:
            self.update_routing_table()
        
        if destination in self.routing_table:
            route = self.routing_table[destination].get(metric)
            if route and len(route.path) > 1:
                return route.path[1]
        
        return None
    
    def handle_link_failure(self, link_id: str) -> None:
        """处理链路故障"""
        if link_id in self.links:
            self.links[link_id].active = False
            # 触发路由重新计算
            self.update_routing_table()
    
    def handle_node_failure(self, node_id: str) -> None:
        """处理节点故障"""
        if node_id in self.nodes:
            # 标记所有相关链路为不活跃
            for link in self.links.values():
                if link.source == node_id or link.destination == node_id:
                    link.active = False
            
            # 触发路由重新计算
            self.update_routing_table()


class LoadBalancer:
    """星际网络负载均衡器"""
    
    def __init__(self, router: InterstellarRouter):
        self.router = router
        self.active_flows: Dict[str, Dict] = defaultdict(dict)
        self.flow_counter = 0
        
    def distribute(self, destination: str, flow_size: float) -> Optional[str]:
        """分配流量到最佳路径"""
        
        routes = self.router.find_route(
            self.router.node_id,
            destination,
            metric=RouteMetric.BANDWIDTH,
            k_paths=3
        )
        
        if not routes:
            return None
        
        # 选择负载最低的路径
        best_route = None
        best_load = float('inf')
        
        for route in routes:
            if len(route.path) < 2:
                continue
            
            next_hop = route.path[1]
            node = self.router.nodes.get(next_hop)
            
            if node and node.load < best_load:
                best_load = node.load
                best_route = route
        
        if best_route and len(best_route.path) > 1:
            next_hop = best_route.path[1]
            
            # 更新节点负载
            if next_hop in self.router.nodes:
                self.router.nodes[next_hop].load += flow_size / best_route.total_bandwidth
            
            # 记录流量
            self.flow_counter += 1
            flow_id = f"flow_{self.flow_counter}"
            self.active_flows[flow_id] = {
                'destination': destination,
                'size': flow_size,
                'route': best_route.path,
                'start_time': time.time()
            }
            
            return next_hop
        
        return None
    
    def rebalance(self) -> int:
        """重平衡负载"""
        rebalanced = 0
        
        # 找出负载过高的节点
        overloaded = [(n, n.load) for n in self.router.nodes.values() if n.load > 0.8]
        
        for node, load in overloaded:
            # 尝试将流量转移到负载较低的邻居
            for neighbor_id in node.neighbors:
                neighbor = self.router.nodes.get(neighbor_id)
                if neighbor and neighbor.load < 0.5:
                    # 简单转移策略
                    transfer_amount = (load - 0.7) * 0.1
                    node.load -= transfer_amount
                    neighbor.load += transfer_amount
                    rebalanced += 1
        
        return rebalanced


class FailoverManager:
    """故障转移管理器"""
    
    def __init__(self, router: InterstellarRouter):
        self.router = router
        self.failover_history: List[Dict] = []
        self.health_check_interval = 30
        self.last_health_check = 0
        
    def check_health(self) -> Dict[str, bool]:
        """健康检查"""
        current_time = time.time()
        
        if current_time - self.last_health_check < self.health_check_interval:
            return {}
        
        self.last_health_check = current_time
        health_status = {}
        
        for node_id, node in self.router.nodes.items():
            # 简单的健康检查：节点可达且负载不是100%
            healthy = node.load < 1.0 and len(node.neighbors) > 0
            health_status[node_id] = healthy
            
            if not healthy:
                self._record_failure(node_id, "unhealthy")
        
        return health_status
    
    def get_alternative_route(self, destination: str) -> Optional[Route]:
        """获取备用路由"""
        
        routes = self.router.find_route(
            self.router.node_id,
            destination,
            metric=RouteMetric.RELIABILITY,
            k_paths=3
        )
        
        # 返回第一条可用路由
        for route in routes:
            if route.is_valid:
                return route
        
        return None
    
    def _record_failure(self, node_id: str, reason: str) -> None:
        """记录故障"""
        self.failover_history.append({
            'time': time.time(),
            'node': node_id,
            'reason': reason
        })
        
        # 触发故障转移
        self.router.handle_node_failure(node_id)


class CostOptimizer:
    """成本优化器"""
    
    def __init__(self, router: InterstellarRouter):
        self.router = router
        self.budget = 1000  # 每日预算
        self.spent_today = 0
        
    def find_cheapest_route(self, source: str, destination: str) -> Optional[Route]:
        """查找最便宜路线"""
        
        routes = self.router.find_route(source, destination, RouteMetric.COST, 5)
        
        for route in routes:
            if route.total_cost <= self.get_remaining_budget():
                return route
        
        return None
    
    def find_fastest_route(self, source: str, destination: str) -> Optional[Route]:
        """查找最快路线"""
        
        routes = self.router.find_route(source, destination, RouteMetric.LATENCY, 5)
        
        if routes:
            return routes[0]
        
        return None
    
    def get_remaining_budget(self) -> float:
        """获取剩余预算"""
        return max(0, self.budget - self.spent_today)
    
    def charge(self, amount: float) -> bool:
        """扣费"""
        if self.get_remaining_budget() >= amount:
            self.spent_today += amount
            return True
        return False


def demo():
    """演示星际路由"""
    print("=" * 60)
    print("星际路由器演示")
    print("=" * 60)
    
    # 创建路由器
    router = InterstellarRouter("earth")
    
    # 添加星际节点
    nodes_data = [
        ("earth", (0, 0, 0), 1000, 0.99),
        ("moon", (0.000001, 0, 0), 100, 0.999),
        ("mars", (0.00037, 0, 0), 500, 0.98),
        ("jupiter", (0.00082, 0, 0), 800, 0.97),
        ("proxima", (4.24, 0, 0), 100, 0.95),
        ("trappist", (39.5, 0, 0), 50, 0.88),
        ("gliese", (20.3, 5.2, 0), 75, 0.92),
    ]
    
    for node_id, pos, bw, rel in nodes_data:
        node = Node(node_id, pos, bw, 0, rel)
        router.add_node(node)
    
    # 添加链路
    links_data = [
        ("link_earth_moon", "earth", "moon", 0.000001),
        ("link_earth_mars", "earth", "mars", 0.00037),
        ("link_earth_jupiter", "earth", "jupiter", 0.00082),
        ("link_earth_proxima", "earth", "proxima", 4.24),
        ("link_proxima_trappist", "proxima", "trappist", 35.3),
        ("link_proxima_gliese", "proxima", "gliese", 15.9),
        ("link_mars_jupiter", "mars", "jupiter", 0.00045),
    ]
    
    for link_id, src, dst, dist in links_data:
        # 计算带宽为两节点的最小值
        src_node = router.nodes[src]
        dst_node = router.nodes[dst]
        bw = min(src_node.bandwidth, dst_node.bandwidth)
        
        link = Link(link_id, src, dst, dist, bw)
        router.add_link(link)
    
    print(f"\n网络拓扑: {len(router.nodes)} 节点, {len(router.links)} 链路")
    
    # 更新路由表
    router.update_routing_table()
    print("路由表已更新")
    
    # 查找路由
    print("\n路由查找测试:")
    
    test_routes = [
        ("earth", "proxima"),
        ("earth", "trappist"),
        ("proxima", "gliese"),
    ]
    
    for src, dst in test_routes:
        routes = router.find_route(src, dst, RouteMetric.COMPOSITE, 3)
        
        print(f"\n  {src} -> {dst}:")
        
        for i, route in enumerate(routes[:3], 1):
            print(f"    路径{i}: {' -> '.join(route.path)}")
            print(f"      跳数: {route.hops}, 延迟: {route.total_latency/3600/24:.2f}天, "
                  f"可靠性: {route.reliability:.4f}")
    
    # 负载均衡演示
    print("\n\n负载均衡演示:")
    lb = LoadBalancer(router)
    
    # 模拟流量分配
    for i in range(5):
        next_hop = lb.distribute("proxima", 10)
        if next_hop:
            print(f"  流量{i+1}: 下一跳 -> {next_hop}")
    
    # 成本优化
    print("\n成本优化演示:")
    cost_optimizer = CostOptimizer(router)
    
    route = cost_optimizer.find_cheapest_route("earth", "proxima")
    if route:
        print(f"  最便宜路线: {' -> '.join(route.path)}, 成本: ${route.total_cost:.4f}")
    
    route = cost_optimizer.find_fastest_route("earth", "proxima")
    if route:
        print(f"  最快路线: {' -> '.join(route.path)}, 延迟: {route.total_latency/3600/24:.2f}天")
    
    # 故障转移
    print("\n故障转移演示:")
    failover = FailoverManager(router)
    health = failover.check_health()
    print(f"  健康检查: {len(health)} 节点")
    
    # 模拟链路故障
    router.handle_link_failure("link_earth_proxima")
    print("  模拟链路故障: link_earth_proxima")
    
    # 重新查找路由
    routes = router.find_route("earth", "proxima", RouteMetric.COMPOSITE, 1)
    if routes:
        print(f"  故障后路线: {' -> '.join(routes[0].path)}")
    else:
        print("  故障后路线: 无可用路由")
    
    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    demo()