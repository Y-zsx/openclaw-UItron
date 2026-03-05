#!/usr/bin/env python3
"""
Agent Service Mesh CLI
管理服务网格的终端工具
"""

import requests
import json
import sys
import argparse

BASE_URL = "http://localhost:8094"

def health():
    """检查服务状态"""
    r = requests.get(f"{BASE_URL}/health")
    print(json.dumps(r.json(), indent=2))

def list_services():
    """列出所有服务"""
    r = requests.get(f"{BASE_URL}/api/services")
    data = r.json()
    print("Registered Services:")
    for svc in data.get("services", []):
        print(f"  - {svc}")

def list_endpoints(service_name: str, labels: str = None):
    """列出服务端点"""
    url = f"{BASE_URL}/api/services/{service_name}/endpoints"
    if labels:
        url += f"?labels={labels}"
    r = requests.get(url)
    data = r.json()
    print(f"Endpoints for {service_name}:")
    for ep in data.get("endpoints", []):
        status = "✓" if ep.get("is_healthy") else "✗"
        print(f"  {status} {ep['endpoint_id']} - {ep['host']}:{ep['port']} (v{ep['version']}, weight:{ep['weight']})")

def register(service_name: str, endpoint_id: str, host: str, port: int, 
             agent_type: str = "generic", version: str = "v1", weight: int = 100):
    """注册端点"""
    data = {
        "service_name": service_name,
        "endpoint_id": endpoint_id,
        "host": host,
        "port": port,
        "agent_type": agent_type,
        "version": version,
        "weight": weight
    }
    r = requests.post(f"{BASE_URL}/api/register", json=data)
    print(json.dumps(r.json(), indent=2))

def deregister(endpoint_id: str):
    """注销端点"""
    r = requests.post(f"{BASE_URL}/api/deregister/{endpoint_id}")
    print(json.dumps(r.json(), indent=2))

def add_route(service_name: str, destination: str, match_labels: str = None, weight: int = 100):
    """添加路由规则"""
    labels = json.loads(match_labels) if match_labels else {}
    data = {
        "service_name": service_name,
        "match_labels": labels,
        "destination_service": destination,
        "weight": weight
    }
    r = requests.post(f"{BASE_URL}/api/routes", json=data)
    print(json.dumps(r.json(), indent=2))

def get_routes(service_name: str):
    """获取路由规则"""
    r = requests.get(f"{BASE_URL}/api/routes/{service_name}")
    data = r.json()
    print(f"Routes for {service_name}:")
    for route in data.get("routes", []):
        labels = route.get("match_labels", {})
        print(f"  → {route['destination_service']} (weight:{route['weight']}, labels:{labels})")

def circuit_state(service_name: str):
    """查看熔断状态"""
    r = requests.get(f"{BASE_URL}/api/circuit-breaker/{service_name}/state")
    print(json.dumps(r.json(), indent=2))

def record_success(service_name: str):
    """记录成功"""
    r = requests.post(f"{BASE_URL}/api/circuit-breaker/{service_name}/record/success")
    print(json.dumps(r.json(), indent=2))

def record_failure(service_name: str):
    """记录失败"""
    r = requests.post(f"{BASE_URL}/api/circuit-breaker/{service_name}/record/failure")
    print(json.dumps(r.json(), indent=2))

def set_rate_limit(service_name: str, rps: int, burst: int = None):
    """设置限流"""
    data = {"rps": rps}
    if burst:
        data["burst"] = burst
    r = requests.post(f"{BASE_URL}/api/rate-limit/{service_name}", json=data)
    print(json.dumps(r.json(), indent=2))

def check_rate_limit(service_name: str):
    """检查限流"""
    r = requests.get(f"{BASE_URL}/api/rate-limit/{service_name}/check")
    data = r.json()
    status = "✓" if data.get("allowed") else "✗"
    print(f"{status} Rate limit: {json.dumps(data, indent=2)}")

def dispatch(service_name: str, labels: str = None):
    """流量调度"""
    data = {"service": service_name}
    if labels:
        data["labels"] = json.loads(labels)
    r = requests.post(f"{BASE_URL}/api/dispatch", json=data)
    if r.status_code == 200:
        data = r.json()
        print(f"Dispatched to {data['endpoint']['host']}:{data['endpoint']['port']}")
    else:
        print(f"Error: {r.status_code}")
        print(json.dumps(r.json(), indent=2))

def stats():
    """服务统计"""
    r = requests.get(f"{BASE_URL}/api/stats")
    print(json.dumps(r.json(), indent=2))

def metrics(limit: int = 10):
    """流量指标"""
    r = requests.get(f"{BASE_URL}/api/metrics")
    data = r.json()
    print(f"Total requests: {data['total']}")
    print(f"Recent {min(limit, len(data['metrics']))} requests:")
    for m in data['metrics'][-limit:]:
        print(f"  {m['source_service']} → {m['destination_service']} ({m['latency_ms']:.1f}ms)")

def main():
    parser = argparse.ArgumentParser(description="Agent Service Mesh CLI")
    sub = parser.add_subparsers(dest="command")
    
    sub.add_parser("health", help="检查服务状态")
    sub.add_parser("services", help="列出所有服务")
    sub.add_parser("stats", help="服务统计")
    sub.add_parser("metrics", help="流量指标")
    
    eps = sub.add_parser("endpoints", help="列出服务端点")
    eps.add_argument("service_name")
    eps.add_argument("--labels", "-l")
    
    reg = sub.add_parser("register", help="注册端点")
    reg.add_argument("--service", required=True)
    reg.add_argument("--id", required=True)
    reg.add_argument("--host", default="localhost")
    reg.add_argument("--port", type=int, required=True)
    reg.add_argument("--type", default="generic")
    reg.add_argument("--version", default="v1")
    reg.add_argument("--weight", type=int, default=100)
    
    dereg = sub.add_parser("deregister", help="注销端点")
    dereg.add_argument("endpoint_id")
    
    route = sub.add_parser("route-add", help="添加路由")
    route.add_argument("--service", required=True)
    route.add_argument("--destination", required=True)
    route.add_argument("--labels")
    route.add_argument("--weight", type=int, default=100)
    
    routes = sub.add_parser("routes", help="查看路由")
    routes.add_argument("service_name")
    
    circ = sub.add_parser("circuit", help="熔断状态")
    circ.add_argument("service_name")
    
    rl = sub.add_parser("rate-limit", help="设置限流")
    rl.add_argument("service_name")
    rl.add_argument("--rps", type=int, required=True)
    rl.add_argument("--burst", type=int)
    
    disp = sub.add_parser("dispatch", help="流量调度")
    disp.add_argument("service_name")
    disp.add_argument("--labels", "-l")
    
    args = parser.parse_args()
    
    if args.command == "health":
        health()
    elif args.command == "services":
        list_services()
    elif args.command == "stats":
        stats()
    elif args.command == "metrics":
        metrics()
    elif args.command == "endpoints":
        list_endpoints(args.service_name, args.labels)
    elif args.command == "register":
        register(args.service, args.id, args.host, args.port, args.type, args.version, args.weight)
    elif args.command == "deregister":
        deregister(args.endpoint_id)
    elif args.command == "route-add":
        add_route(args.service, args.destination, args.labels, args.weight)
    elif args.command == "routes":
        get_routes(args.service_name)
    elif args.command == "circuit":
        circuit_state(args.service_name)
    elif args.command == "rate-limit":
        set_rate_limit(args.service_name, args.rps, args.burst)
    elif args.command == "dispatch":
        dispatch(args.service_name, args.labels)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()