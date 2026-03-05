#!/usr/bin/env python3
"""
Agent Service Mesh & Traffic Management
服务网格架构 - 流量路由、熔断、限流、监控

第47世: 实现Agent服务网格与流量管理
"""

import json
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import random


class CircuitState(Enum):
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断开启
    HALF_OPEN = "half_open"  # 半开尝试


class TrafficPolicy(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONN = "least_conn"
    RANDOM = "random"
    WEIGHTED = "weighted"
    CONSISTENT_HASH = "consistent_hash"


@dataclass
class CircuitBreaker:
    """熔断器"""
    failure_threshold: int = 5        # 失败多少次触发熔断
    success_threshold: int = 3        # 半开状态下成功多少次恢复
    timeout: float = 30.0             # 熔断超时时间(秒)
    half_open_max_requests: int = 3   # 半开状态最大请求数
    
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0
    half_open_requests: int = 0
    
    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.half_open_requests = 0
        else:
            self.failure_count = 0
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.half_open_requests = 0
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
    
    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_requests = 0
                self.success_count = 0
                return True
            return False
        
        # HALF_OPEN
        if self.half_open_requests < self.half_open_max_requests:
            self.half_open_requests += 1
            return True
        return False


@dataclass
class RateLimiter:
    """限流器 - 令牌桶算法"""
    rate: float = 100           # 每秒令牌数
    burst: int = 200            # 桶容量
    
    tokens: float = field(default=200)
    last_update: float = field(default_factory=time.time)
    
    def allow_request(self, tokens_needed: int = 1) -> bool:
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        if self.tokens >= tokens_needed:
            self.tokens -= tokens_needed
            return True
        return False
    
    def get_wait_time(self, tokens_needed: int = 1) -> float:
        if self.tokens >= tokens_needed:
            return 0
        return (tokens_needed - self.tokens) / self.rate


@dataclass
class ServiceEndpoint:
    """服务端点"""
    agent_id: str
    address: str
    weight: int = 100
    max_failures: int = 3
    
    is_healthy: bool = True
    response_time_avg: float = 0.0
    request_count: int = 0
    failure_count: int = 0
    success_count: int = 0
    last_used: float = 0
    
    current_connections: int = 0
    
    def get_health_score(self) -> float:
        """计算健康分数"""
        if not self.is_healthy:
            return 0
        if self.request_count == 0:
            return 100
        
        success_rate = self.success_count / self.request_count
        response_factor = max(0, 1 - self.response_time_avg / 5000)
        return success_rate * 50 + response_factor * 50


@dataclass 
class TrafficMetrics:
    """流量指标"""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    blocked_requests: int = 0
    circuit_breaks: int = 0
    rate_limited: int = 0
    
    response_time_sum: float = 0
    response_time_count: int = 0
    
    requests_by_service: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    errors_by_service: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    recent_latencies: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def record_request(self, service: str, success: bool, latency_ms: float):
        self.total_requests += 1
        self.requests_by_service[service] += 1
        
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
            self.errors_by_service[service] += 1
        
        self.response_time_sum += latency_ms
        self.response_time_count += 1
        self.recent_latencies.append(latency_ms)
    
    def record_blocked(self):
        self.blocked_requests += 1
    
    def record_circuit_break(self):
        self.circuit_breaks += 1
    
    def record_rate_limited(self):
        self.rate_limited += 1
    
    def get_avg_latency(self) -> float:
        if self.response_time_count == 0:
            return 0
        return self.response_time_sum / self.response_time_count
    
    def get_p99_latency(self) -> float:
        if not self.recent_latencies:
            return 0
        sorted_latencies = sorted(self.recent_latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[idx] if idx < len(sorted_latencies) else sorted_latencies[-1]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "blocked_requests": self.blocked_requests,
            "circuit_breaks": self.circuit_breaks,
            "rate_limited": self.rate_limited,
            "avg_latency_ms": round(self.get_avg_latency(), 2),
            "p99_latency_ms": round(self.get_p99_latency(), 2),
            "success_rate": round(self.successful_requests / max(1, self.total_requests) * 100, 2),
            "requests_by_service": dict(self.requests_by_service),
            "errors_by_service": dict(self.errors_by_service)
        }


class AgentServiceMesh:
    """
    Agent服务网格 - 流量管理核心
    
    功能:
    - 服务发现与负载均衡
    - 熔断器保护
    - 限流控制
    - 流量监控
    """
    
    def __init__(self):
        self.services: Dict[str, Dict[str, ServiceEndpoint]] = defaultdict(dict)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.metrics = TrafficMetrics()
        
        self.policy: TrafficPolicy = TrafficPolicy.LEAST_CONN
        self.default_rate_limit = 100  # 每秒100请求
        self.default_circuit_failure_threshold = 5
        
        self._lock = threading.RLock()
        self._middleware: List[Callable] = []
        
        # 状态文件
        self.state_file = "/root/.openclaw/workspace/ultron/agents/service_mesh_state.json"
        self._load_state()
    
    def _load_state(self):
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                # 恢复配置等（指标不恢复）
        except:
            pass
    
    def _save_state(self):
        with self._lock:
            state = {
                "policy": self.policy.value,
                "default_rate_limit": self.default_rate_limit,
                "services": {
                    svc: {eid: {"weight": e.weight} for eid, e in eps.items()}
                    for svc, eps in self.services.items()
                }
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
    
    def register_service(self, service_name: str, agent_id: str, 
                        address: str, weight: int = 100):
        """注册服务端点"""
        with self._lock:
            endpoint = ServiceEndpoint(
                agent_id=agent_id,
                address=address,
                weight=weight
            )
            self.services[service_name][agent_id] = endpoint
            
            # 初始化熔断器和限流器
            if service_name not in self.circuit_breakers:
                self.circuit_breakers[service_name] = CircuitBreaker(
                    failure_threshold=self.default_circuit_failure_threshold
                )
            if service_name not in self.rate_limiters:
                self.rate_limiters[service_name] = RateLimiter(
                    rate=self.default_rate_limit
                )
            
            self._save_state()
            return endpoint
    
    def unregister_service(self, service_name: str, agent_id: str):
        """注销服务端点"""
        with self._lock:
            if service_name in self.services:
                self.services[service_name].pop(agent_id, None)
                if not self.services[service_name]:
                    del self.services[service_name]
                    self.circuit_breakers.pop(service_name, None)
                    self.rate_limiters.pop(service_name, None)
    
    def set_service_healthy(self, service_name: str, agent_id: str, healthy: bool):
        """设置服务健康状态"""
        with self._lock:
            if service_name in self.services:
                endpoint = self.services[service_name].get(agent_id)
                if endpoint:
                    endpoint.is_healthy = healthy
    
    def select_endpoint(self, service_name: str) -> Optional[ServiceEndpoint]:
        """选择服务端点 - 根据负载均衡策略"""
        with self._lock:
            if service_name not in self.services:
                return None
            
            endpoints = [e for e in self.services[service_name].values() 
                        if e.is_healthy]
            if not endpoints:
                return None
            
            # 熔断检查
            cb = self.circuit_breakers.get(service_name)
            if cb and not cb.can_execute():
                self.metrics.record_circuit_break()
                return None
            
            # 限流检查
            rl = self.rate_limiters.get(service_name)
            if rl and not rl.allow_request():
                self.metrics.record_rate_limited()
                return None
            
            # 负载均衡选择
            selected = self._apply_policy(endpoints)
            if selected:
                selected.current_connections += 1
                selected.last_used = time.time()
            
            return selected
    
    def _apply_policy(self, endpoints: List[ServiceEndpoint]) -> Optional[ServiceEndpoint]:
        """应用负载均衡策略"""
        if self.policy == TrafficPolicy.ROUND_ROBIN:
            return min(endpoints, key=lambda e: e.last_used)
        
        elif self.policy == TrafficPolicy.LEAST_CONN:
            return min(endpoints, key=lambda e: e.current_connections)
        
        elif self.policy == TrafficPolicy.RANDOM:
            return random.choice(endpoints)
        
        elif self.policy == TrafficPolicy.WEIGHTED:
            total_weight = sum(e.weight for e in endpoints)
            r = random.uniform(0, total_weight)
            cumulative = 0
            for e in endpoints:
                cumulative += e.weight
                if r <= cumulative:
                    return e
            return endpoints[-1]
        
        elif self.policy == TrafficPolicy.CONSISTENT_HASH:
            # 简化版: 基于agent_id哈希
            return min(endpoints, key=lambda e: hash(e.agent_id))
        
        return endpoints[0]
    
    def record_response(self, service_name: str, agent_id: str, 
                       success: bool, latency_ms: float):
        """记录响应结果"""
        with self._lock:
            # 更新端点统计
            if service_name in self.services:
                endpoint = self.services[service_name].get(agent_id)
                if endpoint:
                    endpoint.current_connections = max(0, endpoint.current_connections - 1)
                    endpoint.request_count += 1
                    if success:
                        endpoint.success_count += 1
                        # 移动平均响应时间
                        endpoint.response_time_avg = (
                            endpoint.response_time_avg * 0.7 + latency_ms * 0.3
                        )
                    else:
                        endpoint.failure_count += 1
            
            # 更新熔断器
            cb = self.circuit_breakers.get(service_name)
            if cb:
                if success:
                    cb.record_success()
                else:
                    cb.record_failure()
            
            # 更新指标
            self.metrics.record_request(service_name, success, latency_ms)
    
    def set_policy(self, policy: TrafficPolicy):
        """设置负载均衡策略"""
        self.policy = policy
    
    def set_rate_limit(self, service_name: str, rate: float, burst: int = None):
        """设置服务限流参数"""
        with self._lock:
            if service_name in self.rate_limiters:
                self.rate_limiters[service_name].rate = rate
                if burst:
                    self.rate_limiters[service_name].burst = burst
            else:
                self.rate_limiters[service_name] = RateLimiter(
                    rate=rate, 
                    burst=burst or int(rate * 2)
                )
    
    def set_circuit_breaker(self, service_name: str, 
                           failure_threshold: int = None,
                           timeout: float = None):
        """设置熔断器参数"""
        with self._lock:
            if service_name in self.circuit_breakers:
                cb = self.circuit_breakers[service_name]
                if failure_threshold:
                    cb.failure_threshold = failure_threshold
                if timeout:
                    cb.timeout = timeout
    
    def get_service_status(self, service_name: str = None) -> Dict[str, Any]:
        """获取服务状态"""
        with self._lock:
            if service_name:
                if service_name not in self.services:
                    return {"error": "Service not found"}
                
                endpoints = []
                for eid, ep in self.services[service_name].items():
                    endpoints.append({
                        "agent_id": eid,
                        "address": ep.address,
                        "healthy": ep.is_healthy,
                        "weight": ep.weight,
                        "requests": ep.request_count,
                        "success_rate": round(ep.success_count / max(1, ep.request_count) * 100, 2),
                        "avg_latency_ms": round(ep.response_time_avg, 2),
                        "current_connections": ep.current_connections
                    })
                
                cb = self.circuit_breakers.get(service_name)
                rl = self.rate_limiters.get(service_name)
                
                return {
                    "service": service_name,
                    "endpoints": endpoints,
                    "circuit_breaker": {
                        "state": cb.state.value if cb else "unknown",
                        "failures": cb.failure_count if cb else 0
                    },
                    "rate_limiter": {
                        "rate": rl.rate if rl else 0,
                        "tokens": round(rl.tokens, 2) if rl else 0
                    }
                }
            
            # 返回所有服务
            result = {}
            for svc in self.services:
                result[svc] = {
                    "endpoint_count": len(self.services[svc]),
                    "healthy_count": sum(1 for e in self.services[svc].values() if e.is_healthy)
                }
            return result
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取流量指标"""
        return self.metrics.to_dict()
    
    def get_circuit_states(self) -> Dict[str, str]:
        """获取所有熔断器状态"""
        return {
            svc: cb.state.value 
            for svc, cb in self.circuit_breakers.items()
        }
    
    def add_middleware(self, middleware: Callable):
        """添加中间件"""
        self._middleware.append(middleware)
    
    def execute_with_fallback(self, service_name: str, 
                             operation: Callable, 
                             fallback: Callable = None) -> Any:
        """执行操作并处理熔断/降级"""
        endpoint = self.select_endpoint(service_name)
        
        if not endpoint:
            if fallback:
                return fallback()
            raise Exception(f"No available endpoint for service: {service_name}")
        
        try:
            start = time.time()
            result = operation(endpoint)
            latency = (time.time() - start) * 1000
            
            self.record_response(service_name, endpoint.agent_id, True, latency)
            return result
            
        except Exception as e:
            latency = (time.time() - start) * 1000 if 'start' in locals() else 0
            self.record_response(service_name, endpoint.agent_id, False, latency)
            
            if fallback:
                return fallback()
            raise


# 全局服务网格实例
_service_mesh = None
_lock = threading.Lock()


def get_service_mesh() -> AgentServiceMesh:
    """获取全局服务网格实例"""
    global _service_mesh
    if _service_mesh is None:
        with _lock:
            if _service_mesh is None:
                _service_mesh = AgentServiceMesh()
    return _service_mesh


# ============ CLI演示 ============

def demo():
    """演示服务网格功能"""
    print("=" * 60)
    print("Agent Service Mesh 演示")
    print("=" * 60)
    
    mesh = get_service_mesh()
    
    # 注册服务
    print("\n[1] 注册服务...")
    mesh.register_service("executor", "executor-1", "localhost:8001", weight=100)
    mesh.register_service("executor", "executor-2", "localhost:8002", weight=150)
    mesh.register_service("analyzer", "analyzer-1", "localhost:9001", weight=100)
    
    # 设置不同策略
    print("\n[2] 测试不同负载均衡策略...")
    
    for policy in [TrafficPolicy.ROUND_ROBIN, TrafficPolicy.LEAST_CONN, 
                   TrafficPolicy.WEIGHTED]:
        mesh.set_policy(policy)
        print(f"\n  策略: {policy.value}")
        selected = []
        for _ in range(6):
            ep = mesh.select_endpoint("executor")
            if ep:
                selected.append(ep.agent_id)
        print(f"    选择结果: {selected}")
    
    # 测试熔断
    print("\n[3] 测试熔断器...")
    mesh.set_circuit_breaker("executor", failure_threshold=3, timeout=5)
    
    # 模拟失败触发熔断
    for i in range(5):
        ep = mesh.select_endpoint("executor")
        if ep:
            mesh.record_response("executor", ep.agent_id, False, 100)
    
    print(f"    熔断状态: {mesh.get_circuit_states()}")
    
    # 尝试请求（应该被熔断）
    for _ in range(3):
        ep = mesh.select_endpoint("executor")
        print(f"    熔断中请求: {'被阻止' if ep is None else ep.agent_id}")
    
    # 测试限流
    print("\n[4] 测试限流器...")
    mesh.set_rate_limit("analyzer", rate=5, burst=10)
    
    for i in range(15):
        ep = mesh.select_endpoint("analyzer")
        status = "通过" if ep else "限流"
        print(f"    请求{i+1}: {status}")
    
    # 流量指标
    print("\n[5] 流量指标:")
    metrics = mesh.get_metrics()
    for k, v in metrics.items():
        print(f"    {k}: {v}")
    
    # 服务状态
    print("\n[6] Executor服务状态:")
    status = mesh.get_service_status("executor")
    print(f"    {json.dumps(status, indent=4)}")
    
    print("\n✅ 服务网格演示完成!")
    return mesh


if __name__ == "__main__":
    demo()