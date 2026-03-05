#!/usr/bin/env python3
"""
Agent Service Mesh API - 服务网格增强版 (v1.1)
提供智能路由、流量镜像、API网关、认证授权、请求转换等功能
端口: 18133
"""

import asyncio
import json
import time
import uuid
import hashlib
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from aiohttp import web
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("service-mesh")

# ==================== 数据结构 ====================

class TrafficPolicy(Enum):
    ROUND_ROBIN = "round_robin"
    LEAST_CONN = "least_conn"
    WEIGHTED = "weighted"
    PERFORMANCE = "performance"
    GEO_AWARE = "geo_aware"
    FAILOVER = "failover"

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class ServiceEndpoint:
    id: str
    name: str
    url: str
    weight: int = 100
    max_concurrent: int = 10
    current_requests: int = 0
    response_time: float = 0.0
    success_rate: float = 100.0
    circuit_state: str = "closed"
    failure_count: int = 0
    last_failure: float = 0
    region: str = "default"
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

@dataclass
class TrafficRoute:
    id: str
    name: str
    source: str
    destination: str
    policy: str
    weight: float = 100
    condition: Dict = field(default_factory=dict)
    enabled: bool = True

@dataclass
class TrafficMirror:
    id: str
    name: str
    source_service: str
    target_services: List[str]
    percentage: float = 10
    enabled: bool = True

@dataclass
class RateLimitRule:
    id: str
    service_id: str
    requests_per_second: int = 100
    burst: int = 200
    enabled: bool = True

# ==================== API网关新增数据结构 ====================

@dataclass
class ApiRoute:
    """API路由规则"""
    id: str
    path: str  # e.g., /api/v1/users
    method: str = "*"  # GET, POST, PUT, DELETE, *
    upstream: str = ""  # target endpoint id
    path_rewrite: str = ""  # path rewrite rule
    timeout: int = 30
    retry: int = 0
    auth_required: bool = False
    rate_limit: int = 0  # requests per second
    cache_ttl: int = 0  # cache TTL in seconds
    headers: Dict = field(default_factory=dict)
    enabled: bool = True

@dataclass
class ApiKey:
    """API密钥"""
    id: str
    key: str
    name: str
    endpoints: List[str]  # allowed endpoints
    rate_limit: int = 100
    expires_at: str = ""
    enabled: bool = True

@dataclass
class RequestTransform:
    """请求转换规则"""
    id: str
    route_id: str
    request_headers: Dict = field(default_factory=dict)
    request_body: str = ""
    response_headers: Dict = field(default_factory=dict)
    response_body: str = ""
    enabled: bool = True

@dataclass
class ServiceHealthCheck:
    """健康检查配置"""
    endpoint_id: str
    path: str = "/health"
    interval: int = 10  # seconds
    timeout: int = 5
    healthy_threshold: int = 3
    unhealthy_threshold: int = 3
    enabled: bool = True

# ==================== 令牌桶限流器 ====================

class TokenBucket:
    def __init__(self, rate: int, burst: int):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()
    
    def allow(self) -> bool:
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_update = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False

# ==================== 服务网格核心 ====================

class ServiceMesh:
    def __init__(self):
        self.endpoints: Dict[str, ServiceEndpoint] = {}
        self.routes: Dict[str, TrafficRoute] = {}
        self.mirrors: Dict[str, TrafficMirror] = {}
        self.rate_limits: Dict[str, RateLimitRule] = {}
        self.traffic_stats: Dict[str, Any] = {}
        self.service_topology: Dict[str, List[str]] = {}
        
        # API网关新增
        self.api_routes: Dict[str, ApiRoute] = {}
        self.api_keys: Dict[str, ApiKey] = {}
        self.request_transforms: Dict[str, RequestTransform] = {}
        self.health_checks: Dict[str, ServiceHealthCheck] = {}
        self.token_buckets: Dict[str, TokenBucket] = {}
        self.cache: Dict[str, Dict] = {}
        
        # 初始化默认端点
        self._init_default_endpoints()
        # 初始化默认API路由
        self._init_default_api_routes()
        
    def _init_default_endpoints(self):
        """初始化默认端点"""
        default_endpoints = [
            ServiceEndpoint("mesh-worker-1", "Mesh-Worker-1", "http://localhost:8001", 
                          weight=100, region="cn-east", capabilities=["execute", "compute"]),
            ServiceEndpoint("mesh-worker-2", "Mesh-Worker-2", "http://localhost:8002",
                          weight=80, region="cn-north", capabilities=["execute", "data"]),
            ServiceEndpoint("mesh-api-1", "Mesh-API-1", "http://localhost:8003",
                          weight=100, region="cn-east", capabilities=["api", "http"]),
        ]
        for ep in default_endpoints:
            self.endpoints[ep.id] = ep
            
    def _init_default_api_routes(self):
        """初始化默认API路由"""
        default_routes = [
            ApiRoute("gw-users", "/api/users", "GET", "mesh-api-1", timeout=30, auth_required=True),
            ApiRoute("gw-users-post", "/api/users", "POST", "mesh-api-1", timeout=30, auth_required=True),
            ApiRoute("gw-tasks", "/api/tasks", "*", "mesh-worker-1", timeout=60, auth_required=False),
            ApiRoute("gw-health", "/health", "*", "mesh-worker-1", timeout=10, auth_required=False),
        ]
        for route in default_routes:
            self.api_routes[route.id] = route
    
    # ===== 端点管理 =====
    def register_endpoint(self, endpoint: ServiceEndpoint) -> Dict:
        self.endpoints[endpoint.id] = endpoint
        logger.info(f"Registered endpoint: {endpoint.name}")
        return {"status": "registered", "endpoint_id": endpoint.id}
    
    def unregister_endpoint(self, endpoint_id: str) -> Dict:
        if endpoint_id in self.endpoints:
            del self.endpoints[endpoint_id]
            return {"status": "unregistered", "endpoint_id": endpoint_id}
        return {"status": "error", "message": "Endpoint not found"}
    
    def get_healthy_endpoints(self) -> List[ServiceEndpoint]:
        return [ep for ep in self.endpoints.values() 
                if ep.circuit_state == "closed" and ep.current_requests < ep.max_concurrent]
    
    # ===== 智能路由 =====
    def add_route(self, route: TrafficRoute) -> Dict:
        self.routes[route.id] = route
        return {"status": "route_added", "route_id": route.id}
    
    def remove_route(self, route_id: str) -> Dict:
        if route_id in self.routes:
            del self.routes[route_id]
            return {"status": "route_removed"}
        return {"status": "error", "message": "Route not found"}
    
    def resolve_route(self, source: str, condition: Dict = None) -> Optional[ServiceEndpoint]:
        for route in self.routes.values():
            if route.enabled and route.source == source:
                if condition:
                    if self._match_condition(condition, route.condition):
                        return self._select_endpoint_by_policy(route.policy)
                else:
                    return self._select_endpoint_by_policy(route.policy)
        return self._select_endpoint_by_policy("weighted")
    
    def _match_condition(self, condition: Dict, route_condition: Dict) -> bool:
        for key, value in route_condition.items():
            if condition.get(key) != value:
                return False
        return True
    
    def _select_endpoint_by_policy(self, policy: str) -> Optional[ServiceEndpoint]:
        healthy = self.get_healthy_endpoints()
        if not healthy:
            return None
            
        if policy == "round_robin":
            return healthy[len(self.traffic_stats) % len(healthy)]
        elif policy == "least_conn":
            return min(healthy, key=lambda x: x.current_requests)
        elif policy == "weighted":
            total_weight = sum(ep.weight for ep in healthy)
            r = (time.time() * 1000) % total_weight
            cumulative = 0
            for ep in healthy:
                cumulative += ep.weight
                if r <= cumulative:
                    return ep
            return healthy[0]
        elif policy == "performance":
            return min(healthy, key=lambda x: x.response_time)
        else:
            return healthy[0]
    
    # ===== 流量镜像 =====
    def add_mirror(self, mirror: TrafficMirror) -> Dict:
        self.mirrors[mirror.id] = mirror
        return {"status": "mirror_added", "mirror_id": mirror.id}
    
    def get_mirror_targets(self, source_service: str) -> List[ServiceEndpoint]:
        targets = []
        for mirror in self.mirrors.values():
            if mirror.enabled and mirror.source_service == source_service:
                for ep_id in mirror.target_services:
                    if ep_id in self.endpoints:
                        targets.append(self.endpoints[ep_id])
        return targets
    
    # ===== 限流 =====
    def add_rate_limit(self, rule: RateLimitRule) -> Dict:
        self.rate_limits[rule.id] = rule
        return {"status": "rate_limit_added", "rule_id": rule.id}
    
    def check_rate_limit(self, service_id: str) -> bool:
        if service_id not in self.rate_limits:
            return True
        rule = self.rate_limits[service_id]
        if not rule.enabled:
            return True
        return True
    
    # ===== 拓扑 =====
    def update_topology(self, source: str, target: str):
        if source not in self.service_topology:
            self.service_topology[source] = []
        if target not in self.service_topology[source]:
            self.service_topology[source].append(target)
    
    def get_topology(self) -> Dict:
        return self.service_topology
    
    # ===== 统计 =====
    def record_request(self, endpoint_id: str, success: bool, response_time: float):
        if endpoint_id in self.endpoints:
            ep = self.endpoints[endpoint_id]
            if success:
                ep.current_requests = max(0, ep.current_requests - 1)
                ep.response_time = (ep.response_time * 0.7 + response_time * 0.3)
                ep.success_rate = min(100, ep.success_rate + 0.1)
                ep.failure_count = 0
            else:
                ep.failure_count += 1
                ep.last_failure = time.time()
                ep.success_rate = max(0, ep.success_rate - 1)
                if ep.failure_count >= 5:
                    ep.circuit_state = "open"
    
    def get_stats(self) -> Dict:
        return {
            "total_endpoints": len(self.endpoints),
            "healthy_endpoints": len(self.get_healthy_endpoints()),
            "total_routes": len(self.routes),
            "active_mirrors": len([m for m in self.mirrors.values() if m.enabled]),
            "topology": self.service_topology,
            "endpoints": [asdict(ep) for ep in self.endpoints.values()]
        }
    
    # ==================== API网关功能 ====================
    
    def add_api_route(self, route: ApiRoute) -> Dict:
        """添加API路由"""
        self.api_routes[route.id] = route
        # 为该路由创建限流器
        if route.rate_limit > 0:
            self.token_buckets[route.id] = TokenBucket(route.rate_limit, route.rate_limit * 2)
        logger.info(f"Added API route: {route.path} -> {route.upstream}")
        return {"status": "api_route_added", "route_id": route.id}
    
    def remove_api_route(self, route_id: str) -> Dict:
        if route_id in self.api_routes:
            del self.api_routes[route_id]
            if route_id in self.token_buckets:
                del self.token_buckets[route_id]
            return {"status": "api_route_removed"}
        return {"status": "error", "message": "API route not found"}
    
    def resolve_api_route(self, path: str, method: str = "*") -> Optional[ApiRoute]:
        """根据路径和方法解析API路由"""
        # 精确匹配优先
        for route in self.api_routes.values():
            if route.enabled:
                if route.path == path and (route.method == "*" or route.method == method):
                    return route
        
        # 模式匹配
        for route in self.api_routes.values():
            if route.enabled:
                pattern = route.path.replace("{param}", "[^/]+")
                if re.match(f"^{pattern}$", path) and (route.method == "*" or route.method == method):
                    return route
        
        return None
    
    def generate_api_key(self, name: str, endpoints: List[str], rate_limit: int = 100) -> Dict:
        """生成API密钥"""
        key_id = str(uuid.uuid4())[:16]
        key_secret = hashlib.sha256(f"{key_id}{time.time()}".encode()).hexdigest()[:32]
        
        api_key = ApiKey(
            id=key_id,
            key=f"sk_{key_secret}",
            name=name,
            endpoints=endpoints,
            rate_limit=rate_limit,
            enabled=True
        )
        self.api_keys[key_id] = api_key
        # 为API密钥创建限流器
        self.token_buckets[f"key_{key_id}"] = TokenBucket(rate_limit, rate_limit * 2)
        
        return {
            "status": "api_key_created",
            "key_id": key_id,
            "api_key": api_key.key,
            "name": name
        }
    
    def validate_api_key(self, key: str) -> Optional[ApiKey]:
        """验证API密钥"""
        for api_key in self.api_keys.values():
            if api_key.enabled and api_key.key == key:
                # 检查限流
                bucket_key = f"key_{api_key.id}"
                if bucket_key in self.token_buckets:
                    if not self.token_buckets[bucket_key].allow():
                        return None
                return api_key
        return None
    
    def add_request_transform(self, transform: RequestTransform) -> Dict:
        self.request_transforms[transform.id] = transform
        return {"status": "transform_added", "transform_id": transform.id}
    
    def apply_request_transform(self, route_id: str, request_data: Dict) -> Dict:
        """应用请求转换"""
        for transform in self.request_transforms.values():
            if transform.enabled and transform.route_id == route_id:
                # 应用请求头转换
                if transform.request_headers:
                    request_data.setdefault("headers", {}).update(transform.request_headers)
                # 应用请求体转换
                if transform.request_body:
                    try:
                        body = json.loads(request_data.get("body", "{}"))
                        body.update(json.loads(transform.request_body))
                        request_data["body"] = json.dumps(body)
                    except:
                        pass
        return request_data
    
    def apply_response_transform(self, route_id: str, response_data: Dict) -> Dict:
        """应用响应转换"""
        for transform in self.request_transforms.values():
            if transform.enabled and transform.route_id == route_id:
                if transform.response_headers:
                    response_data.setdefault("headers", {}).update(transform.response_headers)
                if transform.response_body:
                    try:
                        body = json.loads(response_data.get("body", "{}"))
                        body.update(json.loads(transform.response_body))
                        response_data["body"] = json.dumps(body)
                    except:
                        pass
        return response_data
    
    def get_cache(self, key: str) -> Optional[Dict]:
        """获取缓存"""
        if key in self.cache:
            entry = self.cache[key]
            if time.time() < entry["expires_at"]:
                return entry["data"]
            else:
                del self.cache[key]
        return None
    
    def set_cache(self, key: str, data: Dict, ttl: int):
        """设置缓存"""
        self.cache[key] = {
            "data": data,
            "expires_at": time.time() + ttl
        }
    
    def get_gateway_stats(self) -> Dict:
        """获取网关统计"""
        return {
            "api_routes": len(self.api_routes),
            "active_api_keys": len([k for k in self.api_keys.values() if k.enabled]),
            "transforms": len(self.request_transforms),
            "cache_entries": len(self.cache),
            "routes": [asdict(r) for r in self.api_routes.values()]
        }

# ==================== HTTP API ====================

mesh = ServiceMesh()

async def health(request):
    return web.json_response({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service_mesh_version": "1.1",
        "gateway_enabled": True
    })

async def get_endpoints(request):
    return web.json_response({
        "endpoints": [asdict(ep) for ep in mesh.endpoints.values()],
        "count": len(mesh.endpoints)
    })

async def register_endpoint(request):
    data = await request.json()
    endpoint = ServiceEndpoint(
        id=data.get("id", str(uuid.uuid4())[:8]),
        name=data.get("name", "Unknown"),
        url=data.get("url", ""),
        weight=data.get("weight", 100),
        max_concurrent=data.get("max_concurrent", 10),
        region=data.get("region", "default"),
        capabilities=data.get("capabilities", [])
    )
    result = mesh.register_endpoint(endpoint)
    return web.json_response(result)

async def unregister_endpoint(request):
    endpoint_id = request.match_info.get("id")
    result = mesh.unregister_endpoint(endpoint_id)
    return web.json_response(result)

async def get_routes(request):
    return web.json_response({
        "routes": [asdict(r) for r in mesh.routes.values()]
    })

async def add_route(request):
    data = await request.json()
    route = TrafficRoute(
        id=data.get("id", str(uuid.uuid4())[:8]),
        name=data.get("name", "Route"),
        source=data.get("source", "*"),
        destination=data.get("destination", "*"),
        policy=data.get("policy", "weighted"),
        weight=data.get("weight", 100),
        condition=data.get("condition", {}),
        enabled=data.get("enabled", True)
    )
    result = mesh.add_route(route)
    return web.json_response(result)

async def remove_route(request):
    route_id = request.match_info.get("id")
    result = mesh.remove_route(route_id)
    return web.json_response(result)

async def resolve_destination(request):
    data = await request.json()
    source = data.get("source", "default")
    condition = data.get("condition", {})
    endpoint = mesh.resolve_route(source, condition)
    if endpoint:
        return web.json_response({
            "endpoint": asdict(endpoint),
            "policy_used": "weighted"
        })
    return web.json_response({
        "error": "No available endpoint",
        "status": 503
    }, status=503)

async def get_mirrors(request):
    return web.json_response({
        "mirrors": [asdict(m) for m in mesh.mirrors.values()]
    })

async def add_mirror(request):
    data = await request.json()
    mirror = TrafficMirror(
        id=data.get("id", str(uuid.uuid4())[:8]),
        name=data.get("name", "Mirror"),
        source_service=data.get("source_service", ""),
        target_services=data.get("target_services", []),
        percentage=data.get("percentage", 10),
        enabled=data.get("enabled", True)
    )
    result = mesh.add_mirror(mirror)
    return web.json_response(result)

async def get_topology(request):
    return web.json_response({
        "topology": mesh.get_topology(),
        "visualization": {
            "nodes": list(mesh.endpoints.keys()),
            "edges": [(s, t) for s, targets in mesh.service_topology.items() for t in targets]
        }
    })

async def get_stats(request):
    return web.json_response(mesh.get_stats())

async def record_request(request):
    data = await request.json()
    mesh.record_request(
        data.get("endpoint_id", ""),
        data.get("success", True),
        data.get("response_time", 0)
    )
    return web.json_response({"status": "recorded"})

async def get_rate_limits(request):
    return web.json_response({
        "rate_limits": [asdict(rl) for rl in mesh.rate_limits.values()]
    })

async def add_rate_limit(request):
    data = await request.json()
    rule = RateLimitRule(
        id=data.get("id", str(uuid.uuid4())[:8]),
        service_id=data.get("service_id", ""),
        requests_per_second=data.get("requests_per_second", 100),
        burst=data.get("burst", 200),
        enabled=data.get("enabled", True)
    )
    result = mesh.add_rate_limit(rule)
    return web.json_response(result)

# ==================== API网关新增接口 ====================

async def get_api_routes(request):
    """获取API路由列表"""
    return web.json_response({
        "routes": [asdict(r) for r in mesh.api_routes.values()],
        "count": len(mesh.api_routes)
    })

async def add_api_route(request):
    """添加API路由"""
    data = await request.json()
    route = ApiRoute(
        id=data.get("id", str(uuid.uuid4())[:8]),
        path=data.get("path", "/"),
        method=data.get("method", "*"),
        upstream=data.get("upstream", ""),
        path_rewrite=data.get("path_rewrite", ""),
        timeout=data.get("timeout", 30),
        retry=data.get("retry", 0),
        auth_required=data.get("auth_required", False),
        rate_limit=data.get("rate_limit", 0),
        cache_ttl=data.get("cache_ttl", 0),
        headers=data.get("headers", {}),
        enabled=data.get("enabled", True)
    )
    result = mesh.add_api_route(route)
    return web.json_response(result)

async def remove_api_route(request):
    """删除API路由"""
    route_id = request.match_info.get("id")
    result = mesh.remove_api_route(route_id)
    return web.json_response(result)

async def resolve_api(request):
    """API路由解析"""
    data = await request.json()
    path = data.get("path", "/")
    method = data.get("method", "GET")
    
    route = mesh.resolve_api_route(path, method)
    if route:
        # 检查是否需要认证
        if route.auth_required:
            auth_header = data.get("headers", {}).get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                return web.json_response({
                    "error": "Authentication required",
                    "status": 401
                }, status=401)
            
            # 验证API密钥
            api_key = mesh.validate_api_key(auth_header.replace("Bearer ", ""))
            if not api_key:
                return web.json_response({
                    "error": "Invalid or rate-limited API key",
                    "status": 403
                }, status=403)
        
        # 检查限流
        if route.id in mesh.token_buckets:
            if not mesh.token_buckets[route.id].allow():
                return web.json_response({
                    "error": "Rate limit exceeded",
                    "status": 429
                }, status=429)
        
        # 检查缓存
        cache_key = f"{path}:{method}"
        cached = mesh.get_cache(cache_key)
        if cached and route.cache_ttl > 0:
            return web.json_response({
                "cached": True,
                "data": cached
            })
        
        # 解析上游端点
        endpoint = mesh.endpoints.get(route.upstream)
        if endpoint:
            result = {
                "route": asdict(route),
                "upstream": asdict(endpoint),
                "path_rewrite": route.path_rewrite
            }
            
            # 应用请求转换
            transformed = mesh.apply_request_transform(route.id, data)
            result["transformed_request"] = transformed
            
            return web.json_response(result)
    
    return web.json_response({
        "error": "No matching route found",
        "status": 404
    }, status=404)

async def generate_api_key(request):
    """生成API密钥"""
    data = await request.json()
    result = mesh.generate_api_key(
        name=data.get("name", "API Key"),
        endpoints=data.get("endpoints", []),
        rate_limit=data.get("rate_limit", 100)
    )
    return web.json_response(result)

async def list_api_keys(request):
    """列出API密钥"""
    return web.json_response({
        "api_keys": [
            {
                "id": k.id,
                "name": k.name,
                "endpoints": k.endpoints,
                "rate_limit": k.rate_limit,
                "enabled": k.enabled
            }
            for k in mesh.api_keys.values()
        ],
        "count": len(mesh.api_keys)
    })

async def revoke_api_key(request):
    """撤销API密钥"""
    key_id = request.match_info.get("id")
    if key_id in mesh.api_keys:
        mesh.api_keys[key_id].enabled = False
        return web.json_response({"status": "api_key_revoked"})
    return web.json_response({"error": "API key not found"}, status=404)

async def add_transform(request):
    """添加请求转换"""
    data = await request.json()
    transform = RequestTransform(
        id=data.get("id", str(uuid.uuid4())[:8]),
        route_id=data.get("route_id", ""),
        request_headers=data.get("request_headers", {}),
        request_body=data.get("request_body", ""),
        response_headers=data.get("response_headers", {}),
        response_body=data.get("response_body", ""),
        enabled=data.get("enabled", True)
    )
    result = mesh.add_request_transform(transform)
    return web.json_response(result)

async def get_gateway_stats(request):
    """获取网关统计"""
    return web.json_response(mesh.get_gateway_stats())

async def proxy_request(request):
    """代理请求到上游"""
    data = await request.json()
    path = request.match_info.get("path", "/")
    method = request.method
    
    # 解析路由
    route = mesh.resolve_api_route(path, method)
    if not route:
        return web.json_response({"error": "Route not found"}, status=404)
    
    # 获取上游端点
    endpoint = mesh.endpoints.get(route.upstream)
    if not endpoint:
        return web.json_response({"error": "Upstream not available"}, status=503)
    
    # 构建目标URL
    target_path = route.path_rewrite or path
    target_url = f"{endpoint.url}{target_path}"
    
    # TODO: 实际执行代理请求
    return web.json_response({
        "proxied_to": target_url,
        "upstream": endpoint.name,
        "route_id": route.id
    })

# ==================== 路由配置 ====================

def create_app():
    app = web.Application()
    
    # 基础服务网格API
    app.router.add_get("/health", health)
    app.router.add_get("/endpoints", get_endpoints)
    app.router.add_post("/endpoints/register", register_endpoint)
    app.router.add_delete("/endpoints/{id}", unregister_endpoint)
    app.router.add_get("/routes", get_routes)
    app.router.add_post("/routes", add_route)
    app.router.add_delete("/routes/{id}", remove_route)
    app.router.add_post("/resolve", resolve_destination)
    app.router.add_get("/mirrors", get_mirrors)
    app.router.add_post("/mirrors", add_mirror)
    app.router.add_get("/topology", get_topology)
    app.router.add_get("/stats", get_stats)
    app.router.add_post("/stats/record", record_request)
    app.router.add_get("/rate-limits", get_rate_limits)
    app.router.add_post("/rate-limits", add_rate_limit)
    
    # API网关新增接口
    app.router.add_get("/gateway/routes", get_api_routes)
    app.router.add_post("/gateway/routes", add_api_route)
    app.router.add_delete("/gateway/routes/{id}", remove_api_route)
    app.router.add_post("/gateway/resolve", resolve_api)
    app.router.add_post("/gateway/keys", generate_api_key)
    app.router.add_get("/gateway/keys", list_api_keys)
    app.router.add_delete("/gateway/keys/{id}", revoke_api_key)
    app.router.add_post("/gateway/transforms", add_transform)
    app.router.add_get("/gateway/stats", get_gateway_stats)
    app.router.add_route("*", "/gateway/proxy/{path:.*}", proxy_request)
    
    return app

if __name__ == "__main__":
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=18133)