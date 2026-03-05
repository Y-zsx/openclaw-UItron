#!/usr/bin/env python3
"""
Agent服务网格核心引擎
=====================
实现流量管理、熔断器、限流和服务发现

功能:
- TrafficRouter: 流量路由（金丝雀/A/B测试/镜像）
- CircuitBreaker: 熔断器模式
- RateLimiter: 限流器
- ServiceDiscovery: 服务发现
- MeshController: 统一网格控制器
"""

import time
import threading
import hashlib
import random
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict
import json


class TrafficRouteType(Enum):
    """流量路由类型"""
    BALANCED = "balanced"      # 均衡路由
    CANARY = "canary"          # 金丝雀
    AB_TEST = "ab_test"        # A/B测试
    MIRROR = "mirror"          # 流量镜像
    SHADOW = "shadow"          # 影子模式


class CircuitState(Enum):
    """熔断器状态"""
    CLOSED = "closed"          # 正常
    OPEN = "open"              # 熔断
    HALF_OPEN = "half_open"   # 半开


class CircuitBreaker:
    """
    熔断器实现
    ----------
    原理:
    - 失败率超过阈值时打开熔断
    - 熔断期间快速失败
    - 半开状态探测服务恢复
    """
    
    def __init__(
        self,
        failure_threshold: float = 0.5,   # 失败率阈值
        success_threshold: int = 3,       # 恢复所需成功数
        timeout: float = 30.0,            # 熔断持续时间(秒)
        half_open_timeout: float = 60.0   # 半开状态超时
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.half_open_timeout = half_open_timeout
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = 0
        self._total_requests = 0
        self._failed_requests = 0
        self._lock = threading.RLock()
        
        # 回调函数
        self.on_open: Optional[Callable] = None
        self.on_close: Optional[Callable] = None
        self.on_half_open: Optional[Callable] = None
    
    @property
    def state(self) -> CircuitState:
        with self._lock:
            now = time.time()
            
            if self._state == CircuitState.OPEN:
                # 检查是否应该进入半开
                if now - self._last_failure_time > self.timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    if self.on_half_open:
                        self.on_half_open()
            
            elif self._state == CircuitState.HALF_OPEN:
                # 半开状态超时，回到open
                if now - self._last_failure_time > self.half_open_timeout:
                    self._state = CircuitState.OPEN
                    self._last_failure_time = now  # 重置
            
            return self._state
    
    def record_success(self):
        """记录成功请求"""
        with self._lock:
            self._total_requests += 1
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    if self.on_close:
                        self.on_close()
            
            elif self._state == CircuitState.CLOSED:
                # 成功时逐渐清除失败计数
                self._failure_count = max(0, self._failure_count - 0.5)
    
    def record_failure(self):
        """记录失败请求"""
        with self._lock:
            self._total_requests += 1
            self._failed_requests += 1
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            failure_rate = self._failed_requests / self._total_requests
            
            if self._state == CircuitState.HALF_OPEN:
                # 半开状态失败，回到open
                self._state = CircuitState.OPEN
            
            elif self._state == CircuitState.CLOSED:
                if failure_rate >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    if self.on_open:
                        self.on_open(failure_rate)
    
    def is_available(self) -> bool:
        """检查是否可用"""
        return self.state != CircuitState.OPEN
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            return {
                "state": self.state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
                "total_requests": self._total_requests,
                "failed_requests": self._failed_requests,
                "failure_rate": self._failed_requests / max(1, self._total_requests),
                "last_failure_time": self._last_failure_time
            }


class RateLimiter:
    """
    令牌桶限流器
    -------------
    实现平滑限流，支持突发流量
    """
    
    def __init__(
        self,
        rate: float = 100,          # 每秒令牌数
        capacity: int = 100,        # 桶容量
        refill_interval: float = 1.0  # 填充间隔(秒)
    ):
        self.rate = rate
        self.capacity = capacity
        self.refill_interval = refill_interval
        
        self._tokens = float(capacity)
        self._last_refill = time.time()
        self._lock = threading.Lock()
        
        # 按客户端限流
        self._client_buckets: Dict[str, Dict] = defaultdict(
            lambda: {"tokens": float(capacity), "last_refill": time.time()}
        )
    
    def _refill_bucket(self, bucket: Dict):
        """填充令牌桶"""
        now = time.time()
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(
            self.capacity,
            bucket["tokens"] + elapsed * self.rate
        )
        bucket["last_refill"] = now
    
    def allow_request(self, client_id: str = "default", tokens: int = 1) -> bool:
        """检查是否允许请求"""
        with self._lock:
            bucket = self._client_buckets[client_id]
            self._refill_bucket(bucket)
            
            if bucket["tokens"] >= tokens:
                bucket["tokens"] -= tokens
                return True
            return False
    
    def get_wait_time(self, client_id: str = "default") -> float:
        """获取需要等待的时间(秒)"""
        with self._lock:
            bucket = self._client_buckets[client_id]
            self._refill_bucket(bucket)
            return max(0, (1 - bucket["tokens"]) / self.rate) if bucket["tokens"] < 1 else 0
    
    def get_stats(self, client_id: str = "default") -> Dict:
        """获取统计信息"""
        with self._lock:
            bucket = self._client_buckets.get(client_id, {})
            return {
                "client_id": client_id,
                "available_tokens": bucket.get("tokens", 0),
                "capacity": self.capacity,
                "rate": self.rate
            }


class TrafficRouter:
    """
    流量路由器
    -------------
    支持多种路由策略
    """
    
    def __init__(self):
        self._routes: Dict[str, Dict] = {}  # service -> route config
        self._lock = threading.RLock()
    
    def add_route(
        self,
        service: str,
        route_type: TrafficRouteType,
        targets: List[Dict],
        weights: Optional[List[int]] = None,
        rules: Optional[Dict] = None
    ):
        """
        添加路由规则
        
        targets: [{"version": "v1", "endpoint": "..."}, ...]
        weights: [80, 20]  # 权重
        rules: {"header": {...}, "cookie": {...}}
        """
        with self._lock:
            self._routes[service] = {
                "type": route_type,
                "targets": targets,
                "weights": weights or [100] * len(targets),
                "rules": rules or {},
                "created_at": time.time()
            }
    
    def route(
        self,
        service: str,
        request_context: Optional[Dict] = None
    ) -> Optional[Dict]:
        """
        根据路由规则返回目标服务
        
        request_context: {
            "headers": {...},
            "cookies": {...},
            "ip": "...",
            "user_agent": "..."
        }
        """
        with self._lock:
            route = self._routes.get(service)
            if not route:
                return None
            
            ctx = request_context or {}
            
            if route["type"] == TrafficRouteType.CANARY:
                # 金丝雀: 按权重小比例流量到新版本
                return self._route_canary(route, ctx)
            
            elif route["type"] == TrafficRouteType.AB_TEST:
                # A/B测试: 按用户或session分流
                return self._route_ab_test(route, ctx)
            
            elif route["type"] == TrafficRouteType.MIRROR:
                # 镜像: 返回主目标和镜像目标
                return self._route_mirror(route, ctx)
            
            else:
                # 均衡: 轮询或加权
                return self._route_balanced(route, ctx)
    
    def _route_canary(self, route: Dict, ctx: Dict) -> Dict:
        """金丝雀路由"""
        weights = route["weights"]
        targets = route["targets"]
        
        # 默认95%到主服务，5%到金丝雀
        canary_ratio = weights[-1] / sum(weights) if weights else 0.05
        
        if random.random() < canary_ratio:
            return {"target": targets[-1], "is_canary": True}
        return {"target": targets[0], "is_canary": False}
    
    def _route_ab_test(self, route: Dict, ctx: Dict) -> Dict:
        """A/B测试路由"""
        # 按用户ID哈希分组，保证同一用户走同一版本
        user_id = ctx.get("user_id") or ctx.get("headers", {}).get("X-User-ID", "")
        
        if user_id:
            hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
            idx = hash_val % len(route["targets"])
        else:
            idx = random.randint(0, len(route["targets"]) - 1)
        
        return {"target": route["targets"][idx], "variant": chr(65 + idx)}
    
    def _route_mirror(self, route: Dict, ctx: Dict) -> Dict:
        """镜像路由"""
        return {
            "primary": route["targets"][0],
            "mirror": route["targets"][-1] if len(route["targets"]) > 1 else None,
            "is_mirror": True
        }
    
    def _route_balanced(self, route: Dict, ctx: Dict) -> Dict:
        """均衡路由"""
        weights = route["weights"]
        targets = route["targets"]
        
        # 加权随机
        total = sum(weights)
        r = random.random() * total
        
        cumulative = 0
        for i, w in enumerate(weights):
            cumulative += w
            if r <= cumulative:
                return {"target": targets[i]}
        
        return {"target": targets[0]}
    
    def get_route(self, service: str) -> Optional[Dict]:
        """获取路由配置"""
        with self._lock:
            return self._routes.get(service)
    
    def remove_route(self, service: str):
        """删除路由"""
        with self._lock:
            self._routes.pop(service, None)


class ServiceDiscovery:
    """
    服务发现
    -------------
    自动发现和注册Agent服务
    """
    
    def __init__(self):
        self._services: Dict[str, Dict] = {}  # service_name -> info
        self._instances: Dict[str, List[Dict]] = defaultdict(list)  # service -> instances
        self._lock = threading.RLock()
        
        # 健康检查
        self._health_checks: Dict[str, Callable] = {}
        self._health_thread: Optional[threading.Thread] = None
        self._running = False
    
    def register_service(
        self,
        service_name: str,
        endpoint: str,
        metadata: Optional[Dict] = None,
        health_check: Optional[Callable] = None
    ):
        """注册服务"""
        with self._lock:
            instance_id = f"{service_name}-{len(self._instances[service_name])}"
            
            instance = {
                "id": instance_id,
                "service_name": service_name,
                "endpoint": endpoint,
                "metadata": metadata or {},
                "registered_at": time.time(),
                "last_heartbeat": time.time(),
                "healthy": True
            }
            
            self._instances[service_name].append(instance)
            self._services[instance_id] = instance
            
            if health_check:
                self._health_checks[instance_id] = health_check
    
    def heartbeat(self, instance_id: str) -> bool:
        """接收心跳"""
        with self._lock:
            instance = self._services.get(instance_id)
            if instance:
                instance["last_heartbeat"] = time.time()
                instance["healthy"] = True
                return True
            return False
    
    def discover(self, service_name: str, healthy_only: bool = True) -> List[Dict]:
        """发现服务实例"""
        with self._lock:
            instances = self._instances.get(service_name, [])
            
            if healthy_only:
                # 检查心跳超时
                now = time.time()
                for inst in instances:
                    if now - inst["last_heartbeat"] > 30:  # 30秒超时
                        inst["healthy"] = False
                
                return [i for i in instances if i["healthy"]]
            
            return instances
    
    def get_service_info(self, service_name: str) -> Dict:
        """获取服务信息"""
        with self._lock:
            instances = self.discover(service_name)
            return {
                "service": service_name,
                "instances": len(instances),
                "healthy": sum(1 for i in instances if i["healthy"]),
                "endpoints": [i["endpoint"] for i in instances]
            }
    
    def remove_instance(self, instance_id: str):
        """移除实例"""
        with self._lock:
            instance = self._services.pop(instance_id, None)
            if instance:
                service = instance["service_name"]
                self._instances[service] = [
                    i for i in self._instances[service]
                    if i["id"] != instance_id
                ]


class MeshController:
    """
    服务网格控制器
    --------------
    统一管理所有网格组件
    """
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.rate_limiters: Dict[str, RateLimiter] = {}
        self.router = TrafficRouter()
        self.discovery = ServiceDiscovery()
        
        # 流量统计
        self._traffic_stats: Dict[str, List[Dict]] = defaultdict(list)
        self._stats_lock = threading.Lock()
        
        # 锁
        self._lock = threading.RLock()
    
    def get_circuit_breaker(self, name: str, **kwargs) -> CircuitBreaker:
        """获取或创建熔断器"""
        with self._lock:
            if name not in self.circuit_breakers:
                self.circuit_breakers[name] = CircuitBreaker(**kwargs)
            return self.circuit_breakers[name]
    
    def get_rate_limiter(self, name: str, **kwargs) -> RateLimiter:
        """获取或创建限流器"""
        with self._lock:
            if name not in self.rate_limiters:
                self.rate_limiters[name] = RateLimiter(**kwargs)
            return self.rate_limiters[name]
    
    def record_traffic(
        self,
        service: str,
        target: str,
        latency_ms: float,
        success: bool,
        status_code: int = 200
    ):
        """记录流量统计"""
        with self._stats_lock:
            stat = {
                "timestamp": time.time(),
                "service": service,
                "target": target,
                "latency_ms": latency_ms,
                "success": success,
                "status_code": status_code
            }
            
            self._traffic_stats[service].append(stat)
            
            # 保留最近10000条
            if len(self._traffic_stats[service]) > 10000:
                self._traffic_stats[service] = self._traffic_stats[service][-5000:]
    
    def get_traffic_stats(
        self,
        service: str,
        window_seconds: int = 300
    ) -> Dict:
        """获取流量统计"""
        with self._stats_lock:
            now = time.time()
            stats = self._traffic_stats.get(service, [])
            
            # 过滤时间窗口
            recent = [s for s in stats if now - s["timestamp"] < window_seconds]
            
            if not recent:
                return {
                    "service": service,
                    "requests": 0,
                    "success_rate": 0,
                    "avg_latency_ms": 0,
                    "p95_latency_ms": 0
                }
            
            total = len(recent)
            successes = sum(1 for s in recent if s["success"])
            latencies = [s["latency_ms"] for s in recent]
            latencies.sort()
            
            return {
                "service": service,
                "requests": total,
                "success_rate": successes / total,
                "avg_latency_ms": sum(latencies) / total,
                "p95_latency_ms": latencies[int(total * 0.95)] if total > 20 else max(latencies),
                "p99_latency_ms": latencies[int(total * 0.99)] if total > 100 else max(latencies),
                "window_seconds": window_seconds
            }
    
    def get_status(self) -> Dict:
        """获取网格状态"""
        with self._lock:
            return {
                "circuit_breakers": {
                    name: cb.get_stats()
                    for name, cb in self.circuit_breakers.items()
                },
                "rate_limiters": {
                    name: rl.get_stats()
                    for name, rl in self.rate_limiters.items()
                },
                "routes": list(self.router._routes.keys()),
                "services": list(self.discovery._instances.keys())
            }


# 全局网格控制器
_mesh: Optional[MeshController] = None
_mesh_lock = threading.Lock()


def get_mesh_controller() -> MeshController:
    """获取全局网格控制器"""
    global _mesh
    with _mesh_lock:
        if _mesh is None:
            _mesh = MeshController()
        return _mesh