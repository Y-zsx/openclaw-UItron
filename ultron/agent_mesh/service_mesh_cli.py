#!/usr/bin/env python3
"""
服务网格 CLI 工具
================
命令行管理服务网格
"""

import sys
import requests
import argparse
import json

API_BASE = "http://localhost:8094"


def cmd_circuit(args):
    """熔断器命令"""
    if args.subaction == "create":
        r = requests.post(f"{API_BASE}/api/circuit/{args.name}", json={
            "failure_threshold": args.failure_threshold,
            "success_threshold": args.success_threshold,
            "timeout": args.timeout
        })
    elif args.subaction == "status":
        r = requests.get(f"{API_BASE}/api/circuit/{args.name}")
    elif args.subaction == "success":
        r = requests.post(f"{API_BASE}/api/circuit/{args.name}/success")
    elif args.subaction == "fail":
        r = requests.post(f"{API_BASE}/api/circuit/{args.name}/fail")
    elif args.subaction == "available":
        r = requests.get(f"{API_BASE}/api/circuit/{args.name}/available")
    else:
        print(f"Unknown action: {args.subaction}")
        return
    
    print(json.dumps(r.json(), indent=2))


def cmd_ratelimit(args):
    """限流器命令"""
    if args.subaction == "create":
        r = requests.post(f"{API_BASE}/api/ratelimit/{args.name}", json={
            "rate": args.rate,
            "capacity": args.capacity
        })
    elif args.subaction == "check":
        r = requests.get(f"{API_BASE}/api/ratelimit/{args.name}/check", 
                        params={"client_id": args.client_id})
    elif args.subaction == "status":
        r = requests.get(f"{API_BASE}/api/ratelimit/{args.name}")
    else:
        print(f"Unknown action: {args.subaction}")
        return
    
    print(json.dumps(r.json(), indent=2))


def cmd_route(args):
    """路由命令"""
    if args.subaction == "add":
        r = requests.post(f"{API_BASE}/api/route/{args.service}", json={
            "type": args.type,
            "targets": json.loads(args.targets) if args.targets else [],
            "weights": json.loads(args.weights) if args.weights else None
        })
    elif args.subaction == "get":
        r = requests.get(f"{API_BASE}/api/route/{args.service}")
    elif args.subaction == "dispatch":
        r = requests.post(f"{API_BASE}/api/route/{args.service}/dispatch", json={
            "user_id": args.user_id,
            "headers": {}
        })
    elif args.subaction == "delete":
        r = requests.delete(f"{API_BASE}/api/route/{args.service}")
    else:
        print(f"Unknown action: {args.subaction}")
        return
    
    print(json.dumps(r.json(), indent=2))


def cmd_discover(args):
    """服务发现命令"""
    if args.subaction == "register":
        r = requests.post(f"{API_BASE}/api/discover/register", json={
            "service_name": args.service,
            "endpoint": args.endpoint,
            "metadata": json.loads(args.metadata) if args.metadata else {}
        })
    elif args.subaction == "list":
        r = requests.get(f"{API_BASE}/api/discover/{args.service}")
    elif args.subaction == "heartbeat":
        r = requests.post(f"{API_BASE}/api/discover/{args.service}/heartbeat", json={
            "instance_id": args.instance_id
        })
    else:
        print(f"Unknown action: {args.subaction}")
        return
    
    print(json.dumps(r.json(), indent=2))


def cmd_stats(args):
    """统计命令"""
    if args.subaction == "traffic":
        r = requests.get(f"{API_BASE}/api/stats/traffic/{args.service}",
                        params={"window": args.window})
    else:
        print(f"Unknown action: {args.subaction}")
        return
    
    print(json.dumps(r.json(), indent=2))


def cmd_status(args):
    """状态命令"""
    r = requests.get(f"{API_BASE}/api/status")
    print(json.dumps(r.json(), indent=2))


def main():
    parser = argparse.ArgumentParser(description="服务网格CLI")
    subparsers = parser.add_subparsers()
    
    # 熔断器
    p_circuit = subparsers.add_parser("circuit", help="熔断器管理")
    p_circuit.add_argument("subaction", choices=["create", "status", "success", "fail", "available"])
    p_circuit.add_argument("name", help="熔断器名称")
    p_circuit.add_argument("--failure-threshold", type=float, default=0.5)
    p_circuit.add_argument("--success-threshold", type=int, default=3)
    p_circuit.add_argument("--timeout", type=float, default=30.0)
    p_circuit.set_defaults(func=cmd_circuit)
    
    # 限流器
    p_rate = subparsers.add_parser("ratelimit", help="限流器管理")
    p_rate.add_argument("subaction", choices=["create", "check", "status"])
    p_rate.add_argument("name", help="限流器名称")
    p_rate.add_argument("--rate", type=float, default=100)
    p_rate.add_argument("--capacity", type=int, default=100)
    p_rate.add_argument("--client-id", default="default")
    p_rate.set_defaults(func=cmd_ratelimit)
    
    # 路由
    p_route = subparsers.add_parser("route", help="路由管理")
    p_route.add_argument("subaction", choices=["add", "get", "dispatch", "delete"])
    p_route.add_argument("service", help="服务名称")
    p_route.add_argument("--type", default="balanced")
    p_route.add_argument("--targets", help="目标列表JSON")
    p_route.add_argument("--weights", help="权重列表JSON")
    p_route.add_argument("--user-id", help="用户ID(用于A/B测试)")
    p_route.set_defaults(func=cmd_route)
    
    # 服务发现
    p_disc = subparsers.add_parser("discover", help="服务发现")
    p_disc.add_argument("subaction", choices=["register", "list", "heartbeat"])
    p_disc.add_argument("service", help="服务名称")
    p_disc.add_argument("--endpoint", help="服务端点")
    p_disc.add_argument("--metadata", help="元数据JSON")
    p_disc.add_argument("--instance-id", help="实例ID")
    p_disc.set_defaults(func=cmd_discover)
    
    # 统计
    p_stats = subparsers.add_parser("stats", help="流量统计")
    p_stats.add_argument("subaction", choices=["traffic"])
    p_stats.add_argument("service", help="服务名称")
    p_stats.add_argument("--window", type=int, default=300, help="时间窗口(秒)")
    p_stats.set_defaults(func=cmd_stats)
    
    # 状态
    p_status = subparsers.add_parser("status", help="网格状态")
    p_status.set_defaults(func=cmd_status)
    
    args = parser.parse_args()
    
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()