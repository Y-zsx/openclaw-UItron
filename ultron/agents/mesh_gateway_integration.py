#!/usr/bin/env python3
"""
Agent Service Mesh 与 API Gateway 集成
第56世: 服务网格与API网关深度集成

功能:
- 统一流量入口
- 智能路由与灰度发布
- 全局流量监控面板
- 动态权重配置
- 流量镜像与复制
"""

import asyncio
import json
import time
import uuid
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from aiohttp import web
import threading

# 导入服务网格和API网关
from agent_service_mesh import AgentServiceMesh, get_service_mesh, CircuitState, TrafficPolicy
from agent_api_gateway import AgentAPIGateway, TaskStatus, AgentEndpoint


class IntegrationMode(Enum):
    """集成模式"""
    GATEWAY_DIRECT = "gateway_direct"      # 网关直连
    MESH_PROXY = "mesh_proxy"              # 服务网格代理
    HYBRID = "hybrid"                      # 混合模式


class RoutingStrategy(Enum):
    """路由策略"""
    CANARY = "canary"                      # 灰度发布
    A_B_TEST = "a_b_test"                  # A/B测试
    FEATURE_FLAG = "feature_flag"          # 特性开关
    GEO_ROUTING = "geo_routing"            # 地理路由
    LOAD_BALANCED = "load_balanced"        # 负载均衡


@dataclass
class MeshGatewayConfig:
    """集成配置"""
    mode: str = IntegrationMode.MESH_PROXY.value
    mesh_policy: str = TrafficPolicy.LEAST_CONN.value
    enable_circuit_breaker: bool = True
    enable_rate_limiter: bool = True
    default_rate_limit: int = 100          # 每秒请求数
    circuit_failure_threshold: int = 5
    circuit_timeout: float = 30.0
    fallback_to_mesh: bool = True          # 网格不可用时回退
    enable_canary: bool = True             # 启用灰度发布
    canary_percentage: float = 10.0        # 灰度流量百分比


@dataclass
class CanaryRule:
    """灰度发布规则"""
    rule_id: str = ""
    service_name: str = ""
    version: str = ""
    percentage: float = 10.0
    conditions: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: str = ""
    
    def __post_init__(self):
        if not self.rule_id:
            self.rule_id = str(uuid.uuid4())[:8]
        if not self.created_at:
            self.created_at = time.strftime("%Y-%m-%d %H:%M:%S")


@dataclass
class TrafficRoute:
    """流量路由规则"""
    route_id: str = ""
    name: str = ""
    strategy: str = RoutingStrategy.CANARY.value
    match_conditions: Dict[str, Any] = field(default_factory=dict)
    targets: List[Dict[str, Any]] = field(default_factory=list)
    weight: float = 100.0
    enabled: bool = True
    
    def __post_init__(self):
        if not self.route_id:
            self.route_id = str(uuid.uuid4())[:8]


@dataclass
class IntegratedMetrics:
    """集成指标"""
    mesh_requests: int = 0                 # 服务网格转发的请求
    gateway_direct: int = 0                # 网关直连请求
    mesh_fallback: int = 0                 # 网格回退请求
    circuit_breaks_triggered: int = 0      # 熔断触发次数
    rate_limited_count: int = 0            # 限流次数
    
    canary_requests: int = 0               # 灰度流量
    a_b_test_requests: int = 0             # A/B测试流量
    mirrored_requests: int = 0             # 流量镜像数
    
    mesh_latency_sum: float = 0
    mesh_latency_count: int = 0
    gateway_latency_sum: float = 0
    gateway_latency_count: int = 0
    
    # 按服务统计
    service_metrics: Dict[str, Dict] = field(default_factory=dict)
    
    # 按版本统计
    version_metrics: Dict[str, Dict] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mesh_requests": self.mesh_requests,
            "gateway_direct": self.gateway_direct,
            "mesh_fallback": self.mesh_fallback,
            "circuit_breaks_triggered": self.circuit_breaks_triggered,
            "rate_limited_count": self.rate_limited_count,
            "canary_requests": self.canary_requests,
            "a_b_test_requests": self.a_b_test_requests,
            "mirrored_requests": self.mirrored_requests,
            "avg_mesh_latency": round(self.mesh_latency_sum / max(1, self.mesh_latency_count), 2),
            "avg_gateway_latency": round(self.gateway_latency_sum / max(1, self.gateway_latency_count), 2),
            "service_metrics": self.service_metrics,
            "version_metrics": self.version_metrics
        }


class MeshGatewayIntegration:
    """
    服务网格与API网关集成核心类
    
    功能:
    1. 统一流量入口
    2. 智能路由与灰度发布
    3. 全局流量监控
    4. 动态权重配置
    5. 流量镜像
    """
    
    def __init__(self, mesh: AgentServiceMesh = None, gateway: AgentAPIGateway = None):
        # 服务网格
        self.mesh = mesh or get_service_mesh()
        
        # API网关
        self.gateway = gateway
        
        # 配置
        self.config = MeshGatewayConfig()
        
        # 灰度规则
        self.canary_rules: Dict[str, List[CanaryRule]] = {}
        
        # 流量路由规则
        self.traffic_routes: Dict[str, TrafficRoute] = {}
        
        # 版本注册表
        self.version_registry: Dict[str, Dict[str, Any]] = {}
        
        # 流量镜像配置
        self.mirroring_config: Dict[str, Any] = {}
        
        # 集成指标
        self.metrics = IntegratedMetrics()
        
        # 同步锁
        self._lock = threading.RLock()
        
        # 状态文件
        self.state_file = "/root/.openclaw/workspace/ultron/agents/mesh_gateway_state.json"
        self._load_state()
        
        # 注册内部Agent到服务网格
        self._register_internal_agents()
    
    def _load_state(self):
        """加载状态"""
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                if 'config' in state:
                    self.config.mode = state['config'].get('mode', self.config.mode)
                    self.config.mesh_policy = state['config'].get('mesh_policy', self.config.mesh_policy)
                    self.config.enable_circuit_breaker = state['config'].get('enable_circuit_breaker', True)
                    self.config.enable_rate_limiter = state['config'].get('enable_rate_limiter', True)
                    self.config.enable_canary = state['config'].get('enable_canary', True)
                    self.config.canary_percentage = state['config'].get('canary_percentage', 10.0)
        except:
            pass
    
    def _save_state(self):
        """保存状态"""
        with self._lock:
            state = {
                "config": {
                    "mode": self.config.mode,
                    "mesh_policy": self.config.mesh_policy,
                    "enable_circuit_breaker": self.config.enable_circuit_breaker,
                    "enable_rate_limiter": self.config.enable_rate_limiter,
                    "default_rate_limit": self.config.default_rate_limit,
                    "circuit_failure_threshold": self.config.circuit_failure_threshold,
                    "circuit_timeout": self.config.circuit_timeout,
                    "enable_canary": self.config.enable_canary,
                    "canary_percentage": self.config.canary_percentage
                },
                "metrics": self.metrics.to_dict()
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
    
    def _register_internal_agents(self):
        """注册内部Agent到服务网格"""
        # 注册常用的内部服务
        internal_services = [
            ("executor", "executor-001", "http://localhost:8001", 100, "v1.0"),
            ("executor", "executor-002", "http://localhost:8002", 150, "v1.0"),
            ("analyzer", "analyzer-001", "http://localhost:9001", 100, "v1.0"),
            ("communicator", "comm-001", "http://localhost:9002", 80, "v1.0"),
            ("monitor", "monitor-001", "http://localhost:9003", 100, "v1.0"),
        ]
        
        for service_name, agent_id, address, weight, version in internal_services:
            self.mesh.register_service(service_name, agent_id, address, weight)
            self._register_version(service_name, agent_id, version)
        
        # 配置熔断器和限流器
        if self.config.enable_circuit_breaker:
            for service_name, _, _, _, _ in internal_services:
                self.mesh.set_circuit_breaker(
                    service_name,
                    failure_threshold=self.config.circuit_failure_threshold,
                    timeout=self.config.circuit_timeout
                )
        
        if self.config.enable_rate_limiter:
            for service_name, _, _, _, _ in internal_services:
                self.mesh.set_rate_limit(service_name, self.config.default_rate_limit)
    
    def _register_version(self, service_name: str, agent_id: str, version: str):
        """注册服务版本"""
        if service_name not in self.version_registry:
            self.version_registry[service_name] = {}
        
        self.version_registry[service_name][version] = {
            "agent_id": agent_id,
            "registered_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "traffic_weight": 100
        }
    
    def set_mode(self, mode: str):
        """设置集成模式"""
        self.config.mode = mode
        self._save_state()
    
    def set_mesh_policy(self, policy: str):
        """设置服务网格负载均衡策略"""
        try:
            traffic_policy = TrafficPolicy(policy)
            self.mesh.set_policy(traffic_policy)
            self.config.mesh_policy = policy
            self._save_state()
        except ValueError:
            raise Exception(f"Invalid policy: {policy}")
    
    def register_service_to_mesh(self, service_name: str, agent_id: str, 
                                  address: str, weight: int = 100, version: str = "v1.0"):
        """注册服务到网格"""
        self.mesh.register_service(service_name, agent_id, address, weight)
        self._register_version(service_name, agent_id, version)
        
        # 设置熔断和限流
        if self.config.enable_circuit_breaker:
            self.mesh.set_circuit_breaker(
                service_name, 
                failure_threshold=self.config.circuit_failure_threshold,
                timeout=self.config.circuit_timeout
            )
        
        if self.config.enable_rate_limiter:
            self.mesh.set_rate_limit(service_name, self.config.default_rate_limit)
    
    def add_canary_rule(self, rule: CanaryRule) -> str:
        """添加灰度发布规则"""
        with self._lock:
            if rule.service_name not in self.canary_rules:
                self.canary_rules[rule.service_name] = []
            self.canary_rules[rule.service_name].append(rule)
            return rule.rule_id
    
    def remove_canary_rule(self, service_name: str, rule_id: str) -> bool:
        """移除灰度规则"""
        with self._lock:
            if service_name in self.canary_rules:
                self.canary_rules[service_name] = [
                    r for r in self.canary_rules[service_name] 
                    if r.rule_id != rule_id
                ]
                return True
            return False
    
    def set_canary_percentage(self, service_name: str, percentage: float):
        """设置灰度流量百分比"""
        self.config.canary_percentage = max(0, min(100, percentage))
        
        # 更新版本权重
        if service_name in self.version_registry:
            versions = self.version_registry[service_name]
            stable_weight = 100 - self.config.canary_percentage
            for version, info in versions.items():
                if version == "v1.0" or version == "stable":
                    info["traffic_weight"] = stable_weight
                else:
                    info["traffic_weight"] = self.config.canary_percentage
    
    def _should_route_to_canary(self, service_name: str, request_context: Dict = None) -> bool:
        """判断是否应该路由到灰度版本"""
        if not self.config.enable_canary:
            return False
        
        # 如果有请求上下文，按条件判断
        if request_context:
            canary_rules = self.canary_rules.get(service_name, [])
            for rule in canary_rules:
                if not rule.enabled:
                    continue
                
                # 检查匹配条件
                matches = True
                for key, value in rule.conditions.items():
                    if request_context.get(key) != value:
                        matches = False
                        break
                
                if matches:
                    # 使用随机百分比
                    import random
                    return random.random() * 100 < rule.percentage
        
        # 默认按配置的百分比
        import random
        return random.random() * 100 < self.config.canary_percentage
    
    def add_traffic_route(self, route: TrafficRoute) -> str:
        """添加流量路由规则"""
        with self._lock:
            self.traffic_routes[route.route_id] = route
        return route.route_id
    
    def remove_traffic_route(self, route_id: str) -> bool:
        """移除流量路由规则"""
        with self._lock:
            if route_id in self.traffic_routes:
                del self.traffic_routes[route_id]
                return True
        return False
    
    def update_route_weights(self, route_id: str, weights: Dict[str, float]):
        """更新路由权重"""
        with self._lock:
            if route_id in self.traffic_routes:
                route = self.traffic_routes[route_id]
                for target in route.targets:
                    target_id = target.get("id")
                    if target_id in weights:
                        target["weight"] = weights[target_id]
    
    def configure_traffic_mirroring(self, service_name: str, mirror_to: str, percentage: float = 100):
        """配置流量镜像"""
        self.mirroring_config[service_name] = {
            "mirror_to": mirror_to,
            "percentage": percentage,
            "enabled": True
        }
    
    def select_endpoint_via_mesh(self, service_name: str, request_context: Dict = None) -> Optional[Any]:
        """通过服务网格选择端点（支持灰度）"""
        start_time = time.time()
        
        # 灰度路由判断
        use_canary = self._should_route_to_canary(service_name, request_context)
        
        if use_canary:
            self.metrics.canary_requests += 1
            # 选择灰度版本
            versions = self.version_registry.get(service_name, {})
            canary_versions = [v for v in versions.keys() if v != "v1.0" and v != "stable"]
            if canary_versions:
                # 使用灰度版本
                canary_version = canary_versions[0]
                agent_id = versions[canary_version]["agent_id"]
                endpoint = self.mesh.get_endpoint_by_id(service_name, agent_id)
                if endpoint:
                    self._record_version_metric(service_name, canary_version, start_time)
                    return endpoint
        
        # 通过网格选择端点
        endpoint = self.mesh.select_endpoint(service_name)
        
        latency_ms = (time.time() - start_time) * 1000
        
        if endpoint:
            self.metrics.mesh_requests += 1
            self.metrics.mesh_latency_sum += latency_ms
            self.metrics.mesh_latency_count += 1
            self._record_service_metric(service_name, latency_ms, True)
        else:
            # 检查熔断状态
            circuit_states = self.mesh.get_circuit_states()
            if service_name in circuit_states and circuit_states[service_name] == CircuitState.OPEN.value:
                self.metrics.circuit_breaks_triggered += 1
            
            # 检查限流
            self.metrics.rate_limited_count += 1
            self._record_service_metric(service_name, latency_ms, False)
        
        self._save_state()
        return endpoint
    
    def _record_service_metric(self, service_name: str, latency: float, success: bool):
        """记录服务指标"""
        if service_name not in self.metrics.service_metrics:
            self.metrics.service_metrics[service_name] = {
                "requests": 0,
                "failures": 0,
                "latency_sum": 0,
                "last_request": ""
            }
        
        m = self.metrics.service_metrics[service_name]
        m["requests"] += 1
        if not success:
            m["failures"] += 1
        m["latency_sum"] += latency
        m["last_request"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    def _record_version_metric(self, service_name: str, version: str, start_time: float):
        """记录版本指标"""
        key = f"{service_name}:{version}"
        if key not in self.metrics.version_metrics:
            self.metrics.version_metrics[key] = {
                "requests": 0,
                "first_request": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        self.metrics.version_metrics[key]["requests"] += 1
    
    async def forward_via_mesh(self, service_name: str, method: str, 
                               path: str, payload: Dict = None,
                               request_context: Dict = None) -> Dict[str, Any]:
        """通过服务网格转发请求（支持灰度）"""
        endpoint = self.select_endpoint_via_mesh(service_name, request_context)
        
        if not endpoint:
            # 熔断或限流
            return {
                "error": "Service unavailable",
                "reason": "circuit_open" if self.metrics.circuit_breaks_triggered > 0 else "rate_limited",
                "service": service_name
            }
        
        # 检查是否需要镜像流量
        if service_name in self.mirroring_config:
            mirror_config = self.mirroring_config[service_name]
            if mirror_config["enabled"]:
                import random
                if random.random() * 100 < mirror_config["percentage"]:
                    self.metrics.mirrored_requests += 1
                    # 异步镜像请求（不等待结果）
                    asyncio.create_task(self._mirror_request(service_name, mirror_config["mirror_to"], method, path, payload))
        
        # 构建URL
        url = f"{endpoint.address}{path}"
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                start = time.time()
                
                if method.upper() == "GET":
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        result = await resp.json()
                else:
                    async with session.post(url, json=payload or {}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        result = await resp.json()
                
                latency = (time.time() - start) * 1000
                
                # 记录成功
                self.mesh.record_response(service_name, endpoint.agent_id, True, latency)
                
                return {
                    "result": result,
                    "endpoint": endpoint.agent_id,
                    "latency_ms": round(latency, 2),
                    "version": endpoint.agent_id.split("-")[-1] if endpoint.agent_id else "unknown"
                }
                
        except Exception as e:
            # 记录失败
            self.mesh.record_response(service_name, endpoint.agent_id, False, 100)
            
            # 如果配置了回退
            if self.config.fallback_to_mesh:
                self.metrics.mesh_fallback += 1
                return await self._fallback_request(endpoint, method, path, payload)
            
            return {"error": str(e), "endpoint": endpoint.agent_id}
    
    async def _mirror_request(self, source_service: str, target_service: str, 
                              method: str, path: str, payload: Dict):
        """镜像请求到目标服务"""
        try:
            # 获取目标服务的端点
            target_endpoint = self.mesh.select_endpoint(target_service)
            if not target_endpoint:
                return
            
            url = f"{target_endpoint.address}{path}"
            
            import aiohttp
            async with aiohttp.ClientSession() as session:
                if method.upper() == "GET":
                    await session.get(url, timeout=aiohttp.ClientTimeout(total=5))
                else:
                    await session.post(url, json=payload or {}, timeout=aiohttp.ClientTimeout(total=5))
        except:
            pass  # 镜像失败不影响主请求
    
    async def _fallback_request(self, endpoint: Any, method: str, 
                                path: str, payload: Dict) -> Dict[str, Any]:
        """回退请求 - 直接连接"""
        self.metrics.gateway_direct += 1
        
        url = f"{endpoint.address}{path}"
        
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                start = time.time()
                
                if method.upper() == "GET":
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        result = await resp.json()
                else:
                    async with session.post(url, json=payload or {}, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                        result = await resp.json()
                
                latency = (time.time() - start) * 1000
                self.metrics.gateway_latency_sum += latency
                self.metrics.gateway_latency_count += 1
                
                return {
                    "result": result,
                    "endpoint": endpoint.agent_id,
                    "latency_ms": round(latency, 2),
                    "mode": "fallback"
                }
                
        except Exception as e:
            return {"error": str(e), "fallback_failed": True}
    
    def get_integrated_status(self) -> Dict[str, Any]:
        """获取集成状态"""
        mesh_status = self.mesh.get_service_status()
        circuit_states = self.mesh.get_circuit_states()
        
        return {
            "mode": self.config.mode,
            "mesh_policy": self.config.mesh_policy,
            "circuit_breaker_enabled": self.config.enable_circuit_breaker,
            "rate_limiter_enabled": self.config.enable_rate_limiter,
            "canary_enabled": self.config.enable_canary,
            "canary_percentage": self.config.canary_percentage,
            "mesh_services": mesh_status,
            "circuit_states": circuit_states,
            "version_registry": self.version_registry,
            "traffic_routes_count": len(self.traffic_routes),
            "mirroring_config": self.mirroring_config,
            "integration_metrics": self.metrics.to_dict()
        }
    
    def get_combined_metrics(self) -> Dict[str, Any]:
        """获取组合指标"""
        mesh_metrics = self.mesh.get_metrics()
        
        return {
            "mesh": mesh_metrics,
            "integration": self.metrics.to_dict(),
            "combined": {
                "total_requests": mesh_metrics.get("total_requests", 0) + self.metrics.mesh_requests,
                "success_rate": mesh_metrics.get("success_rate", 0),
                "avg_latency_ms": mesh_metrics.get("avg_latency_ms", 0),
                "canary_traffic": self.metrics.canary_requests,
                "mirrored_traffic": self.metrics.mirrored_requests
            }
        }
    
    def get_traffic_dashboard_data(self) -> Dict[str, Any]:
        """获取流量监控面板数据"""
        # 按服务聚合指标
        service_summary = {}
        for service_name, metrics in self.metrics.service_metrics.items():
            service_summary[service_name] = {
                "total_requests": metrics["requests"],
                "failures": metrics["failures"],
                "success_rate": round((metrics["requests"] - metrics["failures"]) / max(1, metrics["requests"]) * 100, 2),
                "avg_latency": round(metrics["latency_sum"] / max(1, metrics["requests"]), 2),
                "last_request": metrics["last_request"]
            }
        
        return {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "summary": {
                "total_mesh_requests": self.metrics.mesh_requests,
                "total_gateway_requests": self.metrics.gateway_direct,
                "canary_requests": self.metrics.canary_requests,
                "a_b_test_requests": self.metrics.a_b_test_requests,
                "mirrored_requests": self.metrics.mirrored_requests,
                "circuit_breaks": self.metrics.circuit_breaks_triggered,
                "rate_limited": self.metrics.rate_limited_count
            },
            "services": service_summary,
            "versions": self.metrics.version_metrics,
            "circuit_states": self.mesh.get_circuit_states(),
            "versions_registered": self.version_registry
        }
    
    def generate_traffic_dashboard_html(self) -> str:
        """生成流量监控面板HTML"""
        data = self.get_traffic_dashboard_data()
        
        html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>流量监控面板 - 服务网格与API网关</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }}
        h1 {{ color: #00d4ff; }}
        .card {{ background: #16213e; padding: 20px; margin: 10px 0; border-radius: 10px; }}
        .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; }}
        .metric {{ background: #0f3460; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 28px; font-weight: bold; color: #00d4ff; }}
        .metric-label {{ color: #888; font-size: 14px; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #0f3460; }}
        th {{ background: #0f3460; color: #00d4ff; }}
        .status-ok {{ color: #00ff88; }}
        .status-warn {{ color: #ffaa00; }}
        .status-error {{ color: #ff4444; }}
        .version-tag {{ background: #00d4ff; padding: 2px 8px; border-radius: 4px; font-size: 12px; }}
    </style>
</head>
<body>
    <h1>🚀 服务网格与API网关 - 流量监控面板</h1>
    <p>更新时间: {data["timestamp"]}</p>
    
    <div class="card">
        <h2>📊 流量概览</h2>
        <div class="metrics">
            <div class="metric">
                <div class="metric-value">{data["summary"]["total_mesh_requests"]}</div>
                <div class="metric-label">网格请求</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data["summary"]["canary_requests"]}</div>
                <div class="metric-label">灰度流量</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data["summary"]["mirrored_requests"]}</div>
                <div class="metric-label">镜像流量</div>
            </div>
            <div class="metric">
                <div class="metric-value">{data["summary"]["circuit_breaks"]}</div>
                <div class="metric-label">熔断触发</div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <h2>🔍 服务状态</h2>
        <table>
            <tr>
                <th>服务名</th>
                <th>总请求</th>
                <th>成功</th>
                <th>成功率</th>
                <th>平均延迟</th>
                <th>最后请求</th>
            </tr>'''
        
        for service, info in data["services"].items():
            status_class = "status-ok" if info["success_rate"] > 95 else "status-warn" if info["success_rate"] > 80 else "status-error"
            html += f'''
            <tr>
                <td><span class="version-tag">{service}</span></td>
                <td>{info["total_requests"]}</td>
                <td>{info["total_requests"] - info["failures"]}</td>
                <td class="{status_class}">{info["success_rate"]}%</td>
                <td>{info["avg_latency"]}ms</td>
                <td>{info["last_request"]}</td>
            </tr>'''
        
        html += '''
        </table>
    </div>
    
    <div class="card">
        <h2>🔄 熔断状态</h2>
        <table>
            <tr>
                <th>服务</th>
                <th>状态</th>
            </tr>'''
        
        for service, state in data["circuit_states"].items():
            status_class = "status-ok" if state == "closed" else "status-warn" if state == "half-open" else "status-error"
            html += f'''
            <tr>
                <td>{service}</td>
                <td class="{status_class}">{state}</td>
            </tr>'''
        
        html += '''
        </table>
    </div>
    
    <div class="card">
        <h2>📦 版本注册</h2>
        <table>
            <tr>
                <th>服务</th>
                <th>版本</th>
                <th>Agent ID</th>
                <th>流量权重</th>
            </tr>'''
        
        for service, versions in data["versions_registered"].items():
            for version, info in versions.items():
                html += f'''
            <tr>
                <td>{service}</td>
                <td><span class="version-tag">{version}</span></td>
                <td>{info["agent_id"]}</td>
                <td>{info["traffic_weight"]}%</td>
            </tr>'''
        
        html += '''
        </table>
    </div>
    
    <script>
        // 自动刷新
        setInterval(() => location.reload(), 30000);
    </script>
</body>
</html>'''
        
        return html


# 全局集成实例
_integration: Optional[MeshGatewayIntegration] = None
_lock = threading.Lock()


def get_integration() -> MeshGatewayIntegration:
    """获取全局集成实例"""
    global _integration
    if _integration is None:
        with _lock:
            if _integration is None:
                _integration = MeshGatewayIntegration()
    return _integration


# ========== 集成中间件 ==========

class MeshMiddleware:
    """服务网格中间件 - 用于aiohttp"""
    
    def __init__(self, integration: MeshGatewayIntegration):
        self.integration = integration
    
    async def middleware(self, app, handler):
        """中间件处理"""
        async def middleware_handler(request):
            # 检查是否需要经过服务网格
            service = request.headers.get('X-Mesh-Service')
            
            if service:
                # 从请求中提取信息
                method = request.method
                path = request.path
                
                # 构建请求上下文
                request_context = {
                    "user_agent": request.headers.get('User-Agent', ''),
                    "remote": request.remote,
                }
                
                # 尝试通过网格转发
                result = await self.integration.forward_via_mesh(
                    service, method, path, 
                    await request.json() if method in ["POST", "PUT"] else None,
                    request_context
                )
                
                if "error" in result:
                    return web.json_response(result, status=503)
                
                return web.json_response(result.get("result", {}))
            
            # 普通请求直接通过
            return await handler(request)
        
        return middleware_handler


# ========== 网关增强 ==========

def enhance_gateway_with_mesh(gateway: AgentAPIGateway, 
                              integration: MeshGatewayIntegration):
    """为API网关增强服务网格能力"""
    
    # 添加网格状态端点
    async def mesh_status(request):
        return web.json_response(integration.get_integrated_status())
    
    async def mesh_metrics(request):
        return web.json_response(integration.get_combined_metrics())
    
    async def traffic_dashboard(request):
        return web.Response(
            text=integration.generate_traffic_dashboard_html(),
            content_type='text/html'
        )
    
    async def set_mesh_mode(request):
        try:
            data = await request.json()
            mode = data.get('mode')
            integration.set_mode(mode)
            return web.json_response({"status": "ok", "mode": mode})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)
    
    async def set_mesh_policy(request):
        try:
            data = await request.json()
            policy = data.get('policy')
            integration.set_mesh_policy(policy)
            return web.json_response({"status": "ok", "policy": policy})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)
    
    async def set_canary(request):
        try:
            data = await request.json()
            service = data.get('service')
            percentage = data.get('percentage', 10)
            integration.set_canary_percentage(service, percentage)
            return web.json_response({
                "status": "ok", 
                "service": service,
                "percentage": percentage
            })
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)
    
    async def add_route(request):
        try:
            data = await request.json()
            route = TrafficRoute(
                name=data.get('name', ''),
                strategy=data.get('strategy', RoutingStrategy.CANARY.value),
                match_conditions=data.get('match_conditions', {}),
                targets=data.get('targets', [])
            )
            route_id = integration.add_traffic_route(route)
            return web.json_response({"status": "ok", "route_id": route_id})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)
    
    # 添加路由
    gateway.app.router.add_get('/api/mesh/status', mesh_status)
    gateway.app.router.add_get('/api/mesh/metrics', mesh_metrics)
    gateway.app.router.add_get('/api/mesh/dashboard', traffic_dashboard)
    gateway.app.router.add_post('/api/mesh/mode', set_mesh_mode)
    gateway.app.router.add_post('/api/mesh/policy', set_mesh_policy)
    gateway.app.router.add_post('/api/mesh/canary', set_canary)
    gateway.app.router.add_post('/api/mesh/route', add_route)
    
    return gateway


# ========== 演示测试 ==========

async def demo():
    """演示集成功能"""
    print("\n" + "="*60)
    print("服务网格与API网关深度集成演示")
    print("="*60)
    
    integration = get_integration()
    
    # 1. 查看集成状态
    print("\n[1] 集成状态:")
    status = integration.get_integrated_status()
    print(f"    模式: {status['mode']}")
    print(f"    负载均衡策略: {status['mesh_policy']}")
    print(f"    熔断器启用: {status['circuit_breaker_enabled']}")
    print(f"    限流器启用: {status['rate_limiter_enabled']}")
    print(f"    灰度发布启用: {status['canary_enabled']}")
    print(f"    灰度百分比: {status['canary_percentage']}%")
    print(f"    网格服务: {list(status['mesh_services'].keys())}")
    print(f"    版本注册: {list(status['version_registry'].keys())}")
    
    # 2. 测试端点选择（带灰度）
    print("\n[2] 测试服务网格端点选择（灰度路由）:")
    for i in range(10):
        ep = integration.select_endpoint_via_mesh("executor", {"user_type": "premium"})
        version = ep.agent_id.split("-")[-1] if ep else "None"
        print(f"    请求{i+1}: {ep.agent_id if ep else 'None'} (版本: {version})")
    
    # 3. 测试灰度百分比调整
    print("\n[3] 调整灰度百分比到30%:")
    integration.set_canary_percentage("executor", 30)
    canary_count = 0
    for i in range(20):
        ep = integration.select_endpoint_via_mesh("executor")
        if ep:
            version = ep.agent_id.split("-")[-1]
            if version != "001":
                canary_count += 1
    print(f"    灰度版本请求占比: {canary_count}/20 = {canary_count*5}%")
    
    # 4. 添加流量路由规则
    print("\n[4] 添加流量路由规则:")
    route = TrafficRoute(
        name="executor-canary",
        strategy=RoutingStrategy.CANARY.value,
        match_conditions={"user_type": "premium"},
        targets=[
            {"id": "executor-001", "weight": 70},
            {"id": "executor-002", "weight": 30}
        ]
    )
    route_id = integration.add_traffic_route(route)
    print(f"    路由规则ID: {route_id}")
    print(f"    路由规则: {route.name}, 策略: {route.strategy}")
    
    # 5. 配置流量镜像
    print("\n[5] 配置流量镜像:")
    integration.configure_traffic_mirroring("executor", "executor-mirror", 50)
    print(f"    镜像配置: executor -> executor-mirror (50%)")
    
    # 6. 测试组合指标
    print("\n[6] 组合指标:")
    metrics = integration.get_combined_metrics()
    print(f"    网格请求: {metrics['integration']['mesh_requests']}")
    print(f"    灰度请求: {metrics['integration']['canary_requests']}")
    print(f"    镜像请求: {metrics['integration']['mirrored_requests']}")
    print(f"    总请求: {metrics['combined']['total_requests']}")
    
    # 7. 获取流量监控面板数据
    print("\n[7] 流量监控面板:")
    dashboard = integration.get_traffic_dashboard_data()
    print(f"    网格请求: {dashboard['summary']['total_mesh_requests']}")
    print(f"    灰度流量: {dashboard['summary']['canary_requests']}")
    print(f"    镜像流量: {dashboard['summary']['mirrored_requests']}")
    print(f"    熔断触发: {dashboard['summary']['circuit_breaks']}")
    
    # 8. 生成HTML面板
    print("\n[8] 生成流量监控面板HTML:")
    html_path = "/root/.openclaw/workspace/ultron/agents/mesh_traffic_dashboard.html"
    with open(html_path, 'w') as f:
        f.write(integration.generate_traffic_dashboard_html())
    print(f"    已生成: {html_path}")
    
    print("\n" + "="*60)
    print("✅ 深度集成演示完成!")
    print("="*60)
    
    return integration


if __name__ == "__main__":
    asyncio.run(demo())