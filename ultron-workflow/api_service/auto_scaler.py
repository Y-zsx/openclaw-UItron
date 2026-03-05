#!/usr/bin/env python3
"""
Agent服务自动扩缩容控制器
根据负载指标自动调整Agent实例数量
"""
import json
import time
import threading
import psutil
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from flask import Flask, jsonify, request
import sqlite3

app = Flask(__name__)

# 配置
SCALING_CONFIG = {
    "min_instances": 1,
    "max_instances": 10,
    "scale_up_threshold": 0.75,  # CPU/内存使用率超过75%时扩容
    "scale_down_threshold": 0.25,  # 低于25%时缩容
    "scale_up_cooldown": 60,  # 扩容冷却时间(秒)
    "scale_down_cooldown": 180,  # 缩容冷却时间(秒)
    "check_interval": 15,  # 检查间隔(秒)
}

# 存储
SCALING_STATE = {
    "instances": {},  # agent_id -> instance_info
    "last_scale_time": {},  # agent_id -> timestamp
    "scaling_history": [],
    "lock": threading.Lock()
}

DB_PATH = "/root/.openclaw/workspace/ultron-workflow/api_service/scaling.db"

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scaling_history
                 (id INTEGER PRIMARY KEY, timestamp TEXT, agent_id TEXT,
                  event TEXT, old_count INTEGER, new_count INTEGER, reason TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS agent_metrics
                 (id INTEGER PRIMARY KEY, timestamp TEXT, agent_id TEXT,
                  cpu REAL, memory REAL, requests INTEGER, latency REAL)''')
    conn.commit()
    conn.close()

def get_agent_metrics(agent_id: str) -> Dict:
    """获取Agent指标"""
    # 尝试从监控API获取
    try:
        resp = requests.get(f"http://localhost:18096/agent/{agent_id}/metrics", timeout=3)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    
    # 返回默认指标
    return {"cpu": 0.3, "memory": 0.4, "requests": 0, "latency": 0}

def calculate_desired_instances(agent_id: str) -> int:
    """计算所需的实例数量"""
    metrics = get_agent_metrics(agent_id)
    
    cpu = metrics.get("cpu", 0)
    memory = metrics.get("memory", 0)
    requests = metrics.get("requests", 0)
    
    current = SCALING_STATE["instances"].get(agent_id, {}).get("count", 1)
    
    # 基于资源使用率和请求量计算
    resource_score = max(cpu, memory)
    
    # 扩容条件
    if resource_score > SCALING_CONFIG["scale_up_threshold"]:
        if current < SCALING_CONFIG["max_instances"]:
            desired = min(current + 1, SCALING_CONFIG["max_instances"])
            return desired
    
    # 缩容条件
    if resource_score < SCALING_CONFIG["scale_down_threshold"]:
        if current > SCALING_CONFIG["min_instances"]:
            desired = max(current - 1, SCALING_CONFIG["min_instances"])
            return desired
    
    return current

def scale_agent(agent_id: str, new_count: int, reason: str) -> bool:
    """执行扩缩容"""
    with SCALING_STATE["lock"]:
        current = SCALING_STATE["instances"].get(agent_id, {}).get("count", 1)
        
        if current == new_count:
            return False
        
        # 检查冷却时间
        last_scale = SCALING_STATE["last_scale_time"].get(agent_id, 0)
        now = time.time()
        
        if new_count > current:
            # 扩容冷却
            if now - last_scale < SCALING_CONFIG["scale_up_cooldown"]:
                return False
        else:
            # 缩容冷却
            if now - last_scale < SCALING_CONFIG["scale_down_cooldown"]:
                return False
        
        # 执行扩缩容
        SCALING_STATE["instances"][agent_id] = {
            "count": new_count,
            "updated": now
        }
        SCALING_STATE["last_scale_time"][agent_id] = now
        
        # 记录历史
        history_entry = {
            "timestamp": datetime.now().isoformat(),
            "agent_id": agent_id,
            "event": "scale_up" if new_count > current else "scale_down",
            "old_count": current,
            "new_count": new_count,
            "reason": reason
        }
        SCALING_STATE["scaling_history"].append(history_entry)
        
        # 保存到数据库
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO scaling_history (timestamp, agent_id, event, old_count, new_count, reason) VALUES (?, ?, ?, ?, ?, ?)",
                  (history_entry["timestamp"], agent_id, history_entry["event"], 
                   current, new_count, reason))
        conn.commit()
        conn.close()
        
        return True

def scaling_worker():
    """后台扩缩容工作线程"""
    while True:
        try:
            # 获取所有注册的Agent
            agents = list(SCALING_STATE["instances"].keys())
            
            for agent_id in agents:
                desired = calculate_desired_instances(agent_id)
                current = SCALING_STATE["instances"].get(agent_id, {}).get("count", 1)
                
                if desired != current:
                    reason = f"resource_usage: cpu/memory"
                    if scale_agent(agent_id, desired, reason):
                        print(f"[AutoScaler] {agent_id}: {current} -> {desired} ({reason})")
        except Exception as e:
            print(f"[AutoScaler] Error: {e}")
        
        time.sleep(SCALING_CONFIG["check_interval"])

# Flask API
@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "auto_scaler"})

@app.route("/register", methods=["POST"])
def register_agent():
    """注册Agent进行扩缩容管理"""
    data = request.json
    agent_id = data.get("agent_id")
    
    if not agent_id:
        return jsonify({"error": "agent_id required"}), 400
    
    with SCALING_STATE["lock"]:
        if agent_id not in SCALING_STATE["instances"]:
            SCALING_STATE["instances"][agent_id] = {
                "count": 1,
                "min": data.get("min", SCALING_CONFIG["min_instances"]),
                "max": data.get("max", SCALING_CONFIG["max_instances"]),
                "registered": time.time()
            }
    
    return jsonify({"status": "registered", "agent_id": agent_id})

@app.route("/instances/<agent_id>", methods=["GET"])
def get_instances(agent_id):
    """获取Agent实例数"""
    info = SCALING_STATE["instances"].get(agent_id, {})
    return jsonify({
        "agent_id": agent_id,
        "count": info.get("count", 1),
        "min": info.get("min", SCALING_CONFIG["min_instances"]),
        "max": info.get("max", SCALING_CONFIG["max_instances"])
    })

@app.route("/instances/<agent_id>", methods=["POST"])
def set_instances(agent_id):
    """手动设置实例数"""
    data = request.json
    count = data.get("count", 1)
    
    count = max(SCALING_CONFIG["min_instances"], 
                min(count, SCALING_CONFIG["max_instances"]))
    
    scale_agent(agent_id, count, "manual")
    
    return jsonify({"status": "updated", "agent_id": agent_id, "count": count})

@app.route("/history", methods=["GET"])
def get_history():
    """获取扩缩容历史"""
    limit = request.args.get("limit", 20, type=int)
    return jsonify({
        "history": SCALING_STATE["scaling_history"][-limit:]
    })

@app.route("/config", methods=["GET", "POST"])
def config():
    """获取/设置配置"""
    global SCALING_CONFIG
    
    if request.method == "POST":
        data = request.json
        SCALING_CONFIG.update(data)
        return jsonify({"status": "updated", "config": SCALING_CONFIG})
    
    return jsonify(SCALING_CONFIG)

if __name__ == "__main__":
    init_db()
    
    # 启动后台工作线程
    worker = threading.Thread(target=scaling_worker, daemon=True)
    worker.start()
    
    # 启动API服务
    app.run(host="0.0.0.0", port=18143, debug=False)