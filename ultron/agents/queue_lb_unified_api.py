#!/usr/bin/env python3
"""
Agent任务队列与负载均衡统一监控API
===================================
整合任务队列和负载均衡的状态监控

端口: 18162
"""

import json
import time
import requests
from flask import Flask, jsonify, request
from datetime import datetime

app = Flask(__name__)

# 服务端点配置
QUEUE_API = "http://localhost:18099"
LB_API = "http://localhost:8093"
AUTOSCALER_API = "http://localhost:18160"

def get_queue_status():
    """获取任务队列状态"""
    try:
        resp = requests.get(f"{QUEUE_API}/api/queue/summary", timeout=3)
        return resp.json() if resp.status_code == 200 else None
    except:
        return None

def get_lb_status():
    """获取负载均衡状态"""
    try:
        resp = requests.get(f"{LB_API}/api/stats", timeout=3)
        return resp.json() if resp.status_code == 200 else None
    except:
        return None

def get_autoscaler_status():
    """获取自动扩缩容状态"""
    try:
        resp = requests.get(f"{AUTOSCALER_API}/health", timeout=3)
        return resp.json() if resp.status_code == 200 else None
    except:
        return None

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "service": "queue-lb-unified-monitor",
        "status": "ok",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/summary', methods=['GET'])
def summary():
    """统一摘要 - 整合所有状态"""
    queue = get_queue_status()
    lb = get_lb_status()
    autoscaler = get_autoscaler_status()
    
    # 计算综合健康分
    health_score = 100
    issues = []
    
    if not queue:
        health_score -= 30
        issues.append("任务队列离线")
    if not lb:
        health_score -= 30
        issues.append("负载均衡离线")
    if not autoscaler:
        health_score -= 20
        issues.append("自动扩缩容离线")
    
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "health_score": health_score,
        "issues": issues if issues else ["所有系统正常"],
        "components": {
            "task_queue": {
                "status": "online" if queue else "offline",
                "data": queue
            },
            "load_balancer": {
                "status": "online" if lb else "offline",
                "data": lb
            },
            "auto_scaler": {
                "status": "online" if autoscaler else "offline",
                "data": autoscaler
            }
        },
        "summary": {
            "total_agents": queue.get("agents", {}).get("total", 0) if queue else 0,
            "idle_agents": queue.get("agents", {}).get("idle", 0) if queue else 0,
            "busy_agents": queue.get("agents", {}).get("busy", 0) if queue else 0,
            "pending_tasks": queue.get("tasks", {}).get("pending", 0) if queue else 0,
            "running_tasks": queue.get("tasks", {}).get("running", 0) if queue else 0,
            "completed_tasks": queue.get("tasks", {}).get("completed", 0) if queue else 0
        }
    })

@app.route('/api/queue/stats', methods=['GET'])
def queue_stats():
    """任务队列详细统计"""
    queue = get_queue_status()
    if not queue:
        return jsonify({"error": "任务队列不可用"}), 503
    return jsonify(queue)

@app.route('/api/lb/stats', methods=['GET'])
def lb_stats():
    """负载均衡详细统计"""
    lb = get_lb_status()
    if not lb:
        return jsonify({"error": "负载均衡不可用"}), 503
    return jsonify(lb)

@app.route('/api/agents', methods=['GET'])
def agents():
    """获取所有Agent状态"""
    queue = get_queue_status()
    return jsonify({
        "agents": queue.get("agents", {}) if queue else {},
        "idle_agents": queue.get("idle_agents", []) if queue else []
    })

@app.route('/api/tasks', methods=['GET'])
def tasks():
    """获取所有任务状态"""
    queue = get_queue_status()
    return jsonify({
        "tasks": queue.get("tasks", {}) if queue else {},
        "pending_tasks": queue.get("pending_tasks", []) if queue else []
    })

if __name__ == '__main__':
    print("=" * 50)
    print("Agent任务队列与负载均衡统一监控API")
    print("端口: 18162")
    print("=" * 50)
    app.run(host='0.0.0.0', port=18162, debug=False)