#!/usr/bin/env python3
"""
调度器告警阈值配置服务
提供REST API配置和管理调度器告警阈值
端口: 18210
"""

import json
import os
from flask import Flask, jsonify, request
from datetime import datetime

app = Flask(__name__)

CONFIG_FILE = "/root/.openclaw/workspace/ultron/data/scheduler_thresholds.json"

# 默认阈值配置
DEFAULT_THRESHOLDS = {
    "response_time": {
        "warning": 1000,  # ms
        "critical": 3000,  # ms
        "enabled": True
    },
    "failure_rate": {
        "warning": 5,  # percentage
        "critical": 15,  # percentage
        "enabled": True
    },
    "queue_depth": {
        "warning": 50,
        "critical": 100,
        "enabled": True
    },
    "task_duration": {
        "warning": 300,  # seconds
        "critical": 600,  # seconds
        "enabled": True
    },
    "consecutive_failures": {
        "warning": 3,
        "critical": 5,
        "enabled": True
    },
    "memory_usage": {
        "warning": 80,  # percentage
        "critical": 95,  # percentage
        "enabled": True
    },
    "cpu_usage": {
        "warning": 70,
        "critical": 90,
        "enabled": True
    },
    "disk_usage": {
        "warning": 80,
        "critical": 95,
        "enabled": True
    }
}

def load_thresholds():
    """加载阈值配置"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_THRESHOLDS.copy()

def save_thresholds(thresholds):
    """保存阈值配置"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(thresholds, f, indent=2)

@app.route('/api/thresholds', methods=['GET'])
def get_thresholds():
    """获取所有阈值配置"""
    thresholds = load_thresholds()
    return jsonify({
        "status": "ok",
        "thresholds": thresholds,
        "updated_at": datetime.now().isoformat()
    })

@app.route('/api/thresholds/<metric>', methods=['GET'])
def get_threshold(metric):
    """获取指定指标的阈值"""
    thresholds = load_thresholds()
    if metric in thresholds:
        return jsonify({
            "status": "ok",
            "metric": metric,
            "threshold": thresholds[metric]
        })
    return jsonify({
        "status": "error",
        "message": f"Metric '{metric}' not found"
    }), 404

@app.route('/api/thresholds/<metric>', methods=['PUT', 'POST'])
def set_threshold(metric):
    """设置指定指标的阈值"""
    thresholds = load_thresholds()
    data = request.get_json()
    
    if metric not in DEFAULT_THRESHOLDS:
        return jsonify({
            "status": "error",
            "message": f"Metric '{metric}' not supported"
        }), 400
    
    if metric in data:
        thresholds[metric] = data[metric]
    else:
        # 部分更新
        if metric not in thresholds:
            thresholds[metric] = DEFAULT_THRESHOLDS[metric].copy()
        for key in data:
            if key in thresholds[metric]:
                thresholds[metric][key] = data[key]
    
    save_thresholds(thresholds)
    
    return jsonify({
        "status": "ok",
        "metric": metric,
        "threshold": thresholds[metric]
    })

@app.route('/api/thresholds/<metric>', methods=['DELETE'])
def reset_threshold(metric):
    """重置指定指标到默认值"""
    thresholds = load_thresholds()
    
    if metric in DEFAULT_THRESHOLDS:
        thresholds[metric] = DEFAULT_THRESHOLDS[metric].copy()
        save_thresholds(thresholds)
        return jsonify({
            "status": "ok",
            "metric": metric,
            "threshold": thresholds[metric]
        })
    
    return jsonify({
        "status": "error",
        "message": f"Metric '{metric}' not found"
    }), 404

@app.route('/api/thresholds/reset', methods=['POST'])
def reset_all():
    """重置所有阈值到默认值"""
    save_thresholds(DEFAULT_THRESHOLDS.copy())
    return jsonify({
        "status": "ok",
        "message": "All thresholds reset to defaults",
        "thresholds": DEFAULT_THRESHOLDS
    })

@app.route('/api/check', methods=['POST'])
def check_thresholds():
    """检查当前指标是否触发阈值"""
    thresholds = load_thresholds()
    metrics = request.get_json() or {}
    
    alerts = []
    
    for metric, config in thresholds.items():
        if not config.get('enabled', True):
            continue
        
        if metric in metrics:
            value = metrics[metric]
            
            if 'critical' in config and value >= config['critical']:
                alerts.append({
                    "metric": metric,
                    "level": "critical",
                    "value": value,
                    "threshold": config['critical'],
                    "message": f"{metric} 达到 critical 阈值"
                })
            elif 'warning' in config and value >= config['warning']:
                alerts.append({
                    "metric": metric,
                    "level": "warning",
                    "value": value,
                    "threshold": config['warning'],
                    "message": f"{metric} 达到 warning 阈值"
                })
    
    return jsonify({
        "status": "ok",
        "alerts": alerts,
        "alert_count": len(alerts),
        "checked_at": datetime.now().isoformat()
    })

@app.route('/api/metrics', methods=['GET'])
def list_metrics():
    """列出所有支持的指标"""
    return jsonify({
        "status": "ok",
        "metrics": list(DEFAULT_THRESHOLDS.keys()),
        "defaults": DEFAULT_THRESHOLDS
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "scheduler-alert-thresholds"})

if __name__ == '__main__':
    print("启动调度器告警阈值配置服务...")
    print(f"端口: 18210")
    print(f"配置文件: {CONFIG_FILE}")
    app.run(host='0.0.0.0', port=18211, debug=False)