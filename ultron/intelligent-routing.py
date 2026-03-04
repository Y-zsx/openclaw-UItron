#!/usr/bin/env python3
"""
智能路由系统 - Intelligent Routing System
夙愿二十二第2世：智能路由系统

功能：
- 动态路由算法
- 负载均衡策略
- 故障转移机制
"""

import asyncio
import hashlib
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import json


class RoutingStrategy(Enum):
    """路由策略"""
    ROUND_ROBIN = "round_robin"           # 轮询
    WEIGHTED_ROUND_ROBIN = "weighted_rr"  # 加权轮询
    LEAST_CONNECTIONS = "least_conn"      # 最少连接
    LEAST_RESPONSE_TIME = "least_time"    # 最短响应时间
    SOURCE_HASH = "source_hash"           # 源地址哈希
    RANDOM = "random"                     # 随机
    ADAPTIVE = "adaptive"                 # 自适应


class NodeStatus(Enum):
    """节点状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class RouteNode:
    """路由节点"""
    id: str
    host: str
    port: int
    weight: int = 100
    max_connections: int = 1000
    status: NodeStatus = NodeStatus.HEALTHY
    response_time: float = 0.0
    connections: int = 0
    failures: int = 0
    last_check: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def health_score(self) -> float:
        """计算健康分数 (0-100)"""
        if self.status == NodeStatus.UNHEALTHY:
            return 0.0
        
        # 基于响应时间计算 (响应越快分数越高)
        if self.response_time <= 0:
            time_score = 100
        elif self.response_time < 10:
            time_score = 100 - self.response_time
        elif self.response_time < 50:
            time_score = 90 - (self.response_time - 10) * 1.5
        elif self.response_time < 100:
            time_score = 75 - (self.response_time - 50) * 1.0
        else:
            time_score = max(0, 50 - (self.response_time - 100) * 0.5)
        
        # 基于连接数计算
        conn_ratio = self.connections / self.max_connections
        conn_score = 100 * (1 - conn_ratio) if conn_ratio < 1 else 0
        
        # 基于失败率计算
        failure_penalty = min(self.failures * 10, 30)
        
        # 综合分数
        score = (time_score * 0.4 + conn_score * 0.4 + 20) - failure_penalty
        return max(0, min(100, score))


@dataclass
class RouteRule:
    """路由规则"""
    id: str
    name: str
    pattern: str  # URL路径或条件模式
    strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN
    target_nodes: List[str] = field(default_factory=list)  # 节点ID列表
    priority: int = 0
    enabled: bool = True
    timeout: float = 30.0
    retry_count: int = 3
    fallback_enabled: bool = True


@dataclass
class RouteRequest:
    """路由请求"""
    id: str
    source: str
    path: str
    method: str = "GET"
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, str] = field(default_factory=dict)
    body: Any = None
    timestamp: float = field(default_factory=time.time)
    
    @property
    def key(self) -> str:
        """用于哈希的key"""
        return f"{self.source}:{self.path}"


@dataclass
class RouteResult:
    """路由结果"""
    success: bool
    node: Optional[RouteNode] = None
    error: Optional[str] = None
    strategy_used: RoutingStrategy = RoutingStrategy.ROUND_ROBIN
    retry_count: int = 0


class DynamicRouter:
    """动态路由引擎"""
    
    def __init__(self):
        self.nodes: Dict[str, RouteNode] = {}
        self.rules: List[RouteRule] = []
        self.strategies: Dict[RoutingStrategy, Callable] = {
            RoutingStrategy.ROUND_ROBIN: self._round_robin,
            RoutingStrategy.WEIGHTED_ROUND_ROBIN: self._weighted_rr,
            RoutingStrategy.LEAST_CONNECTIONS: self._least_connections,
            RoutingStrategy.LEAST_RESPONSE_TIME: self._least_response_time,
            RoutingStrategy.SOURCE_HASH: self._source_hash,
            RoutingStrategy.RANDOM: self._random,
            RoutingStrategy.ADAPTIVE: self._adaptive,
        }
        self.rr_index = 0  # 轮询索引
        self.stats = {
            "total_requests": 0,
            "successful": 0,
            "failed": 0,
            "by_strategy": {},
            "by_node": {},
        }
    
    # ========== 节点管理 ==========
    
    def add_node(self, node: RouteNode) -> None:
        """添加节点"""
        self.nodes[node.id] = node
        self.stats["by_node"][node.id] = {"requests": 0, "success": 0, "failures": 0}
    
    def remove_node(self, node_id: str) -> bool:
        """移除节点"""
        if node_id in self.nodes:
            del self.nodes[node_id]
            return True
        return False
    
    def update_node_status(self, node_id: str, status: NodeStatus, 
                          response_time: float = 0.0) -> None:
        """更新节点状态"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.status = status
            node.response_time = response_time
            node.last_check = time.time()
            
            # 如果恢复健康，重置失败计数
            if status == NodeStatus.HEALTHY:
                node.failures = 0
    
    def get_healthy_nodes(self, target_nodes: Optional[List[str]] = None) -> List[RouteNode]:
        """获取健康节点列表"""
        nodes = []
        for node_id, node in self.nodes.items():
            if target_nodes and node_id not in target_nodes:
                continue
            if node.status != NodeStatus.UNHEALTHY:
                nodes.append(node)
        return nodes
    
    # ========== 规则管理 ==========
    
    def add_rule(self, rule: RouteRule) -> None:
        """添加路由规则"""
        self.rules.append(rule)
        self.rules.sort(key=lambda r: r.priority, reverse=True)
    
    def match_rule(self, path: str) -> Optional[RouteRule]:
        """匹配路由规则"""
        for rule in self.rules:
            if not rule.enabled:
                continue
            if path.startswith(rule.pattern) or self._match_pattern(path, rule.pattern):
                return rule
        return None
    
    def _match_pattern(self, path: str, pattern: str) -> bool:
        """简单的模式匹配"""
        if "*" in pattern:
            prefix = pattern.replace("*", "")
            return path.startswith(prefix)
        return path == pattern
    
    # ========== 路由策略 ==========
    
    def _round_robin(self, nodes: List[RouteNode]) -> Optional[RouteNode]:
        """轮询策略"""
        if not nodes:
            return None
        node = nodes[self.rr_index % len(nodes)]
        self.rr_index += 1
        return node
    
    def _weighted_rr(self, nodes: List[RouteNode]) -> Optional[RouteNode]:
        """加权轮询"""
        if not nodes:
            return None
        
        # 计算总权重
        total_weight = sum(n.weight for n in nodes)
        if total_weight <= 0:
            return random.choice(nodes)
        
        # 随机选择
        r = random.randint(1, total_weight)
        cumulative = 0
        for node in nodes:
            cumulative += node.weight
            if r <= cumulative:
                return node
        return nodes[-1]
    
    def _least_connections(self, nodes: List[RouteNode]) -> Optional[RouteNode]:
        """最少连接数"""
        if not nodes:
            return None
        return min(nodes, key=lambda n: (n.connections, n.response_time))
    
    def _least_response_time(self, nodes: List[RouteNode]) -> Optional[RouteNode]:
        """最短响应时间"""
        if not nodes:
            return None
        healthy = [n for n in nodes if n.status == NodeStatus.HEALTHY]
        if healthy:
            return min(healthy, key=lambda n: n.response_time)
        return min(nodes, key=lambda n: n.response_time)
    
    def _source_hash(self, nodes: List[RouteNode], source: str = "") -> Optional[RouteNode]:
        """源地址哈希"""
        if not nodes:
            return None
        hash_val = int(hashlib.md5(source.encode()).hexdigest(), 16)
        return nodes[hash_val % len(nodes)]
    
    def _random(self, nodes: List[RouteNode]) -> Optional[RouteNode]:
        """随机选择"""
        if not nodes:
            return None
        return random.choice(nodes)
    
    def _adaptive(self, nodes: List[RouteNode]) -> Optional[RouteNode]:
        """自适应策略 - 基于健康分数"""
        if not nodes:
            return None
        
        # 按健康分数排序，选择最优
        scored = [(n, n.health_score) for n in nodes if n.status != NodeStatus.UNHEALTHY]
        if not scored:
            return None
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        # 加权随机选择top节点
        top_nodes = scored[:max(1, len(scored) // 2)]
        return random.choices(
            [n for n, _ in top_nodes],
            weights=[s for _, s in top_nodes]
        )[0]
    
    # ========== 核心路由 ==========
    
    async def route(self, request: RouteRequest) -> RouteResult:
        """执行路由"""
        self.stats["total_requests"] += 1
        
        # 1. 匹配规则
        rule = self.match_rule(request.path)
        
        # 2. 获取目标节点
        if rule and rule.target_nodes:
            target_nodes = rule.target_nodes
            strategy = rule.strategy
        else:
            target_nodes = None
            strategy = RoutingStrategy.ADAPTIVE
        
        healthy_nodes = self.get_healthy_nodes(target_nodes)
        
        if not healthy_nodes:
            self.stats["failed"] += 1
            return RouteResult(
                success=False,
                error="No healthy nodes available",
                strategy_used=strategy
            )
        
        # 3. 应用路由策略
        strategy_func = self.strategies.get(strategy, self._round_robin)
        
        if strategy == RoutingStrategy.SOURCE_HASH:
            node = strategy_func(healthy_nodes, request.source)
        else:
            node = strategy_func(healthy_nodes)
        
        if not node:
            self.stats["failed"] += 1
            return RouteResult(
                success=False,
                error="Routing strategy returned no node",
                strategy_used=strategy
            )
        
        # 4. 记录统计
        self.stats["successful"] += 1
        self.stats["by_strategy"][strategy.value] = \
            self.stats["by_strategy"].get(strategy.value, 0) + 1
        self.stats["by_node"][node.id]["requests"] += 1
        
        # 增加连接数
        node.connections = min(node.connections + 1, node.max_connections)
        
        return RouteResult(
            success=True,
            node=node,
            strategy_used=strategy
        )
    
    def release_connection(self, node_id: str) -> None:
        """释放连接"""
        if node_id in self.nodes:
            self.nodes[node_id].connections = max(0, self.nodes[node_id].connections - 1)
    
    def record_failure(self, node_id: str) -> None:
        """记录失败"""
        if node_id in self.nodes:
            node = self.nodes[node_id]
            node.failures += 1
            self.stats["by_node"][node_id]["failures"] += 1
            
            # 失败过多标记为不健康
            if node.failures >= 5:
                node.status = NodeStatus.UNHEALTHY
    
    def record_success(self, node_id: str) -> None:
        """记录成功"""
        if node_id in self.nodes:
            self.stats["by_node"][node_id]["success"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            **self.stats,
            "nodes": {
                node_id: {
                    "status": node.status.value,
                    "health_score": node.health_score,
                    "connections": node.connections,
                    "response_time": node.response_time,
                    "failures": node.failures
                }
                for node_id, node in self.nodes.items()
            }
        }


class LoadBalancer:
    """负载均衡器 - 高级负载分配"""
    
    def __init__(self, router: DynamicRouter):
        self.router = router
        self.health_check_interval = 10  # 健康检查间隔(秒)
        self.last_health_check = 0
    
    async def health_check(self) -> None:
        """健康检查"""
        now = time.time()
        if now - self.last_health_check < self.health_check_interval:
            return
        
        self.last_health_check = now
        
        for node_id, node in self.router.nodes.items():
            # 模拟健康检查
            is_healthy = await self._check_node(node)
            
            if is_healthy and node.status == NodeStatus.UNHEALTHY:
                self.router.update_node_status(node_id, NodeStatus.HEALTHY, node.response_time)
            elif not is_healthy and node.status == NodeStatus.HEALTHY:
                self.router.update_node_status(node_id, NodeStatus.DEGRADED, node.response_time)
    
    async def _check_node(self, node: RouteNode) -> bool:
        """检查单个节点"""
        # 这里应该是实际的健康检查逻辑
        # 模拟：检查连接数和失败率
        if node.status == NodeStatus.UNHEALTHY:
            return False
        if node.connections >= node.max_connections:
            return False
        if node.failures >= 10:
            return False
        return True
    
    async def route_request(self, request: RouteRequest) -> RouteResult:
        """路由请求（带健康检查）"""
        await self.health_check()
        return await self.router.route(request)


class FailoverManager:
    """故障转移管理器"""
    
    def __init__(self, router: DynamicRouter):
        self.router = router
        self.failover_rules: Dict[str, List[str]] = {}  # node_id -> failover_node_ids
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
    
    def set_failover_chain(self, primary_id: str, failover_ids: List[str]) -> None:
        """设置故障转移链"""
        self.failover_rules[primary_id] = failover_ids
    
    async def execute_with_failover(self, request: RouteRequest) -> RouteResult:
        """执行带故障转移的请求"""
        result = await self.router.route(request)
        
        if not result.success:
            # 尝试故障转移
            return await self._failover(request, result)
        
        # 检查是否需要熔断
        if result.node:
            breaker = self.circuit_breakers.get(result.node.id)
            if breaker and breaker.is_open:
                return await self._failover(request, result)
        
        return result
    
    async def _failover(self, original_result: RouteResult, 
                       request: RouteRequest) -> RouteResult:
        """执行故障转移"""
        if not original_result.node:
            return original_result
        
        primary_id = original_result.node.id
        failover_ids = self.failover_rules.get(primary_id, [])
        
        for failover_id in failover_ids:
            if failover_id in self.router.nodes:
                node = self.router.nodes[failover_id]
                if node.status != NodeStatus.UNHEALTHY:
                    # 临时修改请求以使用备用节点
                    result = await self.router.route(request)
                    if result.success:
                        return result
        
        return original_result
    
    def register_circuit_breaker(self, node_id: str, 
                                 failure_threshold: int = 5,
                                 timeout: float = 60.0) -> None:
        """注册熔断器"""
        self.circuit_breakers[node_id] = CircuitBreaker(
            node_id, failure_threshold, timeout
        )
    
    def record_result(self, node_id: str, success: bool) -> None:
        """记录结果用于熔断"""
        if node_id in self.circuit_breakers:
            self.circuit_breakers[node_id].record(success)


class CircuitBreaker:
    """熔断器"""
    
    def __init__(self, node_id: str, failure_threshold: int = 5, 
                 timeout: float = 60.0):
        self.node_id = node_id
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half_open
    
    @property
    def is_open(self) -> bool:
        """是否开启熔断"""
        if self.state == "open":
            # 检查是否超时可以尝试半开
            if time.time() - self.last_failure_time > self.timeout:
                self.state = "half_open"
                return False
            return True
        return False
    
    def record(self, success: bool) -> None:
        """记录结果"""
        if success:
            self.failures = 0
            if self.state == "half_open":
                self.state = "closed"
        else:
            self.failures += 1
            self.last_failure_time = time.time()
            
            if self.failures >= self.failure_threshold:
                self.state = "open"


# ========== 实例管理 ==========

_router: Optional[DynamicRouter] = None
_load_balancer: Optional[LoadBalancer] = None
_failover_manager: Optional[FailoverManager] = None


def get_router() -> DynamicRouter:
    """获取路由实例"""
    global _router
    if _router is None:
        _router = DynamicRouter()
    return _router


def get_load_balancer() -> LoadBalancer:
    """获取负载均衡器"""
    global _load_balancer
    if _load_balancer is None:
        _load_balancer = LoadBalancer(get_router())
    return _load_balancer


def get_failover_manager() -> FailoverManager:
    """获取故障转移管理器"""
    global _failover_manager
    if _failover_manager is None:
        _failover_manager = FailoverManager(get_router())
    return _failover_manager


# ========== 主函数 ==========

async def main():
    """测试主函数"""
    print("=== 智能路由系统测试 ===\n")
    
    router = get_router()
    lb = get_load_balancer()
    fm = get_failover_manager()
    
    # 添加测试节点
    nodes = [
        RouteNode("node1", "192.168.1.10", 8080, weight=100),
        RouteNode("node2", "192.168.1.11", 8080, weight=80),
        RouteNode("node3", "192.168.1.12", 8080, weight=60),
    ]
    
    for node in nodes:
        router.add_node(node)
        fm.register_circuit_breaker(node.id)
    
    # 设置故障转移链
    fm.set_failover_chain("node1", ["node2", "node3"])
    
    # 添加路由规则
    rule = RouteRule(
        id="rule1",
        name="API路由",
        pattern="/api",
        strategy=RoutingStrategy.ADAPTIVE,
        priority=10
    )
    router.add_rule(rule)
    
    # 测试路由
    print("测试路由 (10个请求):\n")
    
    for i in range(10):
        request = RouteRequest(
            id=f"req-{i}",
            source=f"client-{i % 3}",
            path=f"/api/v1/resource/{i}",
            method="GET"
        )
        
        result = await lb.route_request(request)
        
        if result.success:
            print(f"请求 {i}: ✓ 路由到 {result.node.id} "
                  f"({result.strategy_used.value})")
            router.release_connection(result.node.id)
        else:
            print(f"请求 {i}: ✗ {result.error}")
    
    # 打印统计
    print("\n=== 路由统计 ===")
    stats = router.get_stats()
    print(f"总请求: {stats['total_requests']}")
    print(f"成功: {stats['successful']}")
    print(f"失败: {stats['failed']}")
    print("\n节点状态:")
    for node_id, info in stats['nodes'].items():
        print(f"  {node_id}: {info['status']} "
              f"(健康分: {info['health_score']:.1f}, "
              f"连接: {info['connections']}, "
              f"响应: {info['response_time']:.2f}ms)")
    
    # 测试节点故障
    print("\n=== 测试故障转移 ===")
    router.update_node_status("node1", NodeStatus.UNHEALTHY)
    
    request = RouteRequest(
        id="failover-test",
        source="test-client",
        path="/api/test",
        method="GET"
    )
    
    result = await fm.execute_with_failover(request)
    
    if result.success:
        print(f"故障转移成功: 路由到 {result.node.id}")
    else:
        print(f"故障转移失败: {result.error}")
    
    print("\n=== 测试完成 ===")


if __name__ == "__main__":
    asyncio.run(main())