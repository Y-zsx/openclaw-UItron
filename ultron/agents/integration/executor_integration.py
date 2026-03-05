#!/usr/bin/env python3
"""
决策引擎与执行器深度集成服务
端口: 18136

功能:
1. 决策引擎 -> 执行器任务提交
2. 执行器结果 -> 决策反馈
3. 自动化触发 -> 执行器任务
"""

from flask import Flask, request, jsonify
import requests
import threading
import time
import json

app = Flask(__name__)

# 服务配置 (当前实际运行的端口)
DECISION_ENGINE_URL = "http://localhost:18120"
AUTOMATION_URL = "http://localhost:18128"
EXECUTOR_URL = "http://localhost:18210"

# 决策动作映射 - 当决策引擎做出决策时，触发对应执行器任务
DECISION_EXECUTOR_MAP = {
    "high_cpu": {
        "task_type": "exec",
        "command": "top -bn1 | head -10",
        "priority": "HIGH",
        "description": "高CPU - 收集进程信息"
    },
    "high_memory": {
        "task_type": "exec", 
        "command": "free -h && ps aux --sort=-%mem | head -10",
        "priority": "HIGH",
        "description": "高内存 - 收集内存快照"
    },
    "disk_full": {
        "task_type": "exec",
        "command": "df -h && du -sh /* 2>/dev/null | sort -hr | head -10",
        "priority": "HIGH",
        "description": "磁盘满 - 收集磁盘使用情况"
    },
    "service_down": {
        "task_type": "exec",
        "command": "systemctl status openclaw || service openclaw status",
        "priority": "CRITICAL",
        "description": "服务down - 检查服务状态"
    },
    "health_check": {
        "task_type": "exec",
        "command": "uptime && free -m | head -2",
        "priority": "LOW",
        "description": "健康检查 - 系统状态"
    }
}


def get_executor_status():
    """获取执行器状态"""
    try:
        resp = requests.get(f"{EXECUTOR_URL}/status", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        return {"error": str(e)}
    return {"error": "Executor unavailable"}


def get_automation_status():
    """获取自动化引擎状态"""
    try:
        resp = requests.get(f"{AUTOMATION_URL}/status", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        return {"error": str(e)}
    return {"error": "Automation unavailable"}


def submit_task(task_config, context=None):
    """提交任务到执行器"""
    try:
        # executor_enhanced.py 期望的格式
        payload = {
            "type": task_config.get("task_type", "exec"),
            "payload": {
                "command": task_config.get("command", "echo 'no command'"),
                "context": context or {}
            },
            "priority": priority_to_int(task_config.get("priority", "NORMAL"))
        }
            
        # 尝试执行器API - 根据实际API结构调整
        resp = requests.post(
            f"{EXECUTOR_URL}/tasks",
            json=payload,
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()
        return {"error": resp.text, "status_code": resp.status_code}
    except Exception as e:
        return {"error": str(e)}


def priority_to_int(priority):
    """优先级转换为数字"""
    priority_map = {
        "LOW": 0,
        "NORMAL": 1,
        "HIGH": 2,
        "CRITICAL": 3
    }
    return priority_map.get(priority.upper(), 1)


def get_task_result(task_id):
    """获取任务结果"""
    try:
        resp = requests.get(f"{EXECUTOR_URL}/tasks/{task_id}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        return {"error": str(e)}
    return {"error": "Task not found"}


# ============ API 端点 ============

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        "service": "executor-integration",
        "status": "healthy",
        "version": "2.0.0",
        "connected_services": {
            "executor": EXECUTOR_URL,
            "automation": AUTOMATION_URL,
            "decision": DECISION_ENGINE_URL
        }
    })


@app.route('/status', methods=['GET'])
def status():
    """获取集成系统整体状态"""
    executor = get_executor_status()
    automation = get_automation_status()
    
    return jsonify({
        "integration_status": "operational",
        "executor": executor,
        "automation": automation,
        "available_actions": len(DECISION_EXECUTOR_MAP)
    })


@app.route('/actions', methods=['GET'])
def list_actions():
    """列出所有可用的决策-执行映射"""
    return jsonify({
        "actions": DECISION_EXECUTOR_MAP,
        "count": len(DECISION_EXECUTOR_MAP)
    })


@app.route('/execute', methods=['POST'])
def execute_action():
    """根据决策类型执行对应任务"""
    data = request.json or {}
    action_type = data.get('action_type', 'health_check')
    context = data.get('context', {})
    
    if action_type not in DECISION_EXECUTOR_MAP:
        return jsonify({
            "error": f"Unknown action type: {action_type}",
            "available": list(DECISION_EXECUTOR_MAP.keys())
        }), 400
    
    task_config = DECISION_EXECUTOR_MAP[action_type]
    result = submit_task(task_config, context)
    
    return jsonify({
        "action_type": action_type,
        "config": task_config,
        "executor_result": result,
        "timestamp": time.time()
    })


@app.route('/execute/<action_type>', methods=['POST'])
def execute_action_path(action_type):
    """路径形式的动作执行"""
    data = request.json or {}
    context = data.get('context', {})
    
    if action_type not in DECISION_EXECUTOR_MAP:
        return jsonify({
            "error": f"Unknown action type: {action_type}",
            "available": list(DECISION_EXECUTOR_MAP.keys())
        }), 400
    
    task_config = DECISION_EXECUTOR_MAP[action_type]
    result = submit_task(task_config, context)
    
    return jsonify({
        "action_type": action_type,
        "config": task_config,
        "executor_result": result,
        "timestamp": time.time()
    })


@app.route('/task/<task_id>', methods=['GET'])
def get_task(task_id):
    """获取任务状态和结果"""
    result = get_task_result(task_id)
    return jsonify(result)


@app.route('/automation/trigger', methods=['POST'])
def automation_trigger():
    """自动化引擎触发执行器"""
    data = request.json or {}
    trigger_type = data.get('trigger_type')
    params = data.get('params', {})
    
    # 触发类型映射到动作
    trigger_action_map = {
        "健康检查": "health_check",
        "high_cpu": "high_cpu",
        "high_memory": "high_memory",
        "disk_full": "disk_full",
        "service_down": "service_down"
    }
    
    action_type = trigger_action_map.get(trigger_type, "health_check")
    
    if action_type in DECISION_EXECUTOR_MAP:
        task_config = DECISION_EXECUTOR_MAP[action_type]
        result = submit_task(task_config, {"trigger": trigger_type, "params": params})
        return jsonify({
            "trigger": trigger_type,
            "action": action_type,
            "result": result
        })
    
    return jsonify({"error": "Unknown trigger"}), 400


if __name__ == '__main__':
    print("=" * 50)
    print("决策引擎与执行器深度集成服务")
    print(f"端口: 18136")
    print(f"执行器: {EXECUTOR_URL}")
    print(f"自动化: {AUTOMATION_URL}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=18136, debug=False)