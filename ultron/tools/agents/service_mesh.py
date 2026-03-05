"""
Agent服务网格与流量管理系统
第47世: 实现Agent服务网格与流量管理

核心功能:
- 服务发现与注册
- 流量路由与管理
- 熔断器模式
- 限流与排队
- 流量监控与分析
- 智能流量调度
"""

import asyncio
import time
import random
import hashlib
import json
import sqlite3
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
from datetime import datetime
import threading
import logging
from flask import Flask, request, jsonify
from werkzeug.serving import make_server
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("service-mesh")


# ============ 枚举定义 ============

class CircuitState(Enum):
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断开启
    HALF_OPEN = "half_open"  # 半开状态


class TrafficPolicy(Enum):
    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    RATE_LIMIT = "rate_limit"
    FAILOVER = "failover"
    CANARY = "canary"
    SHADOW = "shadow"


class ServiceStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPLOYING = "deploying"
    MAINTENANCE = "maintenance"


# ============ 数据模型 ============

@dataclass
class ServiceEndpoint:
    """服务端点"""
    endpoint_id: str
    service_name: str
    agent_type: str
    host: str
    port: int
    version: str = "v1"
    weight: int = 100
    labels: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: ServiceStatus = ServiceStatus.ACTIVE
    is_healthy: bool = True
    current_rps: float = 0.0
    max_rps: float = 1000.0
    latency_p50: float = 0.0
    latency_p99: float = 0.0
    error_rate: float = 0.0
    last_request_time: float = 0.0
    registered_at: float = field(default_factory=time.time)
    last_heartbeat: float = field(default_factory=time.time)


@dataclass
class TrafficRoute:
    """流量路由规则"""
    route_id: str
    service_name: str
    match_labels: Dict[str, str]
    destination_service: str
    weight: int = 100  # 0-100
    timeout_ms: int = 5000
    retries: int = 3
    retry_timeout_ms: int = 2000
    mirror_enabled: bool = False
    mirror_destination: Optional[str] = None
    mirror_percent: int = 0
    enabled: bool = True


@dataclass
class CircuitBreaker:
    """熔断器配置"""
    service_name: str
    failure_threshold: int = 5  # 连续失败次数触发熔断
    success_threshold: int = 2  # 半开转关闭需要的成功次数
    timeout_seconds: int = 30   # 熔断持续时间
    half_open_max_requests: int = 3  # 半开状态最大请求数
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    total_opens: int = 0


@dataclass
class RateLimitRule:
    """限流规则"""
    rule_id: str
    service_name: str
    max_requests_per_second: int = 100
    max_requests_per_minute: int = 1000
    max_concurrent: int = 50
    burst_size: int = 200
    strategy: str = "token_bucket"


@dataclass
class TrafficMetrics:
    """流量指标"""
    request_id: str
    source_service: str
    destination_service: str
    endpoint_id: str
    timestamp: float
    latency_ms: float
    response_size: int
    error: bool = False
    error_type: Optional[str] = None
    retry_count: int = 0


# ============ 高级流量控制数据模型 ============

@dataclass
class ABTestConfig:
    """A/B测试配置"""
    test_id: str
    service_name: str
    variant_a: str  # 服务版本A
    variant_b: str  # 服务版本B
    traffic_split: int = 50  # A的流量百分比 (0-100)
    cookie_name: str = "ab_variant"
    cookie_ttl: int = 86400
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CanaryRelease:
    """金丝雀发布配置"""
    release_id: str
    service_name: str
    baseline_version: str  # 稳定版本
    canary_version: str    # 金丝雀版本
    baseline_weight: int = 90
    canary_weight: int = 10
    progress_increment: int = 5  # 每次增加百分比
    progress_interval_seconds: int = 300  # 递增间隔
    auto_rollback: bool = True
    error_threshold_percent: float = 5.0
    latency_threshold_ms: float = 500.0
    status: str = "preparing"  # preparing, running, promoting, completed, rolled_back
    current_progress: int = 10
    start_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TrafficSplit:
    """流量分割规则"""
    split_id: str
    service_name: str
    splits: List[Dict[str, Any]]  # [{"version": "v1", "weight": 60}, {"version": "v2", "weight": 40}]
    match_conditions: List[Dict[str, str]] = field(default_factory=list)  # 匹配条件
    sticky_session: bool = False
    enabled: bool = True


@dataclass
class TrafficPolicy:
    """流量策略"""
    policy_id: str
    service_name: str
    policy_type: str  # "ab", "canary", "split", "mirror"
    config: Dict[str, Any]
    priority: int = 0
    enabled: bool = True
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


# ============ 高级流量控制器 ============

class AdvancedTrafficController:
    """高级流量控制器 - A/B测试、金丝雀、流量分割"""
    
    def __init__(self):
        self._ab_tests: Dict[str, ABTestConfig] = {}
        self._canary_releases: Dict[str, CanaryRelease] = {}
        self._traffic_splits: Dict[str, TrafficSplit] = {}
        self._traffic_policies: Dict[str, TrafficPolicy] = {}
        self._metrics_history: List[TrafficMetrics] = []
        self._lock = threading.RLock()
    
    # A/B测试管理
    def create_ab_test(self, config: ABTestConfig) -> str:
        with self._lock:
            self._ab_tests[config.test_id] = config
            return config.test_id
    
    def get_ab_test(self, test_id: str) -> Optional[ABTestConfig]:
        return self._ab_tests.get(test_id)
    
    def list_ab_tests(self) -> List[ABTestConfig]:
        return list(self._ab_tests.values())
    
    def update_ab_test(self, test_id: str, traffic_split: int = None, enabled: bool = None) -> bool:
        with self._lock:
            if test_id not in self._ab_tests:
                return False
            if traffic_split is not None:
                self._ab_tests[test_id].traffic_split = traffic_split
            if enabled is not None:
                self._ab_tests[test_id].enabled = enabled
            return True
    
    def delete_ab_test(self, test_id: str) -> bool:
        with self._lock:
            if test_id in self._ab_tests:
                del self._ab_tests[test_id]
                return True
            return False
    
    # 解析A/B测试流量分配
    def resolve_ab_variant(self, service_name: str, request_hash: str) -> Optional[str]:
        """根据请求hash解析A/B版本"""
        with self._lock:
            for test in self._ab_tests.values():
                if test.service_name == service_name and test.enabled:
                    # 使用hash进行一致性哈希
                    hash_val = int(hashlib.md5(request_hash.encode()).hexdigest(), 16) % 100
                    if hash_val < test.traffic_split:
                        return test.variant_a
                    return test.variant_b
            return None
    
    # 金丝雀发布管理
    def create_canary_release(self, release: CanaryRelease) -> str:
        with self._lock:
            self._canary_releases[release.release_id] = release
            return release.release_id
    
    def get_canary_release(self, release_id: str) -> Optional[CanaryRelease]:
        return self._canary_releases.get(release_id)
    
    def list_canary_releases(self, service_name: str = None) -> List[CanaryRelease]:
        with self._lock:
            if service_name:
                return [r for r in self._canary_releases.values() if r.service_name == service_name]
            return list(self._canary_releases.values())
    
    def promote_canary(self, release_id: str, increment: bool = True) -> bool:
        with self._lock:
            if release_id not in self._canary_releases:
                return False
            release = self._canary_releases[release_id]
            if release.status not in ["running", "promoting"]:
                return False
            if increment:
                new_progress = min(100, release.current_progress + release.progress_increment)
                release.current_progress = new_progress
                # 更新权重
                release.canary_weight = new_progress
                release.baseline_weight = 100 - new_progress
                if new_progress >= 100:
                    release.status = "completed"
            return True
    
    def rollback_canary(self, release_id: str) -> bool:
        with self._lock:
            if release_id not in self._canary_releases:
                return False
            release = self._canary_releases[release_id]
            release.status = "rolled_back"
            release.canary_weight = 0
            release.baseline_weight = 100
            return True
    
    # 流量分割管理
    def create_traffic_split(self, split: TrafficSplit) -> str:
        with self._lock:
            self._traffic_splits[split.split_id] = split
            return split.split_id
    
    def get_traffic_split(self, split_id: str) -> Optional[TrafficSplit]:
        return self._traffic_splits.get(split_id)
    
    def resolve_traffic_split(self, service_name: str, request_labels: Dict[str, str] = None) -> Optional[str]:
        """解析流量分割目标版本"""
        with self._lock:
            for split in self._traffic_splits.values():
                if split.service_name == service_name and split.enabled:
                    # 检查匹配条件
                    if split.match_conditions:
                        match = False
                        for cond in split.match_conditions:
                            if request_labels and all(request_labels.get(k) == v for k, v in cond.items()):
                                match = True
                                break
                        if not match:
                            continue
                    # 简单轮询分配
                    total_weight = sum(s["weight"] for s in split.splits)
                    rand = random.randint(1, total_weight)
                    cumsum = 0
                    for s in split.splits:
                        cumsum += s["weight"]
                        if rand <= cumsum:
                            return s["version"]
            return None
    
    # 流量策略管理
    def create_policy(self, policy: TrafficPolicy) -> str:
        with self._lock:
            self._traffic_policies[policy.policy_id] = policy
            return policy.policy_id
    
    def get_policy(self, policy_id: str) -> Optional[TrafficPolicy]:
        return self._traffic_policies.get(policy_id)
    
    def list_policies(self, service_name: str = None) -> List[TrafficPolicy]:
        with self._lock:
            if service_name:
                return [p for p in self._traffic_policies.values() if p.service_name == service_name]
            return list(self._traffic_policies.values())
    
    def update_policy(self, policy_id: str, enabled: bool = None, config: Dict = None) -> bool:
        with self._lock:
            if policy_id not in self._traffic_policies:
                return False
            if enabled is not None:
                self._traffic_policies[policy_id].enabled = enabled
            if config is not None:
                self._traffic_policies[policy_id].config = config
                self._traffic_policies[policy_id].updated_at = time.time()
            return True
    
    def delete_policy(self, policy_id: str) -> bool:
        with self._lock:
            if policy_id in self._traffic_policies:
                del self._traffic_policies[policy_id]
                return True
            return False
    
    # 流量指标收集
    def record_metrics(self, metrics: TrafficMetrics):
        with self._lock:
            self._metrics_history.append(metrics)
            # 保持最近10000条记录
            if len(self._metrics_history) > 10000:
                self._metrics_history = self._metrics_history[-5000:]
    
    def get_traffic_stats(self, service_name: str = None, minutes: int = 60) -> Dict[str, Any]:
        """获取流量统计"""
        with self._lock:
            cutoff = time.time() - minutes * 60
            recent = [m for m in self._metrics_history if m.timestamp > cutoff]
            
            if service_name:
                recent = [m for m in recent if m.destination_service == service_name]
            
            total = len(recent)
            errors = len([m for m in recent if m.error])
            latencies = [m.latency_ms for m in recent]
            
            return {
                "total_requests": total,
                "error_count": errors,
                "error_rate": errors / total if total > 0 else 0,
                "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0,
                "p50_latency": sorted(latencies)[len(latencies)//2] if latencies else 0,
                "p99_latency": sorted(latencies)[int(len(latencies)*0.99)] if latencies else 0,
                "requests_per_minute": total / minutes if minutes > 0 else 0
            }


# ============ 服务网格核心 ============

class ServiceRegistry:
    """服务注册中心"""
    
    def __init__(self, db_path: str = "/tmp/service_mesh_registry.db"):
        self.db_path = db_path
        self._init_db()
        self._endpoints: Dict[str, ServiceEndpoint] = {}
        self._service_map: Dict[str, Set[str]] = defaultdict(set)
        self._lock = threading.RLock()
        self._load_endpoints()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS endpoints (
                endpoint_id TEXT PRIMARY KEY,
                service_name TEXT NOT NULL,
                agent_type TEXT,
                host TEXT,
                port INTEGER,
                version TEXT,
                weight INTEGER,
                labels TEXT,
                metadata TEXT,
                status TEXT,
                is_healthy INTEGER,
                max_rps REAL,
                registered_at REAL,
                last_heartbeat REAL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS traffic_routes (
                route_id TEXT PRIMARY KEY,
                service_name TEXT,
                match_labels TEXT,
                destination_service TEXT,
                weight INTEGER,
                timeout_ms INTEGER,
                retries INTEGER,
                mirror_enabled INTEGER,
                mirror_destination TEXT,
                mirror_percent INTEGER,
                enabled INTEGER
            )
        """)
        conn.commit()
        conn.close()
    
    def _load_endpoints(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM endpoints")
        for row in cursor.fetchall():
            ep = ServiceEndpoint(
                endpoint_id=row[0],
                service_name=row[1],
                agent_type=row[2] or "",
                host=row[3] or "",
                port=row[4] or 0,
                version=row[5] or "v1",
                weight=row[6] or 100,
                labels=json.loads(row[7]) if row[7] else {},
                metadata=json.loads(row[8]) if row[8] else {},
                status=ServiceStatus(row[9]) if row[9] else ServiceStatus.ACTIVE,
                is_healthy=bool(row[10]),
                max_rps=row[11] or 1000,
                registered_at=row[12] or time.time(),
                last_heartbeat=row[13] or time.time()
            )
            self._endpoints[ep.endpoint_id] = ep
            self._service_map[ep.service_name].add(ep.endpoint_id)
        conn.close()
    
    def register_endpoint(self, endpoint: ServiceEndpoint) -> bool:
        with self._lock:
            self._endpoints[endpoint.endpoint_id] = endpoint
            self._service_map[endpoint.service_name].add(endpoint.endpoint_id)
            self._save_endpoint(endpoint)
            return True
    
    def _save_endpoint(self, endpoint: ServiceEndpoint):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO endpoints VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            endpoint.endpoint_id,
            endpoint.service_name,
            endpoint.agent_type,
            endpoint.host,
            endpoint.port,
            endpoint.version,
            endpoint.weight,
            json.dumps(endpoint.labels),
            json.dumps(endpoint.metadata),
            endpoint.status.value,
            endpoint.is_healthy,
            endpoint.max_rps,
            endpoint.registered_at,
            endpoint.last_heartbeat
        ))
        conn.commit()
        conn.close()
    
    def deregister_endpoint(self, endpoint_id: str) -> bool:
        with self._lock:
            if endpoint_id in self._endpoints:
                ep = self._endpoints.pop(endpoint_id)
                self._service_map[ep.service_name].discard(endpoint_id)
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM endpoints WHERE endpoint_id = ?", (endpoint_id,))
                conn.commit()
                conn.close()
                return True
            return False
    
    def get_endpoints(self, service_name: str, labels: Optional[Dict[str, str]] = None) -> List[ServiceEndpoint]:
        with self._lock:
            endpoint_ids = self._service_map.get(service_name, set())
            endpoints = [self._endpoints[eid] for eid in endpoint_ids if eid in self._endpoints]
            
            if labels:
                endpoints = [ep for ep in endpoints if all(
                    ep.labels.get(k) == v for k, v in labels.items()
                )]
            
            return [ep for ep in endpoints if ep.status == ServiceStatus.ACTIVE]
    
    def get_all_services(self) -> List[str]:
        return list(self._service_map.keys())
    
    def update_health(self, endpoint_id: str, is_healthy: bool):
        if endpoint_id in self._endpoints:
            self._endpoints[endpoint_id].is_healthy = is_healthy
            self._endpoints[endpoint_id].last_heartbeat = time.time()


class CircuitBreakerManager:
    """熔断器管理器"""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.RLock()
    
    def get_breaker(self, service_name: str) -> CircuitBreaker:
        with self._lock:
            if service_name not in self._breakers:
                self._breakers[service_name] = CircuitBreaker(service_name=service_name)
            return self._breakers[service_name]
    
    def record_success(self, service_name: str):
        breaker = self.get_breaker(service_name)
        with self._lock:
            if breaker.state == CircuitState.HALF_OPEN:
                breaker.success_count += 1
                if breaker.success_count >= breaker.success_threshold:
                    breaker.state = CircuitState.CLOSED
                    breaker.failure_count = 0
                    breaker.success_count = 0
                    logger.info(f"Circuit breaker closed for {service_name}")
            elif breaker.state == CircuitState.CLOSED:
                breaker.failure_count = 0
    
    def record_failure(self, service_name: str):
        breaker = self.get_breaker(service_name)
        with self._lock:
            breaker.failure_count += 1
            breaker.last_failure_time = time.time()
            
            if breaker.state == CircuitState.CLOSED:
                if breaker.failure_count >= breaker.failure_threshold:
                    breaker.state = CircuitState.OPEN
                    breaker.total_opens += 1
                    logger.warning(f"Circuit breaker opened for {service_name}")
            
            elif breaker.state == CircuitState.OPEN:
                # Check if timeout has passed to transition to half-open
                if time.time() - breaker.last_failure_time >= breaker.timeout_seconds:
                    breaker.state = CircuitState.HALF_OPEN
                    breaker.success_count = 0
                    logger.info(f"Circuit breaker half-open for {service_name}")
    
    def can_request(self, service_name: str) -> bool:
        breaker = self.get_breaker(service_name)
        with self._lock:
            return breaker.state != CircuitState.OPEN
    
    def get_state(self, service_name: str) -> CircuitState:
        return self.get_breaker(service_name).state


class RateLimiter:
    """限流器 - 令牌桶算法"""
    
    def __init__(self, rps: int, burst: int = None):
        self.rps = rps
        self.burst = burst or rps * 2
        self.tokens = float(self.burst)
        self.last_update = time.time()
        self._lock = threading.Lock()
    
    def acquire(self, tokens: int = 1) -> bool:
        with self._lock:
            now = time.time()
            # 补充令牌
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rps)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def wait_for_tokens(self, tokens: int = 1, timeout: float = 5.0):
        start = time.time()
        while time.time() - start < timeout:
            if self.acquire(tokens):
                return True
            time.sleep(0.01)
        return False


class TrafficRouter:
    """流量路由器"""
    
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        self._routes: Dict[str, List[TrafficRoute]] = defaultdict(list)
        self._default_routes: Dict[str, TrafficRoute] = {}
        self._lock = threading.RLock()
    
    def add_route(self, route: TrafficRoute):
        with self._lock:
            self._routes[route.service_name].append(route)
    
    def set_default_route(self, service_name: str, destination: str):
        route = TrafficRoute(
            route_id=f"default_{service_name}",
            service_name=service_name,
            match_labels={},
            destination_service=destination,
            weight=100
        )
        self._default_routes[service_name] = route
    
    def resolve_route(self, service_name: str, request_labels: Optional[Dict[str, str]] = None) -> Optional[str]:
        with self._lock:
            routes = self._routes.get(service_name, [])
            
            # 匹配路由规则
            for route in routes:
                if not route.enabled:
                    continue
                if not route.match_labels:
                    continue
                if request_labels and all(
                    request_labels.get(k) == v for k, v in route.match_labels.items()
                ):
                    return route.destination_service
            
            # 返回默认路由
            if service_name in self._default_routes:
                return self._default_routes[service_name].destination_service
            
            return service_name
    
    def get_canary_weight(self, service_name: str) -> int:
        """获取金丝雀权重"""
        routes = self._routes.get(service_name, [])
        canary_routes = [r for r in routes if "canary" in r.match_labels]
        if canary_routes:
            return canary_routes[0].weight
        return 0


class TrafficManager:
    """流量管理器 - 核心编排"""
    
    def __init__(self, port: int = 8094):
        self.port = port
        self.registry = ServiceRegistry()
        self.circuit_breaker = CircuitBreakerManager()
        self.router = TrafficRouter(self.registry)
        self.advanced_controller = AdvancedTrafficController()  # 高级流量控制
        self._rate_limiters: Dict[str, RateLimiter] = {}
        self._metrics: List[TrafficMetrics] = []
        self._metrics_lock = threading.Lock()
        self._app = Flask(__name__)
        self._setup_routes()
        self._setup_advanced_routes()  # 高级流量控制API
        self._server = None
        self._thread = None
        self._running = False
    
    def _setup_routes(self):
        @self._app.route("/health", methods=["GET"])
        def health():
            return jsonify({"status": "healthy", "service": "service-mesh"})
        
        @self._app.route("/api/services", methods=["GET"])
        def list_services():
            return jsonify({
                "services": self.registry.get_all_services()
            })
        
        @self._app.route("/api/services/<service_name>/endpoints", methods=["GET"])
        def list_endpoints(service_name):
            labels = request.args.get("labels")
            label_dict = json.loads(labels) if labels else None
            endpoints = self.registry.get_endpoints(service_name, label_dict)
            return jsonify({
                "endpoints": [asdict(ep) for ep in endpoints]
            })
        
        @self._app.route("/api/register", methods=["POST"])
        def register_endpoint():
            data = request.json
            endpoint = ServiceEndpoint(
                endpoint_id=data.get("endpoint_id", f"ep_{int(time.time()*1000)}"),
                service_name=data["service_name"],
                agent_type=data.get("agent_type", "generic"),
                host=data.get("host", "localhost"),
                port=data.get("port", 8000),
                version=data.get("version", "v1"),
                weight=data.get("weight", 100),
                labels=data.get("labels", {}),
                metadata=data.get("metadata", {}),
                max_rps=data.get("max_rps", 1000)
            )
            self.registry.register_endpoint(endpoint)
            return jsonify({"success": True, "endpoint_id": endpoint.endpoint_id})
        
        @self._app.route("/api/deregister/<endpoint_id>", methods=["POST"])
        def deregister_endpoint(endpoint_id):
            success = self.registry.deregister_endpoint(endpoint_id)
            return jsonify({"success": success})
        
        @self._app.route("/api/routes", methods=["POST"])
        def add_route():
            data = request.json
            route = TrafficRoute(
                route_id=data.get("route_id", f"route_{int(time.time()*1000)}"),
                service_name=data["service_name"],
                match_labels=data.get("match_labels", {}),
                destination_service=data["destination_service"],
                weight=data.get("weight", 100),
                timeout_ms=data.get("timeout_ms", 5000),
                retries=data.get("retries", 3)
            )
            self.router.add_route(route)
            return jsonify({"success": True, "route_id": route.route_id})
        
        @self._app.route("/api/routes/<service_name>", methods=["GET"])
        def get_routes(service_name):
            routes = self.router._routes.get(service_name, [])
            return jsonify({"routes": [asdict(r) for r in routes]})
        
        @self._app.route("/api/circuit-breaker/<service_name>/state", methods=["GET"])
        def get_circuit_state(service_name):
            state = self.circuit_breaker.get_state(service_name)
            return jsonify({"service": service_name, "state": state.value})
        
        @self._app.route("/api/circuit-breaker/<service_name>/record/success", methods=["POST"])
        def record_success(service_name):
            self.circuit_breaker.record_success(service_name)
            return jsonify({"success": True})
        
        @self._app.route("/api/circuit-breaker/<service_name>/record/failure", methods=["POST"])
        def record_failure(service_name):
            self.circuit_breaker.record_failure(service_name)
            return jsonify({"success": True})
        
        @self._app.route("/api/rate-limit/<service_name>", methods=["POST"])
        def set_rate_limit(service_name):
            data = request.json
            rps = data.get("rps", 100)
            burst = data.get("burst", rps * 2)
            self._rate_limiters[service_name] = RateLimiter(rps, burst)
            return jsonify({"success": True, "rps": rps, "burst": burst})
        
        @self._app.route("/api/rate-limit/<service_name>/check", methods=["GET"])
        def check_rate_limit(service_name):
            limiter = self._rate_limiters.get(service_name)
            if not limiter:
                return jsonify({"allowed": True, "remaining": 99999})
            allowed = limiter.acquire()
            return jsonify({"allowed": allowed})
        
        @self._app.route("/api/dispatch", methods=["POST"])
        def dispatch_request():
            """流量调度核心接口"""
            data = request.json
            service_name = data["service"]
            request_labels = data.get("labels", {})
            
            # 1. 检查熔断器
            if not self.circuit_breaker.can_request(service_name):
                return jsonify({
                    "error": "circuit_open",
                    "message": f"Circuit breaker is open for {service_name}"
                }), 503
            
            # 2. 检查限流
            limiter = self._rate_limiters.get(service_name)
            if limiter and not limiter.acquire():
                return jsonify({
                    "error": "rate_limited",
                    "message": f"Rate limit exceeded for {service_name}"
                }), 429
            
            # 3. 解析路由
            destination = self.router.resolve_route(service_name, request_labels)
            
            # 4. 获取端点
            endpoints = self.registry.get_endpoints(destination, request_labels)
            
            if not endpoints:
                return jsonify({
                    "error": "no_available_endpoints",
                    "message": f"No healthy endpoints for {service_name}"
                }), 503
            
            # 5. 选择端点 (加权随机)
            selected = self._select_endpoint(endpoints)
            
            # 6. 记录指标
            self._record_dispatch(service_name, destination, selected)
            
            return jsonify({
                "service": service_name,
                "endpoint": {
                    "id": selected.endpoint_id,
                    "host": selected.host,
                    "port": selected.port,
                    "version": selected.version
                },
                "route": destination,
                "timestamp": time.time()
            })
        
        @self._app.route("/api/metrics", methods=["GET"])
        def get_metrics():
            with self._metrics_lock:
                recent = self._metrics[-100:] if len(self._metrics) > 100 else self._metrics
                return jsonify({
                    "metrics": [asdict(m) for m in recent],
                    "total": len(self._metrics)
                })
        
        @self._app.route("/api/stats", methods=["GET"])
        def get_stats():
            services = self.registry.get_all_services()
            stats = {}
            for svc in services:
                endpoints = self.registry.get_endpoints(svc)
                circuit = self.circuit_breaker.get_state(svc)
                stats[svc] = {
                    "endpoints": len(endpoints),
                    "circuit_state": circuit.value,
                    "healthy": sum(1 for e in endpoints if e.is_healthy)
                }
            return jsonify(stats)
        
        # ========== 服务网格可视化拓扑API ==========
        @self._app.route("/api/topology", methods=["GET"])
        def get_topology():
            """获取服务网格拓扑数据用于可视化"""
            services = self.registry.get_all_services()
            
            # 构建节点
            nodes = []
            edges = []
            
            for svc in services:
                endpoints = self.registry.get_endpoints(svc)
                circuit = self.circuit_breaker.get_state(svc)
                
                # 获取路由权重
                routes = self.router._routes.get(svc, [])
                traffic_policy = routes[0].weight if routes else 100
                
                # 节点数据
                node = {
                    "id": svc,
                    "label": svc,
                    "type": "service",
                    "endpoints": len(endpoints),
                    "healthy": sum(1 for e in endpoints if e.is_healthy),
                    "circuit_state": circuit.value,
                    "traffic_policy": traffic_policy
                }
                nodes.append(node)
                
                # 为每个endpoint创建边（服务 -> endpoint）
                for ep in endpoints:
                    edge = {
                        "from": svc,
                        "to": ep.endpoint_id,
                        "type": "contains"
                    }
                    edges.append(edge)
            
            # 添加路由边（服务间的流量关系）
            for svc_name, routes in self.router._routes.items():
                for route in routes:
                    if route.destination_service:
                        edge = {
                            "from": svc_name,
                            "to": route.destination_service,
                            "type": "route",
                            "weight": route.weight,
                            "labels": route.match_labels
                        }
                        edges.append(edge)
            
            return jsonify({
                "nodes": nodes,
                "edges": edges,
                "timestamp": time.time()
            })
        
        @self._app.route("/api/topology/graph", methods=["GET"])
        def get_topology_graph():
            """获取图形可视化的拓扑数据 (D3.js compatible)"""
            services = self.registry.get_all_services()
            
            graph = {
                "nodes": [],
                "links": []
            }
            
            # 服务节点
            for svc in services:
                endpoints = self.registry.get_endpoints(svc)
                circuit = self.circuit_breaker.get_state(svc)
                
                graph["nodes"].append({
                    "id": svc,
                    "name": svc,
                    "group": "service",
                    "endpoints": len(endpoints),
                    "healthy": sum(1 for e in endpoints if e.is_healthy),
                    "circuit": circuit.value
                })
                
                # endpoint 节点
                for ep in endpoints:
                    graph["nodes"].append({
                        "id": ep.endpoint_id,
                        "name": ep.endpoint_id,
                        "group": "endpoint",
                        "service": svc,
                        "healthy": ep.is_healthy,
                        "agent_type": ep.agent_type
                    })
                    graph["links"].append({
                        "source": svc,
                        "target": ep.endpoint_id,
                        "value": ep.weight
                    })
            
            return jsonify(graph)
    
    def _setup_advanced_routes(self):
        """高级流量控制API"""
        
        # === A/B测试API ===
        @self._app.route("/api/ab-test", methods=["POST"])
        def create_ab_test():
            data = request.json
            config = ABTestConfig(
                test_id=data.get("test_id", f"ab_{int(time.time()*1000)}"),
                service_name=data["service_name"],
                variant_a=data["variant_a"],
                variant_b=data["variant_b"],
                traffic_split=data.get("traffic_split", 50),
                cookie_name=data.get("cookie_name", "ab_variant"),
                enabled=data.get("enabled", True)
            )
            test_id = self.advanced_controller.create_ab_test(config)
            return jsonify({"success": True, "test_id": test_id})
        
        @self._app.route("/api/ab-test", methods=["GET"])
        def list_ab_tests():
            tests = self.advanced_controller.list_ab_tests()
            return jsonify({"tests": [asdict(t) for t in tests]})
        
        @self._app.route("/api/ab-test/<test_id>", methods=["GET"])
        def get_ab_test(test_id):
            test = self.advanced_controller.get_ab_test(test_id)
            if not test:
                return jsonify({"error": "Test not found"}), 404
            return jsonify({"test": asdict(test)})
        
        @self._app.route("/api/ab-test/<test_id>", methods=["PUT"])
        def update_ab_test(test_id):
            data = request.json
            success = self.advanced_controller.update_ab_test(
                test_id,
                traffic_split=data.get("traffic_split"),
                enabled=data.get("enabled")
            )
            return jsonify({"success": success})
        
        @self._app.route("/api/ab-test/<test_id>", methods=["DELETE"])
        def delete_ab_test(test_id):
            success = self.advanced_controller.delete_ab_test(test_id)
            return jsonify({"success": success})
        
        @self._app.route("/api/ab-test/resolve", methods=["POST"])
        def resolve_ab_variant():
            """解析A/B版本"""
            data = request.json
            variant = self.advanced_controller.resolve_ab_variant(
                data["service_name"],
                data.get("request_hash", str(time.time()))
            )
            return jsonify({"variant": variant})
        
        # === 金丝雀发布API ===
        @self._app.route("/api/canary", methods=["POST"])
        def create_canary_release():
            data = request.json
            release = CanaryRelease(
                release_id=data.get("release_id", f"canary_{int(time.time()*1000)}"),
                service_name=data["service_name"],
                baseline_version=data["baseline_version"],
                canary_version=data["canary_version"],
                baseline_weight=data.get("baseline_weight", 90),
                canary_weight=data.get("canary_weight", 10),
                progress_increment=data.get("progress_increment", 5),
                auto_rollback=data.get("auto_rollback", True),
                status=data.get("status", "preparing")
            )
            release_id = self.advanced_controller.create_canary_release(release)
            return jsonify({"success": True, "release_id": release_id})
        
        @self._app.route("/api/canary", methods=["GET"])
        def list_canary_releases():
            service_name = request.args.get("service_name")
            releases = self.advanced_controller.list_canary_releases(service_name)
            return jsonify({"releases": [asdict(r) for r in releases]})
        
        @self._app.route("/api/canary/<release_id>", methods=["GET"])
        def get_canary_release(release_id):
            release = self.advanced_controller.get_canary_release(release_id)
            if not release:
                return jsonify({"error": "Release not found"}), 404
            return jsonify({"release": asdict(release)})
        
        @self._app.route("/api/canary/<release_id>/promote", methods=["POST"])
        def promote_canary(release_id):
            data = request.json
            success = self.advanced_controller.promote_canary(
                release_id,
                increment=data.get("increment", True)
            )
            release = self.advanced_controller.get_canary_release(release_id)
            return jsonify({"success": success, "release": asdict(release) if release else None})
        
        @self._app.route("/api/canary/<release_id>/rollback", methods=["POST"])
        def rollback_canary(release_id):
            success = self.advanced_controller.rollback_canary(release_id)
            release = self.advanced_controller.get_canary_release(release_id)
            return jsonify({"success": success, "release": asdict(release) if release else None})
        
        # === 流量分割API ===
        @self._app.route("/api/traffic-split", methods=["POST"])
        def create_traffic_split():
            data = request.json
            split = TrafficSplit(
                split_id=data.get("split_id", f"split_{int(time.time()*1000)}"),
                service_name=data["service_name"],
                splits=data["splits"],
                match_conditions=data.get("match_conditions", []),
                sticky_session=data.get("sticky_session", False),
                enabled=data.get("enabled", True)
            )
            split_id = self.advanced_controller.create_traffic_split(split)
            return jsonify({"success": True, "split_id": split_id})
        
        @self._app.route("/api/traffic-split/<split_id>", methods=["GET"])
        def get_traffic_split(split_id):
            split = self.advanced_controller.get_traffic_split(split_id)
            if not split:
                return jsonify({"error": "Split not found"}), 404
            return jsonify({"split": asdict(split)})
        
        @self._app.route("/api/traffic-split/resolve", methods=["POST"])
        def resolve_traffic_split():
            """解析流量分割目标版本"""
            data = request.json
            version = self.advanced_controller.resolve_traffic_split(
                data["service_name"],
                data.get("request_labels")
            )
            return jsonify({"version": version})
        
        # === 流量策略API ===
        @self._app.route("/api/policy", methods=["POST"])
        def create_traffic_policy():
            data = request.json
            policy = TrafficPolicy(
                policy_id=data.get("policy_id", f"policy_{int(time.time()*1000)}"),
                service_name=data["service_name"],
                policy_type=data["policy_type"],
                config=data.get("config", {}),
                priority=data.get("priority", 0),
                enabled=data.get("enabled", True)
            )
            policy_id = self.advanced_controller.create_policy(policy)
            return jsonify({"success": True, "policy_id": policy_id})
        
        @self._app.route("/api/policy", methods=["GET"])
        def list_traffic_policies():
            service_name = request.args.get("service_name")
            policies = self.advanced_controller.list_policies(service_name)
            return jsonify({"policies": [asdict(p) for p in policies]})
        
        @self._app.route("/api/policy/<policy_id>", methods=["PUT"])
        def update_traffic_policy(policy_id):
            data = request.json
            success = self.advanced_controller.update_policy(
                policy_id,
                enabled=data.get("enabled"),
                config=data.get("config")
            )
            return jsonify({"success": success})
        
        @self._app.route("/api/policy/<policy_id>", methods=["DELETE"])
        def delete_traffic_policy(policy_id):
            success = self.advanced_controller.delete_policy(policy_id)
            return jsonify({"success": success})
        
        # === 流量统计API ===
        @self._app.route("/api/traffic-stats", methods=["GET"])
        def get_traffic_stats():
            service_name = request.args.get("service_name")
            minutes = int(request.args.get("minutes", 60))
            stats = self.advanced_controller.get_traffic_stats(service_name, minutes)
            return jsonify(stats)
    
    def _select_endpoint(self, endpoints: List[ServiceEndpoint]) -> ServiceEndpoint:
        """加权随机选择端点"""
        total_weight = sum(ep.weight for ep in endpoints)
        if total_weight == 0:
            return random.choice(endpoints)
        
        r = random.uniform(0, total_weight)
        cumulative = 0
        for ep in endpoints:
            cumulative += ep.weight
            if r <= cumulative:
                return ep
        return endpoints[-1]
    
    def _record_dispatch(self, source: str, dest: str, endpoint: ServiceEndpoint):
        with self._metrics_lock:
            metric = TrafficMetrics(
                request_id=f"req_{int(time.time()*1000000)}",
                source_service=source,
                destination_service=dest,
                endpoint_id=endpoint.endpoint_id,
                timestamp=time.time(),
                latency_ms=random.uniform(10, 100),  # 模拟延迟
                response_size=random.randint(100, 10000)
            )
            self._metrics.append(metric)
            if len(self._metrics) > 10000:
                self._metrics = self._metrics[-5000:]
    
    def start(self):
        if self._running:
            return
        self._running = True
        self._server = make_server("0.0.0.0", self.port, self._app, threaded=True)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"Service Mesh started on port {self.port}")
    
    def stop(self):
        if self._running:
            self._running = False
            if self._server:
                self._server.shutdown()
            logger.info("Service Mesh stopped")


def create_demo_services(mesh: TrafficManager):
    """创建演示服务"""
    # 注册多个Agent服务
    services = [
        {"id": "agent-001", "service": "agent-worker", "type": "worker", "host": "localhost", "port": 8001, "weight": 100},
        {"id": "agent-002", "service": "agent-worker", "type": "worker", "host": "localhost", "port": 8002, "weight": 100},
        {"id": "agent-003", "service": "agent-analyzer", "type": "analyzer", "host": "localhost", "port": 8003, "weight": 80},
        {"id": "agent-004", "service": "agent-analyzer", "type": "analyzer", "host": "localhost", "port": 8004, "weight": 80},
        {"id": "agent-005", "service": "agent-orchestrator", "type": "orchestrator", "host": "localhost", "port": 8005, "weight": 100},
    ]
    
    for svc in services:
        endpoint = ServiceEndpoint(
            endpoint_id=svc["id"],
            service_name=svc["service"],
            agent_type=svc["type"],
            host=svc["host"],
            port=svc["port"],
            labels={"env": "production"},
            weight=svc["weight"]
        )
        mesh.registry.register_endpoint(endpoint)
    
    # 添加路由规则
    # 金丝雀发布路由
    canary_route = TrafficRoute(
        route_id="canary-worker",
        service_name="agent-worker",
        match_labels={"version": "canary"},
        destination_service="agent-worker-v2",
        weight=10  # 10% 流量到金丝雀
    )
    mesh.router.add_route(canary_route)
    
    # 设置限流
    mesh._rate_limiters["agent-worker"] = RateLimiter(rps=200, burst=400)
    mesh._rate_limiters["agent-analyzer"] = RateLimiter(rps=100, burst=200)
    
    logger.info(f"Registered {len(services)} demo services")


def main():
    port = 8094
    mesh = TrafficManager(port=port)
    create_demo_services(mesh)
    mesh.start()
    
    print(f"Agent Service Mesh running on port {port}")
    print(f"API Endpoints:")
    print(f"  - Health: http://localhost:{port}/health")
    print(f"  - Services: http://localhost:{port}/api/services")
    print(f"  - Dispatch: http://localhost:{port}/api/dispatch")
    print(f"  - Stats: http://localhost:{port}/api/stats")
    
    # 保持运行
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        mesh.stop()


if __name__ == "__main__":
    main()