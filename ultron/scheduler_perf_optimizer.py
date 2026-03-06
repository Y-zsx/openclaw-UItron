#!/usr/bin/env python3
"""
调度器性能优化服务
提供调度器性能监控和优化建议
端口: 18218
"""

import json
import time
import psutil
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from collections import deque

app = Flask(__name__)

# 性能指标缓存
METRICS_CACHE = {
    "data": {},
    "last_update": 0,
    "cache_ttl": 30  # 30秒缓存
}

# 历史性能数据（最近100条）
PERFORMANCE_HISTORY = deque(maxlen=100)

def get_scheduler_processes():
    """获取调度器相关进程"""
    processes = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'cmdline']):
        try:
            cmdline = p.info.get('cmdline', [])
            if cmdline and any('scheduler' in str(c).lower() for c in cmdline):
                processes.append({
                    "pid": p.info['pid'],
                    "name": p.info['name'],
                    "cpu": p.info['cpu_percent'],
                    "memory": round(p.info['memory_percent'], 2),
                    "cmdline": ' '.join(cmdline[:3])
                })
        except:
            pass
    return processes

def get_db_stats(db_path):
    """获取数据库统计"""
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # 表统计
        tables = {}
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        for row in c.fetchall():
            table_name = row[0]
            c.execute(f"SELECT COUNT(*) FROM {table_name}")
            tables[table_name] = c.fetchone()[0]
        
        conn.close()
        return tables
    except:
        return {}

def calculate_performance_score(metrics):
    """计算性能得分 (0-100)"""
    score = 100
    
    # CPU使用扣分
    if metrics.get('cpu_percent', 0) > 80:
        score -= 20
    elif metrics.get('cpu_percent', 0) > 60:
        score -= 10
    
    # 内存使用扣分
    if metrics.get('memory_percent', 0) > 85:
        score -= 20
    elif metrics.get('memory_percent', 0) > 70:
        score -= 10
    
    # 磁盘IO扣分
    if metrics.get('disk_io', 0) > 100:
        score -= 10
    
    # 网络延迟扣分
    if metrics.get('avg_response_time', 0) > 1000:
        score -= 15
    elif metrics.get('avg_response_time', 0) > 500:
        score -= 5
    
    # 队列深度扣分
    if metrics.get('queue_depth', 0) > 100:
        score -= 15
    elif metrics.get('queue_depth', 0) > 50:
        score -= 5
    
    return max(0, score)

def get_optimization_suggestions(metrics, score):
    """根据性能指标生成优化建议"""
    suggestions = []
    
    if metrics.get('cpu_percent', 0) > 70:
        suggestions.append({
            "type": "cpu",
            "priority": "high",
            "message": "CPU使用率较高，建议优化调度算法或增加检查间隔"
        })
    
    if metrics.get('memory_percent', 0) > 75:
        suggestions.append({
            "type": "memory",
            "priority": "high", 
            "message": "内存使用率较高，建议清理缓存或增加内存"
        })
    
    if metrics.get('avg_response_time', 0) > 1000:
        suggestions.append({
            "type": "performance",
            "priority": "medium",
            "message": "响应时间较长，建议启用缓存或优化数据库查询"
        })
    
    if metrics.get('queue_depth', 0) > 50:
        suggestions.append({
            "type": "queue",
            "priority": "medium",
            "message": "队列积压较多，建议增加并发处理能力"
        })
    
    if score > 80:
        suggestions.append({
            "type": "status",
            "priority": "info",
            "message": "系统运行良好，无需优化"
        })
    
    return suggestions

@app.route('/api/performance', methods=['GET'])
def performance():
    """获取实时性能指标"""
    current_time = time.time()
    
    # 缓存检查
    if current_time - METRICS_CACHE["last_update"] < METRICS_CACHE["cache_ttl"]:
        return jsonify(METRICS_CACHE["data"])
    
    # CPU和内存
    cpu_percent = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # 调度器进程
    scheduler_procs = get_scheduler_processes()
    
    # 数据库统计
    db_stats = get_db_stats("/root/.openclaw/workspace/ultron/data/alerts.db")
    
    # 调度器API响应时间
    try:
        start = time.time()
        import requests
        requests.get('http://localhost:18195/api/status', timeout=2)
        avg_response_time = (time.time() - start) * 1000
    except:
        avg_response_time = 0
    
    # 队列深度（估算）
    queue_depth = db_stats.get('alerts', 0)
    
    metrics = {
        "cpu_percent": cpu_percent,
        "memory_percent": memory.percent,
        "memory_used_gb": round(memory.used / (1024**3), 2),
        "memory_available_gb": round(memory.available / (1024**3), 2),
        "disk_percent": disk.percent,
        "disk_used_gb": round(disk.used / (1024**3), 2),
        "scheduler_processes": len(scheduler_procs),
        "queue_depth": queue_depth,
        "avg_response_time": round(avg_response_time, 2),
        "timestamp": datetime.now().isoformat()
    }
    
    # 计算性能得分
    score = calculate_performance_score(metrics)
    metrics["performance_score"] = score
    
    # 生成优化建议
    metrics["suggestions"] = get_optimization_suggestions(metrics, score)
    
    # 保存到历史
    PERFORMANCE_HISTORY.append(metrics)
    metrics["history_size"] = len(PERFORMANCE_HISTORY)
    
    # 更新缓存
    METRICS_CACHE["data"] = {
        "status": "ok",
        "metrics": metrics
    }
    METRICS_CACHE["last_update"] = current_time
    
    return jsonify(METRICS_CACHE["data"])

@app.route('/api/performance/history', methods=['GET'])
def performance_history():
    """获取性能历史数据"""
    limit = request.args.get('limit', 20, type=int)
    history = list(PERFORMANCE_HISTORY)[-limit:]
    return jsonify({
        "status": "ok",
        "count": len(history),
        "history": history
    })

@app.route('/api/optimize', methods=['POST'])
def optimize():
    """执行优化操作"""
    action = request.get_json().get('action', 'analyze')
    
    results = []
    
    if action == "clear_cache":
        METRICS_CACHE["data"] = {}
        METRICS_CACHE["last_update"] = 0
        results.append("缓存已清理")
    
    if action == "clear_old_data":
        # 清理30天前的旧数据
        try:
            conn = sqlite3.connect("/root/.openclaw/workspace/ultron/data/alerts.db")
            c = conn.cursor()
            cutoff = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            c.execute(f"DELETE FROM alerts WHERE timestamp < ?", (cutoff,))
            deleted = c.rowcount
            conn.commit()
            conn.close()
            results.append(f"已清理 {deleted} 条旧记录")
        except Exception as e:
            results.append(f"清理失败: {str(e)}")
    
    if action == "vacuum":
        try:
            conn = sqlite3.connect("/root/.openclaw/workspace/ultron/data/alerts.db")
            c = conn.cursor()
            c.execute("VACUUM")
            conn.close()
            results.append("数据库已优化")
        except Exception as e:
            results.append(f"优化失败: {str(e)}")
    
    return jsonify({
        "status": "ok",
        "action": action,
        "results": results
    })

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "scheduler-perf-optimizer",
        "port": 18218
    })

if __name__ == '__main__':
    print("启动调度器性能优化服务...")
    print(f"端口: 18218")
    app.run(host='0.0.0.0', port=18218, debug=False)