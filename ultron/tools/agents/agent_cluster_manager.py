"""
Agent集群负载均衡与故障转移系统
第46世: 实现Agent集群负载均衡与故障转移
"""

import asyncio
import time
import random
import hashlib
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class LoadBalancingStrategy(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONNECTIONS = "least_connections"
    LEAST_RESPONSE_TIME = "least_response_time"
    WEIGHTED = "weighted"
    RANDOM = "random"
    IP_HASH = "ip_hash"


@dataclass
class AgentNode:
    """Agent节点"""
    node_id: str
    agent_type: str
    host: str
    port: int
    weight: int = 1
    max_connections: int = 100
    status: HealthStatus = HealthStatus.UNKNOWN
    current_connections: int = 0
    total_requests: int = 0
    total_failures: int = 0
    avg_response_time: float = 0.0
    last_health_check: float = 0.0
    last_active: float = 0.0
    capabilities: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return (self.total_requests - self.total_failures) / self.total_requests
    
    @property
    def is_available(self) -> bool:
        return (
            self.status == HealthStatus.HEALTHY and 
            self.current_connections < self.max_connections
        )


@dataclass
class ClusterMetrics:
    """集群指标"""
    total_nodes: int = 0
    healthy_nodes: int = 0
    total_requests: int = 0
    total_failures: int = 0
    avg_response_time: float = 0.0
    failover_count: int = 0
    last_sync: float = 0.0


class ClusterHealthChecker:
    """集群健康检测"""
    
    def __init__(self, check_interval: float = 10.0, timeout: float = 5.0):
        self.check_interval = check_interval
        self.timeout = timeout
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._lock = threading.Lock()
        self._listeners: List[callable] = []
    
    def add_listener(self, listener: callable):
        self._listeners.append(listener)
    
    async def start(self, cluster_manager: 'AgentClusterManager'):
        self._running = True
        self._task = asyncio.create_task(self._check_loop(cluster_manager))
    
    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _check_loop(self, cluster_manager: 'AgentClusterManager'):
        while self._running:
            try:
                await self._health_check(cluster_manager)
            except Exception as e:
                print(f"Health check error: {e}")
            await asyncio.sleep(self.check_interval)
    
    async def _health_check(self, cluster_manager: 'AgentClusterManager'):
        """执行健康检查"""
        with cluster_manager._lock:
            nodes = list(cluster_manager._nodes.values())
        
        for node in nodes:
            try:
                # 模拟健康检查 - 实际应该进行TCP/HTTP检测
                is_healthy = await self._perform_check(node)
                
                with self._lock:
                    old_status = node.status
                    if is_healthy:
                        node.status = HealthStatus.HEALTHY
                    elif node.current_connections > node.max_connections * 0.9:
                        node.status = HealthStatus.DEGRADED
                    else:
                        node.status = HealthStatus.UNHEALTHY
                    
                    node.last_health_check = time.time()
                    
                    # 状态变化通知
                    if old_status != node.status:
                        for listener in self._listeners:
                            try:
                                listener(node, old_status, node.status)
                            except Exception as e:
                                print(f"Listener error: {e}")
            except Exception as e:
                print(f"Check failed for {node.node_id}: {e}")
                with self._lock:
                    node.status = HealthStatus.UNHEALTHY
    
    async def _perform_check(self, node: AgentNode) -> bool:
        """执行单节点健康检查"""
        # 模拟检查 - 实际应检测端口/API/进程
        # 基于失败率和响应时间判断
        if node.success_rate < 0.5:
            return False
        if node.avg_response_time > 5000:  # 5秒
            return False
        return random.random() > 0.1  # 90%概率健康


class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self, strategy: LoadBalancingStrategy = LoadBalancingStrategy.LEAST_CONNECTIONS):
        self.strategy = strategy
        self._round_robin_index: Dict[str, int] = defaultdict(int)
    
    def select(
        self, 
        nodes: List[AgentNode], 
        agent_type: str = None,
        client_ip: str = None,
        required_capabilities: Set[str] = None
    ) -> Optional[AgentNode]:
        """选择最优节点"""
        # 过滤可用节点
        available = [
            n for n in nodes 
            if n.is_available and 
            (agent_type is None or n.agent_type == agent_type) and
            (required_capabilities is None or required_capabilities.issubset(n.capabilities))
        ]
        
        if not available:
            return None
        
        # 根据策略选择
        if self.strategy == LoadBalancingStrategy.ROUND_ROBIN:
            return self._round_robin(available, agent_type or "default")
        elif self.strategy == LoadBalancingStrategy.LEAST_CONNECTIONS:
            return self._least_connections(available)
        elif self.strategy == LoadBalancingStrategy.LEAST_RESPONSE_TIME:
            return self._least_response_time(available)
        elif self.strategy == LoadBalancingStrategy.WEIGHTED:
            return self._weighted(available)
        elif self.strategy == LoadBalancingStrategy.RANDOM:
            return random.choice(available)
        elif self.strategy == LoadBalancingStrategy.IP_HASH:
            return self._ip_hash(available, client_ip or "unknown")
        
        return available[0]
    
    def _round_robin(self, nodes: List[AgentNode], key: str) -> AgentNode:
        index = self._round_robin_index[key]
        self._round_robin_index[key] = (index + 1) % len(nodes)
        return nodes[index]
    
    def _least_connections(self, nodes: List[AgentNode]) -> AgentNode:
        return min(nodes, key=lambda n: n.current_connections)
    
    def _least_response_time(self, nodes: List[AgentNode]) -> AgentNode:
        return min(nodes, key=lambda n: n.avg_response_time)
    
    def _weighted(self, nodes: List[AgentNode]) -> AgentNode:
        # 加权随机
        total_weight = sum(n.weight for n in nodes)
        r = random.uniform(0, total_weight)
        cum = 0
        for n in nodes:
            cum += n.weight
            if r <= cum:
                return n
        return nodes[-1]
    
    def _ip_hash(self, nodes: List[AgentNode], client_ip: str) -> AgentNode:
        hash_val = int(hashlib.md5(client_ip.encode()).hexdigest(), 16)
        return nodes[hash_val % len(nodes)]


class FailoverManager:
    """故障转移管理器"""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 1.0):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._failover_count = 0
        self._lock = threading.Lock()
    
    @property
    def failover_count(self) -> int:
        with self._lock:
            return self._failover_count
    
    def increment_failover(self):
        with self._lock:
            self._failover_count += 1
    
    async def execute_with_failover(
        self,
        cluster_manager: 'AgentClusterManager',
        operation: callable,
        agent_type: str = None,
        required_capabilities: Set[str] = None,
        client_ip: str = None
    ) -> Any:
        """带故障转移的执行"""
        last_error = None
        
        for attempt in range(self.max_retries):
            # 选择节点
            node = cluster_manager.select_node(
                agent_type=agent_type,
                required_capabilities=required_capabilities,
                client_ip=client_ip
            )
            
            if not node:
                last_error = "No available nodes"
                await asyncio.sleep(self.retry_delay * (attempt + 1))
                continue
            
            try:
                # 标记连接
                cluster_manager._update_connection(node.node_id, 1)
                cluster_manager._update_request(node.node_id)
                
                # 执行操作
                result = await operation(node)
                
                # 成功 - 记录响应时间
                cluster_manager._update_response_time(node.node_id, 0.1)  # 简化
                return result
                
            except Exception as e:
                last_error = e
                cluster_manager._update_failure(node.node_id)
                cluster_manager.mark_node_unhealthy(node.node_id)
                self.increment_failover()
                
                # 尝试下一节点
                await asyncio.sleep(self.retry_delay * (attempt + 1))
                continue
                
            finally:
                cluster_manager._update_connection(node.node_id, -1)
        
        raise Exception(f"All retries failed: {last_error}")


class ClusterStateSync:
    """集群状态同步"""
    
    def __init__(self, sync_interval: float = 5.0):
        self.sync_interval = sync_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._cluster_state: Dict[str, Any] = {}
        self._lock = threading.Lock()
    
    async def start(self, cluster_manager: 'AgentClusterManager'):
        self._running = True
        self._task = asyncio.create_task(self._sync_loop(cluster_manager))
    
    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
    
    async def _sync_loop(self, cluster_manager: 'AgentClusterManager'):
        while self._running:
            try:
                await self._sync_state(cluster_manager)
            except Exception as e:
                print(f"Sync error: {e}")
            await asyncio.sleep(self.sync_interval)
    
    async def _sync_state(self, cluster_manager: 'AgentClusterManager'):
        """同步集群状态"""
        with self._lock:
            self._cluster_state = {
                "timestamp": time.time(),
                "nodes": {},
                "metrics": cluster_manager.get_metrics().__dict__
            }
            
            for node_id, node in cluster_manager._nodes.items():
                self._cluster_state["nodes"][node_id] = {
                    "status": node.status.value,
                    "connections": node.current_connections,
                    "success_rate": node.success_rate,
                    "avg_response_time": node.avg_response_time,
                    "last_active": node.last_active
                }
    
    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return self._cluster_state.copy()


class AgentClusterManager:
    """Agent集群管理器 - 主类"""
    
    def __init__(
        self,
        strategy: LoadBalancingStrategy = LoadBalancingStrategy.LEAST_CONNECTIONS,
        health_check_interval: float = 10.0,
        sync_interval: float = 5.0
    ):
        self._nodes: Dict[str, AgentNode] = {}
        self._lock = threading.Lock()
        
        # 负载均衡
        self.load_balancer = LoadBalancer(strategy)
        
        # 健康检测
        self.health_checker = ClusterHealthChecker(
            check_interval=health_check_interval
        )
        self.health_checker.add_listener(self._on_node_status_change)
        
        # 故障转移
        self.failover_manager = FailoverManager()
        
        # 状态同步
        self.state_sync = ClusterStateSync(sync_interval)
        
        # 集群指标
        self._metrics = ClusterMetrics()
        self._metrics_lock = threading.Lock()
    
    async def start(self):
        """启动集群管理"""
        await self.health_checker.start(self)
        await self.state_sync.start(self)
    
    async def stop(self):
        """停止集群管理"""
        await self.health_checker.stop()
        await self.state_sync.stop()
    
    def register_node(self, node: AgentNode):
        """注册节点"""
        with self._lock:
            node.last_active = time.time()
            self._nodes[node.node_id] = node
            self._update_metrics()
    
    def unregister_node(self, node_id: str):
        """注销节点"""
        with self._lock:
            if node_id in self._nodes:
                del self._nodes[node_id]
                self._update_metrics()
    
    def get_node(self, node_id: str) -> Optional[AgentNode]:
        with self._lock:
            return self._nodes.get(node_id)
    
    def list_nodes(self, agent_type: str = None, status: HealthStatus = None) -> List[AgentNode]:
        with self._lock:
            nodes = list(self._nodes.values())
        
        if agent_type:
            nodes = [n for n in nodes if n.agent_type == agent_type]
        if status:
            nodes = [n for n in nodes if n.status == status]
        
        return nodes
    
    def select_node(
        self,
        agent_type: str = None,
        required_capabilities: Set[str] = None,
        client_ip: str = None
    ) -> Optional[AgentNode]:
        """选择最优节点"""
        with self._lock:
            nodes = list(self._nodes.values())
        
        return self.load_balancer.select(
            nodes, 
            agent_type=agent_type,
            client_ip=client_ip,
            required_capabilities=required_capabilities
        )
    
    def _update_connection(self, node_id: str, delta: int):
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].current_connections += delta
                self._nodes[node_id].last_active = time.time()
    
    def _update_request(self, node_id: str):
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].total_requests += 1
    
    def _update_failure(self, node_id: str):
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].total_failures += 1
    
    def _update_response_time(self, node_id: str, response_time: float):
        with self._lock:
            if node_id in self._nodes:
                node = self._nodes[node_id]
                # 滑动平均
                if node.avg_response_time == 0:
                    node.avg_response_time = response_time
                else:
                    node.avg_response_time = node.avg_response_time * 0.7 + response_time * 0.3
    
    def mark_node_unhealthy(self, node_id: str):
        """标记节点不健康"""
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].status = HealthStatus.UNHEALTHY
    
    def mark_node_healthy(self, node_id: str):
        """标记节点健康"""
        with self._lock:
            if node_id in self._nodes:
                self._nodes[node_id].status = HealthStatus.HEALTHY
    
    def _on_node_status_change(self, node: AgentNode, old: HealthStatus, new: HealthStatus):
        """节点状态变化回调"""
        print(f"Node {node.node_id}: {old.value} -> {new.value}")
        
        if new == HealthStatus.UNHEALTHY:
            # 触发故障转移
            self.failover_manager.increment_failover()
    
    def _update_metrics(self):
        """更新集群指标"""
        with self._metrics_lock:
            self._metrics.total_nodes = len(self._nodes)
            self._metrics.healthy_nodes = sum(
                1 for n in self._nodes.values() 
                if n.status == HealthStatus.HEALTHY
            )
            self._metrics.failover_count = self.failover_manager.failover_count
            self._metrics.last_sync = time.time()
    
    def get_metrics(self) -> ClusterMetrics:
        with self._metrics_lock:
            # 更新实时数据
            self._metrics.total_nodes = len(self._nodes)
            self._metrics.healthy_nodes = sum(
                1 for n in self._nodes.values() 
                if n.status == HealthStatus.HEALTHY
            )
            self._metrics.total_requests = sum(
                n.total_requests for n in self._nodes.values()
            )
            self._metrics.total_failures = sum(
                n.total_failures for n in self._nodes.values()
            )
            
            response_times = [
                n.avg_response_time for n in self._nodes.values() 
                if n.avg_response_time > 0
            ]
            if response_times:
                self._metrics.avg_response_time = sum(response_times) / len(response_times)
            
            self._metrics.failover_count = self.failover_manager.failover_count
            
            return ClusterMetrics(**self._metrics.__dict__)
    
    def get_cluster_state(self) -> Dict[str, Any]:
        """获取集群状态"""
        return self.state_sync.get_state()


# ==================== 演示 ====================

async def demo():
    print("=" * 60)
    print("Agent集群负载均衡与故障转移演示")
    print("=" * 60)
    
    # 创建集群管理器
    cluster = AgentClusterManager(
        strategy=LoadBalancingStrategy.LEAST_CONNECTIONS,
        health_check_interval=5.0
    )
    
    # 注册节点
    nodes = [
        AgentNode(
            node_id="executor-1",
            agent_type="executor",
            host="192.168.1.10",
            port=8001,
            weight=2,
            max_connections=50,
            capabilities={"execute", "run"}
        ),
        AgentNode(
            node_id="executor-2",
            agent_type="executor",
            host="192.168.1.11",
            port=8001,
            weight=1,
            max_connections=30,
            capabilities={"execute", "run"}
        ),
        AgentNode(
            node_id="analyzer-1",
            agent_type="analyzer",
            host="192.168.1.20",
            port=8002,
            weight=1,
            max_connections=20,
            capabilities={"analyze", "report"}
        ),
    ]
    
    for node in nodes:
        node.status = HealthStatus.HEALTHY
        cluster.register_node(node)
    
    # 启动集群管理
    await cluster.start()
    
    # 等待健康检查
    await asyncio.sleep(2)
    
    print("\n📊 集群状态:")
    metrics = cluster.get_metrics()
    print(f"  总节点: {metrics.total_nodes}")
    print(f"  健康节点: {metrics.healthy_nodes}")
    print(f"  总请求: {metrics.total_requests}")
    print(f"  总失败: {metrics.total_failures}")
    
    print("\n🔄 负载均衡测试:")
    for i in range(10):
        node = cluster.select_node(agent_type="executor")
        if node:
            print(f"  请求{i+1} -> {node.node_id} (连接:{node.current_connections})")
    
    print("\n🔧 故障模拟:")
    # 标记一个节点不健康
    cluster.mark_node_unhealthy("executor-1")
    await asyncio.sleep(1)
    
    print("  executor-1 标记为不健康")
    for i in range(5):
        node = cluster.select_node(agent_type="executor")
        if node:
            print(f"  请求{i+1} -> {node.node_id}")
    
    print("\n📈 最终指标:")
    metrics = cluster.get_metrics()
    print(f"  总请求: {metrics.total_requests}")
    print(f"  总失败: {metrics.total_failures}")
    print(f"  故障转移次数: {metrics.failover_count}")
    
    print("\n🌐 集群状态同步:")
    state = cluster.get_cluster_state()
    print(f"  同步时间: {state.get('timestamp', 0)}")
    print(f"  节点数: {len(state.get('nodes', {}))}")
    
    # 停止集群
    await cluster.stop()
    
    print("\n✅ 演示完成!")
    return True


if __name__ == "__main__":
    asyncio.run(demo())