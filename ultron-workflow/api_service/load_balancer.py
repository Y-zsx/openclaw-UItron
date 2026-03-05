#!/usr/bin/env python3
"""
Agent服务负载均衡器
支持多种负载均衡算法和健康检查
"""
import json
import time
import random
import threading
import requests
from datetime import datetime
from typing import Dict, List, Optional
from flask import Flask, jsonify, request
from collections import defaultdict
import sqlite3

app = Flask(__name__)

# 负载均衡算法
ALGORITHMS = {
    "round_robin": "轮询",
    "least_conn": "最少连接",
    "weighted": "加权轮询",
    "ip_hash": "源IP哈希",
    "random": "随机",
}

# 存储
LB_STATE = {
    "services": {},  # service_name -> backends
    "algorithms": {},  # service_name -> algorithm
    "health": {},  # backend_key -> health_info
    "stats": defaultdict(lambda: {"requests": 0, "errors": 0, "latency_sum": 0}),
    "sticky_sessions": {},  # ip -> backend
    "lock": threading.Lock()
}

DB_PATH = "/root/.openclaw/workspace/ultron-workflow/api_service/loadbalancer.db"

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS request_stats
                 (id INTEGER PRIMARY KEY, timestamp TEXT, service TEXT,
                  backend TEXT, latency REAL, status INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS backend_health
                 (id INTEGER PRIMARY KEY, timestamp TEXT, backend TEXT,
                  status TEXT, latency REAL, error TEXT)''')
    conn.commit()
    conn.close()

def health_check_backend(backend: Dict) -> bool:
    """健康检查单个后端"""
    try:
        url = backend.get("health_url", backend["url"] + "/health")
        resp = requests.get(url, timeout=backend.get("timeout", 5))
        return resp.status_code == 200
    except:
        return False

def get_healthy_backends(service: str) -> List[Dict]:
    """获取健康的后端列表"""
    backends = LB_STATE["services"].get(service, []).copy()
    
    # 过滤不健康的后端
    result = []
    for b in backends:
        key = f"{service}:{b['host']}:{b['port']}"
        health = LB_STATE["health"].get(key, {})
        
        # 检查是否标记为不健康
        if health.get("status") == "unhealthy" and time.time() - health.get("last_check", 0) < 60:
            continue
        
        result.append(b)
    
    return result if result else backends  # 如果全不健康，返回全部

def select_backend_round_robin(service: str, backends: List[Dict]) -> Optional[Dict]:
    """轮询算法"""
    key = f"{service}:rr_index"
    idx = LB_STATE["stats"].get(key, {"index": 0})["index"]
    
    backend = backends[idx % len(backends)]
    LB_STATE["stats"][key] = {"index": (idx + 1) % len(backends)}
    return backend

def select_backend_least_conn(service: str, backends: List[Dict]) -> Optional[Dict]:
    """最少连接算法"""
    min_conn = float('inf')
    selected = None
    
    for b in backends:
        key = f"{service}:{b['host']}:{b['port']}"
        conns = LB_STATE["stats"].get(key, {}).get("active_connections", 0)
        
        if conns < min_conn:
            min_conn = conns
            selected = b
    
    return selected

def select_backend_weighted(service: str, backends: List[Dict]) -> Optional[Dict]:
    """加权轮询算法"""
    weighted = []
    for b in backends:
        weight = b.get("weight", 1)
        weighted.extend([b] * weight)
    
    return random.choice(weighted) if weighted else None

def select_backend_ip_hash(service: str, backends: List[Dict], client_ip: str) -> Optional[Dict]:
    """IP哈希算法"""
    if not client_ip:
        return backends[0] if backends else None
    
    # 使用sticky session
    if client_ip in LB_STATE["sticky_sessions"]:
        backend_key = LB_STATE["sticky_sessions"][client_ip]
        for b in backends:
            key = f"{service}:{b['host']}:{b['port']}"
            if key == backend_key:
                return b
    
    # 新选择
    idx = hash(client_ip) % len(backends)
    backend = backends[idx]
    key = f"{service}:{backend['host']}:{backend['port']}"
    LB_STATE["sticky_sessions"][client_ip] = key
    
    return backend

def select_backend_random(service: str, backends: List[Dict]) -> Optional[Dict]:
    """随机算法"""
    return random.choice(backends) if backends else None

def route_request(service: str, path: str, client_ip: str = None) -> Optional[Dict]:
    """路由请求到后端"""
    with LB_STATE["lock"]:
        backends = get_healthy_backends(service)
        
        if not backends:
            return None
        
        algorithm = LB_STATE["algorithms"].get(service, "round_robin")
        
        if algorithm == "round_robin":
            return select_backend_round_robin(service, backends)
        elif algorithm == "least_conn":
            return select_backend_least_conn(service, backends)
        elif algorithm == "weighted":
            return select_backend_weighted(service, backends)
        elif algorithm == "ip_hash":
            return select_backend_ip_hash(service, backends, client_ip)
        elif algorithm == "random":
            return select_backend_random(service, backends)
        
        return backends[0]

def health_check_worker():
    """后台健康检查工作线程"""
    while True:
        try:
            for service, backends in LB_STATE["services"].items():
                for backend in backends:
                    key = f"{service}:{backend['host']}:{backend['port']}"
                    is_healthy = health_check_backend(backend)
                    
                    LB_STATE["health"][key] = {
                        "status": "healthy" if is_healthy else "unhealthy",
                        "last_check": time.time(),
                        "consecutive_failures": LB_STATE["health"].get(key, {}).get("consecutive_failures", 0) + (0 if is_healthy else 1)
                    }
        except Exception as e:
            print(f"[LoadBalancer] Health check error: {e}")
        
        time.sleep(10)

# Flask API
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "load_balancer"})

@app.route("/service", methods=["POST"])
def add_service():
    """添加服务"""
    data = request.json
    service = data.get("service")
    
    if not service:
        return jsonify({"error": "service name required"}), 400
    
    with LB_STATE["lock"]:
        LB_STATE["services"][service] = data.get("backends", [])
        LB_STATE["algorithms"][service] = data.get("algorithm", "round_robin")
    
    return jsonify({"status": "added", "service": service})

@app.route("/service/<service>", methods=["GET"])
def get_service(service):
    """获取服务信息"""
    backends = LB_STATE["services"].get(service, [])
    algorithm = LB_STATE["algorithms"].get(service, "round_robin")
    
    # 附加健康状态
    result = []
    for b in backends:
        key = f"{service}:{b['host']}:{b['port']}"
        health = LB_STATE["health"].get(key, {})
        b_copy = b.copy()
        b_copy["health"] = health.get("status", "unknown")
        result.append(b_copy)
    
    return jsonify({
        "service": service,
        "algorithm": algorithm,
        "algorithm_name": ALGORITHMS.get(algorithm, algorithm),
        "backends": result,
        "healthy_count": len([b for b in result if b.get("health") == "healthy"])
    })

@app.route("/service/<service>", methods=["DELETE"])
def remove_service(service):
    """移除服务"""
    with LB_STATE["lock"]:
        if service in LB_STATE["services"]:
            del LB_STATE["services"][service]
            if service in LB_STATE["algorithms"]:
                del LB_STATE["algorithms"][service]
            return jsonify({"status": "removed", "service": service})
    
    return jsonify({"error": "service not found"}), 404

@app.route("/service/<service>/backend", methods=["POST"])
def add_backend(service):
    """添加后端"""
    data = request.json
    backend = data.get("backend")
    
    if not backend:
        return jsonify({"error": "backend required"}), 400
    
    with LB_STATE["lock"]:
        if service not in LB_STATE["services"]:
            LB_STATE["services"][service] = []
        
        LB_STATE["services"][service].append(backend)
    
    return jsonify({"status": "added", "backend": backend})

@app.route("/service/<service>/algorithm", methods=["POST"])
def set_algorithm(service):
    """设置负载均衡算法"""
    data = request.json
    algorithm = data.get("algorithm")
    
    if algorithm not in ALGORITHMS:
        return jsonify({"error": f"invalid algorithm. Available: {list(ALGORITHMS.keys())}"}), 400
    
    with LB_STATE["lock"]:
        LB_STATE["algorithms"][service] = algorithm
    
    return jsonify({"status": "updated", "algorithm": algorithm, "name": ALGORITHMS[algorithm]})

@app.route("/proxy/<service>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def proxy(service):
    """代理请求到后端"""
    client_ip = request.remote_addr
    
    # 路由到后端
    backend = route_request(service, request.path, client_ip)
    
    if not backend:
        return jsonify({"error": "no healthy backend available"}), 503
    
    # 构建后端URL
    url = f"{backend['url']}{request.path}"
    
    # 转发请求
    try:
        resp = requests.request(
            method=request.method,
            url=url,
            headers={k: v for k, v in request.headers if k.lower() != "host"},
            json=request.get_json() if request.is_json else None,
            data=request.get_data(),
            timeout=backend.get("timeout", 30),
            allow_redirects=False
        )
        
        # 记录统计
        key = f"{service}:{backend['host']}:{backend['port']}"
        LB_STATE["stats"][key]["requests"] += 1
        if resp.status_code >= 400:
            LB_STATE["stats"][key]["errors"] += 1
        
        return resp.content, resp.status_code, resp.headers.items()
    
    except Exception as e:
        key = f"{service}:{backend['host']}:{backend['port']}"
        LB_STATE["stats"][key]["errors"] += 1
        
        # 标记后端不健康
        LB_STATE["health"][key] = {
            "status": "unhealthy",
            "last_check": time.time(),
            "error": str(e)
        }
        
        return jsonify({"error": "backend error", "details": str(e)}), 502

@app.route("/stats", methods=["GET"])
def get_stats():
    """获取统计信息"""
    return jsonify(dict(LB_STATE["stats"]))

@app.route("/services", methods=["GET"])
def list_services():
    """列出所有服务"""
    return jsonify({
        "services": list(LB_STATE["services"].keys()),
        "algorithms": LB_STATE["algorithms"]
    })

if __name__ == "__main__":
    init_db()
    
    # 启动后台健康检查
    worker = threading.Thread(target=health_check_worker, daemon=True)
    worker.start()
    
    # 启动API服务
    app.run(host="0.0.0.0", port=18144, debug=False)