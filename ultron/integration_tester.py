#!/usr/bin/env python3
"""
全系统集成测试服务
验证所有服务和组件是否正常工作
端口: 18228
"""

import json
import os
import requests
from datetime import datetime
from flask import Flask, jsonify, request

app = Flask(__name__)

# 所有需要测试的服务
SERVICES = {
    # 核心服务
    "gateway": {"port": 18789, "health": "/health"},
    "dashboard": {"port": 8889, "health": "/"},
    
    # 告警系统
    "alert_history": {"port": 18217, "health": "/health"},
    "alert_prediction": {"port": 18225, "health": "/health"},
    "alert_report": {"port": 18224, "health": "/health"},
    "alert_router": {"port": 18222, "health": "/health"},
    "alert_channel": {"port": 18221, "health": "/health"},
    "alert_healer": {"port": 18227, "health": "/health"},
    
    # 调度器
    "task_monitor": {"port": 18195, "health": "/"},
    "scheduler_stats": {"port": 18192, "health": "/health"},
    "queue_api": {"port": 18183, "health": "/health"},
    "queue_dashboard": {"port": 18182, "health": "/health"},
    
    # 性能监控
    "scheduler_perf": {"port": 18218, "health": "/health"},
    "integrated_dashboard": {"port": 18223, "health": "/health"},
    
    # 其他
    "decision_api": {"port": 18190, "health": "/health"},
}

def test_service(name, config):
    """测试单个服务"""
    port = config.get('port')
    health_path = config.get('health', '/health')
    
    try:
        start = datetime.now()
        response = requests.get(f"http://localhost:{port}{health_path}", timeout=3)
        elapsed = (datetime.now() - start).total_seconds() * 1000
        
        if response.status_code == 200:
            return {
                "name": name,
                "port": port,
                "status": "up",
                "response_time": round(elapsed, 1),
                "details": "OK"
            }
        else:
            return {
                "name": name,
                "port": port,
                "status": "degraded",
                "response_time": round(elapsed, 1),
                "details": f"HTTP {response.status_code}"
            }
    except requests.exceptions.Timeout:
        return {
            "name": name,
            "port": port,
            "status": "timeout",
            "details": "Request timeout"
        }
    except requests.exceptions.ConnectionError:
        return {
            "name": name,
            "port": port,
            "status": "down",
            "details": "Connection refused"
        }
    except Exception as e:
        return {
            "name": name,
            "port": port,
            "status": "error",
            "details": str(e)[:50]
        }

def run_full_test():
    """运行完整测试"""
    results = []
    start_time = datetime.now()
    
    for name, config in SERVICES.items():
        result = test_service(name, config)
        results.append(result)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # 统计
    up = sum(1 for r in results if r['status'] == 'up')
    degraded = sum(1 for r in results if r['status'] == 'degraded')
    down = sum(1 for r in results if r['status'] == 'down')
    timeout = sum(1 for r in results if r['status'] == 'timeout')
    error = sum(1 for r in results if r['status'] == 'error')
    
    # 计算健康度
    total = len(results)
    health_score = (up / total * 100) if total > 0 else 0
    
    # 按状态分组
    by_status = {
        "up": [r for r in results if r['status'] == 'up'],
        "degraded": [r for r in results if r['status'] == 'degraded'],
        "down": [r for r in results if r['status'] == 'down'],
    }
    
    return {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total": total,
            "up": up,
            "degraded": degraded,
            "down": down,
            "timeout": timeout,
            "error": error,
            "health_score": round(health_score, 1),
            "test_duration_ms": round(elapsed * 1000, 1)
        },
        "services": results,
        "by_status": by_status
    }

def run_connectivity_test():
    """运行连接测试"""
    import socket
    
    results = []
    for name, config in SERVICES.items():
        port = config.get('port')
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        results.append({
            "name": name,
            "port": port,
            "open": result == 0
        })
    
    open_ports = sum(1 for r in results if r['open'])
    
    return {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "open": open_ports,
        "closed": len(results) - open_ports,
        "results": results
    }

@app.route('/api/test/full', methods=['GET'])
def full_test():
    """完整测试"""
    result = run_full_test()
    return jsonify({
        "status": "ok",
        "test": "full",
        "result": result
    })

@app.route('/api/test/connectivity', methods=['GET'])
def connectivity_test():
    """连接测试"""
    result = run_connectivity_test()
    return jsonify({
        "status": "ok",
        "test": "connectivity",
        "result": result
    })

@app.route('/api/test/service/<name>', methods=['GET'])
def test_single_service(name):
    """测试单个服务"""
    if name not in SERVICES:
        return jsonify({
            "status": "error",
            "message": f"Service '{name}' not found"
        }), 404
    
    result = test_service(name, SERVICES[name])
    return jsonify({
        "status": "ok",
        "result": result
    })

@app.route('/api/services', methods=['GET'])
def list_services():
    """列出所有服务"""
    return jsonify({
        "status": "ok",
        "services": [
            {"name": name, "port": config.get('port'), "health_path": config.get('health')}
            for name, config in SERVICES.items()
        ]
    })

@app.route('/api/report', methods=['GET'])
def report():
    """生成综合报告"""
    full_result = run_full_test()
    conn_result = run_connectivity_test()
    
    # 健康度
    health_score = full_result['summary']['health_score']
    health_status = "healthy" if health_score >= 90 else "degraded" if health_score >= 70 else "unhealthy"
    
    return jsonify({
        "status": "ok",
        "report": {
            "timestamp": datetime.now().isoformat(),
            "health_score": health_score,
            "health_status": health_status,
            "up_services": full_result['summary']['up'],
            "total_services": full_result['summary']['total'],
            "down_services": full_result['summary']['down'],
            "open_ports": conn_result['open'],
            "total_ports": conn_result['total'],
            "test_duration_ms": full_result['summary']['test_duration_ms']
        },
        "details": full_result
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "integration-tester",
        "port": 18228
    })

if __name__ == '__main__':
    print("启动全系统集成测试服务...")
    print(f"端口: 18228")
    print(f"测试服务数: {len(SERVICES)}")
    app.run(host='0.0.0.0', port=18228, debug=False)