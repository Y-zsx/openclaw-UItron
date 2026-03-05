#!/usr/bin/env python3
"""
服务网格 REST API
================
端口: 8094

提供:
- 熔断器管理
- 限流器管理  
- 流量路由配置
- 服务发现
- 流量统计
"""

import json
import time
from datetime import datetime
from flask import Flask, jsonify, request
from service_mesh import (
    get_mesh_controller, MeshController,
    CircuitBreaker, RateLimiter, TrafficRouter,
    TrafficRouteType, CircuitState
)

app = Flask(__name__)
mesh = get_mesh_controller()


# ========== 健康检查 ==========

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "service-mesh-api",
        "timestamp": datetime.now().isoformat()
    })


# ========== 熔断器 API ==========

@app.route('/api/circuit/<name>', methods=['POST'])
def create_circuit(name):
    """创建熔断器"""
    data = request.get_json() or {}
    cb = mesh.get_circuit_breaker(
        name,
        failure_threshold=data.get('failure_threshold', 0.5),
        success_threshold=data.get('success_threshold', 3),
        timeout=data.get('timeout', 30.0)
    )
    return jsonify({
        "message": "Circuit breaker created",
        "name": name,
        "config": {
            "failure_threshold": cb.failure_threshold,
            "success_threshold": cb.success_threshold,
            "timeout": cb.timeout
        }
    })


@app.route('/api/circuit/<name>', methods=['GET'])
def get_circuit(name):
    """获取熔断器状态"""
    cb = mesh.circuit_breakers.get(name)
    if not cb:
        return jsonify({"error": "Circuit breaker not found"}), 404
    
    return jsonify({"name": name, **cb.get_stats()})


@app.route('/api/circuit/<name>/success', methods=['POST'])
def circuit_success(name):
    """记录成功"""
    cb = mesh.circuit_breakers.get(name)
    if not cb:
        return jsonify({"error": "Circuit breaker not found"}), 404
    
    cb.record_success()
    return jsonify({"state": cb.state.value})


@app.route('/api/circuit/<name>/fail', methods=['POST'])
def circuit_fail(name):
    """记录失败"""
    cb = mesh.circuit_breakers.get(name)
    if not cb:
        return jsonify({"error": "Circuit breaker not found"}), 404
    
    cb.record_failure()
    return jsonify({"state": cb.state.value})


@app.route('/api/circuit/<name>/available', methods=['GET'])
def circuit_available(name):
    """检查熔断器是否可用"""
    cb = mesh.circuit_breakers.get(name)
    if not cb:
        return jsonify({"error": "Circuit breaker not found"}), 404
    
    return jsonify({"available": cb.is_available(), "state": cb.state.value})


# ========== 限流器 API ==========

@app.route('/api/ratelimit/<name>', methods=['POST'])
def create_ratelimit(name):
    """创建限流器"""
    data = request.get_json() or {}
    rl = mesh.get_rate_limiter(
        name,
        rate=data.get('rate', 100),
        capacity=data.get('capacity', 100)
    )
    return jsonify({
        "message": "Rate limiter created",
        "name": name,
        "config": {
            "rate": rl.rate,
            "capacity": rl.capacity
        }
    })


@app.route('/api/ratelimit/<name>/check', methods=['GET'])
def check_ratelimit(name):
    """检查限流"""
    client_id = request.args.get('client_id', 'default')
    
    rl = mesh.rate_limiters.get(name)
    if not rl:
        return jsonify({"error": "Rate limiter not found"}), 404
    
    allowed = rl.allow_request(client_id)
    wait_time = rl.get_wait_time(client_id) if not allowed else 0
    
    return jsonify({
        "allowed": allowed,
        "wait_time_seconds": wait_time,
        "stats": rl.get_stats(client_id)
    })


@app.route('/api/ratelimit/<name>', methods=['GET'])
def get_ratelimit(name):
    """获取限流器状态"""
    rl = mesh.rate_limiters.get(name)
    if not rl:
        return jsonify({"error": "Rate limiter not found"}), 404
    
    return jsonify({"name": name, **rl.get_stats()})


# ========== 流量路由 API ==========

@app.route('/api/route/<service>', methods=['POST'])
def add_route(service):
    """添加路由规则"""
    data = request.get_json() or {}
    
    route_type_str = data.get('type', 'balanced')
    try:
        route_type = TrafficRouteType(route_type_str)
    except ValueError:
        return jsonify({"error": f"Invalid route type: {route_type_str}"}), 400
    
    targets = data.get('targets', [])
    weights = data.get('weights')
    rules = data.get('rules', {})
    
    mesh.router.add_route(
        service=service,
        route_type=route_type,
        targets=targets,
        weights=weights,
        rules=rules
    )
    
    return jsonify({
        "message": "Route added",
        "service": service,
        "type": route_type.value
    })


@app.route('/api/route/<service>', methods=['GET'])
def get_route(service):
    """获取路由规则"""
    route = mesh.router.get_route(service)
    if not route:
        return jsonify({"error": "Route not found"}), 404
    
    route_copy = {**route}
    route_copy["type"] = route_copy["type"].value
    return jsonify({"service": service, **route_copy})


@app.route('/api/route/<service>/dispatch', methods=['POST'])
def dispatch(service):
    """路由请求"""
    ctx = request.get_json() or {}
    result = mesh.router.route(service, ctx)
    
    if not result:
        return jsonify({"error": "No route configured"}), 404
    
    return jsonify({
        "service": service,
        "routed_to": result.get("target", {}).get("endpoint"),
        "metadata": result
    })


@app.route('/api/route/<service>', methods=['DELETE'])
def delete_route(service):
    """删除路由"""
    mesh.router.remove_route(service)
    return jsonify({"message": "Route deleted", "service": service})


# ========== 服务发现 API ==========

@app.route('/api/discover/register', methods=['POST'])
def register_service():
    """注册服务实例"""
    data = request.get_json() or {}
    
    service_name = data.get('service_name')
    endpoint = data.get('endpoint')
    metadata = data.get('metadata', {})
    
    if not service_name or not endpoint:
        return jsonify({"error": "service_name and endpoint required"}), 400
    
    mesh.discovery.register_service(
        service_name=service_name,
        endpoint=endpoint,
        metadata=metadata
    )
    
    return jsonify({"message": "Service registered", "service": service_name})


@app.route('/api/discover/<service_name>', methods=['GET'])
def discover_service(service_name):
    """发现服务"""
    healthy_only = request.args.get('healthy_only', 'true').lower() == 'true'
    instances = mesh.discovery.discover(service_name, healthy_only)
    
    return jsonify({
        "service": service_name,
        "instances": len(instances),
        "healthy": sum(1 for i in instances if i["healthy"]),
        "endpoints": [i["endpoint"] for i in instances]
    })


@app.route('/api/discover/<service_name>/heartbeat', methods=['POST'])
def heartbeat(service_name):
    """服务心跳"""
    data = request.get_json() or {}
    instance_id = data.get('instance_id')
    
    if not instance_id:
        return jsonify({"error": "instance_id required"}), 400
    
    success = mesh.discovery.heartbeat(instance_id)
    return jsonify({"success": success})


# ========== 流量统计 API ==========

@app.route('/api/stats/traffic', methods=['POST'])
def record_traffic():
    """记录流量"""
    data = request.get_json() or {}
    
    service = data.get('service')
    target = data.get('target')
    latency_ms = data.get('latency_ms', 0)
    success = data.get('success', True)
    status_code = data.get('status_code', 200)
    
    if not service or not target:
        return jsonify({"error": "service and target required"}), 400
    
    mesh.record_traffic(service, target, latency_ms, success, status_code)
    
    return jsonify({"message": "Traffic recorded"})


@app.route('/api/stats/traffic/<service>', methods=['GET'])
def get_traffic_stats(service):
    """获取流量统计"""
    window = int(request.args.get('window', 300))
    stats = mesh.get_traffic_stats(service, window)
    
    return jsonify(stats)


# ========== 网格状态 API ==========

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取网格整体状态"""
    return jsonify(mesh.get_status())


def run_api(host='0.0.0.0', port=8094):
    print(f"🚀 服务网格API启动: http://{host}:{port}")
    app.run(host=host, port=port, threaded=True)


if __name__ == '__main__':
    run_api()