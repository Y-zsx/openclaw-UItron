#!/usr/bin/env python3
"""
奥创智能成本优化系统
Agent协作网络智能成本优化
"""

import json
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, jsonify, request
import psutil

# 配置
DB_PATH = "/root/.openclaw/workspace/ultron/cost_optimizer/cost_data.db"
PORT = 18242

app = Flask(__name__)

# 成本配置 (每小时成本，单位：元)
COST_CONFIG = {
    "cpu_per_core_per_hour": 0.1,  # 每核CPU每小时0.1元
    "memory_per_gb_per_hour": 0.05,  # 每GB内存每小时0.05元
    "disk_per_gb_per_hour": 0.01,  # 每GB磁盘每小时0.01元
    "network_per_gb_per_hour": 0.5,  # 每GB网络流量0.5元
}

def init_db():
    """初始化数据库"""
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 资源使用记录
    c.execute('''CREATE TABLE IF NOT EXISTS resource_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        cpu_cores REAL,
        cpu_percent REAL,
        memory_gb REAL,
        memory_percent REAL,
        disk_gb REAL,
        disk_percent REAL,
        network_mb REAL,
        cost_per_hour REAL
    )''')
    
    # 优化建议记录
    c.execute('''CREATE TABLE IF NOT EXISTS optimization_suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        category TEXT,
        description TEXT,
        potential_savings REAL,
        status TEXT DEFAULT 'pending',
        implemented INTEGER DEFAULT 0
    )''')
    
    # 成本统计
    c.execute('''CREATE TABLE IF NOT EXISTS cost_stats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        total_cost REAL,
        cpu_cost REAL,
        memory_cost REAL,
        disk_cost REAL,
        network_cost REAL
    )''')
    
    conn.commit()
    conn.close()

def get_system_metrics():
    """获取系统资源指标"""
    cpu_count = psutil.cpu_count()
    cpu_percent = psutil.cpu_percent(interval=0.5)
    
    memory = psutil.virtual_memory()
    memory_gb = memory.used / (1024**3)
    memory_percent = memory.percent
    
    disk = psutil.disk_usage('/')
    disk_gb = disk.used / (1024**3)
    disk_percent = disk.percent
    
    # 网络流量 (累计)
    net_io = psutil.net_io_counters()
    network_mb = (net_io.bytes_sent + net_io.bytes_recv) / (1024**2)
    
    return {
        "cpu_cores": cpu_count,
        "cpu_percent": cpu_percent,
        "memory_gb": round(memory_gb, 2),
        "memory_percent": memory_percent,
        "disk_gb": round(disk_gb, 2),
        "disk_percent": disk_percent,
        "network_mb": round(network_mb, 2)
    }

def calculate_cost(metrics):
    """计算当前资源成本"""
    cpu_cost = metrics["cpu_cores"] * (metrics["cpu_percent"] / 100) * COST_CONFIG["cpu_per_core_per_hour"]
    memory_cost = metrics["memory_gb"] * (metrics["memory_percent"] / 100) * COST_CONFIG["memory_per_gb_per_hour"]
    disk_cost = metrics["disk_gb"] * COST_CONFIG["disk_per_gb_per_hour"]
    network_cost = metrics["network_mb"] / 1024 * COST_CONFIG["network_per_gb_per_hour"]
    
    total_cost = cpu_cost + memory_cost + disk_cost + network_cost
    
    return {
        "total_per_hour": round(total_cost, 4),
        "cpu": round(cpu_cost, 4),
        "memory": round(memory_cost, 4),
        "disk": round(disk_cost, 4),
        "network": round(network_cost, 4)
    }

def generate_optimization_suggestions(metrics, cost):
    """生成成本优化建议"""
    suggestions = []
    
    # CPU优化建议
    if metrics["cpu_percent"] < 20:
        suggestions.append({
            "category": "CPU",
            "description": "CPU利用率较低(%.1f%%)，可考虑缩减CPU核心数或合并服务" % metrics["cpu_percent"],
            "potential_savings": round(cost["cpu"] * 0.3, 4)
        })
    elif metrics["cpu_percent"] > 80:
        suggestions.append({
            "category": "CPU",
            "description": "CPU使用率较高(%.1f%%)，建议优化应用或升级配置" % metrics["cpu_percent"],
            "potential_savings": 0
        })
    
    # 内存优化建议
    if metrics["memory_percent"] < 40:
        suggestions.append({
            "category": "Memory",
            "description": "内存利用率较低(%.1f%%)，可考虑缩减内存配置" % metrics["memory_percent"],
            "potential_savings": round(cost["memory"] * 0.4, 4)
        })
    elif metrics["memory_percent"] > 85:
        suggestions.append({
            "category": "Memory",
            "description": "内存使用率较高(%.1f%%)，建议优化内存使用或增加内存" % metrics["memory_percent"],
            "potential_savings": 0
        })
    
    # 磁盘优化建议
    if metrics["disk_percent"] > 80:
        suggestions.append({
            "category": "Disk",
            "description": "磁盘使用率较高(%.1f%%)，建议清理不必要的文件或扩容" % metrics["disk_percent"],
            "potential_savings": 0
        })
    
    return suggestions

def save_metrics(metrics, cost):
    """保存资源使用数据"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''INSERT INTO resource_usage 
        (timestamp, cpu_cores, cpu_percent, memory_gb, memory_percent, 
         disk_gb, disk_percent, network_mb, cost_per_hour)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
        (datetime.now().isoformat(),
         metrics["cpu_cores"], metrics["cpu_percent"],
         metrics["memory_gb"], metrics["memory_percent"],
         metrics["disk_gb"], metrics["disk_percent"],
         metrics["network_mb"], cost["total_per_hour"]))
    
    conn.commit()
    conn.close()

# API 路由
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "cost-optimizer"})

@app.route('/metrics', methods=['GET'])
def current_metrics():
    """获取当前资源指标和成本"""
    metrics = get_system_metrics()
    cost = calculate_cost(metrics)
    return jsonify({
        "metrics": metrics,
        "cost": cost,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/cost-history', methods=['GET'])
def cost_history():
    """获取成本历史"""
    hours = request.args.get('hours', 24, type=int)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    c.execute('''SELECT timestamp, cost_per_hour FROM resource_usage 
                 WHERE timestamp > ? ORDER BY timestamp''', (since,))
    
    rows = c.fetchall()
    conn.close()
    
    history = [{"timestamp": r[0], "cost_per_hour": r[1]} for r in rows]
    return jsonify({"history": history})

@app.route('/suggestions', methods=['GET'])
def suggestions():
    """获取优化建议"""
    metrics = get_system_metrics()
    cost = calculate_cost(metrics)
    opt_suggestions = generate_optimization_suggestions(metrics, cost)
    
    return jsonify({
        "suggestions": opt_suggestions,
        "total_potential_savings": round(sum(s["potential_savings"] for s in opt_suggestions), 4),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/efficiency', methods=['GET'])
def efficiency():
    """获取资源使用效率评分"""
    metrics = get_system_metrics()
    
    # 计算效率分数 (0-100)
    cpu_score = 100 - abs(50 - metrics["cpu_percent"]) * 2
    memory_score = 100 - abs(50 - metrics["memory_percent"]) * 1.5
    disk_score = 100 - metrics["disk_percent"] * 0.5
    
    efficiency_score = (cpu_score + memory_score + disk_score) / 3
    efficiency_score = max(0, min(100, efficiency_score))
    
    return jsonify({
        "efficiency_score": round(efficiency_score, 1),
        "cpu_score": round(cpu_score, 1),
        "memory_score": round(memory_score, 1),
        "disk_score": round(disk_score, 1),
        "recommendation": "优化" if efficiency_score < 60 else "良好" if efficiency_score < 80 else "优秀",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/summary', methods=['GET'])
def summary():
    """获取成本优化摘要"""
    metrics = get_system_metrics()
    cost = calculate_cost(metrics)
    opt_suggestions = generate_optimization_suggestions(metrics, cost)
    
    # 效率评分
    cpu_score = 100 - abs(50 - metrics["cpu_percent"]) * 2
    memory_score = 100 - abs(50 - metrics["memory_percent"]) * 1.5
    disk_score = 100 - metrics["disk_percent"] * 0.5
    efficiency_score = max(0, min(100, (cpu_score + memory_score + disk_score) / 3))
    
    return jsonify({
        "system": {
            "cpu_cores": metrics["cpu_cores"],
            "cpu_percent": metrics["cpu_percent"],
            "memory_gb": metrics["memory_gb"],
            "memory_percent": metrics["memory_percent"],
            "disk_gb": metrics["disk_gb"],
            "disk_percent": metrics["disk_percent"]
        },
        "cost_per_hour": cost,
        "efficiency_score": round(efficiency_score, 1),
        "suggestions": opt_suggestions,
        "potential_monthly_savings": round(sum(s["potential_savings"] for s in opt_suggestions) * 24 * 30, 2),
        "timestamp": datetime.now().isoformat()
    })

def collect_metrics_loop():
    """后台收集指标"""
    while True:
        try:
            metrics = get_system_metrics()
            cost = calculate_cost(metrics)
            save_metrics(metrics, cost)
        except Exception as e:
            print(f"Error collecting metrics: {e}")
        time.sleep(300)  # 每5分钟记录一次

if __name__ == '__main__':
    import threading
    init_db()
    
    # 启动后台指标收集
    collector = threading.Thread(target=collect_metrics_loop, daemon=True)
    collector.start()
    
    print(f"Cost Optimizer API running on port {PORT}")
    app.run(host='0.0.0.0', port=PORT, debug=False)