#!/usr/bin/env python3
"""
Agent服务动态负载均衡器
支持：动态后端发现、智能健康检查、多算法、自适应流量分配
"""
import json
import time
import random
import threading
import socket
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from flask import Flask, jsonify, request
from collections import defaultdict
from dataclasses import dataclass, field
import sqlite3

app = Flask(__name__)

# 配置
PORT = 18310
DB_PATH = "/root/.openclaw/workspace/ultron-workflow/agents/lb_dynamic.db"

# 负载均衡算法
ALGORITHMS = {
    "round_robin": "轮询",
    "least_conn": "最少连接",
    "weighted": "加权轮询",
    "ip_hash": "源IP哈希",
    "random": "随机",
    "adaptive": "自适应 - 基于性能和健康状态",
    "latency": "延迟优先 - 选择延迟最低的后端"
}

@dataclass
class Backend:
    host: str
    port: int
    weight: int = 1
    max_connections: int = 100
    timeout: int = 30
    health_url: str = ""
    service: str = ""
    
    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"
    
    @property
    def key(self) -> str:
        return f"{self.host}:{self.port}"

@dataclass
class HealthStatus:
    status: str = "unknown"
    last_check: float = 0
    latency: float = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_checks: int = 0
    total_failures: int = 0
    response_time_avg: float = 0
    requests_total: int = 0
    errors_total: int = 0

class LoadBalancerState:
    def __init__(self):
        self.lock = threading.RLock()
        self.services: Dict[str, List[Backend]] = {}
        self.algorithms: Dict[str, str] = {}
        self.health: Dict[str, HealthStatus] = {}
        self.stats: Dict[str, Dict] = defaultdict(lambda: {
            "requests": 0, "errors": 0, "latency_sum": 0, 
            "active_connections": 0, "last_request": 0
        })
        self.sticky_sessions: Dict[str, str] = {}
        self.rr_indices: Dict[str, int] = {}
        self.running = True
    
    def get_backend_key(self, service: str, backend: Backend) -> str:
        return f"{service}:{backend.key}"

state = LoadBalancerState()

def init_db():
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

def health_check(backend: Backend) -> tuple[bool, float, str]:
    try:
        url = backend.health_url or f"{backend.url}/health"
        start = time.time()
        resp = requests.get(url, timeout=5)
        latency = (time.time() - start) * 1000
        return resp.status_code == 200, latency, ""
    except Exception as e:
        return False, 5000, str(e)

def health_check_worker():
    while state.running:
        try:
            with state.lock:
                services_backends = list(state.services.items())
            
            for service, backends in services_backends:
                for backend in backends:
                    key = state.get_backend_key(service, backend)
                    is_healthy, latency, error = health_check(backend)
                    now = time.time()
                    
                    if key not in state.health:
                        state.health[key] = HealthStatus()
                    
                    hs = state.health[key]
                    hs.last_check = now
                    hs.latency = latency
                    hs.total_checks += 1
                    
                    if is_healthy:
                        hs.consecutive_successes += 1
                        hs.consecutive_failures = 0
                        hs.status = "healthy"
                    else:
                        hs.consecutive_failures += 1
                        hs.consecutive_successes = 0
                        hs.total_failures += 1
                        hs.status = "unhealthy" if hs.consecutive_failures >= 3 else "degraded"
                    
                    if hs.response_time_avg == 0:
                        hs.response_time_avg = latency
                    else:
                        hs.response_time_avg = hs.response_time_avg * 0.9 + latency * 0.1
        except Exception as e:
            print(f"[DynamicLB] Health check error: {e}")
        
        time.sleep(5)

def get_healthy_backends(service: str) -> List[Backend]:
    with state.lock:
        backends = state.services.get(service, []).copy()
    
    if not backends:
        return []
    
    result = []
    for b in backends:
        key = state.get_backend_key(service, b)
        hs = state.health.get(key)
        
        if hs is None or hs.status == "healthy" or hs.status == "degraded":
            result.append(b)
    
    return result if result else backends

def select_round_robin(service: str, backends: List[Backend]) -> Optional[Backend]:
    with state.lock:
        key = f"{service}:rr"
        idx = state.rr_indices.get(key, 0)
    
    backend = backends[idx % len(backends)]
    
    with state.lock:
        state.rr_indices[key] = (idx + 1) % len(backends)
    
    return backend

def select_least_conn(service: str, backends: List[Backend]) -> Optional[Backend]:
    min_conn = float('inf')
    selected = None
    
    for b in backends:
        key = state.get_backend_key(service, b)
        conns = state.stats.get(key, {}).get("active_connections", 0)
        
        if conns < min_conn:
            min_conn = conns
            selected = b
    
    return selected

def select_weighted(service: str, backends: List[Backend]) -> Optional[Backend]:
    weights = []
    for b in backends:
        key = state.get_backend_key(service, b)
        hs = state.health.get(key)
        
        base_weight = b.weight
        
        if hs:
            if hs.status == "healthy":
                factor = 1.0
            elif hs.status == "degraded":
                factor = 0.5
            else:
                factor = 0.1
            
            if hs.response_time_avg > 0:
                if hs.response_time_avg < 100:
                    factor *= 1.2
                elif hs.response_time_avg > 1000:
                    factor *= 0.5
            
            base_weight *= factor
        
        weights.append(max(0.1, base_weight))
    
    total = sum(weights)
    r = random.random() * total
    cumulative = 0
    
    for i, w in enumerate(weights):
        cumulative += w
        if r <= cumulative:
            return backends[i]
    
    return backends[-1]

def select_ip_hash(service: str, backends: List[Backend], client_ip: str) -> Optional[Backend]:
    if not client_ip:
        return backends[0] if backends else None
    
    if client_ip in state.sticky_sessions:
        saved_key = state.sticky_sessions[client_ip]
        for b in backends:
            if state.get_backend_key(service, b) == saved_key:
                return b
    
    idx = hash(client_ip) % len(backends)
    backend = backends[idx]
    state.sticky_sessions[client_ip] = state.get_backend_key(service, backend)
    
    return backend

def select_random(service: str, backends: List[Backend]) -> Optional[Backend]:
    return random.choice(backends) if backends else None

def select_adaptive(service: str, backends: List[Backend]) -> Optional[Backend]:
    scores = []
    
    for b in backends:
        key = state.get_backend_key(service, b)
        hs = state.health.get(key)
        stats = state.stats.get(key, {})
        
        score = 100
        
        if hs:
            if hs.status == "healthy":
                score += 20
            elif hs.status == "degraded":
                score -= 20
            else:
                score -= 50
            
            if hs.response_time_avg > 0:
                if hs.response_time_avg < 50:
                    score += 15
                elif hs.response_time_avg < 200:
                    score += 10
                elif hs.response_time_avg > 1000:
                    score -= 20
            
            if hs.requests_total > 0:
                error_rate = hs.errors_total / hs.requests_total
                score -= error_rate * 50
        
        active = stats.get("active_connections", 0)
        max_conn = b.max_connections
        if active > max_conn * 0.8:
            score -= 30
        elif active > max_conn * 0.5:
            score -= 10
        
        score += b.weight * 5
        
        scores.append((score, b))
    
    scores.sort(key=lambda x: -x[0])
    top_n = max(1, len(scores) // 3)
    selected, _ = random.choice(scores[:top_n])
    return selected

def select_latency(service: str, backends: List[Backend]) -> Optional[Backend]:
    best = None
    best_latency = float('inf')
    
    for b in backends:
        key = state.get_backend_key(service, b)
        hs = state.health.get(key)
        
        latency = hs.response_time_avg if hs and hs.response_time_avg > 0 else float('inf')
        
        if latency < best_latency:
            best_latency = latency
            best = b
    
    return best if best else (backends[0] if backends else None)

def route_request(service: str, client_ip: str = None) -> Optional[tuple[Backend, str]]:
    with state.lock:
        backends = get_healthy_backends(service)
        
        if not backends:
            return None
        
        algorithm = state.algorithms.get(service, "adaptive")
        
        if algorithm == "round_robin":
            backend = select_round_robin(service, backends)
        elif algorithm == "least_conn":
            backend = select_least_conn(service, backends)
        elif algorithm == "weighted":
            backend = select_weighted(service, backends)
        elif algorithm == "ip_hash":
            backend = select_ip_hash(service, backends, client_ip)
        elif algorithm == "random":
            backend = select_random(service, backends)
        elif algorithm == "adaptive":
            backend = select_adaptive(service, backends)
        elif algorithm == "latency":
            backend = select_latency(service, backends)
        else:
            backend = backends[0]
        
        if backend:
            key = state.get_backend_key(service, backend)
            state.stats[key]["active_connections"] += 1
            state.stats[key]["requests"] += 1
            state.stats[key]["last_request"] = time.time()
            
            if key in state.health:
                state.health[key].requests_total += 1
            
            return backend, algorithm
        
        return None

def release_connection(service: str, backend: Backend, success: bool, latency: float):
    key = state.get_backend_key(service, backend)
    
    with state.lock:
        if key in state.stats:
            state.stats[key]["active_connections"] = max(0, state.stats[key]["active_connections"] - 1)
            state.stats[key]["latency_sum"] += latency
            if not success:
                state.stats[key]["errors"] += 1
        
        if key in state.health:
            if not success:
                state.health[key].errors_total += 1

# ============== API Endpoints ==============

@app.route("/")
def dashboard():
    """JSON格式的仪表盘"""
    with state.lock:
        services = list(state.services.keys())
        algorithms = dict(state.algorithms)
    
    result = []
    for svc in services:
        backends = []
        healthy_count = 0
        
        with state.lock:
            svc_backends = state.services.get(svc, [])
        
        for b in svc_backends:
            key = state.get_backend_key(svc, b)
            hs = state.health.get(key)
            
            if hs and hs.status == "healthy":
                healthy_count += 1
            
            backends.append({
                "host": b.host,
                "port": b.port,
                "weight": b.weight,
                "health": hs.status if hs else "unknown",
                "latency_ms": round(hs.response_time_avg, 1) if hs else 0
            })
        
        result.append({
            "service": svc,
            "algorithm": algorithms.get(svc, "adaptive"),
            "backends": backends,
            "healthy_count": healthy_count
        })
    
    return jsonify({
        "service": "dynamic_load_balancer",
        "port": PORT,
        "services": result
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "dynamic_load_balancer", "port": PORT})

@app.route("/api/service", methods=["POST"])
def add_service():
    data = request.json
    service = data.get("service")
    algorithm = data.get("algorithm", "adaptive")
    backends = data.get("backends", [])
    
    if not service:
        return jsonify({"error": "service required"}), 400
    
    if algorithm not in ALGORITHMS:
        return jsonify({"error": f"invalid algorithm: {list(ALGORITHMS.keys())}"}), 400
    
    with state.lock:
        state.services[service] = [Backend(**b) for b in backends]
        state.algorithms[service] = algorithm
    
    return jsonify({"status": "added", "service": service, "algorithm": algorithm})

@app.route("/api/service/<service>", methods=["GET"])
def get_service(service):
    with state.lock:
        backends = state.services.get(service, [])
        algorithm = state.algorithms.get(service, "adaptive")
    
    result = []
    for b in backends:
        key = f"{service}:{b.key}"
        hs = state.health.get(key)
        st = state.stats.get(key, {})
        
        result.append({
            "host": b.host,
            "port": b.port,
            "weight": b.weight,
            "health": hs.status if hs else "unknown",
            "latency_ms": round(hs.response_time_avg, 1) if hs else 0,
            "requests": hs.requests_total if hs else 0,
            "errors": hs.errors_total if hs else 0,
            "active_connections": st.get("active_connections", 0)
        })
    
    return jsonify({
        "service": service,
        "algorithm": algorithm,
        "algorithm_name": ALGORITHMS.get(algorithm, algorithm),
        "backends": result,
        "healthy_count": len([r for r in result if r["health"] == "healthy"])
    })

@app.route("/api/service/<service>/backend", methods=["POST"])
def add_backend(service):
    data = request.json
    
    with state.lock:
        if service not in state.services:
            state.services[service] = []
        
        backend = Backend(
            host=data.get("host", "localhost"),
            port=data.get("port", 8000),
            weight=data.get("weight", 1),
            max_connections=data.get("max_connections", 100),
            timeout=data.get("timeout", 30),
            health_url=data.get("health_url", ""),
            service=service
        )
        
        state.services[service].append(backend)
    
    return jsonify({"status": "added", "backend": backend.key})

@app.route("/api/service/<service>/algorithm", methods=["POST"])
def set_algorithm(service):
    data = request.json
    algorithm = data.get("algorithm")
    
    if algorithm not in ALGORITHMS:
        return jsonify({"error": f"invalid algorithm: {list(ALGORITHMS.keys())}"}), 400
    
    with state.lock:
        state.algorithms[service] = algorithm
    
    return jsonify({"status": "updated", "algorithm": algorithm, "name": ALGORITHMS[algorithm]})

@app.route("/api/proxy/<service>", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def proxy(service):
    client_ip = request.remote_addr
    
    result = route_request(service, client_ip)
    
    if not result:
        return jsonify({"error": "no healthy backend"}), 503
    
    backend, algorithm = result
    
    path = request.path.replace(f"/api/proxy/{service}", "") or "/"
    url = f"{backend.url}{path}"
    
    start_time = time.time()
    success = False
    
    try:
        resp = requests.request(
            method=request.method,
            url=url,
            headers={k: v for k, v in request.headers if k.lower() != "host"},
            json=request.get_json() if request.is_json else None,
            data=request.get_data(),
            timeout=backend.timeout,
            allow_redirects=False
        )
        
        success = resp.status_code < 400
        latency = (time.time() - start_time) * 1000
        
        release_connection(service, backend, success, latency)
        
        return resp.content, resp.status_code, resp.headers.items()
    
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        release_connection(service, backend, False, latency)
        
        return jsonify({"error": "proxy failed", "details": str(e)}), 502

@app.route("/api/stats", methods=["GET"])
def get_stats():
    with state.lock:
        stats = {}
        for key, data in state.stats.items():
            parts = key.split(":")
            if len(parts) >= 3:
                service = parts[0]
                backend = ":".join(parts[1:])
            else:
                service = "unknown"
                backend = key
            
            stats[key] = {
                "service": service,
                "backend": backend,
                "requests": data["requests"],
                "errors": data["errors"],
                "avg_latency": data["latency_sum"] / data["requests"] if data["requests"] > 0 else 0,
                "active_connections": data["active_connections"]
            }
    
    return jsonify(stats)

@app.route("/api/services", methods=["GET"])
def list_services():
    with state.lock:
        return jsonify({
            "services": list(state.services.keys()),
            "algorithms": dict(state.algorithms)
        })

@app.route("/api/health", methods=["GET"])
def get_all_health():
    with state.lock:
        result = {}
        for key, hs in state.health.items():
            result[key] = {
                "status": hs.status,
                "latency_ms": round(hs.response_time_avg, 1),
                "requests": hs.requests_total,
                "errors": hs.errors_total,
                "last_check": hs.last_check
            }
        return jsonify(result)

if __name__ == "__main__":
    init_db()
    
    state.health_check_thread = threading.Thread(target=health_check_worker, daemon=True)
    state.health_check_thread.start()
    
    print(f"[DynamicLB] Starting on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)