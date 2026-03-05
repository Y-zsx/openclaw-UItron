#!/usr/bin/env python3
"""
智能容量规划系统
Agent协作网络 - 智能容量规划
"""

import json
import time
import threading
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from collections import deque
import psutil
import os

app = Flask(__name__)

# 存储容量数据
capacity_data = {
    "history": deque(maxlen=1000),
    "predictions": [],
    "alerts": [],
    "recommendations": []
}

# 资源阈值配置
THRESHOLDS = {
    "cpu_warning": 70,
    "cpu_critical": 85,
    "memory_warning": 75,
    "memory_critical": 90,
    "disk_warning": 80,
    "disk_critical": 90,
    "network_warning": 80,
    "network_critical": 95
}

def get_system_metrics():
    """获取系统指标"""
    cpu_percent = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    network = psutil.net_io_counters()
    
    # 获取进程信息
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            pinfo = proc.info
            if pinfo['cpu_percent'] and pinfo['cpu_percent'] > 0:
                processes.append({
                    'pid': pinfo['pid'],
                    'name': pinfo['name'][:30],
                    'cpu': round(pinfo['cpu_percent'], 1),
                    'memory': round(pinfo['memory_percent'], 1)
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    processes.sort(key=lambda x: x['cpu'], reverse=True)
    
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "percent": round(cpu_percent, 1),
            "count": psutil.cpu_count(),
            "status": get_status(cpu_percent, 'cpu')
        },
        "memory": {
            "percent": round(memory.percent, 1),
            "total_gb": round(memory.total / (1024**3), 2),
            "used_gb": round(memory.used / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "status": get_status(memory.percent, 'memory')
        },
        "disk": {
            "percent": round(disk.percent, 1),
            "total_gb": round(disk.total / (1024**3), 2),
            "used_gb": round(disk.used / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "status": get_status(disk.percent, 'disk')
        },
        "network": {
            "bytes_sent": network.bytes_sent,
            "bytes_recv": network.bytes_recv,
            "packets_sent": network.packets_sent,
            "packets_recv": network.packets_recv,
            "status": "normal"
        },
        "top_processes": processes[:10]
    }

def get_status(value, resource_type):
    """获取资源状态"""
    if resource_type == 'cpu':
        if value >= THRESHOLDS['cpu_critical']:
            return "critical"
        elif value >= THRESHOLDS['cpu_warning']:
            return "warning"
    elif resource_type == 'memory':
        if value >= THRESHOLDS['memory_critical']:
            return "critical"
        elif value >= THRESHOLDS['memory_warning']:
            return "warning"
    elif resource_type == 'disk':
        if value >= THRESHOLDS['disk_critical']:
            return "critical"
        elif value >= THRESHOLDS['disk_warning']:
            return "warning"
    return "normal"

def predict_capacity(history, hours=24):
    """基于历史数据预测未来容量需求"""
    if len(history) < 5:
        return None
    
    # 简单线性回归预测
    cpu_values = [h['cpu']['percent'] for h in history]
    mem_values = [h['memory']['percent'] for h in history]
    disk_values = [h['disk']['percent'] for h in history]
    
    # 计算趋势
    def predict_trend(values):
        if len(values) < 2:
            return 0, values[-1] if values else 0
        n = len(values)
        x = list(range(n))
        y = values
        
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(x[i] * y[i] for i in range(n))
        sum_x2 = sum(xi * xi for xi in x)
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x) if (n * sum_x2 - sum_x * sum_x) != 0 else 0
        avg = sum_y / n
        
        # 预测未来
        future_x = n + hours
        predicted = avg + slope * (future_x - n/2)
        return slope, max(0, min(100, predicted))
    
    cpu_slope, cpu_predicted = predict_trend(cpu_values)
    mem_slope, mem_predicted = predict_trend(mem_values)
    disk_slope, disk_predicted = predict_trend(disk_values)
    
    return {
        "prediction_window_hours": hours,
        "cpu": {
            "current": cpu_values[-1],
            "predicted": round(cpu_predicted, 1),
            "trend": "increasing" if cpu_slope > 0.5 else "decreasing" if cpu_slope < -0.5 else "stable",
            "slope": round(cpu_slope, 3)
        },
        "memory": {
            "current": mem_values[-1],
            "predicted": round(mem_predicted, 1),
            "trend": "increasing" if mem_slope > 0.5 else "decreasing" if mem_slope < -0.5 else "stable",
            "slope": round(mem_slope, 3)
        },
        "disk": {
            "current": disk_values[-1],
            "predicted": round(disk_predicted, 1),
            "trend": "increasing" if disk_slope > 0.1 else "decreasing" if disk_slope < -0.1 else "stable",
            "slope": round(disk_slope, 3)
        }
    }

def generate_recommendations(metrics, prediction):
    """生成容量规划建议"""
    recommendations = []
    
    # CPU建议
    if metrics['cpu']['percent'] > THRESHOLDS['cpu_warning']:
        if prediction and prediction['cpu']['predicted'] > 80:
            recommendations.append({
                "resource": "cpu",
                "priority": "high",
                "action": "scale_up",
                "message": f"CPU使用率当前{metrics['cpu']['percent']}%，预测24小时后将达到{prediction['cpu']['predicted']}%，建议扩容CPU核心数或优化工作负载",
                "suggested_action": "考虑增加CPU核心或部署负载均衡"
            })
        else:
            recommendations.append({
                "resource": "cpu",
                "priority": "medium",
                "action": "monitor",
                "message": f"CPU使用率当前{metrics['cpu']['percent']}%，建议持续监控",
                "suggested_action": "关注CPU使用趋势，准备扩容方案"
            })
    
    # 内存建议
    if metrics['memory']['percent'] > THRESHOLDS['memory_warning']:
        if prediction and prediction['memory']['predicted'] > 85:
            recommendations.append({
                "resource": "memory",
                "priority": "high",
                "action": "scale_up",
                "message": f"内存使用率当前{metrics['memory']['percent']}%，预测24小时后将达到{prediction['memory']['predicted']}%，建议扩容内存",
                "suggested_action": "考虑增加内存容量或优化内存使用"
            })
        else:
            recommendations.append({
                "resource": "memory",
                "priority": "medium",
                "action": "monitor",
                "message": f"内存使用率当前{metrics['memory']['percent']}%，建议持续监控",
                "suggested_action": "关注内存使用趋势"
            })
    
    # 磁盘建议
    if metrics['disk']['percent'] > THRESHOLDS['disk_warning']:
        if prediction and prediction['disk']['predicted'] > 85:
            recommendations.append({
                "resource": "disk",
                "priority": "high",
                "action": "scale_up",
                "message": f"磁盘使用率当前{metrics['disk']['percent']}%，预测24小时后将达到{prediction['disk']['predicted']}%，建议扩容磁盘",
                "suggested_action": "考虑增加磁盘容量或清理不必要的文件"
            })
        else:
            recommendations.append({
                "resource": "disk",
                "priority": "medium",
                "action": "cleanup",
                "message": f"磁盘使用率当前{metrics['disk']['percent']}%，建议清理不必要的文件",
                "suggested_action": "定期清理日志和临时文件"
            })
    
    # 正常状态建议
    if not recommendations:
        recommendations.append({
            "resource": "all",
            "priority": "low",
            "action": "optimize",
            "message": "所有资源使用正常，可以考虑优化资源分配以降低成本",
            "suggested_action": "评估是否可以缩减资源以节省成本"
        })
    
    return recommendations

def calculate_resource_efficiency(metrics, history):
    """计算资源使用效率"""
    if len(history) < 10:
        return None
    
    # 计算资源使用波动
    cpu_values = [h['cpu']['percent'] for h in history[-20:]]
    mem_values = [h['memory']['percent'] for h in history[-20:]]
    
    def calc_variance(values):
        if not values:
            return 0
        avg = sum(values) / len(values)
        return sum((v - avg) ** 2 for v in values) / len(values)
    
    cpu_variance = calc_variance(cpu_values)
    mem_variance = calc_variance(mem_values)
    
    # 资源效率评分 (0-100)
    efficiency_score = 100
    
    # 低方差表示稳定使用
    if cpu_variance > 100:
        efficiency_score -= 20
    if mem_variance > 100:
        efficiency_score -= 20
    
    # 高使用率但稳定 = 高效
    avg_cpu = sum(cpu_values) / len(cpu_values)
    avg_mem = sum(mem_values) / len(mem_values)
    
    if avg_cpu > 50 and cpu_variance < 50:
        efficiency_score += 10
    if avg_mem > 50 and mem_variance < 50:
        efficiency_score += 10
    
    return {
        "score": max(0, min(100, efficiency_score)),
        "cpu_variance": round(cpu_variance, 2),
        "mem_variance": round(mem_variance, 2),
        "avg_cpu_usage": round(avg_cpu, 1),
        "avg_mem_usage": round(avg_mem, 1),
        "recommendation": "高效率" if efficiency_score > 80 else "中等效率" if efficiency_score > 50 else "低效率"
    }

# 定期收集数据
def collect_metrics():
    """定期收集系统指标"""
    while True:
        try:
            metrics = get_system_metrics()
            capacity_data["history"].append(metrics)
            
            # 每10条数据生成一次预测和建议
            if len(capacity_data["history"]) % 10 == 0:
                prediction = predict_capacity(list(capacity_data["history"]))
                if prediction:
                    capacity_data["predictions"].append({
                        "timestamp": datetime.now().isoformat(),
                        "prediction": prediction
                    })
                
                recommendations = generate_recommendations(metrics, prediction)
                capacity_data["recommendations"] = recommendations
                
        except Exception as e:
            print(f"收集指标错误: {e}")
        
        time.sleep(60)  # 每分钟收集一次

# 启动收集线程
collector_thread = threading.Thread(target=collect_metrics, daemon=True)
collector_thread.start()

# 等待初始数据
time.sleep(2)

# API 路由
@app.route('/api/capacity/metrics', methods=['GET'])
def get_metrics():
    """获取当前系统指标"""
    return jsonify(get_system_metrics())

@app.route('/api/capacity/history', methods=['GET'])
def get_history():
    """获取历史容量数据"""
    limit = request.args.get('limit', 100, type=int)
    history = list(capacity_data["history"])[-limit:]
    return jsonify({
        "count": len(history),
        "history": history
    })

@app.route('/api/capacity/predict', methods=['GET'])
def get_predictions():
    """获取容量预测"""
    hours = request.args.get('hours', 24, type=int)
    prediction = predict_capacity(list(capacity_data["history"]), hours)
    return jsonify({
        "hours": hours,
        "prediction": prediction,
        "generated_at": datetime.now().isoformat()
    })

@app.route('/api/capacity/recommendations', methods=['GET'])
def get_recommendations():
    """获取容量规划建议"""
    metrics = get_system_metrics()
    prediction = predict_capacity(list(capacity_data["history"]))
    recommendations = generate_recommendations(metrics, prediction)
    return jsonify({
        "recommendations": recommendations,
        "generated_at": datetime.now().isoformat()
    })

@app.route('/api/capacity/efficiency', methods=['GET'])
def get_efficiency():
    """获取资源使用效率"""
    metrics = get_system_metrics()
    efficiency = calculate_resource_efficiency(metrics, list(capacity_data["history"]))
    return jsonify({
        "efficiency": efficiency,
        "generated_at": datetime.now().isoformat()
    })

@app.route('/api/capacity/summary', methods=['GET'])
def get_summary():
    """获取容量规划摘要"""
    metrics = get_system_metrics()
    history = list(capacity_data["history"])
    prediction = predict_capacity(history)
    recommendations = generate_recommendations(metrics, prediction)
    efficiency = calculate_resource_efficiency(metrics, history)
    
    return jsonify({
        "metrics": metrics,
        "prediction": prediction,
        "recommendations": recommendations,
        "efficiency": efficiency,
        "history_count": len(history),
        "generated_at": datetime.now().isoformat()
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "capacity-planner"})

if __name__ == '__main__':
    print("🚀 智能容量规划系统启动中...")
    print("📊 API: http://0.0.0.0:18240")
    app.run(host='0.0.0.0', port=18240, debug=False)