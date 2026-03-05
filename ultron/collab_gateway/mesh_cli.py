#!/usr/bin/env python3
"""
服务网格CLI工具
"""

import json
import argparse
import requests
import sys


DEFAULT_URL = "http://localhost:8089"


def get(url):
    """GET请求"""
    try:
        r = requests.get(f"{DEFAULT_URL}{url}", timeout=5)
        return r.json()
    except Exception as e:
        print(f"Error: {e}")
        return None


def post(url, data=None):
    """POST请求"""
    try:
        r = requests.post(f"{DEFAULT_URL}{url}", json=data, timeout=5)
        return r.json()
    except Exception as e:
        print(f"Error: {e}")
        return None


def put(url, data):
    """PUT请求"""
    try:
        r = requests.put(f"{DEFAULT_URL}{url}", json=data, timeout=5)
        return r.json()
    except Exception as e:
        print(f"Error: {e}")
        return None


def delete(url):
    """DELETE请求"""
    try:
        r = requests.delete(f"{DEFAULT_URL}{url}", timeout=5)
        return r.json() if r.text else {"message": "deleted"}
    except Exception as e:
        print(f"Error: {e}")
        return None


def cmd_status(args):
    """网格状态"""
    result = get("/mesh/status")
    if result:
        print(json.dumps(result, indent=2))
    return 0


def cmd_services(args):
    """服务列表"""
    params = ""
    if args.name:
        params = f"?name={args.name}"
    if args.version:
        params += f"&version={args.version}" if params else f"?version={args.version}"
    if args.capability:
        params += f"&capability={args.capability}" if params else f"?capability={args.capability}"
    
    result = get(f"/mesh/services{params}")
    if result:
        if "services" in result:
            print(json.dumps(result, indent=2))
        else:
            # 详细模式
            for sid, details in result.items():
                print(f"\n=== {sid} ===")
                print(json.dumps(details, indent=2))
    return 0


def cmd_register(args):
    """注册服务"""
    data = {
        "service_id": args.service_id,
        "name": args.name,
        "version": args.version or "v1",
        "capabilities": args.capabilities.split(",") if args.capabilities else [],
        "metadata": {}
    }
    result = post("/mesh/services", data)
    if result:
        print(json.dumps(result, indent=2))
    return 0


def cmd_unregister(args):
    """注销服务"""
    result = delete(f"/mesh/services/{args.service_id}")
    if result:
        print(json.dumps(result, indent=2))
    return 0


def cmd_health(args):
    """更新健康状态"""
    data = {"health_score": args.score}
    if args.state:
        data["state"] = args.state
    result = put(f"/mesh/services/{args.service_id}/health", data)
    if result:
        print(json.dumps(result, indent=2))
    return 0


def cmd_select(args):
    """选择服务"""
    data = {"version": args.version or "v1", "strategy": args.strategy}
    result = post(f"/mesh/services/{args.name}/select", data)
    if result:
        if "error" in result:
            print(f"Error: {result['error']}")
            return 1
        print(json.dumps(result, indent=2))
    return 0


def cmd_policy(args):
    """流量策略"""
    if args.get:
        result = get(f"/mesh/services/{args.service_id}/policy")
        if result:
            print(json.dumps(result, indent=2))
    else:
        data = {
            "max_requests_per_second": args.rps or 100,
            "max_concurrent_requests": args.concurrent or 50,
            "timeout": args.timeout or 30,
            "weight": args.weight or 100,
            "circuit_breaker_enabled": not args.no_circuit,
            "circuit_failure_threshold": args.circuit_threshold or 5
        }
        result = put(f"/mesh/services/{args.service_id}/policy", data)
        if result:
            print(json.dumps(result, indent=2))
    return 0


def cmd_metrics(args):
    """指标"""
    if args.service_id:
        result = get(f"/mesh/metrics/{args.service_id}")
    else:
        result = get("/mesh/metrics")
    if result:
        print(json.dumps(result, indent=2))
    return 0


def cmd_circuit(args):
    """熔断器"""
    if args.reset:
        result = post(f"/mesh/circuit-breakers/{args.service_id}/reset", {})
    else:
        result = get(f"/mesh/circuit-breakers/{args.service_id}")
    if result:
        print(json.dumps(result, indent=2))
    return 0


def cmd_sync(args):
    """同步"""
    result = post("/mesh/sync", {})
    if result:
        print(json.dumps(result, indent=2))
    return 0


def main():
    parser = argparse.ArgumentParser(description="Agent服务网格CLI")
    parser.add_argument("--url", default=DEFAULT_URL, help="网关URL")
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # status
    subparsers.add_parser("status", help="网格状态")
    
    # services
    services_parser = subparsers.add_parser("services", help="服务列表")
    services_parser.add_argument("--name", help="服务名")
    services_parser.add_argument("--version", help="版本")
    services_parser.add_argument("--capability", help="能力")
    
    # register
    register_parser = subparsers.add_parser("register", help="注册服务")
    register_parser.add_argument("service_id", help="服务ID")
    register_parser.add_argument("name", help="服务名")
    register_parser.add_argument("--version", default="v1", help="版本")
    register_parser.add_argument("--capabilities", help="能力(逗号分隔)")
    
    # unregister
    unreg_parser = subparsers.add_parser("unregister", help="注销服务")
    unreg_parser.add_argument("service_id", help="服务ID")
    
    # health
    health_parser = subparsers.add_parser("health", help="更新健康状态")
    health_parser.add_argument("service_id", help="服务ID")
    health_parser.add_argument("score", type=float, help="健康分数")
    health_parser.add_argument("--state", choices=["healthy", "degraded", "unhealthy"], help="状态")
    
    # select
    select_parser = subparsers.add_parser("select", help="选择服务")
    select_parser.add_argument("name", help="服务名")
    select_parser.add_argument("--version", default="v1", help="版本")
    select_parser.add_argument("--strategy", default="round_robin", 
                              choices=["round_robin", "random", "least_connections", "weighted"],
                              help="负载均衡策略")
    
    # policy
    policy_parser = subparsers.add_parser("policy", help="流量策略")
    policy_parser.add_argument("service_id", help="服务ID")
    policy_parser.add_argument("--get", action="store_true", help="获取策略")
    policy_parser.add_argument("--rps", type=float, help="每秒最大请求")
    policy_parser.add_argument("--concurrent", type=int, help="最大并发")
    policy_parser.add_argument("--timeout", type=float, help="超时秒数")
    policy_parser.add_argument("--weight", type=float, help="权重")
    policy_parser.add_argument("--no-circuit", action="store_true", help="禁用熔断")
    policy_parser.add_argument("--circuit-threshold", type=int, help="熔断阈值")
    
    # metrics
    metrics_parser = subparsers.add_parser("metrics", help="指标")
    metrics_parser.add_argument("--service-id", help="服务ID")
    
    # circuit
    circuit_parser = subparsers.add_parser("circuit", help="熔断器")
    circuit_parser.add_argument("service_id", help="服务ID")
    circuit_parser.add_argument("--reset", action="store_true", help="重置熔断器")
    
    # sync
    subparsers.add_parser("sync", help="从网关同步")
    
    args = parser.parse_args()
    
    global DEFAULT_URL
    DEFAULT_URL = args.url
    
    if not args.command:
        parser.print_help()
        return 1
    
    commands = {
        "status": cmd_status,
        "services": cmd_services,
        "register": cmd_register,
        "unregister": cmd_unregister,
        "health": cmd_health,
        "select": cmd_select,
        "policy": cmd_policy,
        "metrics": cmd_metrics,
        "circuit": cmd_circuit,
        "sync": cmd_sync
    }
    
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())