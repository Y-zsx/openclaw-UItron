#!/usr/bin/env python3
"""
服务网格集成REST API
将服务网格功能集成到协作API网关
"""

import json
import logging
from flask import Flask, request, jsonify
from service_mesh import (
    AgentServiceMesh, MeshService, MeshServiceState, TrafficPolicy,
    CircuitState, create_mesh_from_gateway
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def register_mesh_routes(app, gateway):
    """注册服务网格路由到Flask应用"""
    
    # 创建服务网格
    mesh = create_mesh_from_gateway(gateway)
    
    # ========== 服务网格状态 ==========
    
    @app.route("/mesh/status", methods=["GET"])
    def mesh_status():
        """获取网格状态"""
        return jsonify(mesh.get_mesh_status())
    
    @app.route("/mesh/sync", methods=["POST"])
    def mesh_sync():
        """从网关同步服务"""
        count = mesh.sync_with_gateway(gateway)
        return jsonify({
            "synced_services": count,
            "total_services": len(mesh.services)
        })
    
    # ========== 服务管理 ==========
    
    @app.route("/mesh/services", methods=["GET"])
    def mesh_list_services():
        """列出所有服务"""
        name = request.args.get("name")
        version = request.args.get("version")
        capability = request.args.get("capability")
        
        if name or version or capability:
            services = mesh.get_healthy_services(name, version, capability)
            return jsonify({
                "services": [s.to_dict() for s in services]
            })
        
        return jsonify(mesh.get_service_details())
    
    @app.route("/mesh/services", methods=["POST"])
    def mesh_register_service():
        """注册服务"""
        data = request.get_json()
        
        service = MeshService(
            service_id=data.get("service_id", data.get("service_id")),
            name=data["name"],
            version=data.get("version", "v1"),
            endpoints=data.get("endpoints", []),
            capabilities=data.get("capabilities", []),
            metadata=data.get("metadata", {})
        )
        
        result = mesh.register_service(service)
        return jsonify(result), 201
    
    @app.route("/mesh/services/<service_id>", methods=["GET"])
    def mesh_get_service(service_id):
        """获取服务详情"""
        details = mesh.get_service_details(service_id)
        if "error" in details:
            return jsonify(details), 404
        return jsonify(details)
    
    @app.route("/mesh/services/<service_id>", methods=["DELETE"])
    def mesh_unregister_service(service_id):
        """注销服务"""
        success = mesh.unregister_service(service_id)
        if success:
            return jsonify({"message": f"Service {service_id} unregistered"})
        return jsonify({"error": "Service not found"}), 404
    
    @app.route("/mesh/services/<service_id>/health", methods=["PUT"])
    def mesh_update_health(service_id):
        """更新服务健康状态"""
        data = request.get_json()
        
        health_score = data.get("health_score", 100.0)
        state_str = data.get("state")
        
        state = None
        if state_str:
            try:
                state = MeshServiceState(state_str)
            except ValueError:
                pass
        
        success = mesh.update_service_health(service_id, health_score, state)
        if success:
            return jsonify({"message": f"Health updated for {service_id}"})
        return jsonify({"error": "Service not found"}), 404
    
    # ========== 流量管理 ==========
    
    @app.route("/mesh/services/<service_id>/select", methods=["POST"])
    def mesh_select_service(service_id):
        """选择服务 (负载均衡)"""
        # 这里service_id实际上是服务名称
        data = request.get_json() or {}
        version = data.get("version", "v1")
        strategy = data.get("strategy", "round_robin")
        
        service = mesh.select_service(service_id, version, strategy)
        if service:
            return jsonify(service.to_dict())
        return jsonify({"error": "No healthy service available"}), 503
    
    @app.route("/mesh/services/<service_id>/can-route", methods=["GET"])
    def mesh_can_route(service_id):
        """检查是否可以路由"""
        can_route, reason = mesh.can_route(service_id)
        return jsonify({
            "service_id": service_id,
            "can_route": can_route,
            "reason": reason
        })
    
    @app.route("/mesh/services/<service_id>/route", methods=["POST"])
    def mesh_route_request(service_id):
        """路由请求 (带完整熔断和限流)"""
        can_route, reason = mesh.can_route(service_id)
        if not can_route:
            return jsonify({
                "error": "Service unavailable",
                "reason": reason
            }), 503
        
        # 更新并发计数
        metrics = mesh.metrics.get(service_id)
        if metrics:
            metrics.current_concurrent += 1
            metrics.max_concurrent = max(metrics.max_concurrent, metrics.current_concurrent)
        
        # 执行请求 (模拟)
        start_time = __import__("time").time()
        success = True
        latency = 0
        
        try:
            # TODO: 实际调用服务
            import time
            time.sleep(0.01)  # 模拟
            latency = (time.time() - start_time) * 1000
        except Exception as e:
            success = False
            latency = (time.time() - start_time) * 1000
        finally:
            if metrics:
                metrics.current_concurrent -= 1
            mesh.record_request(service_id, success, latency)
        
        return jsonify({
            "success": success,
            "latency_ms": latency,
            "service_id": service_id
        })
    
    # ========== 流量策略 ==========
    
    @app.route("/mesh/services/<service_id>/policy", methods=["GET"])
    def mesh_get_policy(service_id):
        """获取流量策略"""
        policy = mesh.traffic_policies.get(service_id)
        if policy:
            return jsonify(policy.to_dict())
        return jsonify({"error": "Policy not found"}), 404
    
    @app.route("/mesh/services/<service_id>/policy", methods=["PUT"])
    def mesh_update_policy(service_id):
        """更新流量策略"""
        data = request.get_json()
        
        policy = TrafficPolicy(
            service_id=service_id,
            max_requests_per_second=data.get("max_requests_per_second", 100),
            max_concurrent_requests=data.get("max_concurrent_requests", 50),
            timeout=data.get("timeout", 30),
            retry_attempts=data.get("retry_attempts", 3),
            retry_backoff_ms=data.get("retry_backoff_ms", 100),
            weight=data.get("weight", 100),
            circuit_breaker_enabled=data.get("circuit_breaker_enabled", True),
            circuit_failure_threshold=data.get("circuit_failure_threshold", 5),
            circuit_timeout=data.get("circuit_timeout", 30)
        )
        
        mesh.update_traffic_policy(service_id, policy)
        return jsonify(policy.to_dict())
    
    # ========== 指标 ==========
    
    @app.route("/mesh/metrics", methods=["GET"])
    def mesh_metrics():
        """获取所有服务指标"""
        return jsonify({
            service_id: m.to_dict()
            for service_id, m in mesh.metrics.items()
        })
    
    @app.route("/mesh/metrics/<service_id>", methods=["GET"])
    def mesh_service_metrics(service_id):
        """获取服务指标"""
        metrics = mesh.metrics.get(service_id)
        if metrics:
            return jsonify(metrics.to_dict())
        return jsonify({"error": "Metrics not found"}), 404
    
    # ========== 熔断器 ==========
    
    @app.route("/mesh/circuit-breakers", methods=["GET"])
    def mesh_circuit_breakers():
        """获取所有熔断器状态"""
        return jsonify({
            service_id: {
                "state": cb.state.value,
                "failure_count": cb.failure_count,
                "success_count": cb.success_count,
                "last_failure_time": cb.last_failure_time
            }
            for service_id, cb in mesh.circuit_breakers.items()
        })
    
    @app.route("/mesh/circuit-breakers/<service_id>", methods=["GET"])
    def mesh_circuit_breaker(service_id):
        """获取熔断器状态"""
        cb = mesh.circuit_breakers.get(service_id)
        if cb:
            return jsonify({
                "service_id": service_id,
                "state": cb.state.value,
                "failure_count": cb.failure_count,
                "success_count": cb.success_count,
                "is_available": cb.is_available()
            })
        return jsonify({"error": "Circuit breaker not found"}), 404
    
    @app.route("/mesh/circuit-breakers/<service_id>/reset", methods=["POST"])
    def mesh_reset_circuit_breaker(service_id):
        """重置熔断器"""
        cb = mesh.circuit_breakers.get(service_id)
        if cb:
            cb.state = CircuitState.CLOSED
            cb.failure_count = 0
            cb.success_count = 0
            return jsonify({"message": f"Circuit breaker reset for {service_id}"})
        return jsonify({"error": "Circuit breaker not found"}), 404
    
    logger.info("服务网格路由注册完成")
    
    return mesh


# ========== 独立运行 ==========

def main():
    """独立运行服务网格API"""
    import argparse
    from collab_api_gateway import CollabAPIGateway
    
    parser = argparse.ArgumentParser(description="服务网格API")
    parser.add_argument("--port", type=int, default=8090, help="端口")
    parser.add_argument("--gateway-port", type=int, default=8089, help="网关端口")
    
    args = parser.parse_args()
    
    # 启动网关
    gateway = CollabAPIGateway(port=args.gateway_port)
    
    # 注册网格路由
    mesh = register_mesh_routes(gateway.app, gateway)
    
    # 启动网关服务
    logger.info(f"启动服务网格API on port {args.port}")
    gateway.app.run(host="0.0.0.0", port=args.port, debug=False)


if __name__ == "__main__":
    main()