#!/usr/bin/env python3
"""
调度器告警通知集成服务
定期检查调度器指标，触发阈值告警并发送到通知系统
端口: 18212
"""

import os
import sys
import json
import time
import threading
import requests
from datetime import datetime
from flask import Flask, jsonify, request

app = Flask(__name__)

# 配置
SCHEDULER_API_PORT = 18195
THRESHOLD_API_PORT = 18211
ALERT_API_PORT = 18170
CHECK_INTERVAL = 60  # 默认60秒检查一次

# 调度器指标来源
SCHEDULER_METRICS_URLS = [
    f"http://localhost:{SCHEDULER_API_PORT}/api/summary",
    f"http://localhost:{SCHEDULER_API_PORT}/api/metrics",
    f"http://localhost:{SCHEDULER_API_PORT}/api/status",
]

# 活跃告警缓存（避免重复创建）
active_alerts = {}
alert_lock = threading.Lock()


def collect_scheduler_metrics():
    """收集调度器指标"""
    metrics = {}
    
    try:
        # 获取摘要
        r = requests.get(f"http://localhost:{SCHEDULER_API_PORT}/api/summary", timeout=5)
        if r.status_code == 200:
            data = r.json()
            summary = data.get("metrics", {})
            metrics["total_executions"] = summary.get("total_executions", 0)
            metrics["running_tasks"] = summary.get("running_tasks", 0)
            metrics["failed_tasks_24h"] = summary.get("failed_tasks_24h", 0)
            
            # 计算失败率
            total = summary.get("total_executions", 0)
            failed = summary.get("failed_tasks_24h", 0)
            if total > 0:
                metrics["failure_rate"] = (failed / total) * 100
            else:
                metrics["failure_rate"] = 0
            
            # 平均执行时间
            duration_stats = data.get("duration_stats_24h", {})
            metrics["avg_duration"] = duration_stats.get("avg", 0)
            metrics["max_duration"] = duration_stats.get("max", 0)
            
            # 成功率
            success_rate = data.get("success_rate_24h", {})
            metrics["success_rate"] = success_rate.get("success_rate", 100)
    except Exception as e:
        print(f"获取调度器摘要失败: {e}")
    
    # 获取队列深度（从监控API）
    try:
        r = requests.get(f"http://localhost:{SCHEDULER_API_PORT}/api/running", timeout=5)
        if r.status_code == 200:
            data = r.json()
            metrics["queue_depth"] = len(data.get("tasks", []))
        else:
            metrics["queue_depth"] = 0
    except:
        metrics["queue_depth"] = 0
    
    # 获取失败任务
    try:
        r = requests.get(f"http://localhost:{SCHEDULER_API_PORT}/api/failed", timeout=5)
        if r.status_code == 200:
            data = r.json()
            metrics["consecutive_failures"] = len(data.get("tasks", []))
        else:
            metrics["consecutive_failures"] = 0
    except:
        metrics["consecutive_failures"] = 0
    
    return metrics


def check_thresholds(metrics):
    """检查阈值"""
    try:
        r = requests.post(
            f"http://localhost:{THRESHOLD_API_PORT}/api/check",
            json=metrics,
            timeout=5,
            headers={"Content-Type": "application/json"}
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"阈值检查失败: {e}")
    return None


def create_alert(alert_data):
    """创建告警到通知系统"""
    try:
        # 转换阈值告警格式到通知系统格式
        level_map = {"warning": "warning", "critical": "error"}
        
        payload = {
            "level": level_map.get(alert_data.get("level", "warning"), "warning"),
            "message": alert_data.get("message", "调度器告警"),
            "service_name": "scheduler-alert-monitor",
            "rule_name": f"调度器阈值告警: {alert_data.get('metric')}",
            "rule_id": f"scheduler_threshold_{alert_data.get('metric')}",
            "source": "scheduler",
            "labels": {
                "check_type": "scheduler_threshold",
                "metric": alert_data.get("metric"),
            },
            "annotations": {
                "metric": alert_data.get("metric"),
                "value": alert_data.get("value"),
                "threshold": alert_data.get("threshold"),
                "level": alert_data.get("level"),
                "checked_at": datetime.now().isoformat(),
            },
            "value": alert_data.get("value"),
            "threshold": alert_data.get("threshold"),
        }
        
        r = requests.post(
            f"http://localhost:{ALERT_API_PORT}/alerts",
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"}
        )
        return r.status_code == 200 or r.status_code == 201
    except Exception as e:
        print(f"创建告警失败: {e}")
        return False


def resolve_alert(metric):
    """解决告警"""
    try:
        # 查找该metric的活跃告警
        r = requests.get(
            f"http://localhost:{ALERT_API_PORT}/alerts?status=firing&rule_id=scheduler_threshold_{metric}",
            timeout=5
        )
        if r.status_code == 200:
            data = r.json()
            for alert in data.get("alerts", []):
                alert_id = alert.get("id")
                if alert_id:
                    # 发送解决请求
                    resolve_r = requests.post(
                        f"http://localhost:{ALERT_API_PORT}/alerts/{alert_id}/resolve",
                        json={"resolve_message": f"{metric} 指标已恢复正常"},
                        timeout=5
                    )
                    return resolve_r.status_code == 200
    except Exception as e:
        print(f"解决告警失败: {e}")
    return False


def process_alerts(alert_result):
    """处理告警：创建新告警或解决旧告警"""
    if not alert_result:
        return
    
    alerts = alert_result.get("alerts", [])
    triggered_metrics = set()
    
    # 处理触发的告警
    for alert in alerts:
        metric = alert.get("metric")
        level = alert.get("level")
        key = f"{metric}_{level}"
        
        triggered_metrics.add(metric)
        
        with alert_lock:
            # 检查是否已存在相同告警
            if key not in active_alerts:
                # 创建新告警
                if create_alert(alert):
                    active_alerts[key] = {
                        "metric": metric,
                        "level": level,
                        "created_at": datetime.now().isoformat()
                    }
                    print(f"[ALERT] 创建告警: {metric} - {level}")
    
    # 检查需要解决的告警（之前触发但现在未触发）
    all_metrics = ["response_time", "failure_rate", "queue_depth", "task_duration",
                   "consecutive_failures", "memory_usage", "cpu_usage", "disk_usage"]
    
    with alert_lock:
        for key in list(active_alerts.keys()):
            metric = active_alerts[key].get("metric")
            if metric not in triggered_metrics:
                # 解决告警
                if resolve_alert(metric):
                    del active_alerts[key]
                    print(f"[RESOLVED] 解决告警: {metric}")


def check_loop(interval=60):
    """检查循环"""
    while True:
        try:
            # 收集指标
            metrics = collect_scheduler_metrics()
            print(f"[INFO] 收集指标: {metrics}")
            
            # 检查阈值
            result = check_thresholds(metrics)
            if result:
                print(f"[INFO] 阈值检查结果: {result.get('alert_count', 0)} 个告警")
                process_alerts(result)
        except Exception as e:
            print(f"[ERROR] 检查循环异常: {e}")
        
        time.sleep(interval)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "scheduler-alert-integration",
        "active_alerts": len(active_alerts)
    })


@app.route('/api/check_now', methods=['POST'])
def check_now():
    """手动触发一次检查"""
    metrics = collect_scheduler_metrics()
    result = check_thresholds(metrics)
    
    if result:
        process_alerts(result)
        return jsonify({
            "status": "ok",
            "metrics": metrics,
            "alerts": result.get("alerts", []),
            "alert_count": result.get("alert_count", 0)
        })
    
    return jsonify({
        "status": "error",
        "message": "Threshold check failed"
    }), 500


@app.route('/api/metrics', methods=['GET'])
def get_current_metrics():
    """获取当前指标"""
    metrics = collect_scheduler_metrics()
    return jsonify({
        "status": "ok",
        "metrics": metrics,
        "updated_at": datetime.now().isoformat()
    })


@app.route('/api/active_alerts', methods=['GET'])
def get_active_alerts():
    """获取活跃告警"""
    with alert_lock:
        return jsonify({
            "status": "ok",
            "active_alerts": active_alerts,
            "count": len(active_alerts)
        })


if __name__ == '__main__':
    print("启动调度器告警通知集成服务...")
    print(f"调度器API: localhost:{SCHEDULER_API_PORT}")
    print(f"阈值API: localhost:{THRESHOLD_API_PORT}")
    print(f"告警API: localhost:{ALERT_API_PORT}")
    print(f"检查间隔: {CHECK_INTERVAL}秒")
    
    # 启动后台检查线程
    check_thread = threading.Thread(target=check_loop, args=(CHECK_INTERVAL,), daemon=True)
    check_thread.start()
    
    # 启动Flask服务
    app.run(host='0.0.0.0', port=18212, debug=False)