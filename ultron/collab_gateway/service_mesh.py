#!/usr/bin/env python3
"""
Agent服务网格 - API网关集成
实现服务发现、流量管理、熔断器、负载均衡策略、安全传输
"""

import json
import time
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MeshServiceState(Enum):
    """服务状态"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断
    HALF_OPEN = "half_open"  # 半开


@dataclass
class MeshService:
    """网格服务定义"""
    service_id: str
    name: str
    version: str = "v1"
    endpoints: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    state: MeshServiceState = MeshServiceState.HEALTHY
    registered_at: str = ""
    last_heartbeat: str = ""
    health_score: float = 100.0
    
    def to_dict(self) -> Dict:
        return {
            "service_id": self.service_id,
            "name": self.name,
            "version": self.version,
            "endpoints": self.endpoints,
            "capabilities": self.capabilities,
            "metadata": self.metadata,
            "state": self.state.value,
            "registered_at": self.registered_at,
            "last_heartbeat": self.last_heartbeat,
            "health_score": self.health_score
        }


@dataclass
class CircuitBreaker:
    """熔断器"""
    service_id: str
    failure_threshold: int = 5       # 失败次数阈值
    success_threshold: int = 3       # 成功次数阈值恢复
    timeout: float = 30.0            # 熔断超时(秒)
    half_open_max_requests: int = 3  # 半开状态最大请求数
    
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0
    half_open_requests: int = 0
    
    def record_success(self):
        """记录成功"""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                logger.info(f"服务 {self.service_id} 熔断器关闭")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        """记录失败"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                logger.warning(f"服务 {self.service_id} 熔断器打开")
                self.state = CircuitState.OPEN
        elif self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                logger.info(f"服务 {self.service_id} 熔断器进入半开状态")
                self.state = CircuitState.HALF_OPEN
                self.half_open_requests = 0
        elif self.state == CircuitState.HALF_OPEN:
            self.half_open_requests += 1
            if self.half_open_requests >= self.half_open_max_requests:
                logger.warning(f"服务 {self.service_id} 熔断器重新打开")
                self.state = CircuitState.OPEN
    
    def is_available(self) -> bool:
        """检查服务是否可用"""
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            # 检查超时
            if time.time() - self.last_failure_time > self.timeout:
                logger.info(f"服务 {self.service_id} 熔断器超时，进入半开")
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            return self.half_open_requests < self.half_open_max_requests
        return False


@dataclass
class TrafficPolicy:
    """流量策略"""
    service_id: str
    max_requests_per_second: float = 100.0
    max_concurrent_requests: int = 50
    timeout: float = 30.0
    retry_attempts: int = 3
    retry_backoff_ms: int = 100
    
    # 流量权重 (用于金丝雀发布)
    weight: float = 100.0
    
    # 熔断配置
    circuit_breaker_enabled: bool = True
    circuit_failure_threshold: int = 5
    circuit_timeout: float = 30.0
    
    def to_dict(self) -> Dict:
        return {
            "service_id": self.service_id,
            "max_requests_per_second": self.max_requests_per_second,
            "max_concurrent_requests": self.max_concurrent_requests,
            "timeout": self.timeout,
            "retry_attempts": self.retry_attempts,
            "retry_backoff_ms": self.retry_backoff_ms,
            "weight": self.weight,
            "circuit_breaker_enabled": self.circuit_breaker_enabled,
            "circuit_failure_threshold": self.circuit_failure_threshold,
            "circuit_timeout": self.circuit_timeout
        }


@dataclass
class MeshMetrics:
    """网格指标"""
    service_id: str
    total_requests: int = 0
    total_success: int = 0
    total_failure: int = 0
    total_latency_ms: float = 0.0
    current_concurrent: int = 0
    max_concurrent: int = 0
    requests_per_second: float = 0.0
    error_rate: float = 0.0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # 延迟百分位存储
    _latencies: List[float] = field(default_factory=list)
    
    def record_request(self, success: bool, latency_ms: float):
        """记录请求"""
        self.total_requests += 1
        if success:
            self.total_success += 1
        else:
            self.total_failure += 1
        self.total_latency_ms += latency_ms
        self._latencies.append(latency_ms)
        
        # 保持最近10000个延迟数据
        if len(self._latencies) > 10000:
            self._latencies = self._latencies[-5000:]
        
        # 计算统计
        self.error_rate = self.total_failure / max(1, self.total_requests)
        self.avg_latency_ms = self.total_latency_ms / max(1, self.total_requests)
        
        # 计算百分位
        if self._latencies:
            sorted_latencies = sorted(self._latencies)
            n = len(sorted_latencies)
            self.p50_latency_ms = sorted_latencies[int(n * 0.5)]
            self.p95_latency_ms = sorted_latencies[int(n * 0.95)] if n > 20 else sorted_latencies[-1]
            self.p99_latency_ms = sorted_latencies[int(n * 0.99)] if n > 100 else sorted_latencies[-1]
    
    def to_dict(self) -> Dict:
        return {
            "service_id": self.service_id,
            "total_requests": self.total_requests,
            "total_success": self.total_success,
            "total_failure": self.total_failure,
            "current_concurrent": self.current_concurrent,
            "max_concurrent": self.max_concurrent,
            "requests_per_second": self.requests_per_second,
            "error_rate": self.error_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms
        }


class AgentServiceMesh:
    """Agent服务网格 - 与API网关集成"""
    
    def __init__(self, gateway=None):
        self.gateway = gateway
        
        # 服务注册表
        self.services: Dict[str, MeshService] = {}
        
        # 服务分组 (按name版本分组)
        self.service_groups: Dict[str, Set[str]] = defaultdict(set)
        
        # 熔断器
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # 流量策略
        self.traffic_policies: Dict[str, TrafficPolicy] = {}
        
        # 网格指标
        self.metrics: Dict[str, MeshMetrics] = {}
        
        # 速率限制
        self.rate_limits: Dict[str, List[float]] = defaultdict(list)
        
        # 锁
        self._lock = threading.RLock()
        
        # 网格配置
        self.config = {
            "enable_circuit_breaker": True,
            "enable_rate_limiting": True,
            "enable_load_balancing": True,
            "default_timeout": 30.0,
            "default_rps": 100
        }
        
        logger.info("Agent服务网格初始化完成")
    
    def register_service(self, service: MeshService) -> Dict:
        """注册服务到网格"""
        with self._lock:
            service.registered_at = datetime.now().isoformat()
            service.last_heartbeat = service.registered_at
            
            self.services[service.service_id] = service
            
            # 添加到服务组
            group_key = f"{service.name}:{service.version}"
            self.service_groups[group_key].add(service.service_id)
            
            # 初始化熔断器
            self.circuit_breakers[service.service_id] = CircuitBreaker(
                service_id=service.service_id
            )
            
            # 初始化流量策略
            self.traffic_policies[service.service_id] = TrafficPolicy(
                service_id=service.service_id
            )
            
            # 初始化指标
            self.metrics[service.service_id] = MeshMetrics(
                service_id=service.service_id
            )
            
            logger.info(f"服务注册到网格: {service.name}/{service.version} ({service.service_id})")
            
            return service.to_dict()
    
    def unregister_service(self, service_id: str) -> bool:
        """注销服务"""
        with self._lock:
            if service_id not in self.services:
                return False
            
            service = self.services[service_id]
            
            # 从服务组移除
            group_key = f"{service.name}:{service.version}"
            if group_key in self.service_groups:
                self.service_groups[group_key].discard(service_id)
            
            # 清理
            del self.services[service_id]
            if service_id in self.circuit_breakers:
                del self.circuit_breakers[service_id]
            if service_id in self.traffic_policies:
                del self.traffic_policies[service_id]
            if service_id in self.metrics:
                del self.metrics[service_id]
            
            logger.info(f"服务注销: {service_id}")
            return True
    
    def update_service_health(self, service_id: str, health_score: float, 
                               state: MeshServiceState = None):
        """更新服务健康状态"""
        with self._lock:
            if service_id not in self.services:
                return False
            
            service = self.services[service_id]
            service.health_score = health_score
            service.last_heartbeat = datetime.now().isoformat()
            
            if state:
                service.state = state
            elif health_score < 50:
                service.state = MeshServiceState.UNHEALTHY
            elif health_score < 80:
                service.state = MeshServiceState.DEGRADED
            else:
                service.state = MeshServiceState.HEALTHY
            
            return True
    
    def get_healthy_services(self, name: str = None, version: str = None,
                             capability: str = None) -> List[MeshService]:
        """获取健康的服务列表"""
        with self._lock:
            results = []
            
            for service in self.services.values():
                # 按名称过滤
                if name and service.name != name:
                    continue
                
                # 按版本过滤
                if version and service.version != version:
                    continue
                
                # 按能力过滤
                if capability and capability not in service.capabilities:
                    continue
                
                # 检查健康状态
                if service.state == MeshServiceState.HEALTHY:
                    results.append(service)
                elif service.state == MeshServiceState.DEGRADED:
                    # 降级服务也可选
                    results.append(service)
            
            return results
    
    def select_service(self, name: str, version: str = "v1",
                       strategy: str = "round_robin") -> Optional[MeshService]:
        """负载均衡选择服务"""
        with self._lock:
            services = self.get_healthy_services(name, version)
            
            if not services:
                return None
            
            # 负载均衡策略
            if strategy == "random":
                import random
                return random.choice(services)
            
            elif strategy == "least_connections":
                # 选择并发最少的服务
                return min(services, 
                          key=lambda s: self.metrics.get(s.service_id, MeshMetrics(s.service_id)).current_concurrent)
            
            elif strategy == "weighted":
                # 按权重选择
                total_weight = sum(
                    self.traffic_policies.get(s.service_id, TrafficPolicy(s.service_id)).weight 
                    for s in services
                )
                import random
                r = random.uniform(0, total_weight)
                cumulative = 0
                for s in services:
                    w = self.traffic_policies.get(s.service_id, TrafficPolicy(s.service_id)).weight
                    cumulative += w
                    if r <= cumulative:
                        return s
                return services[-1]
            
            else:  # round_robin
                # 简单轮询
                return services[hash(str(time.time())) % len(services)]
    
    def can_route(self, service_id: str) -> tuple[bool, str]:
        """检查是否可以路由到服务 (熔断+速率限制)"""
        with self._lock:
            # 检查熔断器
            if self.config["enable_circuit_breaker"]:
                cb = self.circuit_breakers.get(service_id)
                if cb and not cb.is_available():
                    return False, "circuit_breaker_open"
            
            # 检查速率限制
            if self.config["enable_rate_limiting"]:
                policy = self.traffic_policies.get(service_id)
                if policy:
                    now = time.time()
                    # 清理旧请求记录
                    self.rate_limits[service_id] = [
                        t for t in self.rate_limits[service_id] 
                        if now - t < 1.0
                    ]
                    
                    rps = len(self.rate_limits[service_id])
                    if rps >= policy.max_requests_per_second:
                        return False, "rate_limit_exceeded"
                    
                    self.rate_limits[service_id].append(now)
            
            # 检查并发限制
            metrics = self.metrics.get(service_id)
            if metrics:
                policy = self.traffic_policies.get(service_id)
                if policy and metrics.current_concurrent >= policy.max_concurrent_requests:
                    return False, "concurrent_limit_exceeded"
            
            return True, "ok"
    
    def record_request(self, service_id: str, success: bool, latency_ms: float):
        """记录请求结果"""
        with self._lock:
            metrics = self.metrics.get(service_id)
            if metrics:
                metrics.record_request(success, latency_ms)
            
            cb = self.circuit_breakers.get(service_id)
            if cb:
                if success:
                    cb.record_success()
                else:
                    cb.record_failure()
    
    def update_traffic_policy(self, service_id: str, policy: TrafficPolicy):
        """更新流量策略"""
        with self._lock:
            self.traffic_policies[service_id] = policy
            
            # 更新熔断器配置
            cb = self.circuit_breakers.get(service_id)
            if cb and policy.circuit_breaker_enabled:
                cb.failure_threshold = policy.circuit_failure_threshold
                cb.timeout = policy.circuit_timeout
            
            logger.info(f"更新流量策略: {service_id}")
    
    def get_mesh_status(self) -> Dict:
        """获取网格状态"""
        with self._lock:
            total_services = len(self.services)
            healthy_services = sum(
                1 for s in self.services.values() 
                if s.state == MeshServiceState.HEALTHY
            )
            
            # 聚合指标
            total_requests = sum(m.total_requests for m in self.metrics.values())
            total_errors = sum(m.total_failure for m in self.metrics.values())
            
            return {
                "total_services": total_services,
                "healthy_services": healthy_services,
                "degraded_services": sum(
                    1 for s in self.services.values() 
                    if s.state == MeshServiceState.DEGRADED
                ),
                "unhealthy_services": sum(
                    1 for s in self.services.values() 
                    if s.state == MeshServiceState.UNHEALTHY
                ),
                "total_requests": total_requests,
                "total_errors": total_errors,
                "overall_error_rate": total_errors / max(1, total_requests),
                "service_groups": len(self.service_groups),
                "circuit_breakers_open": sum(
                    1 for cb in self.circuit_breakers.values()
                    if cb.state == CircuitState.OPEN
                )
            }
    
    def get_service_details(self, service_id: str = None) -> Dict:
        """获取服务详情"""
        with self._lock:
            if service_id:
                service = self.services.get(service_id)
                if not service:
                    return {"error": "service not found"}
                
                cb = self.circuit_breakers.get(service_id)
                policy = self.traffic_policies.get(service_id)
                metrics = self.metrics.get(service_id)
                
                return {
                    "service": service.to_dict(),
                    "circuit_breaker": {
                        "state": cb.state.value if cb else "unknown",
                        "failure_count": cb.failure_count if cb else 0
                    } if cb else None,
                    "policy": policy.to_dict() if policy else None,
                    "metrics": metrics.to_dict() if metrics else None
                }
            else:
                # 返回所有服务
                return {
                    service_id: {
                        "service": s.to_dict(),
                        "circuit_breaker": {
                            "state": self.circuit_breakers[service_id].state.value,
                            "failure_count": self.circuit_breakers[service_id].failure_count
                        } if service_id in self.circuit_breakers else None,
                        "metrics": self.metrics[service_id].to_dict() if service_id in self.metrics else None
                    }
                    for service_id, s in self.services.items()
                }
    
    def sync_with_gateway(self, gateway) -> int:
        """从API网关同步服务"""
        with self._lock:
            synced = 0
            
            if not gateway or not hasattr(gateway, 'agents'):
                return 0
            
            for agent_id, agent in gateway.agents.items():
                # 检查是否已注册
                if agent_id in self.services:
                    # 更新健康状态
                    health_score = agent.get('health_score', 100.0)
                    self.update_service_health(agent_id, health_score)
                else:
                    # 注册新服务
                    service = MeshService(
                        service_id=agent_id,
                        name=agent.get('metadata', {}).get('name', agent_id),
                        version=agent.get('metadata', {}).get('version', 'v1'),
                        capabilities=agent.get('capabilities', []),
                        metadata=agent.get('metadata', {}),
                        health_score=agent.get('health_score', 100.0)
                    )
                    self.register_service(service)
                
                synced += 1
            
            logger.info(f"从网关同步 {synced} 个服务")
            return synced


def create_mesh_from_gateway(gateway) -> AgentServiceMesh:
    """从API网关创建服务网格"""
    mesh = AgentServiceMesh(gateway)
    
    # 同步现有代理
    mesh.sync_with_gateway(gateway)
    
    return mesh


# ========== CLI工具 ==========

def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent服务网格管理")
    parser.add_argument("command", choices=["status", "services", "metrics", "sync"],
                       help="命令")
    parser.add_argument("--service-id", help="服务ID")
    parser.add_argument("--gateway-url", default="http://localhost:8089",
                       help="网关URL")
    
    args = parser.parse_args()
    
    mesh = AgentServiceMesh()
    
    if args.command == "status":
        status = mesh.get_mesh_status()
        print(json.dumps(status, indent=2))
    
    elif args.command == "services":
        details = mesh.get_service_details(args.service_id)
        print(json.dumps(details, indent=2))
    
    elif args.command == "metrics":
        # 显示指标
        for service_id, m in mesh.metrics.items():
            print(json.dumps(m.to_dict(), indent=2))
    
    elif args.command == "sync":
        # 需要导入网关
        print("请在代码中调用 sync_with_gateway()")


if __name__ == "__main__":
    main()