#!/usr/bin/env python3
"""
决策引擎与工作流深度集成服务
端口: 18130
功能:
1. 决策引擎触发工作流执行
2. 工作流查询决策条件
3. 自动告警处理工作流
"""

from flask import Flask, request, jsonify
import requests
import threading
import time
import json

app = Flask(__name__)

# 服务配置
DECISION_ENGINE_URL = "http://localhost:18122"
WORKFLOW_ENGINE_URL = "http://localhost:8099"
AGENT_EXECUTOR_URL = "http://localhost:8096"

# 决策-工作流映射规则 - 映射到Agent执行器任务
DECISION_ACTION_MAP = {
    "cpu_high": {"action": "shell", "command": "echo 'CPU告警触发' && uptime"},
    "memory_high": {"action": "shell", "command": "echo '内存告警触发' && free -h"},
    "disk_full": {"action": "shell", "command": "echo '磁盘告警触发' && df -h"},
    "service_down": {"action": "shell", "command": "echo '服务down告警触发' && systemctl status openclaw"},
    "error_rate_high": {"action": "shell", "command": "echo '错误率告警触发' && tail -50 /var/log/syslog 2>/dev/null || tail -50 /var/log/messages"},
    "response_slow": {"action": "shell", "command": "echo '响应慢告警触发' && netstat -an | grep TIME_WAIT | wc -l"}
}

# 缓存
workflow_cache = {}
decision_cache = {}


def get_workflows():
    """获取可用动作列表"""
    return {"actions": DECISION_ACTION_MAP}


def get_decision_rules():
    """获取决策规则"""
    try:
        resp = requests.get(f"{DECISION_ENGINE_URL}/rules", timeout=5)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return {"rules": []}


def execute_action(action_config, context):
    """通过Agent执行器执行动作"""
    try:
        # 使用 agent_task_executor.py 的 API
        payload = {
            "task_type": action_config.get("action", "shell"),
            "command": action_config.get("command", "echo 'no command'"),
            "context": context
        }
        resp = requests.post(
            f"{AGENT_EXECUTOR_URL}/api/execute",
            json=payload,
            timeout=30
        )
        if resp.status_code == 200:
            return resp.json()
        return {"error": resp.text}
    except Exception as e:
        return {"error": str(e)}


def query_decision(condition):
    """查询决策引擎评估条件"""
    try:
        resp = requests.post(
            f"{DECISION_ENGINE_URL}/evaluate",
            json={"condition": condition},
            timeout=5
        )
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return {"result": False, "error": "Decision engine unavailable"}


@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "service": "decision-workflow-integration",
        "status": "healthy",
        "version": "1.0.0",
        "features": [
            "decision_to_workflow",
            "workflow_query_decision",
            "auto_alert_handling",
            "context_sharing"
        ]
    })


@app.route('/map', methods=['GET'])
def get_map():
    """获取决策-工作流映射"""
    return jsonify({
        "mappings": DECISION_ACTION_MAP,
        "workflows": get_workflows(),
        "active": len(DECISION_ACTION_MAP)
    })


@app.route('/trigger', methods=['POST'])
def trigger_workflow():
    """根据决策触发自动化动作"""
    data = request.json or {}
    decision_id = data.get('decision_id', 'manual')
    context = data.get('context', {})
    
    # 获取当前活跃告警
    try:
        resp = requests.get(f"{DECISION_ENGINE_URL}/alerts", timeout=5)
        if resp.status_code == 200:
            alerts = resp.json().get('alerts', [])
            results = []
            for alert in alerts:
                # 使用 rule_id 进行匹配
                rule_id = alert.get('rule_id')
                if rule_id and rule_id in DECISION_ACTION_MAP:
                    action = DECISION_ACTION_MAP[rule_id]
                    action_result = execute_action(action, {
                        **context,
                        "alert": alert,
                        "trigger": decision_id,
                        "rule_id": rule_id
                    })
                    results.append({
                        "rule_id": rule_id,
                        "alert_id": alert.get('id'),
                        "action": action.get('command', '')[:50],
                        "result": action_result
                    })
            return jsonify({
                "status": "completed",
                "triggered": len(results),
                "results": results
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    return jsonify({"status": "no_alerts", "triggered": 0})


@app.route('/evaluate', methods=['POST'])
def evaluate_for_workflow():
    """为工作流评估决策条件"""
    data = request.json or {}
    condition = data.get('condition', '')
    
    result = query_decision(condition)
    return jsonify(result)


@app.route('/execute', methods=['POST'])
def execute_with_decision():
    """带决策条件的动作执行"""
    data = request.json or {}
    action_name = data.get('action')
    condition = data.get('condition')
    context = data.get('context', {})
    
    # 先评估条件
    if condition:
        decision = query_decision(condition)
        if not decision.get('result', False):
            return jsonify({
                "status": "skipped",
                "reason": "condition_not_met",
                "decision": decision
            })
    
    # 获取动作配置并执行
    if action_name and action_name in DECISION_ACTION_MAP:
        action = DECISION_ACTION_MAP[action_name]
        result = execute_action(action, context)
    else:
        return jsonify({"error": f"Unknown action: {action_name}"}), 400
    
    return jsonify({
        "status": "executed",
        "action": action_name,
        "result": result
    })


@app.route('/stats', methods=['GET'])
def stats():
    """集成统计"""
    return jsonify({
        "mappings_count": len(DECISION_ACTION_MAP),
        "decision_engine": DECISION_ENGINE_URL,
        "workflow_engine": WORKFLOW_ENGINE_URL,
        "agent_executor": AGENT_EXECUTOR_URL
    })


if __name__ == '__main__':
    print("🚀 决策引擎与工作流深度集成服务启动")
    print(f"   端口: 18135")
    print(f"   决策引擎: {DECISION_ENGINE_URL}")
    print(f"   工作流引擎: {WORKFLOW_ENGINE_URL}")
    app.run(host='0.0.0.0', port=18135, debug=False)