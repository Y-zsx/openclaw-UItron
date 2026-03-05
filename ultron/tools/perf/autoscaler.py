#!/usr/bin/env python3
"""
自动扩缩容与负载均衡服务
Agent服务自动扩缩容与负载均衡
端口: 8097
"""

import asyncio
import json
import time
import sqlite3
import threading
from datetime import datetime
from flask import Flask, jsonify, request
from collections import defaultdict
import requests

app = Flask(__name__)

# 配置
PERF_API_URL = "http://localhost:8095"
DB_PATH = "/root/.openclaw/workspace/ultron/data/autoscaler.db"

# 扩缩容规则
SCALING_RULES = {
    "cpu_high": 80,          # CPU > 80% 扩容
    "cpu_low": 20,           # CPU < 20% 缩容
    "memory_high": 85,       # 内存 > 85% 扩容
    "memory_low": 30,        # 内存 < 30% 缩容
    "request_queue_high": 50, # 请求队列 > 50 扩容
    "request_queue_low": 5,  # 请求队列 < 5 缩容
    "response_time_high": 2000, # 响应时间 > 2s 扩容
    "min_instances": 1,      # 最小实例数
    "max_instances": 10,     # 最大实例数
    "cooldown_seconds": 60,  # 扩缩容冷却时间
}

# 负载均衡策略
LB_STRATEGIES = {
    "round_robin": "轮询",
    "least_connections": "最少连接",
    "weighted": "加权轮询",
    "ip_hash": "IP哈希",
    "adaptive": "自适应",
}

# 内存存储
scaling_history = []
load_balancer_stats = defaultdict(lambda: {"requests": 0, "errors": 0, "latency": 0, "connections": 0})
instance_pool = {}
current_strategy = "adaptive"
health_check_interval = 30

# 初始化数据库
def init_db():
    import os
    os.makedirs("/root/.openclaw/workspace/ultron/data", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scaling_events
                 (id INTEGER PRIMARY KEY, timestamp TEXT, agent TEXT, 
                  event_type TEXT, old_instances INTEGER, new_instances INTEGER,
                  reason TEXT, metrics TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS lb_stats
                 (id INTEGER PRIMARY KEY, timestamp TEXT, agent TEXT,
                  strategy TEXT, requests INTEGER, errors INTEGER,
                  avg_latency REAL)''')
    conn.commit()
    conn.close()

init_db()

def get_perf_metrics():
    """获取性能指标"""
    try:
        resp = requests.get(f"{PERF_API_URL}/snapshot", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return None

def get_agent_metrics():
    """获取Agent指标"""
    try:
        resp = requests.get(f"{PERF_API_URL}/agents", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return {"agents": []}

def calculate_instance_score(agent_name, metrics):
    """计算实例评分"""
    score = 100
    
    if "cpu" in metrics:
        cpu = metrics["cpu"]
        if cpu > SCALING_RULES["cpu_high"]:
            score -= 30
        elif cpu < SCALING_RULES["cpu_low"]:
            score += 10
    
    if "memory" in metrics:
        mem = metrics["memory"]
        if mem > SCALING_RULES["memory_high"]:
            score -= 30
        elif mem < SCALING_RULES["memory_low"]:
            score += 10
    
    if "response_time" in metrics:
        rt = metrics["response_time"]
        if rt > SCALING_RULES["response_time_high"]:
            score -= 20
    
    if "request_count" in metrics:
        score += min(metrics["request_count"] / 10, 20)
    
    return max(0, min(100, score))

def determine_scaling(agent_name, metrics):
    """确定扩缩容决策"""
    current_instances = instance_pool.get(agent_name, {}).get("instances", 1)
    recommended = current_instances
    
    reasons = []
    
    # CPU判断
    if "cpu" in metrics:
        if metrics["cpu"] > SCALING_RULES["cpu_high"]:
            recommended = min(current_instances + 1, SCALING_RULES["max_instances"])
            reasons.append(f"CPU {metrics['cpu']:.1f}% > {SCALING_RULES['cpu_high']}%")
        elif metrics["cpu"] < SCALING_RULES["cpu_low"]:
            recommended = max(current_instances - 1, SCALING_RULES["min_instances"])
            reasons.append(f"CPU {metrics['cpu']:.1f}% < {SCALING_RULES['cpu_low']}%")
    
    # 内存判断
    if "memory" in metrics:
        if metrics["memory"] > SCALING_RULES["memory_high"]:
            recommended = min(current_instances + 1, SCALING_RULES["max_instances"])
            reasons.append(f"内存 {metrics['memory']:.1f}% > {SCALING_RULES['memory_high']}%")
        elif metrics["memory"] < SCALING_RULES["memory_low"]:
            recommended = max(current_instances - 1, SCALING_RULES["min_instances"])
            reasons.append(f"内存 {metrics['memory']:.1f}% < {SCALING_RULES['memory_low']}%")
    
    # 请求队列判断
    if "queue_size" in metrics:
        if metrics["queue_size"] > SCALING_RULES["request_queue_high"]:
            recommended = min(current_instances + 1, SCALING_RULES["max_instances"])
            reasons.append(f"队列 {metrics['queue_size']} > {SCALING_RULES['request_queue_high']}")
        elif metrics["queue_size"] < SCALING_RULES["request_queue_low"]:
            recommended = max(current_instances - 1, SCALING_RULES["min_instances"])
    
    # 响应时间判断
    if "response_time" in metrics:
        if metrics["response_time"] > SCALING_RULES["response_time_high"]:
            recommended = min(current_instances + 1, SCALING_RULES["max_instances"])
            reasons.append(f"响应时间 {metrics['response_time']:.0f}ms > {SCALING_RULES['response_time_high']}ms")
    
    return recommended, current_instances != recommended, reasons

def select_backend(agent_name, strategy=None):
    """负载均衡选择后端"""
    global current_strategy
    strategy = strategy or current_strategy
    
    agent_instances = instance_pool.get(agent_name, {}).get("backends", [])
    if not agent_instances:
        return None
    
    stats = load_balancer_stats[agent_name]
    
    if strategy == "round_robin":
        # 轮询
        return agent_instances[stats["requests"] % len(agent_instances)]
    
    elif strategy == "least_connections":
        # 最少连接
        return min(agent_instances, key=lambda x: stats["connections"])
    
    elif strategy == "weighted":
        # 加权轮询 (基于评分)
        weights = [calculate_instance_score(a, instance_pool.get(agent_name, {}).get(f"metrics_{a}", {})) 
                   for a in agent_instances]
        total = sum(weights)
        if total == 0:
            return agent_instances[0]
        rand = stats["requests"] % total
        cumsum = 0
        for i, w in enumerate(weights):
            cumsum += w
            if rand <= cumsum:
                return agent_instances[i]
        return agent_instances[0]
    
    elif strategy == "ip_hash":
        # IP哈希
        # 简化实现
        return agent_instances[hash(agent_name) % len(agent_instances)]
    
    else:  # adaptive
        # 自适应 - 选择负载最低的
        scores = [(a, calculate_instance_score(a, instance_pool.get(agent_name, {}).get(f"metrics_{a}", {}))) 
                  for a in agent_instances]
        return max(scores, key=lambda x: x[1])[0]

# API端点
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "autoscaler"})

@app.route("/scaling/status", methods=["GET"])
def scaling_status():
    """扩缩容状态"""
    return jsonify({
        "instance_pool": instance_pool,
        "rules": SCALING_RULES,
        "history": scaling_history[-10:]
    })

@app.route("/scaling/decide", methods=["POST"])
def scaling_decide():
    """手动触发扩缩容决策"""
    data = request.json or {}
    agent_name = data.get("agent", "default")
    force = data.get("force", False)
    
    metrics = get_agent_metrics()
    agent_data = next((a for a in metrics.get("agents", []) if a.get("name") == agent_name), None)
    
    if not agent_data:
        # 使用系统指标
        perf = get_perf_metrics()
        agent_data = {
            "cpu": perf.get("system", {}).get("cpu_percent", 0),
            "memory": perf.get("system", {}).get("memory_percent", 0),
        }
    
    recommended, should_scale, reasons = determine_scaling(agent_name, agent_data)
    
    current = instance_pool.get(agent_name, {}).get("instances", 1)
    
    if should_scale or force:
        instance_pool[agent_name] = {
            "instances": recommended,
            "backends": [f"{agent_name}-{i}" for i in range(recommended)],
            "last_update": time.time()
        }
        
        # 记录事件
        event = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "event_type": "scale_up" if recommended > current else "scale_down",
            "old_instances": current,
            "new_instances": recommended,
            "reason": "; ".join(reasons) if reasons else "手动触发"
        }
        scaling_history.append(event)
        
        # 存入数据库
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO scaling_events (timestamp, agent, event_type, old_instances, new_instances, reason, metrics) VALUES (?, ?, ?, ?, ?, ?, ?)",
                  (event["timestamp"], event["agent"], event["event_type"], 
                   event["old_instances"], event["new_instances"], 
                   event["reason"], json.dumps(agent_data)))
        conn.commit()
        conn.close()
    
    return jsonify({
        "agent": agent_name,
        "current_instances": current,
        "recommended_instances": recommended,
        "scaled": should_scale or force,
        "reasons": reasons,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/scaling/history", methods=["GET"])
def scaling_history_api():
    """扩缩容历史"""
    limit = request.args.get("limit", 20, type=int)
    return jsonify({
        "history": scaling_history[-limit:],
        "total": len(scaling_history)
    })

@app.route("/lb/status", methods=["GET"])
def lb_status():
    """负载均衡状态"""
    return jsonify({
        "current_strategy": current_strategy,
        "strategies": LB_STRATEGIES,
        "stats": dict(load_balancer_stats)
    })

@app.route("/lb/select", methods=["POST"])
def lb_select():
    """负载均衡选择后端"""
    data = request.json or {}
    agent_name = data.get("agent", "default")
    strategy = data.get("strategy", current_strategy)
    
    backend = select_backend(agent_name, strategy)
    
    load_balancer_stats[agent_name]["requests"] += 1
    
    return jsonify({
        "agent": agent_name,
        "strategy": strategy,
        "selected_backend": backend,
        "total_requests": load_balancer_stats[agent_name]["requests"]
    })

@app.route("/lb/strategy", methods=["POST"])
def set_strategy():
    """设置负载均衡策略"""
    data = request.json or {}
    strategy = data.get("strategy", "adaptive")
    
    if strategy not in LB_STRATEGIES:
        return jsonify({"error": "无效策略"}), 400
    
    global current_strategy
    current_strategy = strategy
    
    return jsonify({
        "success": True,
        "strategy": strategy,
        "description": LB_STRATEGIES[strategy]
    })

@app.route("/lb/stats", methods=["POST"])
def update_lb_stats():
    """更新负载均衡统计"""
    data = request.json or {}
    agent_name = data.get("agent", "default")
    
    if "requests" in data:
        load_balancer_stats[agent_name]["requests"] = data["requests"]
    if "errors" in data:
        load_balancer_stats[agent_name]["errors"] = data["errors"]
    if "latency" in data:
        load_balancer_stats[agent_name]["latency"] = data["latency"]
    if "connections" in data:
        load_balancer_stats[agent_name]["connections"] = data["connections"]
    
    return jsonify({"success": True})

@app.route("/rules", methods=["GET", "POST"])
def scaling_rules_api():
    """扩缩容规则配置"""
    global SCALING_RULES
    
    if request.method == "GET":
        return jsonify(SCALING_RULES)
    
    # POST - 更新规则
    data = request.json or {}
    for key in SCALING_RULES:
        if key in data:
            SCALING_RULES[key] = data[key]
    
    return jsonify({
        "success": True,
        "rules": SCALING_RULES
    })

@app.route("/snapshot", methods=["GET"])
def snapshot():
    """完整快照"""
    perf = get_perf_metrics()
    agents = get_agent_metrics()
    
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "scaling": {
            "instance_pool": instance_pool,
            "rules": SCALING_RULES,
            "history_count": len(scaling_history)
        },
        "load_balancer": {
            "strategy": current_strategy,
            "strategies": LB_STRATEGIES,
            "stats": dict(load_balancer_stats)
        },
        "performance": perf,
        "agents": agents
    })

# 自动扩缩容任务
def auto_scaling_loop():
    """自动扩缩容循环"""
    while True:
        try:
            # 获取所有注册Agent
            agents = get_agent_metrics()
            
            for agent in agents.get("agents", []):
                agent_name = agent.get("name", "unknown")
                recommended, should_scale, reasons = determine_scaling(agent_name, agent)
                
                current = instance_pool.get(agent_name, {}).get("instances", 1)
                
                if should_scale:
                    instance_pool[agent_name] = {
                        "instances": recommended,
                        "backends": [f"{agent_name}-{i}" for i in range(recommended)],
                        "last_update": time.time()
                    }
                    
                    event = {
                        "timestamp": datetime.now().isoformat(),
                        "agent": agent_name,
                        "event_type": "scale_up" if recommended > current else "scale_down",
                        "old_instances": current,
                        "new_instances": recommended,
                        "reason": "; ".join(reasons) if reasons else "自动触发"
                    }
                    scaling_history.append(event)
                    
                    # 冷却
                    time.sleep(SCALING_RULES["cooldown_seconds"])
        
        except Exception as e:
            print(f"自动扩缩容错误: {e}")
        
        time.sleep(30)

# 启动自动扩缩容线程
def start_auto_scaling():
    thread = threading.Thread(target=auto_scaling_loop, daemon=True)
    thread.start()

if __name__ == "__main__":
    # 初始化默认Agent实例
    default_agents = ["agent-alpha", "agent-beta", "api-gateway", "service-mesh", 
                     "agent-orchestrator", "workflow-engine", "agent-deployer"]
    
    for agent in default_agents:
        instance_pool[agent] = {
            "instances": 1,
            "backends": [f"{agent}-0"],
            "last_update": time.time()
        }
    
    start_auto_scaling()
    print("🚀 自动扩缩容服务启动 (端口8100)")
    app.run(host="0.0.0.0", port=8100, debug=False)