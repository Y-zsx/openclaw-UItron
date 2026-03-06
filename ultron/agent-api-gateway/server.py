#!/usr/bin/env python3
"""Agent服务统一API网关 - 第209世"""

from flask import Flask, request, jsonify
import requests
import uuid
import time
from datetime import datetime
import threading

app = Flask(__name__)

# 路由配置
ROUTES = {
    "/api/agent/chat": {"target": "http://localhost:18301", "timeout": 30},
    "/api/agent/exec": {"target": "http://localhost:18302", "timeout": 30},
    "/api/agent/monitor": {"target": "http://localhost:18304", "timeout": 10},
    "/api/agent/logs": {"target": "http://localhost:18305", "timeout": 10},
    "/api/agent/trace": {"target": "http://localhost:18306", "timeout": 10},
    "/api/agent/replay": {"target": "http://localhost:18307", "timeout": 30},
}

# 请求统计
STATS = {"total": 0, "success": 0, "failed": 0, "requests": []}
STATS_LOCK = threading.Lock()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok", 
        "service": "api-gateway",
        "port": 18309,
        "routes": len(ROUTES),
        "stats": {"total": STATS["total"], "success": STATS["success"], "failed": STATS["failed"]}
    })

@app.route("/routes", methods=["GET"])
def list_routes():
    return jsonify({"routes": ROUTES})

@app.route("/stats", methods=["GET"])
def get_stats():
    return jsonify(STATS)

@app.route("/stats/reset", methods=["POST"])
def reset_stats():
    with STATS_LOCK:
        STATS["total"] = 0
        STATS["success"] = 0
        STATS["failed"] = 0
        STATS["requests"] = []
    return jsonify({"status": "reset"})

@app.route("/proxy/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE"])
def proxy(subpath):
    path = f"/{subpath}"
    
    # 路由查找
    route = None
    for route_path, config in ROUTES.items():
        if path.startswith(route_path):
            route = config
            break
    
    if not route:
        return jsonify({"error": "No route configured", "path": path}), 404
    
    target_url = route["target"] + path
    start_time = time.time()
    
    try:
        # 转发请求
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers={k: v for k, v in request.headers if k.lower() != "host"},
            json=request.get_json() if request.is_json else None,
            params=request.args,
            timeout=route["timeout"]
        )
        
        duration = time.time() - start_time
        
        with STATS_LOCK:
            STATS["total"] += 1
            STATS["success"] += 1
            STATS["requests"].append({
                "path": path,
                "method": request.method,
                "status": resp.status_code,
                "duration": round(duration, 3),
                "time": datetime.now().isoformat()
            })
            # 保留最近100条
            STATS["requests"] = STATS["requests"][-100:]
        
        return resp.content, resp.status_code, resp.headers.items()
        
    except Exception as e:
        duration = time.time() - start_time
        
        with STATS_LOCK:
            STATS["total"] += 1
            STATS["failed"] += 1
            STATS["requests"].append({
                "path": path,
                "method": request.method,
                "status": 0,
                "error": str(e),
                "duration": round(duration, 3),
                "time": datetime.now().isoformat()
            })
        
        return jsonify({"error": str(e), "path": path}), 502

if __name__ == "__main__":
    print("🚀 Agent服务统一API网关 启动在端口 18309")
    print("📍 已配置路由:")
    for path, config in ROUTES.items():
        print(f"   {path} -> {config['target']}")
    app.run(host="0.0.0.0", port=18309, debug=False)
